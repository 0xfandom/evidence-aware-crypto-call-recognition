"""Build contract-shaped inputs and references from the hand-written probe source.

The probe posts in data/probes.source.jsonl were written from the policy
alone, by a separate author who did not see the classifier. This script only adds the
technical envelope (IDs, timestamps, hashes, evidence catalogue) in the published
input shape, and the matching reference rows in the client's reference shape.

Usage: python3 scripts/build_probes.py [NAME]   (NAME defaults to "probes"; "holdout" builds the second
set, "legacy" the sets imported from the first prototype by import_legacy.py)

A `decisive` entry of null means the asset's cashtag alone is required, in whichever
source names it (used by the legacy sets, which have no decisive spans).
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from evidence_aware_crypto_call_recognition.contract import fingerprint, text_sha256, utf16_length  # noqa: E402
from evidence_aware_crypto_call_recognition.integrity import expected_catalogue, input_errors  # noqa: E402

DATA = ROOT / "data"


def _hex(seed: str, length: int) -> str:
    return hashlib.sha256(seed.encode()).hexdigest()[:length]


def build_case(row: dict, position: int) -> tuple[dict, dict]:
    name = row["name"]
    case_id = f"dev-{_hex('case:' + name, 10)}"
    author = f"sim_author_{_hex('author:' + name, 12)}"
    day = 1 + position % 27
    published = f"2025-05-{day:02d}T12:00:00Z"
    primary = {"source_id": f"sim_post_{_hex('primary:' + name, 12)}p", "author_id": author, "published_at_utc": published,
               "text": row["primary_text"], "text_sha256": text_sha256(row["primary_text"]), "capture_scope": row["capture_scope"]}
    context = []
    for index, (same_author, text) in enumerate(zip(row["same_author_context"], row["context_texts"])):
        context.append({"source_id": f"sim_post_{_hex(f'context:{name}:{index}', 12)}q",
                        "author_id": author if same_author else f"sim_author_{_hex(f'other:{name}:{index}', 12)}",
                        "published_at_utc": f"2025-04-{day:02d}T0{index}:00:00Z", "text": text,
                        "text_sha256": text_sha256(text), "capture_scope": "FULL_TEXT"})
    case = {"case_id": case_id, "synthetic": True, "available_at_utc": f"2025-05-{day:02d}T12:10:00Z", "primary": primary,
            "context": context, "unavailable_context": row["unavailable"], "asset_identity_evidence": [], "evidence_catalogue": []}
    case["evidence_catalogue"] = expected_catalogue(case)
    errors = input_errors(case)
    if errors:
        raise SystemExit(f"{name}: built an invalid input: {errors}")

    def span(source: dict, start: int, end: int) -> dict:
        text = source["text"]
        return {"source_id": source["source_id"], "start_utf16": utf16_length(text[:start]), "end_utf16": utf16_length(text[:end])}

    text = row["primary_text"]
    buy_support: dict[str, list[dict]] = {}
    for asset, decisive in zip(row["buy_assets"], row["decisive"]):
        spans = []
        if decisive is not None:
            start = text.index(decisive)
            spans.append(span(primary, start, start + len(decisive)))
        if decisive is None or asset not in decisive:
            holder = next(s for s in context if asset in s["text"])
            at = holder["text"].index(asset)
            spans.append(span(holder, at, at + len(asset)))
        buy_support[asset] = spans
    if row["label"] == "BUY":
        required = [s for spans in buy_support.values() for s in spans]
    else:
        required = [span(primary, 0, len(text))]
    reference = {"case_id": case_id, "input_sha256": fingerprint(case), "expected_status": "OK", "label": row["label"],
                 "buy_assets": row["buy_assets"], "required_support": required, "buy_support": buy_support,
                 "expected_errors": [], "boundary_tags": row["tags"] + (["debatable"] if row["debatable"] else []),
                 "reference_reason": row["note"], "reference_origin": "PROBE_WRITTEN_FROM_POLICY_NOT_HUMAN_GOLD",
                 "probe_name": name}
    return case, reference


def main(name: str = "probes") -> int:
    source = DATA / f"{name}.source.jsonl"
    INPUTS = DATA / f"{name}.inputs.jsonl"
    REFERENCES = DATA / f"{name}.references.jsonl"
    rows = [json.loads(line) for line in source.read_text(encoding="utf-8").splitlines() if line.strip()]
    built = [build_case(row, position) for position, row in enumerate(rows)]
    INPUTS.write_text("".join(json.dumps(c, ensure_ascii=False) + "\n" for c, _ in built), encoding="utf-8")
    REFERENCES.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for _, r in built), encoding="utf-8")
    print(f"wrote {len(built)} probe cases to {INPUTS.relative_to(ROOT)} and {REFERENCES.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:2]))
