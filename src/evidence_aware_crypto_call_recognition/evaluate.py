"""Quick per-case comparison of predictions with a reference file.

A development aid only. The client's `candidate_package/assessment.py score` is the
authoritative scorer; this module exists so a mismatch can be read case by case, and so
small-sample results carry an interval. The Wilson interval and the per-tag breakdown are
kept from the first version of this module.

Usage: python3 -m evidence_aware_crypto_call_recognition.evaluate INPUTS REFERENCES PREDICTIONS
"""
from __future__ import annotations

import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path


def wilson_interval(successes: int, total: int, z: float = 1.96) -> tuple[float, float] | None:
    if total == 0:
        return None
    p = successes / total
    denominator = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denominator
    margin = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return round(max(0.0, centre - margin), 3), round(min(1.0, centre + margin), 3)


def _rate(successes: int, total: int) -> str:
    interval = wilson_interval(successes, total)
    return f"{successes}/{total}" + (f" (95% CI {interval[0]:.2f}-{interval[1]:.2f})" if interval else "")


def load(path: str) -> dict[str, dict]:
    rows = [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
    return {row["case_id"]: row for row in rows}


def covered(required: dict, spans: list[dict]) -> bool:
    return any(s["source_id"] == required["source_id"] and s["start_utf16"] <= required["start_utf16"]
               and s["end_utf16"] >= required["end_utf16"] for s in spans)


def main(inputs_path: str, references_path: str, predictions_path: str) -> int:
    inputs, references, predictions = load(inputs_path), load(references_path), load(predictions_path)
    mismatches = 0
    buy = Counter()
    by_tag: dict[str, Counter] = defaultdict(Counter)
    for case_id, reference in references.items():
        case, prediction = inputs[case_id], predictions.get(case_id)
        if prediction is None:
            print(f"{case_id}: MISSING")
            mismatches += 1
            continue
        if reference["expected_status"] != "OK":
            ok = prediction["status"] == "INPUT_INVALID" and set(reference["expected_errors"]) & set(prediction["error_codes"])
            print(f"{case_id}: {'ok ' if ok else 'BAD'} INPUT_INVALID {prediction.get('error_codes')}")
            mismatches += not ok
            continue
        catalogue = {s["evidence_id"]: s for s in case["evidence_catalogue"]}
        label = prediction.get("label")
        assets = sorted(b["asset_mention"] for b in prediction.get("current_buys", []))
        accepted = prediction.get("confidence", 0) >= 0.75
        support = all(covered(r, [catalogue[i] for i in prediction.get("evidence_ids", [])]) for r in reference["required_support"])
        for asset, required in reference.get("buy_support", {}).items():
            entry = next((b for b in prediction.get("current_buys", []) if b["asset_mention"] == asset), None)
            if not entry or not all(covered(r, [catalogue[i] for i in entry["evidence_ids"]]) for r in required):
                support = False
        good = label == reference["label"] and assets == sorted(reference["buy_assets"]) and accepted and support
        mismatches += not good
        accepted_buy = label == "BUY" and accepted
        buy["reference"] += reference["label"] == "BUY"
        buy["found"] += reference["label"] == "BUY" and accepted_buy and good
        buy["accepted"] += accepted_buy
        buy["false"] += accepted_buy and reference["label"] != "BUY"
        for tag in reference["boundary_tags"]:
            by_tag[tag]["total"] += 1
            by_tag[tag]["correct"] += good
        print(f"{case_id}: {'ok ' if good else 'BAD'} ref={reference['label']:<10} got={label:<10} "
              f"conf={prediction.get('confidence')} assets={assets} support={support} tags={reference['boundary_tags']}")
    print(f"\n{len(references) - mismatches}/{len(references)} cases fully match (label, asset set, gate, support spans)")
    print(f"fully correct: {_rate(len(references) - mismatches, len(references))}")
    print(f"BUY found:     {_rate(buy['found'], buy['reference'])}")
    print(f"accepted false BUY: {buy['false']} of {buy['accepted']} accepted BUYs")
    print("by tag: " + ", ".join(f"{t} {c['correct']}/{c['total']}" for t, c in sorted(by_tag.items())))
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:4]))
