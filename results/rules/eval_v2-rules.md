# Evaluation — `eval_v2.jsonl` — backend `rules`

n = 48 · gold labels {'BUY': 18, 'NO_NEW_BUY': 20, 'ABSTAIN': 10}

| Metric | Value |
|---|---|
| BUY correctly recognised | 12 |
| BUY missed → NO_NEW_BUY | 2 |
| BUY missed → ABSTAIN | 4 |
| Incorrect BUY (false positives) | 0 (from NO_NEW_BUY 0, from ABSTAIN 0) |
| BUY precision (95% CI) | 1.0 (0.757, 1.0) |
| BUY recall (95% CI) | 0.667 (0.437, 0.837) |
| Abstentions | 15 (0.312) — on gold ABSTAIN 8, BUY 4, NO_NEW_BUY 3 |
| 3-way accuracy (95% CI) | 0.771 (0.635, 0.867) |
| Accuracy when not abstaining | 0.879 |
| Attribution errors on predicted BUY | {'asset_extra': 1} |
| Decisions the guard corrected | 1 |
| Cost | $0.0 · 0 LLM calls · 0 cache hits · 0 in / 0 out tokens |
| Latency per post | mean 0.1 ms · p95 0.217 ms · wall 0.03 s |

## Confusion matrix (rows = gold, columns = predicted)

| gold \ pred | BUY | NO_NEW_BUY | ABSTAIN |
|---|---|---|---|
| BUY | 12 | 2 | 4 |
| NO_NEW_BUY | 0 | 17 | 3 |
| ABSTAIN | 0 | 2 | 8 |

## Split by tags: context_only_asset, payment_currency, warning

| rows | n | BUY correct / gold | false BUY | BUY recall (95% CI) | abstentions | 3-way accuracy (95% CI) |
|---|---|---|---|---|---|---|
| with any of these tags | 18 | 3 / 8 | 0 | 0.375 (0.137, 0.694) | 9 | 0.5 (0.29, 0.71) |
| without them | 30 | 9 / 10 | 0 | 0.9 (0.596, 0.982) | 6 | 0.933 (0.787, 0.982) |

## Accuracy by tag

| tag | correct / total |
|---|---|
| conditional | 2 / 2 |
| context_only_asset | 3 / 6 |
| contract_address | 2 / 2 |
| emoji | 11 / 15 |
| existing_position | 4 / 4 |
| explicit | 8 / 11 |
| forecast | 3 / 3 |
| generic_advice | 1 / 1 |
| implicit | 9 / 12 |
| joke | 1 / 1 |
| long_post | 2 / 2 |
| missing_author | 1 / 1 |
| missing_source | 1 / 1 |
| multi_asset | 7 / 10 |
| negation | 3 / 5 |
| no_asset | 3 / 3 |
| non_english_mix | 1 / 2 |
| payment_currency | 4 / 6 |
| promo | 3 / 3 |
| question | 1 / 1 |
| quote | 2 / 3 |
| referral | 1 / 1 |
| reply_context | 2 / 4 |
| repost | 1 / 1 |
| retrospective | 2 / 2 |
| sarcasm | 3 / 3 |
| slang | 5 / 6 |
| warning | 2 / 6 |

## Mismatches

| source_id | gold | predicted | reasons | text |
|---|---|---|---|---|
| ev2-telegram-1009 | BUY | NO_NEW_BUY | ASSET_WITHOUT_RECOGNISED_ACTION | bhai $DOGE abhi le lo, 0.10 pe bahut sasta hai. baad mein mat rona 😅 |
| ev2-x-1029 | ABSTAIN | NO_NEW_BUY | ASSET_WITHOUT_RECOGNISED_ACTION | $SEI 👀👀👀 |
| ev2-discord-2002 | BUY | NO_NEW_BUY | RETROSPECTIVE, MARKET_TALK_WITHOUT_KNOWN_ASSET, WEAK_SPOT_CONTEXT_ASSET | yes. bought more this morning and still bidding below here |
| ev2-x-2004 | NO_NEW_BUY | ABSTAIN | QUOTE_STANCE_UNCLEAR, WEAK_SPOT_CONTEXT_ASSET | Not touching this. Team wallet holds 40% of supply. |
| ev2-telegram-2006 | ABSTAIN | NO_NEW_BUY | NO_ASSET_NO_ACTION, WEAK_SPOT_CONTEXT_ASSET | ok this might be the one |
| ev2-x-2007 | NO_NEW_BUY | ABSTAIN | BUY_CUE_WITH_ASSET, WARNING_CONTEXT | ⚠️ $GLOOM is a honeypot. You can buy but you cannot sell. Sell function blacklists every non-team wallet. Stay away. |
| ev2-telegram-2008 | NO_NEW_BUY | ABSTAIN | BUY_CUE_WITH_ASSET, WARNING_CONTEXT | People are buying $MOONRAT blindly because a bot channel shilled it. Dev just pulled 80% of the liquidity. Rug confirmed. |
| ev2-discord-2010 | BUY | ABSTAIN | BUY_CUE_WITH_ASSET, WARNING_CONTEXT | Bridge exploit on $VYRA, ~$14M drained. avoid until there's a real audit. Meanwhile I'm rotating into $ETH, buying spot here. |
| ev2-x-2011 | BUY | ABSTAIN | PROMOTIONAL_CONTENT, WEAK_SPOT_WARNING, WEAK_SPOT_MULTIPLE_ASSETS | PSA: the $ZORPH presale is a scam, the 'team' photos are AI-generated. If you want exposure to this sector just buy $FET and sleep well. |
| ev2-x-2013 | BUY | ABSTAIN | UNRESOLVED_ASSET, WEAK_SPOT_MULTIPLE_ASSETS | Just swapped all my $USDC into $SOL. This is the bottom, get in. |
| ev2-telegram-2016 | BUY | ABSTAIN | POSSIBLE_SARCASM_OR_JOKE, WEAK_SPOT_MULTIPLE_ASSETS | paid 0.5 ETH for 2M $NOODL lol 🍜 bag secured, still buying under 2c |
