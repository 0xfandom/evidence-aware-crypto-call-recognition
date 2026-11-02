"""LLM backend on the Claude Agent SDK, with caching and a hard spend budget.

Every failure (missing SDK, auth, timeout, budget, malformed output) becomes an
ABSTAIN proposal with a reason code. There is no silent fallback to the rules.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import time
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Literal

import anyio
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from evidence_aware_crypto_call_recognition.contract import POLICY_VERSION, Cost, EvidenceOrigin, Label, Post
from evidence_aware_crypto_call_recognition.proposal import Proposal, ProposedCall

DEFAULT_MODEL = "claude-haiku-5-5"
DEFAULT_MAX_USD_PER_POST = 0.05
DEFAULT_RUN_BUDGET_USD = 2.00
DEFAULT_CACHE_DIR = Path(".cache/llm")
TIMEOUT_SECONDS = 120
MODEL_REASON_PREFIX = "MODEL:"
_REASON_CODE = re.compile(r"[A-Z][A-Z0-9_]{0,47}")

SYSTEM_PROMPT = resources.files("evidence_aware_crypto_call_recognition.prompts").joinpath("classify_v1.md").read_text()
PROMPT_VERSION = "classify_v1@" + hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest()[:12]


class _LlmCall(BaseModel):
    model_config = ConfigDict(extra="forbid")
    asset_as_written: str | None
    supporting_text: str
    evidence_origin: Literal["post", "parent", "quoted"]
    explicitness: Literal["explicit", "implicit"]
    conditional: bool
    condition_text: str | None


class LlmOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: Literal["BUY", "NO_NEW_BUY", "ABSTAIN"]
    confidence: float = Field(ge=0.0, le=1.0)
    calls: list[_LlmCall]
    reasons: list[str]
    limitations: list[str]


OUTPUT_SCHEMA = LlmOutput.model_json_schema()


@dataclass
class RunBudget:
    """Shared across one run. Once spent, remaining posts abstain instead of calling the API."""

    limit_usd: float
    spent_usd: float = 0.0
    _lock: anyio.Lock = field(default_factory=anyio.Lock)

    @property
    def is_exhausted(self) -> bool:
        return self.spent_usd >= self.limit_usd


@dataclass(frozen=True)
class LlmSettings:
    model: str = DEFAULT_MODEL
    max_usd_per_post: float = DEFAULT_MAX_USD_PER_POST
    run_budget_usd: float = DEFAULT_RUN_BUDGET_USD
    cache_dir: Path | None = DEFAULT_CACHE_DIR

    @classmethod
    def from_env(cls) -> LlmSettings:
        return cls(
            model=os.environ.get("EACR_MODEL") or DEFAULT_MODEL,
            max_usd_per_post=float(os.environ.get("EACR_MAX_BUDGET_USD_PER_POST") or DEFAULT_MAX_USD_PER_POST),
            run_budget_usd=float(os.environ.get("EACR_RUN_BUDGET_USD") or DEFAULT_RUN_BUDGET_USD),
        )


def _user_prompt(post: Post) -> str:
    payload = {
        "platform": post.platform.value,
        "kind": post.context.kind.value,
        "text": post.text,
        "parent_text": post.context.parent_text,
        "quoted_text": post.context.quoted_text,
    }
    return "<post>\n" + json.dumps(payload, ensure_ascii=False, indent=1) + "\n</post>"


def _cache_key(post: Post, model: str) -> str:
    raw = "|".join([post.content_hash(), model, PROMPT_VERSION, POLICY_VERSION])
    return hashlib.sha256(raw.encode()).hexdigest()


def _abstain(reason: str, detail: str, settings: LlmSettings, cost: Cost | None = None) -> Proposal:
    return Proposal(Label.ABSTAIN, 0.0, reasons=(reason,), limitations=(detail,), cost=cost or Cost(),
                    backend="llm", model=settings.model, prompt_version=PROMPT_VERSION)


def _to_proposal(output: LlmOutput, settings: LlmSettings, cost: Cost) -> Proposal:
    """The model's free text never reaches the output: a model-written limitation could claim a token is
    verified. Its limitations are dropped (the cache keeps the raw answer) and its reason codes are kept
    only when well-formed, marked as the model's."""
    return Proposal(
        label=Label(output.label),
        confidence=output.confidence,
        calls=tuple(
            ProposedCall(c.asset_as_written, c.supporting_text, c.explicitness, EvidenceOrigin(c.evidence_origin),
                         c.conditional, c.condition_text)
            for c in output.calls
        ),
        reasons=tuple(f"{MODEL_REASON_PREFIX}{r}" for r in output.reasons if _REASON_CODE.fullmatch(r)),
        cost=cost,
        backend="llm",
        model=settings.model,
        prompt_version=PROMPT_VERSION,
    )


