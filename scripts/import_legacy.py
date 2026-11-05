"""Convert the first version's labelled datasets into the probe source format.

The first version of this repository kept three synthetic sets in its own format, each
row `{"post": Post, "gold": Gold}`: data/dev.jsonl, data/eval.jsonl and data/eval_v2.jsonl,
154 rows in all. The package-contract reader was not written against them.
The conversion keeps the post text, the reply parent or quoted post as context, the gold
label and assets, and the tags. `build_probes.py legacy` then adds the package envelope.

Mapping, and what does not carry over:
  - ABSTAIN has no equivalent label. It is mapped to UNCLEAR and tagged `debatable`, because
    under this package's policy some of those rows are NO_NEW_BUY or BUY.
  - Reposts are skipped: the package has no repost shape, and the primary text would not be
    the captured author's own words.
  - BUY rows whose asset never appears as a `$TICKER` are skipped: the contract only accepts
    literal cashtags.
  - A missing author gets a synthetic author ID (tagged `author_added`), since the package
    rejects a missing author as an integrity error rather than a semantic case.
  - The old sets have no decisive spans, so a BUY reference only requires the cited evidence
    to contain the asset's cashtag.

Usage: python3 scripts/import_legacy.py OLD_DATA_DIR

The original files are no longer on the branch. To regenerate from them:
  git archive a72e641 data | tar -x -C /tmp/eacr-v1 && python3 scripts/import_legacy.py /tmp/eacr-v1/data
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "data" / "legacy.source.jsonl"
FILES = ("dev.jsonl", "eval.jsonl", "eval_v2.jsonl")


def convert(row: dict, origin: str, line_number: int) -> tuple[dict | None, str | None]:
    post, gold = row["post"], row["gold"]
    context = post["context"]
    if context["kind"] == "repost":
        return None, "repost"
    handle = (post["author"] or {}).get("handle")
    context_texts, same_author = [], []
    for text, other in ((context.get("parent_text"), context.get("parent_author_handle")),
                        (context.get("quoted_text"), context.get("quoted_author_handle"))):
        if text:
            context_texts.append(text)
            same_author.append(other is not None and other == handle)
    label = "UNCLEAR" if gold["label"] == "ABSTAIN" else gold["label"]
    assets, decisive = [], []
    if label == "BUY":
        for symbol in gold["assets"]:
            cashtag = f"${symbol}"
            pattern = re.compile(re.escape(cashtag) + r"(?![A-Za-z0-9_])")
            if not any(pattern.search(t) for t in [post["text"], *context_texts]):
                return None, "bare_ticker"
            assets.append(cashtag)
            decisive.append(cashtag if pattern.search(post["text"]) else None)
    tags = [*gold["tags"], f"legacy:{origin}"]
    if post["author"] is None:
        tags.append("author_added")
    return {
        "name": f"legacy_{origin}_{line_number}",
        "primary_text": post["text"],
        "capture_scope": "FULL_TEXT",
        "same_author_context": same_author,
        "context_texts": context_texts,
        "unavailable": [],
        "label": label,
        "buy_assets": assets,
        "decisive": decisive,
        "tags": tags,
        "debatable": gold["label"] == "ABSTAIN",
        "note": gold.get("notes") or "",
    }, None


def main(old_data_dir: str) -> int:
    converted, skipped = [], {}
    for name in FILES:
        lines = (Path(old_data_dir) / name).read_text(encoding="utf-8").splitlines()
        for line_number, line in enumerate(lines, start=1):
            if not line.strip():
                continue
            row, reason = convert(json.loads(line), name.removesuffix(".jsonl"), line_number)
            if row is None:
                skipped[reason] = skipped.get(reason, 0) + 1
            else:
                converted.append(row)
    TARGET.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in converted), encoding="utf-8")
    print(f"wrote {len(converted)} rows to {TARGET.relative_to(ROOT)}; skipped {skipped}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
