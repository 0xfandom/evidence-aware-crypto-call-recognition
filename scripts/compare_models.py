"""Opus 5.5 vs Haiku 5.5 on every dataset, for the llm and hybrid backends.

Committed reports may replay cached LLM answers and then show $0. Real cost and
latency per post come from `results/measured_llm_costs.json`, recorded on each
model's uncached run, so hybrid rows show what their escalated posts cost.

Opus rows were measured on an earlier prompt, and its hybrid rows also on the
earlier hybrid rule (confident rules BUYs skipped the LLM). Haiku rows are current.

Usage: uv run python scripts/compare_models.py
"""

import json
from pathlib import Path

RESULTS = Path("results")
MEASURED = json.loads((RESULTS / "measured_llm_costs.json").read_text())
MODELS = {"opus-5.5": ("claude-opus-5-5", RESULTS / "opus"), "haiku-5.5": ("claude-haiku-5-5", RESULTS / "haiku")}


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def main() -> None:
    print("| Set | Model | Backend | BUY correct / gold | False BUY | 3-way accuracy [95% CI] | Abstain "
          "| Attribution errors | LLM calls | Cost | Cost / LLM post | Mean latency / LLM post |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for dataset in ("eval_v2", "eval", "dev"):
        for name, (model_id, folder) in MODELS.items():
            measured = MEASURED[model_id][dataset]
            for backend in ("llm", "hybrid"):
                stem = folder / f"{dataset}-{backend}"
                report = json.loads(stem.with_suffix(".json").read_text())
                decisions = read_jsonl(Path(f"{stem}.decisions.jsonl"))
                used = [measured[d["input_hash"]] for d in decisions
                        if d["versions"]["backend"] in ("llm", "hybrid:llm")]
                usd = sum(c["usd"] for c in used)
                latency = sum(c["latency_ms"] for c in used) / len(used) / 1000 if used else 0.0
                buy = report["buy"]
                gold_buy = sum(report["confusion_gold_x_predicted"]["BUY"].values())
                attribution = sum(report["attribution_errors_on_predicted_buy"].values())
                print(f"| {dataset} | {name} | {backend} | {buy['correct']} / {gold_buy} | {buy['false_buy']} "
                      f"| {report['accuracy_3way']} {report['accuracy_3way_ci95']} | {report['abstention']['count']} "
                      f"| {attribution} | {len(used)} | ${usd:.3f} | ${usd / len(used) if used else 0:.4f} "
                      f"| {latency:.1f} s |")


if __name__ == "__main__":
    main()
