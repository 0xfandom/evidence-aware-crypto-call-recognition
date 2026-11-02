# Evaluation — `eval.jsonl` — backend `rules`

n = 40 · gold labels {'BUY': 14, 'NO_NEW_BUY': 18, 'ABSTAIN': 8}

| Metric | Value |
|---|---|
| BUY correctly recognised | 8 |
| BUY missed → NO_NEW_BUY | 6 |
| BUY missed → ABSTAIN | 0 |
| Incorrect BUY (false positives) | 0 (from NO_NEW_BUY 0, from ABSTAIN 0) |
| BUY precision (95% CI) | 1.0 (0.676, 1.0) |
| BUY recall (95% CI) | 0.571 (0.326, 0.786) |
| Abstentions | 9 (0.225) — on gold ABSTAIN 5, BUY 0, NO_NEW_BUY 4 |
| 3-way accuracy (95% CI) | 0.675 (0.52, 0.799) |
| Accuracy when not abstaining | 0.71 |
| Attribution errors on predicted BUY | {'asset_missed': 1, 'asset_extra': 1} |
| Decisions the guard corrected | 2 |
| Cost | $0.0 · 0 LLM calls · 0 cache hits · 0 in / 0 out tokens |
| Latency per post | mean 0.11 ms · p95 0.499 ms · wall 0.03 s |

## Confusion matrix (rows = gold, columns = predicted)

| gold \ pred | BUY | NO_NEW_BUY | ABSTAIN |
|---|---|---|---|
| BUY | 8 | 6 | 0 |
| NO_NEW_BUY | 0 | 14 | 4 |
| ABSTAIN | 0 | 3 | 5 |

## Accuracy by tag

| tag | correct / total |
|---|---|
| conditional | 2 / 2 |
| contract_address | 2 / 3 |
| emoji | 8 / 13 |
| existing_position | 2 / 2 |
| explicit | 6 / 7 |
| forecast | 3 / 3 |
| generic_advice | 0 / 1 |
| implicit | 7 / 13 |
| joke | 0 / 1 |
| long_post | 3 / 3 |
| missing_author | 1 / 2 |
| missing_source | 2 / 2 |
| multi_asset | 3 / 4 |
| negation | 3 / 5 |
| no_asset | 2 / 3 |
| non_english_mix | 1 / 2 |
| promo | 2 / 2 |
| question | 2 / 2 |
| quote | 0 / 3 |
| referral | 2 / 2 |
| reply_context | 1 / 3 |
| repost | 1 / 1 |
| retrospective | 2 / 2 |
| sarcasm | 0 / 2 |
| slang | 5 / 8 |

## Mismatches

| source_id | gold | predicted | reasons | text |
|---|---|---|---|---|
| eval-x-0007 | ABSTAIN | NO_NEW_BUY | NO_ASSET_NO_ACTION, WEAK_SPOT_CONTEXT_ASSET | hmm 👀 |
| eval-x-0012 | ABSTAIN | NO_NEW_BUY | ASSET_WITHOUT_RECOGNISED_ACTION | putting my rent money into $BONK tonight. what's the worst that could happen lmao |
| eval-telegram-0013 | NO_NEW_BUY | ABSTAIN | BUY_CUE_WITH_ASSET, WARNING_CONTEXT | ⚠️ SCAM ALERT ⚠️ 0x13877c3add83c48e2bc25e7872de5b077bb20aea is a honeypot. you can buy but you can't sell. do NOT ape this. |
| eval-x-0018 | ABSTAIN | NO_NEW_BUY | NO_ASSET_NO_ACTION, WEAK_SPOT_CONTEXT_ASSET | we'll see 🤔 |
| eval-x-0020 | NO_NEW_BUY | ABSTAIN | UNRESOLVED_ASSET | Rule #1: buy the fear, sell the greed. DCA weekly and stop refreshing charts every 5 minutes. |
| eval-discord-0022 | BUY | NO_NEW_BUY | ASSET_WITHOUT_RECOGNISED_ACTION | yall sleepin on $GLORP lol. 400k mcap, im lodaing up evry dip till 2m |
| eval-x-0025 | BUY | NO_NEW_BUY | ASSET_WITHOUT_RECOGNISED_ACTION | $SUI. no contest. |
| eval-x-0026 | NO_NEW_BUY | ABSTAIN | QUOTE_STANCE_UNCLEAR, WEAK_SPOT_CONTEXT_ASSET | lol no. this is exactly how you become exit liquidity. |
| eval-x-0028 | BUY | NO_NEW_BUY | RETROSPECTIVE, MARKET_TALK_WITHOUT_KNOWN_ASSET, WEAK_SPOT_CONTEXT_ASSET | 100% with you on this one, just market bought a stack myself |
| eval-discord-0034 | BUY | NO_NEW_BUY | ASSET_WITHOUT_RECOGNISED_ACTION | scaling in to $TIA here, 1/3 size now, rest under 4. cheap here imo |
| eval-x-0035 | NO_NEW_BUY | ABSTAIN | POSSIBLE_SARCASM_OR_JOKE | yes absolutely buy more $FTT, the old team is definitely coming back to fix everything 🤡🤡 |
| eval-x-0036 | BUY | NO_NEW_BUY | ASSET_WITHOUT_RECOGNISED_ACTION, WEAK_SPOT_MULTIPLE_ASSETS | trimmed my $DOGE into strength, every cent of it going into $JUP. dog had its run, jup is the play now |
| eval-x-0037 | BUY | NO_NEW_BUY | ASSET_WITHOUT_RECOGNISED_ACTION | bhai $PEPE abhi le lo, ye dip dobara nahi milega 🐸 |
