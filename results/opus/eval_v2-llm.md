# Evaluation — `eval_v2.jsonl` — backend `llm`

n = 48 · gold labels {'BUY': 18, 'NO_NEW_BUY': 20, 'ABSTAIN': 10}

| Metric | Value |
|---|---|
| BUY correctly recognised | 18 |
| BUY missed → NO_NEW_BUY | 0 |
| BUY missed → ABSTAIN | 0 |
| Incorrect BUY (false positives) | 0 (from NO_NEW_BUY 0, from ABSTAIN 0) |
| BUY precision (95% CI) | 1.0 (0.824, 1.0) |
| BUY recall (95% CI) | 1.0 (0.824, 1.0) |
| Abstentions | 10 (0.208) — on gold ABSTAIN 9, BUY 0, NO_NEW_BUY 1 |
| 3-way accuracy (95% CI) | 0.958 (0.86, 0.988) |
| Accuracy when not abstaining | 0.974 |
| Attribution errors on predicted BUY | none |
| Decisions the guard corrected | 1 |
| Cost | $0.0 · 0 LLM calls · 48 cache hits · 0 in / 0 out tokens |
| Latency per post | mean 0.0 ms · p95 0.0 ms · wall 0.03 s |

## Confusion matrix (rows = gold, columns = predicted)

| gold \ pred | BUY | NO_NEW_BUY | ABSTAIN |
|---|---|---|---|
| BUY | 18 | 0 | 0 |
| NO_NEW_BUY | 0 | 19 | 1 |
| ABSTAIN | 0 | 1 | 9 |

## Accuracy by tag

| tag | correct / total |
|---|---|
| conditional | 2 / 2 |
| context_only_asset | 6 / 6 |
| contract_address | 2 / 2 |
| emoji | 14 / 15 |
| existing_position | 4 / 4 |
| explicit | 11 / 11 |
| forecast | 3 / 3 |
| generic_advice | 1 / 1 |
| implicit | 12 / 12 |
| joke | 1 / 1 |
| long_post | 2 / 2 |
| missing_author | 1 / 1 |
| missing_source | 1 / 1 |
| multi_asset | 10 / 10 |
| negation | 5 / 5 |
| no_asset | 3 / 3 |
| non_english_mix | 2 / 2 |
| payment_currency | 6 / 6 |
| promo | 3 / 3 |
| question | 1 / 1 |
| quote | 3 / 3 |
| referral | 1 / 1 |
| reply_context | 4 / 4 |
| repost | 0 / 1 |
| retrospective | 2 / 2 |
| sarcasm | 3 / 3 |
| slang | 6 / 6 |
| warning | 6 / 6 |

## Mismatches

| source_id | gold | predicted | reasons | text |
|---|---|---|---|---|
| ev2-x-1020 | NO_NEW_BUY | ABSTAIN | REPOST_WITHOUT_COMMENTARY, ENDORSEMENT_UNCLEAR | Buy $TAO under 300, generational entry. |
| ev2-x-1029 | ABSTAIN | NO_NEW_BUY | NO_BUY_ACTION, MERE_MENTION | $SEI 👀👀👀 |
