# Evaluation — `dev.jsonl` — backend `hybrid`

n = 66 · gold labels {'BUY': 26, 'NO_NEW_BUY': 32, 'ABSTAIN': 8}

| Metric | Value |
|---|---|
| BUY correctly recognised | 26 |
| BUY missed → NO_NEW_BUY | 0 |
| BUY missed → ABSTAIN | 0 |
| Incorrect BUY (false positives) | 0 (from NO_NEW_BUY 0, from ABSTAIN 0) |
| BUY precision (95% CI) | 1.0 (0.871, 1.0) |
| BUY recall (95% CI) | 1.0 (0.871, 1.0) |
| Abstentions | 8 (0.121) — on gold ABSTAIN 8, BUY 0, NO_NEW_BUY 0 |
| 3-way accuracy (95% CI) | 1.0 (0.945, 1.0) |
| Accuracy when not abstaining | 1.0 |
| Attribution errors on predicted BUY | none |
| Decisions the guard corrected | 1 |
| Cost | $0.0 · 0 LLM calls · 47 cache hits · 0 in / 0 out tokens |
| Latency per post | mean 0.02 ms · p95 0.064 ms · wall 0.03 s |

## Confusion matrix (rows = gold, columns = predicted)

| gold \ pred | BUY | NO_NEW_BUY | ABSTAIN |
|---|---|---|---|
| BUY | 26 | 0 | 0 |
| NO_NEW_BUY | 0 | 32 | 0 |
| ABSTAIN | 0 | 0 | 8 |

## Accuracy by tag

| tag | correct / total |
|---|---|
| conditional | 5 / 5 |
| contract_address | 3 / 3 |
| emoji | 4 / 4 |
| existing_position | 5 / 5 |
| explicit | 18 / 18 |
| forecast | 5 / 5 |
| generic_advice | 2 / 2 |
| implicit | 10 / 10 |
| joke | 3 / 3 |
| long_post | 3 / 3 |
| missing_author | 1 / 1 |
| missing_source | 1 / 1 |
| multi_asset | 6 / 6 |
| negation | 5 / 5 |
| no_asset | 2 / 2 |
| non_english_mix | 1 / 1 |
| promo | 3 / 3 |
| question | 2 / 2 |
| quote | 2 / 2 |
| referral | 2 / 2 |
| reply_context | 2 / 2 |
| repost | 1 / 1 |
| retrospective | 6 / 6 |
| sarcasm | 2 / 2 |
| slang | 2 / 2 |

## Mismatches

| source_id | gold | predicted | reasons | text |
|---|---|---|---|---|
