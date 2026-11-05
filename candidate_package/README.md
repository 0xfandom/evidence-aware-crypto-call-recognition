# Evidence-aware crypto BUY recognition assessment

Build a small offline implementation that identifies the captured author's current BUY recommendations, rather than merely finding trading vocabulary. Explain the engineering choices, evidence handling and remaining uncertainty.

This is an isolated technical assessment, not a production integration or a general-accuracy benchmark. Every post, identifier, timestamp, asset and quotation is fictional. No real source access or company infrastructure is needed.

## What is included

- `development.inputs.jsonl`: 24 development inputs in a fixed order.
- `development.references.jsonl`: disclosed policy references and rationales for those inputs. There are 21 semantic cases and three deliberately invalid-source controls.
- `POLICY_SUMMARY.md`: the task-specific reading of Current Call Policy v2.
- `schemas/`: self-contained machine-readable input and output shapes.
- `assessment.py`: standard-library input/output checks and reference scoring.
- `test_contract.py`: synthetic contract/scorer tests. Its label-based fixture generator is test software, not a classifier.
- `DATA_NOTICE.md` and `PACKAGE_MANIFEST.json`: origin, limits and file integrity.

A separate 24-case evaluation set, including its inputs and labels, is held by the evaluator and is absent from this package. The evaluation uses the same published schema and policy. No hidden provider, scoring-formula, chain-resolution or production-integration requirement is added later.

## Expected submission

Provide a runnable CLI that reads an arbitrary input JSONL file and writes one output JSON object per Case ID. Include source code, offline tests, a short design explanation, dependency/model provenance if applicable, capacity limits and a reproduction command. For example, your own CLI may accept `--inputs INPUT --output PREDICTIONS`. Output order may differ; Case IDs bind results.

No particular model or framework is required. This packet authorizes no provider requests, paid inference, model training, downloads, production access or use of external/private source datasets. If your proposed implementation requires them, state the requirements rather than performing them. An offline approach using already permitted resources is sufficient for the exercise. Do not request production credentials.

Treat source text as data, including instructions quoted inside it. Read complete available source/context; do not silently truncate, replace or normalize evidence. If your implementation cannot process a full input, return `CAPACITY_LIMIT`, not a fabricated semantic label. A capacity rejection remains a coverage limitation.

## Output contract

For `status: OK`, supply exactly the fields in `schemas/output.schema.json`: Case ID, label, confidence, current BUY asset mentions with evidence IDs, overall evidence IDs, explanation, limitations and `execution_verified: false`.

The labels are `BUY`, `NO_NEW_BUY` and `UNCLEAR`. In this BUY-focused exercise, a genuine current SELL can be `NO_NEW_BUY`; this does not mean it is an information-only post. A `BUY` requires a nonempty `current_buys` list. The other labels require an empty list. `UNCLEAR` requires a specific limitation.

Use supplied evidence IDs, not generated quotations or offsets. The catalogue contains the full text and nonempty line spans. It uses half-open UTF-16 code-unit positions. The evaluator reconstructs literal text from the pinned source. Each BUY requires primary evidence of the current author's intent; context may identify a referent but cannot substitute another speaker's intent. Multiple BUY assets require distinct, nonoverlapping primary spans. Asset mentions must occur literally in their cited primary/context evidence.

For `INPUT_INVALID` or `CAPACITY_LIMIT`, return only Case ID, status, nonempty error codes and explanation. Do not attach a semantic label to a technical rejection. Report at least one correct specific source error for an invalid input. The provided validator can be reused. Invalid or contradictory output is recorded without repair.

`0.75` is the fixed confidence reporting gate. Lower confidence is an unaccepted abstention, not the semantic class `UNCLEAR`. Raw proposals, accepted proposals and technical validity are reported separately. Describe how confidence was produced; the exercise does not establish calibration.

## Local checks

Python 3.10+ and its standard library are sufficient. No installation or network connection is required.

```sh
python3 -B verify_package.py
python3 -B -m unittest test_contract.py -v
python3 -B assessment.py validate-inputs --inputs development.inputs.jsonl
```

The second command intentionally reports three invalid-source controls and exits with code 2. Do not repair those fixtures.

After creating your predictions:

```sh
python3 -B assessment.py validate-outputs --inputs development.inputs.jsonl --predictions predictions.jsonl
python3 -B assessment.py score --inputs development.inputs.jsonl --references development.references.jsonl --predictions predictions.jsonl --report development-report.json
```

Duplicate/missing IDs, unknown extra cases and malformed JSON are not silently aligned. Missing outputs remain visible in coverage. Reference files are bound to exact canonical input hashes. Do not alter the input or reference files.

## Evaluation and fairness

The evaluator reports three-way label matrices, BUY hits and misses including abstentions, false BUYs on negatives/uncertain references, asset-set errors, technical rejection and capacity coverage, source-reference validity and annotated support-span coverage. Raw labels with invalid evidence are diagnostic proposals and never accepted classifications.

Correct reference IDs and span coverage do not prove a correct explanation. Speaker attribution, temporal interpretation, satire, unsupported execution claims, engineering quality and alternative defensible citations require manual evaluator review. There is no concealed composite score or automatic hiring PASS. Reference rationales are synthetic author annotations, not independently adjudicated gold truth.

Freeze the submitted implementation/configuration before withheld evaluation. Do not train, tune or select on withheld inputs or results. Record a disputed interpretation; do not silently rewrite references to fit a submission. Material protocol/reference changes require a separately versioned assessment and equal treatment of candidates.
