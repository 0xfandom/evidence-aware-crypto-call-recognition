# Labelling policy — BUY call recognition

Policy version: `2026-11-02.1`

This document is the source of truth for what counts as a BUY. The datasets,
the rule engine, the LLM prompt and the tests are all written against it. When
they disagree with this document, they are wrong.

## The question we answer

> Does this post contain a **genuine, current BUY recommendation** for a
> **specific asset**, made **by the post's own author**?

| Label | Meaning |
|---|---|
| `BUY` | Yes. At least one asset has a current buy call by the author. |
| `NO_NEW_BUY` | No. The post contains no actionable new buy call. |
| `ABSTAIN` | We cannot decide safely from the evidence we have. |

`ABSTAIN` is a real answer, not a failure. A wrong `BUY` damages a person's
credibility score. A wrong `ABSTAIN` costs a human review. We prefer the second.

## A post is `BUY` only if all five tests pass

1. **Own voice.** The author is making the call. Quoting, reposting or
   reporting someone else's call does not count, unless the author explicitly
   adopts it ("agree, buying too").
2. **Buy-side action.** The post tells the audience to acquire the asset, or
   the author discloses buying it now in a way meant as a signal. Examples:
   "buy", "load up", "accumulate", "get in", "ape", "bid", "adding here",
   "long" (a long entry counts as buy-side).
3. **Current.** The call is about now (or a concrete trigger from now on). Past
   calls ("called SOL at 8") and track-record claims are not new calls.
4. **Actionable, not only a forecast.** "BTC to 150k" is a price view, not an
   instruction. A forecast becomes `BUY` only together with a buy action.
5. **Genuine.** Not a joke, not sarcasm, not a paid promotion, not a referral
   or sign-up pitch.

## Case rules

| Case | Label | Notes |
|---|---|---|
| Direct instruction: "Buy $SOL here" | `BUY` | explicit |
| Implicit: "$SOL under 100 is a gift", "if you're not in $SOL you're ngmi", "don't fade $SOL here" | `BUY` | implicit; needs a specific asset and present-tense framing |
| Author buying now, as a signal: "Adding more $ETH here" | `BUY` | implicit |
| Existing position only: "Still holding my $ETH", "my bags: BTC, ETH" | `NO_NEW_BUY` | holding is not a new buy |
| Pure forecast: "$BTC 150k by Q2" | `NO_NEW_BUY` | |
| Forecast plus action: "$BTC 150k by Q2, keep stacking" | `BUY` | |
| Retrospective: "Told you to buy $PEPE at 0.000001" | `NO_NEW_BUY` | unless a fresh call is also made |
| Concrete conditional: "Buy $ETH if it reclaims 3k" | `BUY` | `conditional=true`, condition text kept |
| Vague hypothetical: "might look at $ADA one day" | `NO_NEW_BUY` | |
| Negation / warning: "Don't buy $X", "not touching $X" | `NO_NEW_BUY` | |
| Question: "Should I buy $SOL?" | `NO_NEW_BUY` | |
| Referral / sign-up / giveaway: "Use my code on Bybit for $50" | `NO_NEW_BUY` | no asset call |
| Paid or disclosed promotion that says buy: "#ad buy $NEWTOKEN" | `ABSTAIN` | conflict of interest; route to review (open product question below) |
| Clear sarcasm: "Sure, buy more $LUNA, what could go wrong 🤡" | `NO_NEW_BUY` | |
| Possible sarcasm / joke we cannot rule out | `ABSTAIN` | |
| Multiple assets: "Buying $SOL, dumping $ETH" | `BUY` | one call per asset; only SOL is a BUY |
| Bare repost of someone else's call | `NO_NEW_BUY` | not the original author |
| Quote with explicit endorsement: "Agree, I'm in too" | `BUY` | asset may come from the quoted text |
| Quote / reply with unclear stance: "interesting 👀" | `ABSTAIN` | |
| Reply that answers "what should I buy?" with "$SOL" | `BUY` | the call needs the parent context |
| Buy action, but the specific asset cannot be identified ("this one sends, get in" + no ticker) | `BUY` with asset `UNRESOLVED` *or* `ABSTAIN` | `BUY` only if the text clearly points to one specific asset; otherwise `ABSTAIN` |
| Generic market advice: "buy the dip", "DCA is king" | `NO_NEW_BUY` | no specific asset |
| Long post with one call buried inside | judged on that call | supporting text is the sentence that carries it |

## Evidence rules (apply to every accepted `BUY`)

Every `BUY` must carry:

- **Source identifier** — copied from the input. If the input has none, the
  output is `ABSTAIN` (`MISSING_SOURCE_ID`).
- **Author** — copied from input metadata only, never inferred from text. If
  absent, the author is marked `UNRESOLVED`.
- **Supporting text** — a verbatim span of the post (or of the provided
  context, flagged as such) that mentions the asset it supports. Text that does
  not appear verbatim, or does not mention its asset, is rejected.
- **Action** — `BUY`, and whether it is `explicit` or `implicit`, and
  `conditional` with the condition text if any.
- **Asset** — the symbol or address exactly as written, with a status:
  - `SYMBOL` — a ticker or known name appears; *not* mapped to a contract.
  - `ADDRESS` — a contract address string appears; *not* checked on-chain.
  - `UNRESOLVED` — no specific asset could be identified.
  `verified` is always `false` in this prototype. A ticker like `$PEPE` can
  belong to many contracts; we never claim we know which one.
- **Limitations** — plain-language list of what is uncertain.

If any essential item fails these checks, the system either downgrades to
`ABSTAIN` or marks the field as unresolved. It never fills a gap by guessing.

## Open product questions (decided provisionally here)

1. **Paid promotion with a buy instruction.** Scored as a call (the KOL did say
   buy) or excluded (not genuine)? Provisional: `ABSTAIN` + review.
2. **Conditional calls.** Scored when issued, or only when the trigger fires?
   Provisional: `BUY` with `conditional=true`; scoring decides.
3. **Leveraged longs vs spot buys.** Same call type? Provisional: both `BUY`.
4. **Author-unresolved BUYs.** Should scoring ever credit them? Provisional: the
   classifier may emit them, scoring must not attribute them to anyone.
