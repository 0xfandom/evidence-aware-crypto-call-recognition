# Evidence-Aware Crypto Call Recognition

Tells whether a crypto social-media post contains a **genuine, current BUY
recommendation by its own author**, and backs every BUY with evidence checked
against the post.

Credibility scores for crypto influencers depend on knowing which posts were
real buy calls. Most posts only look like calls: price forecasts, old calls,
existing positions, jokes, paid promotions. This prototype separates them and
refuses to guess when the evidence is thin.

| Label | Meaning |
|---|---|
| `BUY` | A genuine, current buy call by the author, with checked evidence attached |
| `NO_NEW_BUY` | No new buy call (forecast, holding, past call, joke, referral, question, warning…) |
| `ABSTAIN` | Not enough evidence to decide safely, so it goes to a human instead |

A wrong BUY damages a real person's score; an abstention only costs a review.
The system is built around that asymmetry.

## Installation

Requirements: [uv](https://docs.astral.sh/uv/) (it installs Python 3.12 if
needed). The first install needs internet access; everything after that runs
offline.

```bash
uv sync --extra llm      # installs the package; the llm extra adds the Claude Agent SDK
```

Node.js is **not** needed: the web UI ships pre-built. Node is only needed to
change the UI (see [Web UI and API](#web-ui-and-api)).

## Usage

The package installs two equivalent commands: `eacr` and
`evidence-aware-crypto-call-recognition`.

```bash
uv run pytest                                # run the test suite
uv run eacr eval data/eval_v2.jsonl          # evaluate on the held-out set
uv run eacr classify posts.jsonl             # classify posts (a JSONL file, or - for stdin)
uv run eacr serve                            # web UI at http://127.0.0.1:8000, API docs at /docs
```

All of these use the offline **rules** classifier by default. Add
`--backend hybrid` or `--backend llm` to use Claude (see
[Using Claude](#using-claude-optional)).

### Example: classify one post

```bash
echo '{"source_id":"x:1","author":{"handle":"@kol"},"text":"Buying $SOL here, 140 is the level"}' \
  | uv run eacr classify -
```

Output (abridged; the full decision also carries limitations, versions and cost):

```json
{
  "label": "BUY",
  "confidence": 0.85,
  "source": {"source_id": "x:1"},
  "author": {"status": "ATTRIBUTED", "handle": "@kol"},
  "calls": [{
    "asset": {"status": "SYMBOL", "symbol": "SOL", "as_written": "$SOL", "verified": false},
    "supporting_text": "Buying $SOL here, 140 is the level",
    "explicitness": "explicit"
  }]
}
```

Each input line is a post (as above) or a dataset row
`{"post": {...}, "gold": {...}}`. The full input/output contract is in
[`docs/architecture.md`](docs/architecture.md).

### Example: evaluate

`uv run eacr eval data/eval_v2.jsonl` prints a report and writes it to `runs/`
(git-ignored) as Markdown, JSON and the full decisions. The first lines:

```
| BUY correctly recognised | 12 |
| BUY missed → NO_NEW_BUY | 2 |
| BUY missed → ABSTAIN | 4 |
| Incorrect BUY (false positives) | 0 (from NO_NEW_BUY 0, from ABSTAIN 0) |
| BUY precision (95% CI) | 1.0 (0.757, 1.0) |
| BUY recall (95% CI) | 0.667 (0.437, 0.837) |
```

The report also covers abstentions, attribution errors, cost and latency, a
confusion matrix and accuracy per case type.

## Web UI and API

```bash
uv run eacr serve            # add --port 8765 to change the port
```

- **One post:** paste a post or load an example, then see the label, the
  evidence highlighted in the post, source and author, the asset (never marked
  verified), who decided, and the latency.
- **Many posts:** paste or upload JSON/JSONL. With gold labels it also shows the
  evaluation metrics, and rows that disagree with the gold label are marked.
- **Demo links:** `/?example=sarcasm&backend=hybrid` opens an example and runs
  it. Examples: `explicit`, `implicit`, `forecast`, `past-call`, `sarcasm`,
  `scam-warning`, `reply`, `no-source`.

| Endpoint | Body | Returns |
|---|---|---|
| `GET /api/health` | — | Status and policy, prompt, model and code versions |
| `POST /api/classify` | `{"post": {...}, "backend": "rules"}` | One decision |
| `POST /api/classify/text` | `{"text": "...", "source_id": null, "author_handle": null, ...}` | One decision |
| `POST /api/classify/batch` | `{"items": [...], "backend": "rules"}` (up to 200) | Decisions, a summary, and metrics when gold labels are present |

- The server listens on localhost only, without authentication.
- Pasted text without a source id gets the marker `manual:<hash>` and a
  limitation saying it must not be used for scoring. JSON posts without a source
  id abstain.
- The React source is in `frontend/`. To change the UI, run
  `npm install && npm run build` there; it rebuilds into the Python package.

## Using Claude (optional)

`--backend llm` sends every post to Claude; `--backend hybrid` lets the rules
settle only clear non-calls and sends everything else, including every rules
BUY, to Claude. Both use the
[Claude Agent SDK](https://code.claude.com/docs/en/agent-sdk), which ships its
own CLI, so nothing else needs installing.

Copy the template and set **one** credential:

```bash
cp .env.example .env
```

| Option | How to get it | `.env` key |
|---|---|---|
| Claude subscription token | Install Claude Code, run `claude setup-token`, log in, copy the token | `CLAUDE_CODE_OAUTH_TOKEN` |
| Anthropic API key | [console.anthropic.com](https://console.anthropic.com) → Settings → API keys | `ANTHROPIC_API_KEY` |
| Existing Claude Code login | Nothing to set; the SDK uses it | — |

Optional settings (defaults shown in `.env.example`):

| Setting | Default | Effect |
|---|---|---|
| `EACR_MODEL` / `--model` | `claude-haiku-5-5` | Claude model |
| `EACR_MAX_BUDGET_USD_PER_POST` | `0.05` | Hard cost cap per call |
| `EACR_RUN_BUDGET_USD` / `--run-budget` | `2.00` | Cap per run; once spent, remaining posts abstain |

- **Cache:** answers are cached in `.cache/llm/` by post, model, prompt and
  policy, so an unchanged post is never paid for twice. Use `--no-cache` to
  disable it.
- **Live test:** `EACR_LIVE=1 uv run pytest -m live` makes one real call, for
  under $0.01.
- `.env` is git-ignored; never commit a credential.

## How it works

```
Post ──▶ classifier proposes (rules | llm | hybrid) ──▶ evidence guard checks ──▶ Decision
```

- **Rules:** offline and instant. In the hybrid they may only rule a post out
  (no buy call). A rules BUY is never final: Claude must confirm it, because
  buy wording alone cannot tell "I'm buying" from "whales are buying" or a
  past trade. Known weak spots (an asset named only in a quoted post, scam
  warnings, several assets) also always go to Claude.
- **Claude:** reads implicit, slang, typo and non-English calls. It never sees
  the author or source id, and any failure becomes `ABSTAIN`.
- **Evidence guard:** every proposed call must quote the post word for word,
  and the quote must mention its asset. The asset must be written in the post,
  source and author come from input metadata only, and `verified` is always
  `false`. The guard can only drop or downgrade, never add.

Design decisions and rejected alternatives are in
[`docs/architecture.md`](docs/architecture.md).

## Results

Held-out set `data/eval_v2.jsonl`: 48 synthetic posts, 18 of them real BUYs.

| Classifier | Model | BUY correct | False BUY | Attribution errors | Cost | Latency per post |
|---|---|---|---|---|---|---|
| rules | — | 12 / 18 | 0 | 1 | $0 | under 1 ms |
| **hybrid** | **Haiku 5.5 (default)** | **17 / 18** | **0** | **0** | **$0.026** | about 5 s when sent to Claude |

- No Claude run produced a false BUY or invented evidence.
- On this data the hybrid sends 45 of 48 posts to Claude, so it saves little
  over `--backend llm` ($0.027). The saving comes from everyday posts with no
  asset and no buy wording, which this BUY-heavy test set has few of.
- These are **not** accuracy claims: the data is small and synthetic, and the
  95% intervals are wide.
- Opus 5.5 was also measured, on an earlier prompt and hybrid rule; see
  [`docs/findings.md`](docs/findings.md), which also covers limitations and next steps.
- Committed reports are in `results/haiku/` (the default model) and `results/`
  (Opus, earlier prompt and hybrid rule). Reports that replayed cached answers
  show $0; `uv run python scripts/compare_models.py` recomputes their real cost.

## Project layout

```
src/evidence_aware_crypto_call_recognition/   the package: rules, Claude backend, guard, pipeline, API, CLI
frontend/                                      React + Tailwind source of the web UI
tests/                                         pytest suite (the live Claude test is skipped by default)
data/                                          synthetic development and held-out datasets
docs/                                          policy, architecture, findings, production plan
results/                                       committed evaluation reports and measured costs
scripts/                                       model comparison table
```

## Documentation

| Document | Contents |
|---|---|
| [`docs/solution.md`](docs/solution.md) | How each of the brief's five challenges is handled, with evidence |
| [`docs/labeling_policy.md`](docs/labeling_policy.md) | What counts as BUY: the rules everything else follows |
| [`docs/architecture.md`](docs/architecture.md) | Pipeline, input/output contract, evidence guarantees, decisions |
| [`docs/findings.md`](docs/findings.md) | Results, limitations, next steps |
| [`docs/production.md`](docs/production.md) | Path to a production pipeline |
| [`data/README.md`](data/README.md) | How the datasets were made |
