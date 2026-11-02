"""Evaluation against a labelled JSONL dataset. Metrics re-check evidence independently of the guard."""

from __future__ import annotations

import json
import math
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

import anyio

from evidence_aware_crypto_call_recognition.contract import AssetStatus, Decision, Label, LabelledPost
from evidence_aware_crypto_call_recognition.llm import LlmSettings
from evidence_aware_crypto_call_recognition.pipeline import Backend, classify_many

LABELS = (Label.BUY, Label.NO_NEW_BUY, Label.ABSTAIN)


def load_dataset(path: Path) -> list[LabelledPost]:
    return [LabelledPost.model_validate_json(line) for line in path.read_text().splitlines() if line.strip()]


def wilson_interval(successes: int, total: int, z: float = 1.96) -> tuple[float, float] | None:
    if total == 0:
        return None
    p = successes / total
    denominator = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denominator
    margin = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return round(max(0.0, centre - margin), 3), round(min(1.0, centre + margin), 3)


def _asset_key(decision_call) -> str:
    asset = decision_call.asset
    if asset.status == AssetStatus.UNRESOLVED:
        return "UNRESOLVED"
    return asset.address if asset.status == AssetStatus.ADDRESS else asset.symbol


def _attribution_errors(row: LabelledPost, decision: Decision) -> list[str]:
    """Independent re-check of the evidence contract for one predicted BUY."""
    post = row.post
    errors = []
    if decision.source.source_id != post.source_id:
        errors.append("source_id_mismatch")
    expected_handle = post.author.handle if post.author else None
    if decision.author.handle != expected_handle:
        errors.append("author_mismatch")
    sources = [t for t in (post.text, post.context.parent_text, post.context.quoted_text) if t]
    for call in decision.calls:
        if not any(call.supporting_text in t for t in sources):
            errors.append("supporting_text_not_verbatim")
        if call.asset.verified:
            errors.append("asset_claimed_verified")
    if row.gold.label == Label.BUY:
        predicted = {_asset_key(c) for c in decision.calls}
        gold = set(row.gold.assets)
        if gold - predicted:
            errors.append("asset_missed")
        if predicted - gold - {"UNRESOLVED"}:
            errors.append("asset_extra")
    return errors


@dataclass(frozen=True)
class EvalResult:
    report: dict
    decisions: list[Decision]


def evaluate(rows: list[LabelledPost], backend: Backend, settings: LlmSettings | None = None,
             concurrency: int = 4) -> EvalResult:
    started = time.perf_counter()
    decisions = anyio.run(classify_many, [r.post for r in rows], backend, settings, concurrency)
    return build_report(rows, decisions, backend, time.perf_counter() - started)


def build_report(rows: list[LabelledPost], decisions: list[Decision], backend: Backend,
                 wall_seconds: float) -> EvalResult:
    confusion = {g.value: {p.value: 0 for p in LABELS} for g in LABELS}
    by_tag: dict[str, Counter] = defaultdict(Counter)
    attribution = Counter()
    mismatches = []
    corrected = 0

    for row, decision in zip(rows, decisions, strict=True):
        gold, predicted = row.gold.label, decision.label
        confusion[gold.value][predicted.value] += 1
        for tag in row.gold.tags:
            by_tag[tag]["total"] += 1
            by_tag[tag]["correct"] += int(gold == predicted)
        if decision.guard_corrections:
            corrected += 1
        if predicted == Label.BUY:
            for error in _attribution_errors(row, decision):
                attribution[error] += 1
        if gold != predicted:
            mismatches.append({
                "source_id": row.post.source_id, "gold": gold.value, "predicted": predicted.value,
                "confidence": decision.confidence, "reasons": list(decision.reasons), "tags": list(row.gold.tags),
                "text": row.post.text[:160],
            })

    buy = confusion[Label.BUY.value]
    true_buy = buy[Label.BUY.value]
    gold_buy = sum(buy.values())
    predicted_buy = sum(confusion[g.value][Label.BUY.value] for g in LABELS)
    false_buy = predicted_buy - true_buy
    abstained = sum(confusion[g.value][Label.ABSTAIN.value] for g in LABELS)
    decided = len(rows) - abstained
    decided_correct = sum(confusion[g.value][g.value] for g in (Label.BUY, Label.NO_NEW_BUY))
    correct = sum(confusion[g.value][g.value] for g in LABELS)
    latencies = sorted(d.cost.latency_ms for d in decisions)

    report = {
        "backend": backend.value,
        "n": len(rows),
        "label_distribution": {g.value: sum(confusion[g.value].values()) for g in LABELS},
        "confusion_gold_x_predicted": confusion,
        "buy": {
            "correct": true_buy,
            "missed_as_no_new_buy": buy[Label.NO_NEW_BUY.value],
            "missed_as_abstain": buy[Label.ABSTAIN.value],
            "false_buy": false_buy,
            "false_buy_from_no_new_buy": confusion[Label.NO_NEW_BUY.value][Label.BUY.value],
            "false_buy_from_abstain": confusion[Label.ABSTAIN.value][Label.BUY.value],
            "precision": round(true_buy / predicted_buy, 3) if predicted_buy else None,
            "precision_ci95": wilson_interval(true_buy, predicted_buy),
            "recall": round(true_buy / gold_buy, 3) if gold_buy else None,
            "recall_ci95": wilson_interval(true_buy, gold_buy),
        },
        "abstention": {
            "count": abstained,
            "rate": round(abstained / len(rows), 3) if rows else None,
            "on_gold_abstain": confusion[Label.ABSTAIN.value][Label.ABSTAIN.value],
            "on_gold_buy": buy[Label.ABSTAIN.value],
            "on_gold_no_new_buy": confusion[Label.NO_NEW_BUY.value][Label.ABSTAIN.value],
        },
        "accuracy_3way": round(correct / len(rows), 3) if rows else None,
        "accuracy_3way_ci95": wilson_interval(correct, len(rows)),
        "accuracy_when_decided": round(decided_correct / decided, 3) if decided else None,
        "attribution_errors_on_predicted_buy": dict(attribution),
        "decisions_with_guard_corrections": corrected,
        "cost": {
            "usd_total": round(sum(d.cost.usd for d in decisions), 4),
            "llm_calls": sum(d.cost.llm_calls for d in decisions),
            "cache_hits": sum(d.cost.cache_hits for d in decisions),
            "input_tokens": sum(d.cost.input_tokens for d in decisions),
            "output_tokens": sum(d.cost.output_tokens for d in decisions),
            "latency_ms_mean": round(sum(latencies) / len(latencies), 2) if latencies else None,
            "latency_ms_p95": latencies[max(0, math.ceil(0.95 * len(latencies)) - 1)] if latencies else None,
            "wall_seconds": round(wall_seconds, 2),
        },
        "by_tag": {t: {"correct": c["correct"], "total": c["total"]} for t, c in sorted(by_tag.items())},
        "mismatches": mismatches,
    }
    return EvalResult(report=report, decisions=decisions)


