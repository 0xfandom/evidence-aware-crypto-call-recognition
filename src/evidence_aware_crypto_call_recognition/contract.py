from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

POLICY_VERSION = "2026-11-02.1"
# Prefix for posts pasted by hand. Such ids are local markers, never real platform post ids.
MANUAL_SOURCE_PREFIX = "manual:"


class Label(StrEnum):
    BUY = "BUY"
    NO_NEW_BUY = "NO_NEW_BUY"
    ABSTAIN = "ABSTAIN"


class Platform(StrEnum):
    X = "x"
    TELEGRAM = "telegram"
    DISCORD = "discord"
    YOUTUBE = "youtube"
    OTHER = "other"


class PostKind(StrEnum):
    ORIGINAL = "original"
    REPLY = "reply"
    QUOTE = "quote"
    REPOST = "repost"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Author(_Strict):
    handle: str | None = None
    platform_user_id: str | None = None
    display_name: str | None = None


class PostContext(_Strict):
    kind: PostKind = PostKind.ORIGINAL
    parent_text: str | None = None
    parent_author_handle: str | None = None
    quoted_text: str | None = None
    quoted_author_handle: str | None = None


class Post(_Strict):
    """One social media post. This is the input contract."""

    source_id: str | None = Field(
        default=None, description="Platform-native post ID. Missing => ABSTAIN."
    )
    platform: Platform = Platform.OTHER
    url: str | None = None
    posted_at: str | None = Field(default=None, description="ISO-8601 timestamp")
    author: Author | None = None
    text: str
    context: PostContext = PostContext()

    def content_hash(self) -> str:
        """Stable hash of everything that can change the decision, used for reuse."""
        canonical = json.dumps(self.model_dump(mode="json"), sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(canonical.encode()).hexdigest()


class AssetStatus(StrEnum):
    SYMBOL = "SYMBOL"
    ADDRESS = "ADDRESS"
    UNRESOLVED = "UNRESOLVED"


class Asset(_Strict):
    status: AssetStatus
    symbol: str | None = None
    address: str | None = None
    as_written: str | None = Field(default=None, description="Exact text it was read from")
    verified: Literal[False] = Field(
        default=False,
        description="Always false: no registry or on-chain lookup is done in this prototype.",
    )


class EvidenceOrigin(StrEnum):
    POST = "post"
    PARENT = "parent"
    QUOTED = "quoted"


class Call(_Strict):
    action: Literal["BUY"] = "BUY"
    asset: Asset
    supporting_text: str
    evidence_origin: EvidenceOrigin = EvidenceOrigin.POST
    explicitness: Literal["explicit", "implicit"]
    conditional: bool = False
    condition_text: str | None = None


class AuthorStatus(StrEnum):
    ATTRIBUTED = "ATTRIBUTED"
    UNRESOLVED = "UNRESOLVED"


class ResolvedAuthor(_Strict):
    status: AuthorStatus
    handle: str | None = None
    platform_user_id: str | None = None


class SourceRef(_Strict):
    source_id: str | None
    platform: Platform
    url: str | None
    posted_at: str | None
    is_manual_input: bool = Field(
        default=False, description="True when the post was pasted by hand and has no platform source"
    )


class Cost(_Strict):
    usd: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: float = 0.0
    llm_calls: int = 0
    cache_hits: int = 0


class Versions(_Strict):
    policy: str = POLICY_VERSION
    code: str
    backend: str
    model: str | None = None
    prompt: str | None = None


class Decision(_Strict):
    """One classification result. This is the output contract."""

    source: SourceRef
    author: ResolvedAuthor
    label: Label
    calls: tuple[Call, ...] = ()
    confidence: float = Field(ge=0.0, le=1.0)
    reasons: tuple[str, ...] = Field(default=(), description="Machine-readable reason codes")
    limitations: tuple[str, ...] = Field(default=(), description="Plain-language caveats")
    guard_corrections: tuple[str, ...] = Field(
        default=(), description="What the evidence guard changed or removed"
    )
    input_hash: str
    versions: Versions
    cost: Cost = Cost()


class Gold(_Strict):
    """Reference annotation for one dataset row."""

    label: Label
    assets: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    notes: str | None = None


class LabelledPost(_Strict):
    post: Post
    gold: Gold
