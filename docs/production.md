# From prototype to production pipeline

This is how I would turn the prototype into a service that feeds the credibility
score. The principle throughout: a call that changes someone's public score must
be reproducible, attributable to a specific model and policy version, and
reversible.

## 1. Integration into the backend and scoring architecture

```
 ingestion ──▶ posts table ──▶ classification queue ──▶ classifier workers ──▶ decisions table ──▶ scoring
 (platform     (immutable,     (only new or changed      (rules → LLM →        (append-only,       (reads only
  collectors)   content_hash)   content_hash × versions)   evidence guard)       versioned)          ACTIVE versions)
```

- The classifier is a **pure function** `Post → Decision` with no access to the
  scoring database. It is deployed as a worker consuming a queue, not inside the
  request path of the scoring API.
- Decisions are written to an **append-only** table keyed by
  `(source_id, input_hash, policy_version, prompt_version, model, code_version)`.
  Nothing is updated in place, so any score can be recomputed from history.
- Scoring reads decisions through a view that selects the **active** version set.
  Switching versions is a config change, not a data migration.
- `ABSTAIN` decisions go to a review queue. Human labels flow back into the
  labelled data store (see §7), never directly into scores.
- The JSON contract in `evidence_aware_crypto_call_recognition.contract` becomes a versioned schema
  (JSON Schema / protobuf) shared with the scoring service.

## 2. Reuse of previously classified, unchanged posts

- `Post.content_hash()` covers everything that can change a decision: text,
  context, author metadata, kind. If the hash and the active version set are
  unchanged, the stored decision is reused; no model call is made.
- The prototype already does this for LLM calls (`.cache/llm`, keyed by content
  hash, model, prompt version and policy version). In production this moves to
  the decisions table itself.
- Edited posts get a new hash and are re-classified; the old decision is kept for
  audit. Deleted posts keep their decision but are excluded from scoring
  (platform terms usually require this).
- Version bumps do **not** trigger a full re-run automatically. A re-run is a
  planned backfill job with a budget (§4) and a validation gate (§7).

## 3. Model and policy versioning

Four independent versions, all stored on every decision (already in `Decision.versions`):

| Version | Changes when | Example |
|---|---|---|
| policy | the definition of BUY changes | `2026-11-02.1` |
| prompt | the LLM instructions change | `classify_v1@<sha256 prefix>` |
| model | the provider model id changes | `claude-haiku-5-5` |
| code | rules, guard or contract change | package version / git SHA |

- Model ids are pinned, never "latest".
- A policy change requires re-labelling the affected gold data before any
  classifier change is evaluated against it.

## 4. API cost and request-budget protection

Already in the prototype:
- the hybrid backend only calls the LLM when rules are unsure (posts with no asset
  and no action never cost anything);
- a per-post cap (`max_budget_usd` on the Agent SDK call);
- a per-run cap (`RunBudget`): once spent, remaining posts `ABSTAIN` with
  `BUDGET_EXHAUSTED` instead of failing silently or overspending;
- caching of unchanged posts.

For production, add:
- daily and monthly org-level spend limits at the provider, plus our own counter
  with alerts at 50 / 80 / 100%;
- rate limiting per worker and a circuit breaker on provider errors;
- the Batch API for backfills (lower price, no latency requirement);
- a model-tier decision made from measured data. The prototype measured Opus 5.5
  against Haiku 5.5 (`docs/findings.md`, "Model tier"). Haiku cost about 1/20 as
  much per post, with no false BUY and no attribution error. Confirm that on real
  data before switching, and keep Opus as a second opinion for Haiku's
  abstentions if that recovers recall.
- Note on the SDK choice: the prototype uses the Claude Agent SDK.
  For a high-volume worker I would move the call to the plain Messages API
  (`anthropic` SDK): no CLI subprocess per post, lower latency, exact token
  accounting and batch support. The backend interface already isolates this.

## 5. Monitoring, rollback and deployment safeguards

Monitor per version set, daily:
- label distribution (share of BUY, ABSTAIN) and its drift;
- guard correction rate (how often the model produced non-verbatim or irrelevant
  evidence, or invented assets). A rise is an early warning of prompt or model regression;
- LLM error / timeout / budget-exhausted rates;
- cost per 1,000 posts and p95 latency;
- review-queue size and human agreement rate on reviewed items.

Deploy safely:
- **shadow mode first**: a new version set writes decisions but scoring ignores
  them; compare against the active set on the same posts;
- then a canary share of new posts;
- automatic halt if BUY rate or guard-correction rate moves outside agreed bounds;
- rollback = point the active-version view back. Because decisions are
  append-only, rollback needs no data repair.

## 6. Data provenance and privacy

- Store the source URL, platform post id, fetch time and collector version with
  every post. A decision without a traceable source is never scored (the guard
  already abstains on a missing `source_id`).
- Respect platform terms: store only what is needed, honour deletions.
- The model receives only the post text and context, never the author handle or
  ID (see `llm._user_prompt`). Authors are attached by our code from metadata.
- Use a provider configuration with appropriate data-retention terms and check
  that the platform's terms allow sending post content to a third-party model,
  before any production data is sent.
- Treat post content as untrusted input: it can contain prompt-injection text.
  The guard limits the damage (no invented evidence), but a post *can* still
  push the model toward a label; monitoring and review catch that.

## 7. Independent validation before scoring changes

- Maintain three data sets: a **dev set** (free to look at), a **frozen test
  set** (only scored at release time), and a **rolling audit sample** of fresh
  production posts labelled by two annotators with adjudication.
- Report BUY precision and recall with confidence intervals, plus attribution
  errors, on the frozen test set for every candidate version.
- Release gate: BUY precision must not drop (inside its CI), attribution errors
  must be zero, and the changes to individual scores must be reviewed for a
  sample of affected KOLs before activation.
- Whoever changes the classifier does not label the test set.

## 8. Most important technical risks and priorities

1. **False BUYs harm real people.** Highest priority is precision on BUY and
   correct attribution, not overall accuracy. Abstain and review instead.
2. **Small, synthetic evaluation data.** All current numbers come from 154
   synthetic posts written by AI assistants. They do not represent production text. Getting a real,
   independently labelled sample is the most valuable next step.
3. **Policy ambiguity.** Paid promotions, conditional calls, leveraged longs and
   unresolved authors need product decisions; the classifier cannot fix an
   unclear definition.
4. **Asset identity.** A ticker is not a token. Linking symbols to contracts
   needs a curated registry, chain context and time context. Until then every
   asset stays unverified.
5. **Model drift and prompt injection.** Pinned versions, monitoring of the
   guard-correction rate, and shadow deployments.
6. **Cost growth with volume.** Rules pre-filter, caching, batch and model-tier
   choice.

## First three steps if I joined the team

1. **Agree the policy and build a real labelled sample.** Workshop the open
   questions in `docs/labeling_policy.md` with product and research, then label
   ~500 real posts (two annotators, adjudicated, inter-annotator agreement
   reported). Freeze a test split. Without this, no accuracy claim means much.
2. **Run the classifier in shadow mode on live ingestion.** Append-only decisions
   table with versions, the evidence guard, caching and budgets as in the
   prototype, plus the monitoring in §5. No impact on scores yet.
3. **Close the loop with review.** Route ABSTAIN and a random sample of BUY
   decisions to reviewers, measure precision on real traffic, and only then gate
   the first scoring change on the frozen test set.
