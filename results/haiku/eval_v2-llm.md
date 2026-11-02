# Evaluation — `eval_v2.jsonl` — backend `llm`

n = 48 · gold labels {'BUY': 18, 'NO_NEW_BUY': 20, 'ABSTAIN': 10}

| Metric | Value |
|---|---|
| BUY correctly recognised | 17 |
| BUY missed → NO_NEW_BUY | 0 |
| BUY missed → ABSTAIN | 1 |
| Incorrect BUY (false positives) | 0 (from NO_NEW_BUY 0, from ABSTAIN 0) |
| BUY precision (95% CI) | 1.0 (0.816, 1.0) |
| BUY recall (95% CI) | 0.944 (0.742, 0.99) |
| Abstentions | 9 (0.188) — on gold ABSTAIN 8, BUY 1, NO_NEW_BUY 0 |
| 3-way accuracy (95% CI) | 0.938 (0.832, 0.979) |
| Accuracy when not abstaining | 0.949 |
| Attribution errors on predicted BUY | none |
| Decisions the guard corrected | 1 |
| Cost | $0.0273 · 48 LLM calls · 0 cache hits · 152278 in / 20550 out tokens |
| Latency per post | mean 5142.52 ms · p95 6292.3 ms · wall 64.76 s |

## Confusion matrix (rows = gold, columns = predicted)

| gold \ pred | BUY | NO_NEW_BUY | ABSTAIN |
|---|---|---|---|
| BUY | 17 | 0 | 1 |
| NO_NEW_BUY | 0 | 20 | 0 |
| ABSTAIN | 0 | 2 | 8 |

## Accuracy by tag

| tag | correct / total |
|---|---|
| conditional | 2 / 2 |
| context_only_asset | 5 / 6 |
| contract_address | 2 / 2 |
| emoji | 13 / 15 |
| existing_position | 4 / 4 |
| explicit | 11 / 11 |
| forecast | 3 / 3 |
| generic_advice | 1 / 1 |
| implicit | 11 / 12 |
| joke | 1 / 1 |
| long_post | 2 / 2 |
| missing_author | 1 / 1 |
| missing_source | 1 / 1 |
| multi_asset | 10 / 10 |
| negation | 5 / 5 |
| no_asset | 3 / 3 |
| non_english_mix | 2 / 2 |
| payment_currency | 5 / 6 |
| promo | 3 / 3 |
| question | 1 / 1 |
| quote | 3 / 3 |
| referral | 1 / 1 |
| reply_context | 3 / 4 |
| repost | 1 / 1 |
| retrospective | 2 / 2 |
| sarcasm | 3 / 3 |
| slang | 5 / 6 |
| warning | 6 / 6 |

## Mismatches

| source_id | gold | predicted | reasons | text |
|---|---|---|---|---|
| ev2-x-1029 | ABSTAIN | NO_NEW_BUY | NO_BUY_ACTION, ATTENTION_EMOJI_ONLY | $SEI 👀👀👀 |
| ev2-telegram-2006 | ABSTAIN | NO_NEW_BUY | VAGUE_HYPOTHETICAL, NO_BUY_SIDE_ACTION, PARENT_IS_OBSERVATION_NOT_PICK_REQUEST | ok this might be the one |
| ev2-telegram-2016 | BUY | ABSTAIN | POSSIBLE_JOKE_OR_SARCASM, BUY_SIDE_WORDING_PRESENT, MEME_TONE | paid 0.5 ETH for 2M $NOODL lol 🍜 bag secured, still buying under 2c |
