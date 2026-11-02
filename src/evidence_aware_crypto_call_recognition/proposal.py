"""What a backend proposes. Untrusted until the evidence guard has checked it."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from evidence_aware_crypto_call_recognition.contract import Cost, EvidenceOrigin, Label


@dataclass(frozen=True)
class ProposedCall:
    asset_as_written: str | None
    supporting_text: str
    explicitness: Literal["explicit", "implicit"]
    evidence_origin: EvidenceOrigin = EvidenceOrigin.POST
    conditional: bool = False
    condition_text: str | None = None


@dataclass(frozen=True)
class Proposal:
    label: Label
    confidence: float
    calls: tuple[ProposedCall, ...] = ()
    reasons: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    cost: Cost = field(default_factory=Cost)
    backend: str = "rules"
    model: str | None = None
    prompt_version: str | None = None
