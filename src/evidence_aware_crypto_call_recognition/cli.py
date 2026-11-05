"""Command line: read input JSONL, write one output JSON object per Case ID."""
from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path

from evidence_aware_crypto_call_recognition import __version__
from evidence_aware_crypto_call_recognition.decide import decide
from evidence_aware_crypto_call_recognition.integrity import capacity_errors, input_errors
from evidence_aware_crypto_call_recognition.selfcheck import output_errors


class InputFileError(ValueError):
    pass


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict:
    result: dict = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate field {key!r}")
        result[key] = value
    return result


def _reject_constant(name: str) -> float:
    raise ValueError(f"non-finite number {name}")


def read_cases(path: Path) -> list[dict]:
    cases: list[dict] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line, object_pairs_hook=_reject_duplicate_keys, parse_constant=_reject_constant)
        except ValueError as error:
            raise InputFileError(f"{path}: line {number}: invalid JSON ({error})") from error
        if not isinstance(value, dict) or not isinstance(value.get("case_id"), str):
            raise InputFileError(f"{path}: line {number}: a JSON object with a string case_id is required")
        cases.append(value)
    ids = [case["case_id"] for case in cases]
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    if duplicates:
        raise InputFileError(f"{path}: duplicate case IDs cannot be bound to results: {', '.join(duplicates)}")
    return cases


def process_case(case: dict) -> tuple[dict, dict | None]:
    case_id = case["case_id"]
    errors = input_errors(case)
    if errors:
        return ({"case_id": case_id, "status": "INPUT_INVALID", "error_codes": errors,
                 "explanation": "Technical rejection before reading: " + ", ".join(errors)
                 + ". No semantic label is attached to an invalid source."}, None)
    capacity = capacity_errors(case)
    if capacity:
        return ({"case_id": case_id, "status": "CAPACITY_LIMIT", "error_codes": capacity,
                 "explanation": "The case exceeds the local processing limits, so it was not read in part."}, None)
    decision = decide(case)
    output = {
        "case_id": case_id,
        "status": "OK",
        "label": decision.label,
        "confidence": decision.confidence,
        "current_buys": decision.current_buys,
        "evidence_ids": decision.evidence_ids,
        "explanation": decision.explanation,
        "limitations": decision.limitations,
        "execution_verified": False,
    }
    return output, decision.trace


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="eacr", description=__doc__)
    parser.add_argument("--inputs", required=True, type=Path, help="input JSONL, one case per line")
    parser.add_argument("--output", required=True, type=Path, help="predictions JSONL to write")
    parser.add_argument("--trace", type=Path, help="optional JSONL with the sentence-level reading of each case")
    parser.add_argument("--version", action="version", version=f"eacr {__version__}")
    args = parser.parse_args(argv)

    try:
        cases = read_cases(args.inputs)
    except (InputFileError, OSError, UnicodeDecodeError) as error:
        print(f"eacr: {error}", file=sys.stderr)
        return 2

    outputs, traces, self_check_failures = [], [], 0
    for case in cases:
        try:
            output, trace = process_case(case)
        except Exception as error:  # one broken case must not lose every other result
            traceback.print_exc(file=sys.stderr)
            output, trace = ({"case_id": case["case_id"], "status": "CAPACITY_LIMIT", "error_codes": ["PROCESSING_FAILURE"],
                              "explanation": f"The local reader failed on this case ({type(error).__name__}); "
                                             "no label is fabricated."}, None)
        problems = output_errors(case, output)
        if problems:
            self_check_failures += 1
            print(f"eacr: self-check failed for {case['case_id']}: {', '.join(problems)}", file=sys.stderr)
        outputs.append(output)
        traces.append({"case_id": case["case_id"], "reading": trace})

    args.output.write_text("".join(json.dumps(o, ensure_ascii=False) + "\n" for o in outputs), encoding="utf-8")
    if args.trace:
        args.trace.write_text("".join(json.dumps(t, ensure_ascii=False) + "\n" for t in traces), encoding="utf-8")
    counts: dict[str, int] = {}
    for output in outputs:
        key = output.get("label") or output["status"]
        counts[key] = counts.get(key, 0) + 1
    summary = ", ".join(f"{k} {v}" for k, v in sorted(counts.items()))
    print(f"eacr: wrote {len(outputs)} results to {args.output} ({summary})", file=sys.stderr)
    return 3 if self_check_failures else 0


if __name__ == "__main__":
    sys.exit(main())
