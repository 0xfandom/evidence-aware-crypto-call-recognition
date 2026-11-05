from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from evidence_aware_crypto_call_recognition.contract import text_sha256  # noqa: E402
from evidence_aware_crypto_call_recognition.integrity import expected_catalogue  # noqa: E402

PACKAGE = ROOT / "candidate_package"
DATA = ROOT / "data"


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def make_case(text: str, context: list[str] | None = None, unavailable: list[str] | None = None,
              scope: str = "FULL_TEXT", case_id: str = "dev-0123456789") -> dict:
    """A valid contract input around the given texts, for focused behaviour tests."""
    primary = {"source_id": "sim_post_testprimary", "author_id": "sim_author_aaaaaaaaaaaa",
               "published_at_utc": "2025-05-02T12:00:00Z", "text": text, "text_sha256": text_sha256(text),
               "capture_scope": scope}
    sources = []
    for index, context_text in enumerate(context or []):
        sources.append({"source_id": f"sim_post_testcontext{index}", "author_id": "sim_author_bbbbbbbbbbbb",
                        "published_at_utc": "2025-05-01T12:00:00Z", "text": context_text,
                        "text_sha256": text_sha256(context_text), "capture_scope": "FULL_TEXT"})
    case = {"case_id": case_id, "synthetic": True, "available_at_utc": "2025-05-02T12:10:00Z", "primary": primary,
            "context": sources,
            "unavailable_context": [{"kind": kind, "reference": f"https://example.invalid/{kind.lower()}"} for kind in unavailable or []],
            "asset_identity_evidence": [], "evidence_catalogue": []}
    case["evidence_catalogue"] = expected_catalogue(case)
    return case
