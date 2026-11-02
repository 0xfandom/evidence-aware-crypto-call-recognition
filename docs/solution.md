# Solution: how the five challenges are handled

This document maps each challenge in the assessment brief to what was built,
where it lives in the code, and the evidence that it works. Details are in the
linked documents; numbers come from the committed reports in `results/`.

The guiding principle, from the brief's concern about "the risks of incorrect
automated financial assessments": **a wrong BUY damages a real person's
credibility score, while an abstention only costs a human review.** Every design
choice below leans towards abstaining rather than guessing.

## Summary

| Challenge | Approach | Evidence |
|---|---|---|
| 1. Semantic recognition | A written BUY policy; a cascade where offline rules may only rule a post out and Claude confirms every BUY | 17 of 18 held-out BUYs found by the hybrid, 0 false BUYs |
| 2. Evidence integrity | A deterministic guard after every classifier; typed contract that cannot claim a verified token | 0 attribution errors from the LLM pipeline; guard invariants under test |
| 3. Technical implementation | Python package with CLI, HTTP API and web UI; strict input/output contract; 112 passing tests | One-command install; offline by default |
| 4. Evaluation | Independent held-out sets, freeze before measuring, Wilson intervals, cost and latency | Reports in `results/`, reproducible with one command |
| 5. Technical leadership | Production plan covering all eight topics and the first three steps | [`production.md`](production.md) |

## Challenge 1: Semantic recognition

**Approach.** The definition came first: [`labeling_policy.md`](labeling_policy.md)
states five tests a post must pass to be a BUY (own voice, buy-side action,
current, actionable, genuine) and a ruling for every hard case. Code, prompt,
datasets and tests are all written against it.

Recognition is a two-stage cascade:

- **Rules** (`rules.py`): offline, under 1 ms. Sentence-level cues for buying,
  selling, negation, questions, past calls and hedging; each asset is linked to
  its nearest buy or sell cue, which separates multi-asset posts. Promotions,
  possible sarcasm and unresolved assets force `ABSTAIN`.
- **Claude** (`llm.py`): reads implicit wording, slang, typos and other
  languages, with the policy in its system prompt.
- **Hybrid** (`pipeline.py`): the rules decide alone only on a confident
  `NO_NEW_BUY`. Every rules BUY goes to Claude, because buy wording alone cannot
  tell the author's own call from "whales are buying", a past trade or a joke.
  Posts with known weak spots also always go to Claude: an asset named only in
  the parent or quoted post, a scam or exploit warning, and more than one asset.

**How each case in the brief is handled:**

| Case in the brief | Handling |
|---|---|
| Direct and implicit recommendations | Explicit and implicit cue lexicons; Claude for wording the rules do not know |
| Price forecasts vs recommendations | Test 4 of the policy: a forecast alone is `NO_NEW_BUY`; forecast plus action is `BUY` |
| Existing positions vs new buying | Holding cues give `NO_NEW_BUY`; a current buy disclosure ("adding here") is `BUY` |
| Promotional and referral statements | Disclosed paid promotion gives `ABSTAIN` (review); referral and giveaway pitches give `NO_NEW_BUY` |
| Sarcasm, jokes, ambiguity | Clear sarcasm gives `NO_NEW_BUY`; possible jokes give `ABSTAIN` |
| Multiple assets and conditional calls | One call per bought asset; conditional calls are `BUY` with `conditional` and the condition text |
| Long posts and source context | Evidence is the sentence that carries the call; parent and quoted posts are used as context and flagged as such |

**Alternatives rejected** (details in [`architecture.md`](architecture.md)):
rules alone (recall falls sharply on new wording), an LLM trusted without
checks (no guarantee against invented evidence), a fine-tuned model (no real
labelled data), and sentiment or NLI models (bullish is not a recommendation).

**Evidence.** On the held-out set the rules alone found 12 of 18 BUYs; the
hybrid with Haiku found 17, with no false BUY. The rules' misses
(slang, typos, non-English) are exactly the cases escalated to Claude.

## Challenge 2: Evidence integrity

**Approach.** Classifiers only *propose*. A deterministic guard (`guard.py`)
checks every proposal against the original input before anything is emitted,
and it can only drop a call or downgrade a label, never add or upgrade.

| Required by the brief | How it is guaranteed |
|---|---|
| Original source identifier | Copied from input metadata; missing source id forces `ABSTAIN` |
| Attributable author or unresolved state | Copied from metadata only, never inferred; otherwise `UNRESOLVED`, with a limitation that it must not be attributed |
| Relevant supporting text | Must be a verbatim span of the post or its context, mention its asset, and be more than the bare ticker; otherwise the call is dropped |
| Recommended action | `BUY`, explicit or implicit, conditional with a condition text that must be copied from the post |
| Asset or unresolved state | Must be written in the post as a whole word; status `SYMBOL`, `ADDRESS` or `UNRESOLVED` |
| Clear limitations | Written by code for every BUY: unverified asset, unchecked address, conditional, evidence from context, unresolved author. The model's own limitations are never passed through |

- **Never imply a verified token:** `asset.verified` is typed `Literal[False]`,
  so the system cannot emit a verified token identity even by mistake, and no
  model-written sentence (which could claim one) reaches the output.
- **Never invent source information:** Claude never sees the author or source
  id, so it cannot change them. Pasted text without a source id gets an explicit
  `manual:<hash>` marker and a "must not be used for scoring" limitation.
- **Every change is recorded** in `guard_corrections`, so the rate at which a
  model tries to break the rules can be monitored.

