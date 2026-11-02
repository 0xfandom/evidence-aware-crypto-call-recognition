# Findings, limitations and next steps

## Summary

- **No false BUY and no attribution error from the LLM-backed pipeline** on any
  held-out post, with either Opus 5.5 or Haiku 5.5.
- **The evidence guard was never needed for evidence.** Across 154 Opus and 154
  Haiku decisions, no model paraphrased a quote, invented an asset or quoted a
  sentence that does not mention its asset. The guard's only interventions were
  withdrawing BUYs from posts with no source id, which is the policy working as
  designed.
- **Rules alone do not generalise.** They found 92% of BUYs on the data they
  were written against, but only 57–67% on held-out data. They miss slang,
  typos and non-English calls.
- **A hybrid is only as safe as its escalation rule.** A rule decision that is
  confident and wrong never reaches the model. Escalating posts with known weak
  spots (asset named only in a quoted post, warning posts, several assets)
  removed the 2 false BUYs the first hybrid made on the held-out set. A later
  review still found rules BUYs that were confident and wrong on shapes the
  datasets do not contain ("whales are buying", past trades, "just kidding").
  So the hybrid now never accepts a rules BUY: the rules may only rule a post
  out, and Claude confirms every BUY.
- **On this data the hybrid saves little.** It sends 45 of 48 held-out posts to
  Claude ($0.026 vs $0.027 for every post). The saving depends on how much
  real traffic is everyday chatter with no asset and no buy wording.
- **Haiku costs about 1/20 of Opus** ($0.0006 vs $0.012 per post) with no loss
  in safety on this data, so it is the default.
- **None of this is an accuracy estimate.** All data is small and synthetic.

## Headline results

Held-out `data/eval_v2.jsonl`: 48 synthetic posts (18 BUY / 20 NO_NEW_BUY /
10 ABSTAIN), written by a separate assistant session before the escalation rule
was frozen.

| Backend | Model | BUY correct | Missed | False BUY | Precision [95% CI] | Recall [95% CI] | Attribution errors | LLM calls | Cost |
|---|---|---|---|---|---|---|---|---|---|
| rules | — | 12 | 6 | 0 | 1.00 [0.76, 1.00] | 0.67 [0.44, 0.84] | 1 | 0 | $0 |
| **hybrid (default)** | **Haiku** | **17** | **1** | **0** | **1.00 [0.82, 1.00]** | **0.94 [0.74, 0.99]** | **0** | 45 | **$0.026** |
| llm | Haiku | 17 | 1 | 0 | 1.00 [0.82, 1.00] | 0.94 [0.74, 0.99] | 0 | 48 | $0.027 |

- **Hybrid rule changed after the held-out runs.** Every rules BUY now goes to
  Claude. The change came from new probe posts, not from `eval_v2` errors, and
  the Haiku results above did not change; only the number of LLM calls rose
  (39 → 45). They were re-run from cached answers, at no cost.
- **Opus is not in this table** because it was measured on an earlier prompt
  and the earlier hybrid rule. Its results are in "Model tier" below.
- **Haiku's one miss** is a real BUY written with "lol", which went to ABSTAIN as
  a possible joke. That is the safe direction.
- **The remaining non-BUY errors** are on gold-ABSTAIN posts such as a bare
  ticker with emoji. Whether such posts deserve review is a policy question.
- **Speed:** about 5–6.5 s per LLM post, most of it Agent SDK start-up. The rules
  take under 1 ms.
- **Reproduce:** `uv run eacr eval data/eval_v2.jsonl --backend hybrid`, and
  `uv run python scripts/compare_models.py` for the full model table on all three
  datasets. Real costs come from `results/measured_llm_costs.json`, recorded on
  uncached runs, because reports that replay cached answers show $0.

## Model tier: Opus 5.5 vs Haiku 5.5

Same code, guard and settings; only the model changes. Haiku was measured on the
current prompt (`classify_v1@0ed51e26f8cb`). Opus was measured on the previous
prompt (`classify_v1@62c84cdedae0`), which differed only in three clarifications:
the quote must name its asset, `condition_text` is copied from the post, and the
`kind` field is explained. Opus was not re-run, to avoid about $2 of repeat cost.
Its hybrid reports in `results/` also use the earlier hybrid rule, which let
confident rules BUYs skip Claude; its llm reports are not affected by that.

