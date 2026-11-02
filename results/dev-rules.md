# Evaluation — `dev.jsonl` — backend `rules`

n = 66 · gold labels {'BUY': 26, 'NO_NEW_BUY': 32, 'ABSTAIN': 8}

| Metric | Value |
|---|---|
| BUY correctly recognised | 24 |
| BUY missed → NO_NEW_BUY | 0 |
| BUY missed → ABSTAIN | 2 |
| Incorrect BUY (false positives) | 0 (from NO_NEW_BUY 0, from ABSTAIN 0) |
| BUY precision (95% CI) | 1.0 (0.862, 1.0) |
| BUY recall (95% CI) | 0.923 (0.759, 0.979) |
| Abstentions | 10 (0.152) — on gold ABSTAIN 7, BUY 2, NO_NEW_BUY 1 |
| 3-way accuracy (95% CI) | 0.939 (0.854, 0.976) |
| Accuracy when not abstaining | 0.982 |
| Attribution errors on predicted BUY | none |
| Decisions the guard corrected | 1 |
| Cost | $0.0 · 0 LLM calls · 0 cache hits · 0 in / 0 out tokens |
| Latency per post | mean 0.07 ms · p95 0.155 ms · wall 0.03 s |

## Confusion matrix (rows = gold, columns = predicted)

| gold \ pred | BUY | NO_NEW_BUY | ABSTAIN |
|---|---|---|---|
| BUY | 24 | 0 | 2 |
| NO_NEW_BUY | 0 | 31 | 1 |
| ABSTAIN | 0 | 1 | 7 |

## Accuracy by tag

| tag | correct / total |
|---|---|
| conditional | 4 / 5 |
| contract_address | 2 / 3 |
| emoji | 3 / 4 |
| existing_position | 5 / 5 |
| explicit | 18 / 18 |
| forecast | 5 / 5 |
| generic_advice | 2 / 2 |
| implicit | 8 / 10 |
| joke | 2 / 3 |
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
| slang | 1 / 2 |

## Mismatches

| source_id | gold | predicted | reasons | text |
|---|---|---|---|---|
| dev-x-0007 | BUY | ABSTAIN | BUY_CUE_WITH_ASSET, LOW_CONFIDENCE | If you're not in $TIA before the next leg you're ngmi |
| dev-x-0061 | NO_NEW_BUY | ABSTAIN | POSSIBLE_SARCASM_OR_JOKE | Me buying $BTC at 100k next year after swearing I'd buy at 30k 🤡 |
| dev-x-0064 | BUY | ABSTAIN | BUY_CUE_WITH_ASSET, LOW_CONFIDENCE | I'd be a buyer of $BTC at 52k. |
| dev-telegram-0065 | ABSTAIN | NO_NEW_BUY | ASSET_WITHOUT_RECOGNISED_ACTION | aKXgjUPmzUucYVWy3oZ4HSy55d2uruXoDLNejR8RhRmF 👀👀 chart looks primed |
