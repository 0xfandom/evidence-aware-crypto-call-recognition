# Evaluation — `eval.jsonl` — backend `hybrid`

n = 40 · gold labels {'BUY': 14, 'NO_NEW_BUY': 18, 'ABSTAIN': 8}

| Metric | Value |
|---|---|
| BUY correctly recognised | 14 |
| BUY missed → NO_NEW_BUY | 0 |
| BUY missed → ABSTAIN | 0 |
| Incorrect BUY (false positives) | 0 (from NO_NEW_BUY 0, from ABSTAIN 0) |
| BUY precision (95% CI) | 1.0 (0.785, 1.0) |
| BUY recall (95% CI) | 1.0 (0.785, 1.0) |
| Abstentions | 7 (0.175) — on gold ABSTAIN 7, BUY 0, NO_NEW_BUY 0 |
| 3-way accuracy (95% CI) | 0.975 (0.871, 0.996) |
| Accuracy when not abstaining | 0.97 |
| Attribution errors on predicted BUY | none |
| Decisions the guard corrected | 2 |
| Cost | $0.0 · 0 LLM calls · 31 cache hits · 0 in / 0 out tokens |
| Latency per post | mean 0.02 ms · p95 0.094 ms · wall 0.03 s |

## Confusion matrix (rows = gold, columns = predicted)

| gold \ pred | BUY | NO_NEW_BUY | ABSTAIN |
|---|---|---|---|
| BUY | 14 | 0 | 0 |
| NO_NEW_BUY | 0 | 18 | 0 |
| ABSTAIN | 0 | 1 | 7 |

## Accuracy by tag

| tag | correct / total |
|---|---|
| conditional | 2 / 2 |
| contract_address | 3 / 3 |
| emoji | 12 / 13 |
| existing_position | 2 / 2 |
| explicit | 7 / 7 |
| forecast | 3 / 3 |
| generic_advice | 1 / 1 |
| implicit | 13 / 13 |
| joke | 1 / 1 |
| long_post | 3 / 3 |
| missing_author | 2 / 2 |
| missing_source | 2 / 2 |
| multi_asset | 4 / 4 |
| negation | 5 / 5 |
| no_asset | 3 / 3 |
| non_english_mix | 2 / 2 |
| promo | 2 / 2 |
| question | 2 / 2 |
| quote | 3 / 3 |
| referral | 2 / 2 |
| reply_context | 2 / 3 |
| repost | 1 / 1 |
| retrospective | 2 / 2 |
| sarcasm | 2 / 2 |
| slang | 8 / 8 |

## Mismatches

| source_id | gold | predicted | reasons | text |
|---|---|---|---|---|
| eval-x-0018 | ABSTAIN | NO_NEW_BUY | NONCOMMITTAL_REPLY, NO_BUY_ACTION, ESCALATED_FROM_RULES:NO_NEW_BUY | we'll see 🤔 |