| Set | Model | BUY correct / gold | False BUY | 3-way accuracy | Cost / LLM post | Latency / LLM post |
|---|---|---|---|---|---|---|
| eval_v2 (held-out) | Opus | 18 / 18 | 0 | 0.96 | $0.0118 | 5.1 s |
| eval_v2 (held-out) | Haiku | 17 / 18 | 0 | 0.94 | $0.0006 | 5.1 s |
| eval (development) | Opus | 14 / 14 | 0 | 0.98 | $0.0137 | 6.5 s |
| eval (development) | Haiku | 14 / 14 | 0 | 0.95 | $0.0006 | 5.3 s |
| dev | Opus | 26 / 26 | 0 | 1.00 | $0.0116 | 5.5 s |
| dev | Haiku | 26 / 26 | 0 | 0.98 | $0.0005 | 5.2 s |

- **Haiku's extra errors all fall on the safe side.** None moved toward BUY.
- **The two models can't be told apart on quality.** On the held-out set Haiku
  makes 1–2 more errors in 48, and the confidence intervals overlap almost
  completely. The data does show that Haiku is far cheaper.
- **Latency barely depends on the model,** because most of it is Agent SDK
  start-up. Moving to the Messages API would matter more.

## What we learned

1. **Define before building.** Writing the policy first made every hard case a
   testable rule and exposed four product questions the business must answer
   (paid promos, conditional calls, leveraged longs, unattributed BUYs).
2. **Separate what the model proposes from what the system accepts.** The
   guard turns "the model should not invent evidence" into "the system cannot
   output invented or irrelevant evidence", and records every correction.
3. **Never let the cheap stage give the risky answer.** A confident wrong rule
   decision never reaches the model. Escalating on the post's shape helped, but
   a review still found confident wrong rules BUYs. The lasting fix is
   structural: the rules may only rule a post out; only Claude, checked by the
   guard, may say BUY.
4. **Measure honestly.** Each held-out set was written independently and
   frozen. Code was frozen before each first held-out run, and a problem found
   on one eval set was only measured on a newer one; the older set then became
   development data.

## Limitations

**Evaluation**
- **Small and synthetic.** 154 posts in total, all written by AI assistants to
  one policy. Real posts are messier: images, threads, deleted context, bots,
  many languages.
- **Wide intervals.** With 18 gold BUYs, perfect recall still has a 95% lower
  bound of 0.82, and Haiku and Opus cannot be told apart on quality.
- **Not truly independent.** The same model family wrote the eval sets and is
  measured on them. The `eval_v2` challenge themes were chosen because of known
  failure types.
- **Single annotator.** One annotator per set, no agreement measured. Several
  ABSTAIN golds are debatable.
- **No gold evidence spans.** Attribution checks cover source, author, asset and
  evidence that is verbatim and mentions its asset, but not whether the best
  sentence was chosen.
- **Uncalibrated confidence.** Confidence scores are not validated as
  probabilities.

**System**
- **No images, video or links.** A call made in a chart screenshot is invisible.
- **No asset registry.** Tickers are never resolved to contracts (reported as
  unverified), and the rules know about 30 bare tickers.
- **One level of context.** Threads are not stitched; only one parent or quoted
  post is used.
- **Thin action detail.** Entry, target, stop and timeframe are not extracted.
- **Rule weak spots** (covered by the LLM, documented by tests):
  - typos and non-English calls;
  - any "if" marks a call as conditional;
  - an undisclosed shill reads as a buy.
- **Prompt injection.** The guard stops invented evidence, but post text can
  still push the model toward a label. This was not tested adversarially.
- **Agent SDK overhead.** One CLI subprocess per call is too heavy for
  production volume (`docs/production.md` §4).
- **No SELL support.** SELL calls are out of scope; sell wording is only used to
  avoid false BUYs.

## Recommended next steps

1. **Real data first:** an independently labelled sample of real posts, two
   annotators, agreement measured, gold evidence spans, and a frozen test split.
2. **Resolve the open policy questions** with product before tuning further.
3. **Measure the escalation share on real traffic** and tune the weak-spot list
   against it.
4. **Test the Haiku → Opus cascade:** Opus re-checks only Haiku's abstentions.
   Then move the LLM call to the Messages API with batching.
5. **Add an asset registry** with chain and time context, keeping
   `verified=false` until a symbol is actually resolved, and extract entry,
   target and stop when written.
6. **Run in shadow mode** with the monitoring in `docs/production.md`.