def render_markdown(report: dict, dataset_name: str) -> str:
    b, a, c = report["buy"], report["abstention"], report["cost"]
    lines = [
        f"# Evaluation — `{dataset_name}` — backend `{report['backend']}`",
        "",
        f"n = {report['n']} · gold labels {report['label_distribution']}",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| BUY correctly recognised | {b['correct']} |",
        f"| BUY missed → NO_NEW_BUY | {b['missed_as_no_new_buy']} |",
        f"| BUY missed → ABSTAIN | {b['missed_as_abstain']} |",
        f"| Incorrect BUY (false positives) | {b['false_buy']} (from NO_NEW_BUY {b['false_buy_from_no_new_buy']}, from ABSTAIN {b['false_buy_from_abstain']}) |",
        f"| BUY precision (95% CI) | {b['precision']} {b['precision_ci95']} |",
        f"| BUY recall (95% CI) | {b['recall']} {b['recall_ci95']} |",
        f"| Abstentions | {a['count']} ({a['rate']}) — on gold ABSTAIN {a['on_gold_abstain']}, BUY {a['on_gold_buy']}, NO_NEW_BUY {a['on_gold_no_new_buy']} |",
        f"| 3-way accuracy (95% CI) | {report['accuracy_3way']} {report['accuracy_3way_ci95']} |",
        f"| Accuracy when not abstaining | {report['accuracy_when_decided']} |",
        f"| Attribution errors on predicted BUY | {report['attribution_errors_on_predicted_buy'] or 'none'} |",
        f"| Decisions the guard corrected | {report['decisions_with_guard_corrections']} |",
        f"| Cost | ${c['usd_total']} · {c['llm_calls']} LLM calls · {c['cache_hits']} cache hits · {c['input_tokens']} in / {c['output_tokens']} out tokens |",
        f"| Latency per post | mean {c['latency_ms_mean']} ms · p95 {c['latency_ms_p95']} ms · wall {c['wall_seconds']} s |",
        "",
        "## Confusion matrix (rows = gold, columns = predicted)",
        "",
        "| gold \\ pred | BUY | NO_NEW_BUY | ABSTAIN |",
        "|---|---|---|---|",
    ]
    for gold, row in report["confusion_gold_x_predicted"].items():
        lines.append(f"| {gold} | {row['BUY']} | {row['NO_NEW_BUY']} | {row['ABSTAIN']} |")
    lines += ["", "## Accuracy by tag", "", "| tag | correct / total |", "|---|---|"]
    lines += [f"| {t} | {v['correct']} / {v['total']} |" for t, v in report["by_tag"].items()]
    lines += ["", "## Mismatches", "", "| source_id | gold | predicted | reasons | text |", "|---|---|---|---|---|"]
    for m in report["mismatches"]:
        text = m["text"].replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {m['source_id']} | {m['gold']} | {m['predicted']} | {', '.join(m['reasons'])} | {text} |")
    return "\n".join(lines) + "\n"


def write_report(result: EvalResult, dataset: Path, out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{dataset.stem}-{result.report['backend']}"
    json_path, md_path = out_dir / f"{stem}.json", out_dir / f"{stem}.md"
    json_path.write_text(json.dumps(result.report, indent=2, ensure_ascii=False) + "\n")
    md_path.write_text(render_markdown(result.report, dataset.name))
    decisions_path = out_dir / f"{stem}.decisions.jsonl"
    decisions_path.write_text("".join(d.model_dump_json() + "\n" for d in result.decisions))
    return json_path, md_path
