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


def _compare_one(case: dict, reference: dict, prediction: dict | None) -> dict:
    row = {"case_id": reference["case_id"], "reference_label": reference.get("label"),
           "expected_status": reference["expected_status"], "tags": reference["boundary_tags"]}
    if prediction is None:
        return {**row, "ok": False, "status": "MISSING"}
    row.update(status=prediction["status"], label=prediction.get("label"), confidence=prediction.get("confidence"),
               error_codes=prediction.get("error_codes", []))
    if reference["expected_status"] != "OK":
        ok = prediction["status"] == "INPUT_INVALID" and bool(set(reference["expected_errors"]) & set(prediction["error_codes"]))
        return {**row, "ok": ok}
    catalogue = {s["evidence_id"]: s for s in case["evidence_catalogue"]}
    assets = sorted(b["asset_mention"] for b in prediction.get("current_buys", []))
    accepted = prediction.get("confidence", 0) >= 0.75
    support = all(covered(r, [catalogue[i] for i in prediction.get("evidence_ids", [])]) for r in reference["required_support"])
    for asset, required in reference.get("buy_support", {}).items():
        entry = next((b for b in prediction.get("current_buys", []) if b["asset_mention"] == asset), None)
        if not entry or not all(covered(r, [catalogue[i] for i in entry["evidence_ids"]]) for r in required):
            support = False
    ok = row["label"] == reference["label"] and assets == sorted(reference["buy_assets"]) and accepted and support
    return {**row, "ok": ok, "assets": assets, "reference_assets": sorted(reference["buy_assets"]),
            "accepted": accepted, "support": support}


def compare(inputs: dict[str, dict], references: dict[str, dict], predictions: dict[str, dict]) -> dict:
    """Per-case rows and a summary: fully correct, BUYs found, accepted false BUYs, by tag."""
    rows = [_compare_one(inputs[case_id], reference, predictions.get(case_id)) for case_id, reference in references.items()]
    buy = Counter()
    by_tag: dict[str, Counter] = defaultdict(Counter)
    for row in rows:
        if row["expected_status"] != "OK" or row["status"] == "MISSING":
            continue
        accepted_buy = row["label"] == "BUY" and row["accepted"]
        buy["reference"] += row["reference_label"] == "BUY"
        buy["found"] += row["reference_label"] == "BUY" and row["ok"]
        buy["accepted"] += accepted_buy
        buy["false"] += accepted_buy and row["reference_label"] != "BUY"
        for tag in row["tags"]:
            by_tag[tag]["total"] += 1
            by_tag[tag]["correct"] += row["ok"]
    correct = sum(row["ok"] for row in rows)
    summary = {"cases": len(rows), "correct": correct, "correct_ci95": wilson_interval(correct, len(rows)),
               "reference_buys": buy["reference"], "buys_found": buy["found"],
               "buys_found_ci95": wilson_interval(buy["found"], buy["reference"]),
               "accepted_buys": buy["accepted"], "accepted_false_buys": buy["false"],
               "by_tag": {tag: dict(counts) for tag, counts in sorted(by_tag.items())}}
    return {"rows": rows, "summary": summary}


def main(inputs_path: str, references_path: str, predictions_path: str) -> int:
    result = compare(load(inputs_path), load(references_path), load(predictions_path))
    for row in result["rows"]:
        mark = "ok " if row["ok"] else "BAD"
        if row["status"] == "MISSING":
            print(f"{row['case_id']}: MISSING")
        elif row["expected_status"] != "OK":
            print(f"{row['case_id']}: {mark} INPUT_INVALID {row['error_codes']}")
        else:
            print(f"{row['case_id']}: {mark} ref={row['reference_label']:<10} got={row['label']:<10} "
                  f"conf={row['confidence']} assets={row['assets']} support={row['support']} tags={row['tags']}")
    s = result["summary"]
    print(f"\n{s['correct']}/{s['cases']} cases fully match (label, asset set, gate, support spans)")
    print(f"fully correct: {_rate(s['correct'], s['cases'])}")
    print(f"BUY found:     {_rate(s['buys_found'], s['reference_buys'])}")
    print(f"accepted false BUY: {s['accepted_false_buys']} of {s['accepted_buys']} accepted BUYs")
    print("by tag: " + ", ".join(f"{t} {c['correct']}/{c['total']}" for t, c in s["by_tag"].items()))
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:4]))
