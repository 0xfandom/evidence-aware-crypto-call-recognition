"""HTTP API and web UI. Same pipeline, guard, cache and budgets as the CLI."""

from __future__ import annotations

import hashlib
import time
from dataclasses import replace
from importlib import resources
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from evidence_aware_crypto_call_recognition import __version__
from evidence_aware_crypto_call_recognition.contract import (
    MANUAL_SOURCE_PREFIX,
    POLICY_VERSION,
    Author,
    Decision,
    Label,
    LabelledPost,
    Platform,
    Post,
    PostContext,
    PostKind,
)
from evidence_aware_crypto_call_recognition.evaluate import build_report
from evidence_aware_crypto_call_recognition.llm import PROMPT_VERSION, LlmSettings
from evidence_aware_crypto_call_recognition.pipeline import Backend, classify_many

MAX_BATCH_POSTS = 200


class _Request(BaseModel):
    model_config = ConfigDict(extra="forbid")
    backend: Backend = Backend.RULES
    model: str | None = Field(default=None, description="LLM model id; default from EACR_MODEL")
    run_budget_usd: float | None = Field(default=None, gt=0, description="Hard USD cap for this request")


class ClassifyRequest(_Request):
    post: Post


class TextRequest(_Request):
    text: str = Field(min_length=1)
    source_id: str | None = Field(default=None, description="Leave empty to mark the post as manual input")
    author_handle: str | None = None
    platform: Platform = Platform.OTHER
    kind: PostKind = PostKind.ORIGINAL
    parent_text: str | None = None
    quoted_text: str | None = None


class BatchRequest(_Request):
    items: list[dict[str, Any]] = Field(
        min_length=1, description="Posts, or dataset rows {'post': ..., 'gold': ...} to also get metrics"
    )


class BatchResponse(BaseModel):
    decisions: list[Decision]
    summary: dict[str, Any]
    evaluation: dict[str, Any] | None = None


def _settings(request: _Request) -> LlmSettings:
    settings = LlmSettings.from_env()
    if request.model:
        settings = replace(settings, model=request.model)
    if request.run_budget_usd is not None:
        settings = replace(settings, run_budget_usd=request.run_budget_usd)
    return settings


def _summary(decisions: list[Decision], wall_seconds: float) -> dict[str, Any]:
    return {
        "posts": len(decisions),
        "labels": {label.value: sum(d.label == label for d in decisions) for label in Label},
        "llm_calls": sum(d.cost.llm_calls for d in decisions),
        "cache_hits": sum(d.cost.cache_hits for d in decisions),
        "usd_total": round(sum(d.cost.usd for d in decisions), 6),
        "wall_seconds": round(wall_seconds, 3),
    }


def _post_from_text(request: TextRequest) -> Post:
    source_id = (request.source_id or "").strip()
    if not source_id:
        digest = hashlib.sha256(request.text.encode()).hexdigest()[:12]
        source_id = f"{MANUAL_SOURCE_PREFIX}{digest}"
    return Post(
        source_id=source_id,
        platform=request.platform,
        author=Author(handle=request.author_handle) if request.author_handle else None,
        text=request.text,
        context=PostContext(kind=request.kind, parent_text=request.parent_text or None,
                            quoted_text=request.quoted_text or None),
    )


def _parse_items(items: list[dict[str, Any]]) -> tuple[list[Post], list[LabelledPost] | None]:
    posts: list[Post] = []
    labelled: list[LabelledPost] = []
    for index, item in enumerate(items):
        try:
            if "post" in item:
                if "gold" in item:
                    row = LabelledPost.model_validate(item)
                    labelled.append(row)
                    posts.append(row.post)
                else:
                    posts.append(Post.model_validate(item["post"]))
            else:
                posts.append(Post.model_validate(item))
        except ValidationError as error:
            raise HTTPException(status_code=422, detail=f"item {index}: {error.errors()[0]['msg']}") from error
    return posts, (labelled if len(labelled) == len(posts) else None)


app = FastAPI(
    title="Evidence-Aware Crypto Call Recognition",
    version=__version__,
    description="Recognises genuine, current crypto BUY calls in social posts, with checked evidence.",
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "code": __version__,
        "policy": POLICY_VERSION,
        "prompt": PROMPT_VERSION,
        "default_model": LlmSettings.from_env().model,
    }


@app.post("/api/classify", response_model=Decision)
async def classify_post(request: ClassifyRequest) -> Decision:
    (decision,) = await classify_many([request.post], request.backend, _settings(request), concurrency=1)
    return decision


@app.post("/api/classify/text", response_model=Decision)
async def classify_text(request: TextRequest) -> Decision:
    (decision,) = await classify_many([_post_from_text(request)], request.backend, _settings(request), concurrency=1)
    return decision


@app.post("/api/classify/batch", response_model=BatchResponse)
async def classify_batch(request: BatchRequest) -> BatchResponse:
    if len(request.items) > MAX_BATCH_POSTS:
        raise HTTPException(status_code=413, detail=f"at most {MAX_BATCH_POSTS} posts per request")
    posts, labelled = _parse_items(request.items)
    started = time.perf_counter()
    decisions = await classify_many(posts, request.backend, _settings(request))
    wall_seconds = time.perf_counter() - started
    evaluation = build_report(labelled, decisions, request.backend, wall_seconds).report if labelled else None
    return BatchResponse(decisions=decisions, summary=_summary(decisions, wall_seconds), evaluation=evaluation)


_static = resources.files("evidence_aware_crypto_call_recognition.web").joinpath("static")
if _static.is_dir() and _static.joinpath("index.html").is_file():
    app.mount("/", StaticFiles(directory=str(_static), html=True), name="ui")
else:

    @app.get("/")
    def ui_missing() -> dict[str, str]:
        return {"detail": "UI not built. Run `npm install && npm run build` in frontend/, or use /docs."}