async def _call_agent_sdk(post: Post, settings: LlmSettings) -> tuple[dict, Cost]:
    from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

    with tempfile.TemporaryDirectory(prefix="eacr-") as workdir:
        options = ClaudeAgentOptions(
            system_prompt=SYSTEM_PROMPT,
            tools=[],
            setting_sources=[],
            model=settings.model,
            effort="low",
            max_turns=3,
            max_budget_usd=settings.max_usd_per_post,
            output_format={"type": "json_schema", "schema": OUTPUT_SCHEMA},
            cwd=workdir,
        )
        started = time.perf_counter()
        result: ResultMessage | None = None
        with anyio.fail_after(TIMEOUT_SECONDS):
            async for message in query(prompt=_user_prompt(post), options=options):
                if isinstance(message, ResultMessage):
                    result = message
        latency_ms = (time.perf_counter() - started) * 1000

    if result is None:
        raise RuntimeError("Agent SDK returned no result message")
    usage = result.usage or {}
    cost = Cost(
        usd=result.total_cost_usd or 0.0,
        input_tokens=int(usage.get("input_tokens", 0)) + int(usage.get("cache_read_input_tokens", 0))
        + int(usage.get("cache_creation_input_tokens", 0)),
        output_tokens=int(usage.get("output_tokens", 0)),
        latency_ms=round(latency_ms, 1),
        llm_calls=1,
    )
    if result.is_error or result.structured_output is None:
        detail = "; ".join(result.errors or []) or result.subtype
        raise RuntimeError(f"Agent SDK error ({result.subtype}): {detail}")
    return result.structured_output, cost


async def classify_with_llm(post: Post, settings: LlmSettings, budget: RunBudget) -> Proposal:
    cache_file = settings.cache_dir / f"{_cache_key(post, settings.model)}.json" if settings.cache_dir else None
    if cache_file and cache_file.exists():
        cached = json.loads(cache_file.read_text())
        output = LlmOutput.model_validate(cached["output"])
        return _to_proposal(output, settings, Cost(cache_hits=1))

    async with budget._lock:
        if budget.is_exhausted:
            return _abstain("BUDGET_EXHAUSTED", f"Run budget of ${budget.limit_usd:.2f} used up; post not sent to the LLM.",
                            settings)

    try:
        raw_output, cost = await _call_agent_sdk(post, settings)
    except ImportError:
        return _abstain("LLM_UNAVAILABLE", "claude-agent-sdk is not installed (uv sync --extra llm).", settings)
    except TimeoutError:
        return _abstain("LLM_TIMEOUT", f"No answer within {TIMEOUT_SECONDS}s.", settings)
    except Exception as error:  # SDK, CLI, auth and network failures all end in ABSTAIN, with the cause kept
        return _abstain("LLM_ERROR", f"{type(error).__name__}: {str(error)[:300]}", settings)

    async with budget._lock:
        budget.spent_usd += cost.usd

    try:
        output = LlmOutput.model_validate(raw_output)
    except ValidationError as error:
        return _abstain("LLM_OUTPUT_INVALID", f"Output failed schema validation: {error.error_count()} error(s).",
                        settings, cost)

    if cache_file:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps({"output": output.model_dump(), "model": settings.model,
                                          "prompt_version": PROMPT_VERSION, "policy": POLICY_VERSION}))
    return _to_proposal(output, settings, cost)