**Evidence.** `tests/test_guard.py` covers each rule: paraphrased quotes,
invented assets and addresses (including an asset hidden inside an ordinary
word), irrelevant quotes, bare-ticker quotes, invented condition text, missing
source ids and unresolved authors. Across 308 Claude decisions (Opus and Haiku), the guard
never had to reject model evidence; its only interventions were posts without a
source id.

## Challenge 3: Technical implementation

| Expectation in the brief | What exists |
|---|---|
| Reproducible setup and execution | `uv sync --extra llm` from a lockfile; Python 3.12; runs offline with no account. The web UI ships pre-built |
| Clearly defined input/output contract | Strict Pydantic models in `contract.py` (unknown fields rejected); documented in [`architecture.md`](architecture.md); the same contract over CLI, HTTP API and UI |
| Automated tests for important edge cases | 112 passing tests: policy cases, guard invariants, Claude wrapper (cache, budget, failures, escalation), API, CLI and metrics. Seven documented rule limitations (typos, non-English, and buy wording that is not the author's current call) are marked as expected failures |
| Understandable implementation | Small modules with one job each: assets, rules, LLM backend, guard, pipeline, evaluation, API |
| Explicit uncertainty handling | The `ABSTAIN` label, confidence with a floor for BUY, reason codes and limitations on every decision; every Claude error, timeout or exhausted budget becomes `ABSTAIN` |
| No hardcoded classifications | No per-example rules; lexicons were built from the development set only, and phrases seen in held-out errors were deliberately not added |

Cost and safety controls are part of the implementation, not an add-on: a cache
keyed by post, model, prompt and policy; a per-call cap and a per-run cap that
reserves the per-call cap for every call in progress, so parallel calls cannot
overspend; and a Claude configuration with all tools disabled and user settings
not loaded.

Run it: `uv run pytest`, `uv run eacr eval data/eval_v2.jsonl`,
`uv run eacr serve` (see the [README](../README.md)). The Claude results
reproduce offline with `--replay results/llm-cache`, which uses the recorded
answers and never calls the API.

## Challenge 4: Evaluation

**Data.** No dataset had been supplied, so three synthetic sets were built
([`data/README.md`](../data/README.md)): a development set, and two held-out sets
each written by a separate assistant session that saw only the policy and the
contract. Each held-out set was frozen with a SHA-256 hash, and the code was
frozen before its first run.

**What is measured** (`evaluate.py`), as the brief asks:

| Brief | Metric |
|---|---|
| Correctly recognised BUY | BUY true positives, precision with a 95% Wilson interval |
| Missed BUY | Split into missed as `NO_NEW_BUY` and missed as `ABSTAIN`; recall with interval |
| Incorrect BUY | False positives, split by gold label |
| Abstentions | Count, rate, and breakdown by gold label |
| Source/evidence attribution errors | Re-checked independently of the guard: source, author, verbatim evidence, verified claims, missed or extra assets |
| Execution cost and runtime | USD, tokens, Claude calls, cache hits, mean and p95 latency, wall time |

**Results on the held-out set** (48 posts, 18 BUYs):

| Classifier | BUY correct | False BUY | Attribution errors | Cost |
|---|---|---|---|---|
| rules | 12 | 0 | 1 | $0 |
| hybrid, Haiku 5.5 (default) | 17 | 0 | 0 | $0.026 |

**Development-set results are not presented as accuracy.** The rules found 92%
of BUYs on the data they were written against and 57–67% on held-out data; that
gap is reported as the main finding about rules.

**Limits of a small dataset**, stated in [`findings.md`](findings.md): with 18
gold BUYs a perfect recall still has a 95% lower bound of 0.82, one post moves
recall by about 6 points, the data is synthetic and written by the same model
family, and labels have a single annotator. The numbers show that failure types
were handled, not real-world accuracy.

## Challenge 5: Technical leadership

[`production.md`](production.md) addresses every topic in the brief:

| Topic | Plan |
|---|---|
| Integration into backend and scoring | Classifier as a queue worker; append-only, versioned decisions table; scoring reads only the active version set |
| Reuse of unchanged posts | Content hash of the post; already implemented for Claude calls as a cache |
| Model and policy versioning | Policy, prompt, model and code versions on every decision (already in the output) |
| API cost and request budgets | Rules pre-filter, cache and spend caps (already built), plus provider limits, alerts, rate limits and batch processing |
| Monitoring, rollback, safeguards | Label drift, guard-correction rate, error and cost metrics; shadow mode, canary, rollback by switching the active version |
| Data provenance and privacy | Source metadata on every post; the model sees only post text; provider retention terms checked first |
| Independent validation | Frozen test set, release gate on BUY precision and zero attribution errors, labelled by people who did not change the classifier |
| Risks and priorities | False BUYs first, then the lack of real labelled data, policy ambiguity, asset identity, drift and cost |

**First three steps** if joining the team: agree the policy and label about 500
real posts with two annotators; run the classifier in shadow mode on live
ingestion; then route abstentions and a sample of BUYs to review and gate the
first scoring change on a frozen test set.

## Deliverables and constraints

| Brief | Where |
|---|---|
| Runnable repository | This repository |
| Short README | [`README.md`](../README.md) |
| Test results and evaluation command | `results/test-report.txt`; `uv run eacr eval data/eval_v2.jsonl` |
| Findings, limitations, next steps | [`findings.md`](findings.md) |
| No production systems or company credentials | Fully standalone; all data is synthetic |
| External APIs | Claude is optional; the default path is offline. Claude runs used the author's own credentials and cost about $2.35 in total, covering every evaluation, test and demo run |
