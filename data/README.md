# Datasets

Every set here uses the assessment package's shapes, so the package's scorer can read it
directly. The package's own development set stays in `candidate_package/`. All sets are
synthetic, and none of the labels is human-adjudicated. They test the contract and the
policy boundaries; they do not estimate accuracy on real KOL posts.

| Set | Rows | BUY / NO_NEW_BUY / UNCLEAR | Written by | Role |
|---|---|---|---|---|
| `candidate_package/development.*` | 24 (21 + 3 integrity) | 8 / 9 / 4 | The client | Disclosed development set; the reader was written with it in view |
| `probes.*` | 36 | 15 / 17 / 4 | A separate AI-assisted session, from `POLICY_SUMMARY.md` alone, without the code | First check; tuning data after its first run |
| `holdout.*` | 30 | 12 / 13 / 5 | The same method, wording varied on purpose | Run once with the code frozen; tuning data after that |
| `legacy.*` | 147 | 54 / 67 / 26 | The 0.1.0 sets (`dev`, `eval`, `eval_v2`), converted | Run once with the code frozen; labels follow the 0.1.0 policy |

Each set has three files:

- `NAME.source.jsonl`: the authoring form (text, label, BUY assets, decisive wording, tags).
  It is edited by hand or by `scripts/import_legacy.py`.
- `NAME.inputs.jsonl`: package input cases, built by `scripts/build_probes.py NAME`.
- `NAME.references.jsonl`: package reference rows, built by the same script.

## Input case (`*.inputs.jsonl`)

| Field | Content |
|---|---|
| `case_id` | `dev-` plus 10 hex characters |
| `synthetic` | `true` |
| `available_at_utc` | Capture cutoff; nothing after it may be used |
| `primary` | The post being judged (source fields below) |
| `context` | Earlier posts: reply parent, quoted post, same-author posts |
| `unavailable_context` | Media or parents that are referenced but not captured |
| `asset_identity_evidence` | Empty: no external asset identity is claimed |
| `evidence_catalogue` | The only citable spans: each whole source and each non-empty line |

A source has `source_id`, `author_id`, `published_at_utc`, `text`, `text_sha256` and
`capture_scope`. A catalogue span has `evidence_id` (`ev_` plus 24 hex characters),
`source_id`, `start_utf16` and `end_utf16`, half-open and counted in UTF-16 code units.

## Reference row (`*.references.jsonl`)

`case_id`, `input_sha256`, `expected_status`, `label`, `buy_assets`, `required_support`
(spans the cited evidence must cover), `buy_support` (the same, per BUY asset),
`expected_errors`, `boundary_tags` (including `debatable` where a reading is arguable),
`reference_reason`, `reference_origin` and `probe_name`.

## How the 0.1.0 sets were converted

`scripts/import_legacy.py` maps each `{post, gold}` row:

- `post.text` becomes `primary.text`. A reply parent or quoted post becomes a context
  source, with the same author only when the handles match.
- `ABSTAIN` becomes `UNCLEAR`, tagged `debatable`: under the package policy some of those
  rows are `NO_NEW_BUY` or `BUY`.
- Reposts (3) are skipped: the package has no repost shape. BUY rows whose asset is never
  written as a `$TICKER` (4) are skipped: the contract accepts only literal cashtags.
- A missing author gets a synthetic ID (tagged `author_added`), since the package treats a
  missing author as an integrity error, not a semantic case.
- The 0.1.0 sets have no decisive spans, so a BUY reference requires only that the cited
  evidence contain the asset's cashtag.

The original files are in the history at commit `a72e641`. To rebuild:

```sh
mkdir -p /tmp/eacr-v1 && git archive a72e641 data | tar -x -C /tmp/eacr-v1
python3 scripts/import_legacy.py /tmp/eacr-v1/data
python3 scripts/build_probes.py legacy
```

This reproduces `data/legacy.*` byte for byte.
