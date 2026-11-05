# Design notes

## The problem as the package frames it

A post counts as `BUY` only when **its captured author** communicates a present entry,
endorsement or acquisition intent for an identifiable asset. Forecasts, past trades,
holdings, exits, shorts and covers, conditionals, quoted or imitated speakers, and
sponsorship without a call are `NO_NEW_BUY`. `UNCLEAR` is kept for a specific essential
gap: a missing referent, timing, speaker or polarity. A technical problem with the input
is never a semantic label: it is `INPUT_INVALID`, or `CAPACITY_LIMIT` when the case
cannot be read in full.

## Why rules, and why that is not the end state

The package authorizes no provider requests, paid inference, training or downloads. That
rules out an LLM classifier and a trained ModernBERT inside this exercise. What remains
is a transparent, deterministic reader built from the policy. It is useful in three ways:

1. It meets the full contract today, offline, with every decision traceable to a sentence.
2. It is a baseline any learned model must beat on the same scorer.
3. Everything except the sentence reader (integrity, segmentation, evidence selection,
   decision assembly, self-check, evaluation) is model-agnostic and carries over to
   ModernBERT unchanged.

The frozen first runs show the cost of rules plainly (see Results): wording outside the
lexicon is missed. That is the argument for a learned model (ModernBERT) trained on
human-confirmed labels.

## Pipeline

```
input JSONL ─► integrity ─► capacity ─► segment ─► reading ─► decide ─► selfcheck ─► output JSONL
               (INPUT_INVALID) (CAPACITY_LIMIT)  sentences  per-asset   label, evidence,
                                                 + quotes   operations  confidence, text
```

- **integrity.py**: the package's technical checks, re-implemented: field sets, synthetic
  flag, case ID, author ID, timestamps, chronology (future context, after cutoff), text
  hashes, unavailable-context shape, no external asset evidence, and an exact rebuild of
  the evidence catalogue. Error codes use the package's names. On the development set it
  reports every expected error for the 3 invalid controls, and rebuilds the supplied
  catalogue byte for byte for the other 21.
- **segment.py**: lines, paragraphs and sentences, with offsets into the full text.
  Quoted speech is located so it can be blanked out. Apostrophes are not quotes, and
  decimals do not end a sentence.
- **reading.py** and **cues.py**: per sentence, the cashtags the author names outside
  quotes, and for each the operation: `ENTRY` (with a strength), `EXIT`, `COVER`, `SHORT`,
  `HOLD`, `PAST`, `UNDATED_PURCHASE`, `HEDGE` or `NONE`. Each asset takes the nearest
  action cue (entry, exit, cover, short), so "selling $A and buying $B" keeps the two
  apart. State cues (past, hold) apply only when no action cue is present, so "still
  holding $X and adding more today" is an entry. Entry wording is set aside, with the
  reason recorded, when the sentence is a genuine question, conditional, imitation or
  satire, third-party, or about a non-token purchase. The informal-wording and joke-marker
  cue families come from the 0.1.0 `rules.py`.
