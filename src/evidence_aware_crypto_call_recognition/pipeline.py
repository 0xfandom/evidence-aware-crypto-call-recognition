from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import replace
from enum import StrEnum

import anyio

from evidence_aware_crypto_call_recognition.contract import Cost, Decision, Label, Post
from evidence_aware_crypto_call_recognition.guard import apply_guard
from evidence_aware_crypto_call_recognition.llm import LlmSettings, RunBudget, classify_with_llm
from evidence_aware_crypto_call_recognition.proposal import Proposal
from evidence_aware_crypto_call_recognition.rules import classify_with_rules

# Rules decide alone only when they are confident; everything else goes to the LLM.
HYBRID_ESCALATE_BELOW = 0.8


class Backend(StrEnum):
    RULES = "rules"
    LLM = "llm"
    HYBRID = "hybrid"


def _timed_rules(post: Post) -> Proposal:
    started = time.perf_counter()
    proposal = classify_with_rules(post)
    return replace(proposal, cost=Cost(latency_ms=round((time.perf_counter() - started) * 1000, 3)))


async def propose(post: Post, backend: Backend, settings: LlmSettings, budget: RunBudget) -> Proposal:
    if backend == Backend.RULES:
        return _timed_rules(post)
    if backend == Backend.LLM:
        return await classify_with_llm(post, settings, budget)

    rules = _timed_rules(post)
    if rules.label != Label.ABSTAIN and rules.confidence >= HYBRID_ESCALATE_BELOW:
        return replace(rules, backend="hybrid:rules")
    llm = await classify_with_llm(post, settings, budget)
    return replace(llm, backend="hybrid:llm", reasons=llm.reasons + (f"ESCALATED_FROM_RULES:{rules.label.value}",))


async def classify(post: Post, backend: Backend = Backend.RULES, settings: LlmSettings | None = None,
                   budget: RunBudget | None = None) -> Decision:
    settings = settings or LlmSettings.from_env()
    budget = budget or RunBudget(settings.run_budget_usd)
    return apply_guard(post, await propose(post, backend, settings, budget))


async def classify_many(posts: Sequence[Post], backend: Backend = Backend.RULES,
                        settings: LlmSettings | None = None, concurrency: int = 4) -> list[Decision]:
    settings = settings or LlmSettings.from_env()
    budget = RunBudget(settings.run_budget_usd)
    results: list[Decision | None] = [None] * len(posts)
    limiter = anyio.CapacityLimiter(concurrency)

    async def run_one(index: int, post: Post) -> None:
        async with limiter:
            results[index] = await classify(post, backend, settings, budget)

    async with anyio.create_task_group() as group:
        for index, post in enumerate(posts):
            group.start_soon(run_one, index, post)
    return [r for r in results if r is not None]


def classify_sync(post: Post, backend: Backend = Backend.RULES, settings: LlmSettings | None = None) -> Decision:
    return anyio.run(classify, post, backend, settings)
