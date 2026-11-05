"""Technical input checks: identity, hashes, chronology and the evidence catalogue.

The rules mirror `assessment.input_errors` in the client package so that a case we
reject is one the evaluator also rejects. `tests/test_package_parity.py` keeps the two
in step.
"""
from __future__ import annotations

import re
from datetime import datetime

from evidence_aware_crypto_call_recognition.contract import CONTRACT_VERSION, fingerprint, text_sha256, utf16_length

CASE_FIELDS = {"case_id", "synthetic", "available_at_utc", "primary", "context",
               "unavailable_context", "asset_identity_evidence", "evidence_catalogue"}
SOURCE_FIELDS = {"source_id", "author_id", "published_at_utc", "text", "text_sha256", "capture_scope"}
UNAVAILABLE_KINDS = ("IMAGE", "VIDEO", "REPLY_PARENT", "LINKED_PAGE", "MISSING_PREFIX")

# Generous local limits. Above them we return CAPACITY_LIMIT instead of reading part of a source.
MAX_SOURCES = 200
MAX_UTF16_PER_CASE = 2_000_000


def parse_utc(value: object) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("UTC timestamp required")
    return datetime.fromisoformat(value[:-1] + "+00:00")


def source_spans(source: dict, case_id: str, role: str) -> list[dict]:
    text = source["text"]
    bounds = {(0, len(text))}
    cursor = 0
    for line in text.splitlines(keepends=True):
        if line.strip():
            bounds.add((cursor, cursor + len(line)))
        cursor += len(line)
    spans = []
    for start, end in sorted(bounds):
        if end <= start:
            continue
        start16, end16 = utf16_length(text[:start]), utf16_length(text[:end])
        key = [CONTRACT_VERSION, case_id, role, source["source_id"], source["author_id"],
               source["published_at_utc"], source["capture_scope"], text_sha256(text), start16, end16]
        spans.append({"evidence_id": "ev_" + fingerprint(key)[:24], "source_id": source["source_id"],
                      "start_utf16": start16, "end_utf16": end16})
    return spans


def expected_catalogue(case: dict) -> list[dict]:
    sources = [case["primary"], *case["context"]]
    return [span for index, source in enumerate(sources)
            for span in source_spans(source, case["case_id"], "PRIMARY" if index == 0 else "RETAINED_CONTEXT")]


def input_errors(case: dict) -> list[str]:
    errors: list[str] = []
    try:
        if set(case) != CASE_FIELDS:
            errors.append("INPUT_FIELDS")
        if case.get("synthetic") is not True:
            errors.append("NOT_SYNTHETIC")
        if not re.fullmatch(r"(dev|eval)-[0-9a-f]{10}", case["case_id"]):
            errors.append("CASE_ID")
        cutoff = parse_utc(case["available_at_utc"])
        sources = [case["primary"], *case["context"]]
        ids = [source["source_id"] for source in sources]
        if len(ids) != len(set(ids)):
            errors.append("DUPLICATE_SOURCE_ID")
        primary_time = None
        for index, source in enumerate(sources):
            if set(source) != SOURCE_FIELDS:
                errors.append("SOURCE_FIELDS")
            if not isinstance(source["source_id"], str) or not source["source_id"].startswith("sim_post_"):
                errors.append("SOURCE_ID")
            if not isinstance(source["author_id"], str) or not re.fullmatch(r"sim_author_[0-9a-f]{12}", source["author_id"]):
                errors.append("MISSING_AUTHOR_ID")
            if not isinstance(source["text"], str) or not source["text"]:
                errors.append("EMPTY_SOURCE_TEXT")
            if source["text_sha256"] != text_sha256(source["text"]):
                errors.append("TEXT_HASH_MISMATCH")
            if source["capture_scope"] not in ("FULL_TEXT", "FRAGMENT"):
                errors.append("CAPTURE_SCOPE")
            try:
                published = parse_utc(source["published_at_utc"])
                if index == 0:
                    primary_time = published
                elif primary_time and published > primary_time:
                    errors.append("FUTURE_CONTEXT")
                if published > cutoff:
                    errors.append("AFTER_INPUT_CUTOFF")
            except (ValueError, TypeError):
                errors.append("MISSING_OR_INVALID_TIMESTAMP")
        if not isinstance(case["asset_identity_evidence"], list) or case["asset_identity_evidence"]:
            errors.append("UNEXPECTED_EXTERNAL_ASSET_EVIDENCE")
        if any(set(item) != {"kind", "reference"} or item["kind"] not in UNAVAILABLE_KINDS
               or not isinstance(item["reference"], str) for item in case["unavailable_context"]):
            errors.append("UNAVAILABLE_CONTEXT_FIELDS")
        if case["evidence_catalogue"] != expected_catalogue(case):
            errors.append("EVIDENCE_CATALOGUE_MISMATCH")
    except (KeyError, TypeError, ValueError, AttributeError, UnicodeError):
        errors.append("MALFORMED_INPUT")
    return sorted(set(errors))


def capacity_errors(case: dict) -> list[str]:
    sources = [case["primary"], *case["context"]]
    if len(sources) > MAX_SOURCES:
        return ["LOCAL_SOURCE_COUNT_CAPACITY"]
    if sum(utf16_length(source["text"]) for source in sources) > MAX_UTF16_PER_CASE:
        return ["LOCAL_INPUT_CAPACITY"]
    return []
