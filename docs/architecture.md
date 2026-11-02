# Architecture and technical decisions

## Pipeline

```
            Post (validated input)
               │
     ┌─────────┴──────────┐
     │  backend: proposes  │   untrusted
     │  rules │ llm │ hybrid│
     └─────────┬──────────┘
               │ Proposal (label, calls, confidence, reasons)
               ▼
        evidence guard          trusted: checks every claim against the input
               │
               ▼
     Decision (output contract, versioned, costed)
```

| Module | Role |
|---|---|
| `contract.py` | Input/output schema, policy version, content hash |
| `assets.py` | Finds tickers, known names and contract addresses exactly as written |
| `rules.py` | Offline recogniser: sentence-level buy/sell/negation/retro/hedge cues, quote and reply handling, risk flags (promo, sarcasm, warnings) that force `ABSTAIN`, and weak-spot detection that caps confidence so the hybrid escalates |
| `llm.py` | Claude Agent SDK call: tools disabled, user settings not loaded, JSON-schema output, per-post and per-run budget, cache, every failure → `ABSTAIN` |
| `pipeline.py` | `rules`, `llm`, `hybrid` (rules decide when confident ≥ 0.8 and no weak spot is flagged; otherwise escalate to the LLM) |
| `guard.py` | Evidence integrity, confidence floor, manual-input marker, limitations |
| `evaluate.py` | Metrics, Wilson confidence intervals, independent re-check of attribution |
| `api.py` | HTTP API (FastAPI) and the web UI mount; same pipeline, cache and budgets as the CLI |
| `cli.py` | `eacr classify`, `eacr eval`, `eacr serve` |
| `web/static/` | Pre-built React + Tailwind UI (source in `frontend/`) |
| `prompts/classify_v1.md` | LLM instructions; its hash is the prompt version |

## Input / output contract

Pydantic models in `src/evidence_aware_crypto_call_recognition/contract.py`. Unknown input fields are rejected.

**Input**: one `Post` per line.

```json
{"source_id": "x:1789", "platform": "x", "url": null, "posted_at": "2026-10-02T07:15:00Z",
 "author": {"handle": "@kol", "platform_user_id": "1002", "display_name": "Kai"},
 "text": "Buying $SOL here. 140 is the line in the sand.",
 "context": {"kind": "original", "parent_text": null, "parent_author_handle": null,
             "quoted_text": null, "quoted_author_handle": null}}
```

`context.kind` is `original | reply | quote | repost`. Parent and quoted text
are used as evidence when the call depends on them.

**Output**: one `Decision` per line.

```json
{
  "source": {"source_id": "x:1789", "platform": "x", "url": null, "posted_at": "2026-10-02T07:15:00Z",
             "is_manual_input": false},
  "author": {"status": "ATTRIBUTED", "handle": "@kol", "platform_user_id": "1002"},
  "label": "BUY",
  "calls": [{
    "action": "BUY",
    "asset": {"status": "SYMBOL", "symbol": "SOL", "address": null, "as_written": "$SOL", "verified": false},
    "supporting_text": "Buying $SOL here.",
    "evidence_origin": "post",
    "explicitness": "explicit",
    "conditional": false,
    "condition_text": null
  }],
  "confidence": 0.85,
  "reasons": ["BUY_CUE_WITH_ASSET"],
  "limitations": ["Asset identified from the text only. It is not matched to a contract address, ..."],
  "guard_corrections": [],
  "input_hash": "b969…",
  "versions": {"policy": "2026-11-02.1", "code": "0.1.0", "backend": "rules", "model": null, "prompt": null},
  "cost": {"usd": 0.0, "input_tokens": 0, "output_tokens": 0, "latency_ms": 0.05, "llm_calls": 0, "cache_hits": 0}
}
```

## Evidence guarantees

Enforced in `guard.py` and tested in `tests/test_guard.py`:
- `source.source_id` and `author` are **copied from input metadata only**; the
  model never sees or returns them. A missing source id gives `ABSTAIN`. A
  missing author gives `author.status = UNRESOLVED`, with a limitation saying
  the call must not be attributed.
- `supporting_text` must appear **verbatim** in the post, parent or quoted text,
  and must **mention its asset**: in the quoted sentence or the one before it, or,
  for a reply or quote, in the post being answered when only that post names it.
  Otherwise the call is dropped.
- An asset must be **written in the text**; an invented ticker or address is
  dropped. `asset.verified` is typed `Literal[False]`, so the prototype cannot
  claim a verified token identity even by mistake.
- Text pasted into the API without a source id gets the marker `manual:<hash>`,
  `source.is_manual_input: true` and a limitation that it must not be used for
  scoring. Posts submitted as JSON without a source id abstain.
- The guard can only remove calls, downgrade to `ABSTAIN` or mark fields
  unresolved. It never adds or upgrades anything. Each change is listed in
  `guard_corrections`.

## Technical decisions

**Cheap deterministic rules in front, an LLM for the hard cases, and a
deterministic guard behind both.**

- **Why rules first.** Most KOL posts contain no asset and no buy wording ("gm",
  memes, macro takes). Rules settle those for free, in microseconds, with an
  explanation. They also handle post *structure* (reposts, missing ids)
  deterministically, and give a fully offline baseline.
- **Why an LLM at all.** Implicit calls, slang, typos, mixed languages, sarcasm
  and reply context are where rules fail. On held-out data the rules alone keep
  precision but lose recall.
- **Why a guard after the model.** An LLM can paraphrase evidence, normalise
  "Solana" to a contract, or invent a ticker. Prompts reduce this; only code can
  guarantee it. The guard makes invented evidence impossible to output, and
  counts how often the model tried.
- **Why `ABSTAIN` is easy to reach.** A false BUY damages a real person's score;
  an abstention costs one review. Promotions, possible sarcasm, unresolved
  assets, unclear quote stance, low confidence and every backend failure all
  route to `ABSTAIN`.
- **Why Haiku is the default model.** On the held-out set it matched Opus on
  false BUYs and attribution errors (zero for both) at about 1/20 of the cost.
  See `docs/findings.md`.

## Alternatives considered and rejected

| Alternative | Why not |
|---|---|
| Rules / keywords only | Cannot read implicit or non-English calls; recall falls sharply on unseen phrasing |
| LLM only, trusting its output | No guarantee against invented evidence or assets, and less deterministic on post structure |
| Fine-tuned classifier (e.g. a small transformer) | No real labelled data; ~150 synthetic rows would overfit. The right step once a few thousand labelled posts exist |
| Zero-shot NLI / sentiment models | Bullish sentiment ≠ recommendation; cannot tell forecast, holding or past call from a new call, and gives no evidence spans |
| Claude Messages API instead of the Agent SDK | Lighter and better for volume. The Agent SDK was chosen for this project; the backend is isolated in `llm.py`, so switching is a one-module change (`docs/production.md` §4) |
