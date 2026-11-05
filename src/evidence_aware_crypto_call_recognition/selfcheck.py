"""Check our own output against the published output contract before it is written.

Mirrors `assessment.output_errors` in the client package. A failure here is a bug in
this implementation; the CLI reports it and exits non-zero instead of repairing it.
"""
from __future__ import annotations

from evidence_aware_crypto_call_recognition.contract import ASSET_MENTION_EXACT, LABELS, utf16_slice
from evidence_aware_crypto_call_recognition.integrity import input_errors

OK_FIELDS = {"case_id", "status", "label", "confidence", "current_buys", "evidence_ids", "explanation",
             "limitations", "execution_verified"}
REJECTION_FIELDS = {"case_id", "status", "error_codes", "explanation"}


def _cited_text(case: dict, span: dict) -> str:
    source = next(s for s in [case["primary"], *case["context"]] if s["source_id"] == span["source_id"])
    return utf16_slice(source["text"], span["start_utf16"], span["end_utf16"])


def output_errors(case: dict, prediction: dict) -> list[str]:
    errors: list[str] = []
    if prediction.get("case_id") != case.get("case_id"):
        errors.append("CASE_BINDING")
    status = prediction.get("status")
    if status in ("INPUT_INVALID", "CAPACITY_LIMIT"):
        if set(prediction) != REJECTION_FIELDS:
            errors.append("NON_OK_FIELDS")
        codes = prediction.get("error_codes")
        if not isinstance(codes, list) or not codes or any(not isinstance(c, str) or not c for c in codes):
            errors.append("ERROR_CODES")
        if not isinstance(prediction.get("explanation"), str) or not prediction["explanation"].strip():
            errors.append("EXPLANATION")
        return sorted(set(errors))
    if status != "OK":
        return ["OUTPUT_STATUS"]
    if input_errors(case):
        return sorted(set(errors + ["INPUT_INVALID_MUST_NOT_CLASSIFY"]))
    if set(prediction) != OK_FIELDS:
        errors.append("OK_FIELDS")
    if prediction.get("label") not in LABELS:
        errors.append("LABEL")
    confidence = prediction.get("confidence")
    if type(confidence) not in (float, int) or not 0 <= confidence <= 1:
        errors.append("CONFIDENCE")
    if prediction.get("execution_verified") is not False:
        errors.append("EXECUTION_NOT_VERIFIED")
    explanation = prediction.get("explanation")
    if not isinstance(explanation, str) or not explanation.strip() or len(explanation) > 3000:
        errors.append("EXPLANATION")
    limits = prediction.get("limitations")
    if not isinstance(limits, list) or len(limits) > 12 or any(not isinstance(x, str) or not x.strip() for x in limits):
        errors.append("LIMITATIONS")
    elif prediction.get("label") == "UNCLEAR" and not limits:
        errors.append("UNCLEAR_REQUIRES_LIMITATION")
    catalogue = {span["evidence_id"]: span for span in case["evidence_catalogue"]}
    evidence = prediction.get("evidence_ids")
    if not isinstance(evidence, list) or not evidence or len(evidence) > 32 or any(not isinstance(x, str) for x in evidence):
        errors.append("EVIDENCE_IDS")
        evidence = []
    if len(evidence) != len(set(evidence)):
        errors.append("DUPLICATE_EVIDENCE")
    if set(evidence) - catalogue.keys():
        errors.append("UNKNOWN_EVIDENCE_ID")
    primary_id = case["primary"]["source_id"]
    if not any(catalogue[x]["source_id"] == primary_id for x in evidence if x in catalogue):
        errors.append("PRIMARY_EVIDENCE_REQUIRED")
    buys = prediction.get("current_buys")
    if not isinstance(buys, list) or len(buys) > 16:
        errors.append("CURRENT_BUYS")
        buys = []
    if (prediction.get("label") == "BUY") != bool(buys):
        errors.append("LABEL_ASSET_CONTRADICTION")
    seen: set[str] = set()
    primary_spans_per_asset: list[list[dict]] = []
    for buy in buys:
        if not isinstance(buy, dict) or set(buy) != {"asset_mention", "evidence_ids"}:
            errors.append("BUY_FIELDS")
            continue
        asset, ids = buy["asset_mention"], buy["evidence_ids"]
        if not isinstance(asset, str) or not ASSET_MENTION_EXACT.fullmatch(asset) or asset in seen:
            errors.append("DUPLICATE_OR_INVALID_ASSET")
        if not isinstance(asset, str):
            continue
        seen.add(asset)
        if not isinstance(ids, list) or not ids or any(not isinstance(x, str) for x in ids):
            errors.append("BUY_EVIDENCE")
            continue
        if len(ids) != len(set(ids)):
            errors.append("DUPLICATE_BUY_EVIDENCE")
        if set(ids) - set(evidence):
            errors.append("BUY_EVIDENCE_NOT_DECLARED")
        selected = [catalogue[x] for x in ids if x in catalogue]
        primary_spans = [span for span in selected if span["source_id"] == primary_id]
        if not primary_spans:
            errors.append("BUY_PRIMARY_INTENT_REQUIRED")
        if not any(asset in _cited_text(case, span) for span in selected):
            errors.append("ASSET_NOT_IN_CITED_SOURCE")
        primary_spans_per_asset.append(primary_spans)
    for i, left in enumerate(primary_spans_per_asset):
        for right in primary_spans_per_asset[i + 1:]:
            if any(max(a["start_utf16"], b["start_utf16"]) < min(a["end_utf16"], b["end_utf16"]) for a in left for b in right):
                errors.append("MULTI_ASSET_SHARED_PRIMARY_SPAN")
    return sorted(set(errors))