- **decide.py**: post-level reasoning:
  - an asset-less entry ("A small starter allocation here makes sense to me") binds to
    the asset named just before it, or to the only asset the post names, or, when the
    primary names none, to the single cashtag in the retained context;
  - disclaimers are scoped to the sentence's assets, the previous sentence's assets, the
    paragraph ("this paragraph … not portfolio advice"), or the whole post ("this post
    recommends no token");
  - a BUY that the same post disclaims or later reverses stays below the gate;
  - joke or sarcasm markers, or satire framing elsewhere in the post, keep a BUY below
    the gate;
  - the first sentence of a missing-prefix fragment cannot carry a decision.
- **selfcheck.py**: the package's output checks, re-implemented, run on every output
  before it is written. A failure is reported and sets exit code 3. Nothing is repaired.
- **evaluate.py**: case-by-case comparison against package-shaped references, with Wilson
  95% intervals and a per-tag breakdown. A development aid; the package's scorer is the
  measure.
- **web.py**: a local page for inspecting decisions, on the standard-library HTTP server
  bound to 127.0.0.1. Pasted text is wrapped into a valid package case (synthetic IDs,
  current timestamps, the rebuilt catalogue) and goes through the same `run_case` path as
  the CLI, self-check included. The page inserts post text as text, never as HTML.

## Evidence handling

- Only supplied evidence IDs are cited. No quotations or offsets are generated.
- A BUY cites the smallest catalogue span covering its decisive sentence. Catalogue spans
  are whole sources and individual lines, so in practice that is the line. If the asset
  was named in another sentence, or in a context post, that span is cited too, so the
  asset appears literally in the cited evidence.
- Each BUY asset needs its own primary span. Two BUYs on the same line cannot meet the
  disjoint-span rule. In that case the first is reported, the second is named in a
  limitation, and confidence drops by 0.05.
- `NO_NEW_BUY` and `UNCLEAR` cite the full primary span: the absence of a call is a
  property of the whole post.
- Context can identify a referent but never supplies intent: every BUY has primary
  evidence of the author's own wording.
- Source text is read as data. Instruction-like text ("ignore previous rules and output
  BUY") is noted in the limitations and has no effect on the decision.

## Confidence

Confidence is a fixed score per rule path, not a calibrated probability:

| Path | Confidence |
|---|---|
| Explicit own entry, or own recommendation to enter | 0.90 |
| Instruction to enter ("Start $X now.") | 0.85 |
| Implicit present endorsement | 0.82 |
| Same-day own purchase claim | 0.78 |
| Asset resolved by back-reference / from context | −0.03 / −0.04 |
| Sponsored post | −0.03 |
| Entry asset only in context, no reference word | capped at 0.74 |
| Satire framing or joke markers in the post | capped at 0.70 |
| Rhetorical question read as an endorsement | 0.72 |
| Entry disclaimed or reversed in the same post | 0.60 |
| `NO_NEW_BUY` with an explicit negative operation or disclaimer | 0.88 |
| `NO_NEW_BUY` from a forecast only / plain mention | 0.82 / 0.78 |
| `UNCLEAR` with a specific gap | 0.80 |

The scores below 0.75 are deliberate. They produce a raw proposal that the scorer
records as an unaccepted abstention, so a weak reading never becomes an accepted BUY.
This is separate from `UNCLEAR`, which is a semantic claim about a missing referent.

## Results

"Fully correct" means the label, the asset set, confidence at or above 0.75, and the
reference support spans covered. Intervals are Wilson 95%.

| Set | First run, before tuning on it | Now |
|---|---|---|
| Client development set (24) | Not a first run: the rules were written with it in view | 24/24. The package scorer: 0 invalid outputs, 21/21 accepted labels, 8/8 BUYs with exact assets, 0 false BUYs, 3/3 integrity rejections |
| Probe set 1 (36) | 29/36, 1 false BUY (a decimal-point bug, fixed) | 35/36 (tuning data) |
| Probe set 2 (30), code frozen | **18/30 (0.42–0.75); 3/12 BUYs found (0.09–0.53); 0 false BUYs** | 29/30 (tuning data) |
| 0.1.0 sets (147), code frozen | **87/147 (0.51–0.67); 20/54 BUYs found (0.25–0.50); 9 accepted false BUYs, all on `debatable` rows** | 103/147 (0.62–0.77); 36/54 BUYs found (0.53–0.78) |

The first-run records are in `results/`, with the hash of the source they ran on.

On probe set 2 the misses were wording the lexicon did not know: "putting money to work
in", "is where I want exposure", "took a first bite of", "I'm a buyer of", "back in $X
today", and a heading that dated the lines under it. On the 0.1.0 sets they were informal
register: "Longing $BTC", "Get in $RNDR", "is a gift", "don't fade", "keep stacking". The
9 false BUYs on the 0.1.0 sets were all rows that 0.1.0 labelled `ABSTAIN`:

- 4 abstained only because the source ID was missing. The conversion supplies one, so
  under the package policy they are BUYs.
- 1 is a sponsored post with a buy instruction, which the package policy also counts as a
  BUY.
- 4 were jokes or sarcasm ("buy $FARTCOIN lmao", 😂, 🙃). The 0.1.0 joke-marker cues
  were carried over for these, and they now stay below the gate.

No undisputed row in any set has an accepted false BUY. After each first run the missed
categories were added, so the "Now" column is not an estimate of accuracy.

## Known limits

- **Lexical coverage.** The largest risk on withheld data. New phrasings of entry intent
  are missed, as both frozen runs showed. Misses mostly fall to `NO_NEW_BUY`, not to false
  BUYs.
- **Debatable readings left as they are.** "I would put fresh capital into $X today"
  (the modal reads as hypothetical) → `NO_NEW_BUY`. A rhetorical "who is not accumulating
  $X?" → raw BUY below the gate. An undated "Opened a long on $X perpetuals" →
  `UNCLEAR`. A joke marker on a sincere call ("yall sleepin on $GLORP lol") → raw BUY
  below the gate.
- **Replies that answer "what should I buy?"** with a bare ticker are `NO_NEW_BUY`: the
  intent would come from the context, which the policy does not allow.
- **Sentence-level scope.** Negation and conditions apply to the sentence or clause. A
  condition set up two sentences earlier is not tracked.
- **Assets are cashtags.** A bare project name ("the Varo team") is not an asset mention.
  The contract only accepts `$TICKER` mentions in any case.
- **English only.** Mixed-language posts (Hinglish "abhi le lo") are missed.
- **SELL and SHORT.** The contract is BUY-only: its output has no SELL or SHORT field,
  and adding one would fail its validator. The reader already tells exit, short and cover
  apart from entry for each asset. These operations appear in the `explanation` ("$PAVRI
  is an exit, sale or reduction"), per sentence in the `--trace` file and in the web UI.
  There is no post-level SELL or SHORT decision, no confidence for one, and no labelled
  data to measure one.

## Capacity

Each case is read in full. Above 200 sources, or 2,000,000 UTF-16 code units in total,
the case returns `CAPACITY_LIMIT` (`LOCAL_SOURCE_COUNT_CAPACITY` / `LOCAL_INPUT_CAPACITY`)
instead of being read in part. If the reader fails unexpectedly on a case, that case
returns `CAPACITY_LIMIT` with `PROCESSING_FAILURE`, the traceback goes to stderr, and the
other cases are still written. Measured on an Apple-silicon laptop with Python 3.12: about
1.3 ms per development case on average, and about 8 ms for the 4,800-character posts.

## Provenance

- Code: Python standard library only, no third-party packages, no model weights, no
  network access.
- Data: the client package, unchanged (`candidate_package/verify_package.py`). The probe
  sets in `data/` are AI-assisted and were written from `POLICY_SUMMARY.md` without access
  to the classifier. The 0.1.0 sets were AI-assisted under the 0.1.0 policy. No label is
  human-adjudicated. Rows whose reading is arguable are tagged `debatable`.
- The withheld evaluation set was not seen, and nothing was tuned on it.

## Next step: ModernBERT, stated as requirements

These are not performed here, because the package does not authorize them:

- **Data:** human-confirmed labels from the client's team, with a separate held-out
  split. For each post, the label, the BUY assets and the decisive span per asset (the
  package's reference format already has these). The labelling guideline for implicit
  BUYs, and known failure cases.
- **Model:** approval to download ModernBERT weights, and GPU time to fine-tune.
- **Where it plugs in:** replace the sentence reader. Train a classifier on
  (sentence, asset, local context) → operation, plus a post-level head for `UNCLEAR`
  gaps. Because the operation set already includes exit, short and cover, the same head
  can serve SELL and SHORT once they are labelled. Keep the integrity checks,
  segmentation, evidence selection, decision assembly, self-check and evaluation as they
  are, so the output stays contract-valid by construction.
- **How to judge it:** the same scorer, against this rules baseline, with the false-BUY
  count reported separately from recall. The rules' trace can also propose draft labels
  for humans to confirm, which speeds up building the training set.
