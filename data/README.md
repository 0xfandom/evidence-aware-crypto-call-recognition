# Datasets

No development data was supplied with the brief, so all three sets here are
**synthetic**: every post, handle and most tickers are invented. They exist to
exercise the policy cases, not to estimate real-world accuracy.

| File | Rows | BUY / NO_NEW_BUY / ABSTAIN | Written by | Used for |
|---|---|---|---|---|
| `dev.jsonl` | 66 | 26 / 32 / 8 | the classifier author, while building the rules | building and debugging |
| `eval.jsonl` | 40 | 14 / 18 / 8 | a separate AI-assistant session that saw only `docs/labeling_policy.md` and the JSON contract — not the code, not the dev set | first held-out measurement; afterwards **development data**, because its errors shaped the escalation rule |
| `eval_v2.jsonl` | 48 | 18 / 20 / 10 | another fresh assistant session, same restrictions; its report to the classifier author gave counts only, no content | current held-out set: 30 general rows + 18 challenge rows (`context_only_asset`, `warning`, `payment_currency`) |

SHA-256 at freeze time:
- `dev.jsonl` `7560d12e897c8c03690c4c7963e86094e748c22b790ff5ae26e83560667d48b7`
- `eval.jsonl` `ccbd49dee59b9d01ac76298bfbaa349cbc3f175030bba64cac34f1ff8be1d698`
- `eval_v2.jsonl` `67a0937c7707d7a19a036548e4e1eec24ac87baf84c99e77576936633d302aee`

## Format

One JSON object per line: `{"post": Post, "gold": Gold}` (see
`src/evidence_aware_crypto_call_recognition/contract.py`).

```json
{
  "post": {
    "source_id": "dev-x-0001",
    "platform": "x",
    "url": null,
    "posted_at": "2026-10-02T07:15:00Z",
    "author": {"handle": "@satsmaxi_kai", "platform_user_id": "1002", "display_name": "Kai"},
    "text": "Buying $SOL here. 140 is the line in the sand, bids filled.",
    "context": {"kind": "original", "parent_text": null, "parent_author_handle": null,
                "quoted_text": null, "quoted_author_handle": null}
  },
  "gold": {"label": "BUY", "assets": ["SOL"], "tags": ["explicit"], "notes": null}
}
```

- `gold.assets` lists the symbols (uppercase) or contract addresses that carry a
  BUY call. It is empty for `NO_NEW_BUY` and `ABSTAIN`.
- `gold.tags` name the hard cases present, used for the per-tag breakdown.
- `classify` also accepts bare `Post` objects, one per line.

## To use the company's datasets

Convert them to this format (or add a small adapter) and run:

```bash
uv run eacr eval path/to/dev.jsonl --backend rules
uv run eacr eval path/to/eval.jsonl --backend hybrid
```

## Known biases

- All three sets were written by AI assistants guided by the same policy, so the
  writing style is cleaner and more "textbook" than real posts.
- The `eval.jsonl` author was given a list of slang to vary. Those exact phrases were
  deliberately not added to the rules, but the classifier author did see a short
  summary of that set (a few example phrases) before the rules were frozen.
- Sizes are tiny: one row changes BUY recall on `eval_v2.jsonl` by about 6 points.
