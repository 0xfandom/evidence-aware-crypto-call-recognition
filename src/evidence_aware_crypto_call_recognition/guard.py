"""Evidence guard: turns an untrusted Proposal into a Decision that obeys the evidence rules.

The guard can only remove, downgrade or mark things unresolved. It never adds a
call, never upgrades a label and never fills a missing field.
"""

from __future__ import annotations

import re

from evidence_aware_crypto_call_recognition import __version__
from evidence_aware_crypto_call_recognition.assets import asset_is_written_in, find_asset_mentions
from evidence_aware_crypto_call_recognition.contract import (
    Asset,
    AssetStatus,
    AuthorStatus,
    Call,
    Decision,
    EvidenceOrigin,
    MANUAL_SOURCE_PREFIX,
    Label,
    Post,
    PostKind,
    ResolvedAuthor,
    SourceRef,
    Versions,
)
from evidence_aware_crypto_call_recognition.proposal import Proposal, ProposedCall

MIN_BUY_CONFIDENCE = 0.6
_TICKER_LIKE = re.compile(r"^\$?[A-Za-z][A-Za-z0-9]{1,11}$")
_SENTENCE_END = re.compile(r"(?<=[.!?\n])\s+")

LIMITATION_UNVERIFIED_ASSET = (
    "Asset identified from the text only. It is not matched to a contract address, chain or listing, "
    "and the same ticker can refer to different tokens."
)
LIMITATION_UNVERIFIED_ADDRESS = (
    "A contract address is copied from the text. It was not checked on-chain and may be a fake or a scam token."
)


def _origin_text(post: Post, origin: EvidenceOrigin) -> str | None:
    if origin == EvidenceOrigin.POST:
        return post.text
    if origin == EvidenceOrigin.PARENT:
        return post.context.parent_text
    return post.context.quoted_text


def _resolve_author(post: Post) -> ResolvedAuthor:
    author = post.author
    if author and (author.handle or author.platform_user_id):
        return ResolvedAuthor(status=AuthorStatus.ATTRIBUTED, handle=author.handle,
                              platform_user_id=author.platform_user_id)
    return ResolvedAuthor(status=AuthorStatus.UNRESOLVED)


def _resolve_asset(asset_as_written: str | None) -> tuple[Asset, str | None]:
    """Classifies an asset already known to be written in the source. Returns it and any correction made."""
    if not asset_as_written or not asset_as_written.strip():
        return Asset(status=AssetStatus.UNRESOLVED), None
    written = asset_as_written.strip()
    mentions = find_asset_mentions(written)
    if mentions:
        return mentions[0].to_asset().model_copy(update={"as_written": written}), None
    if _TICKER_LIKE.match(written):
        return Asset(status=AssetStatus.SYMBOL, symbol=written.lstrip("$").upper(), as_written=written), None
    return (Asset(status=AssetStatus.UNRESOLVED, as_written=written),
            f"'{written}' is not a recognisable ticker or address; marked unresolved")


def _evidence_window(origin_text: str, supporting: str) -> str:
    """The sentence(s) containing the supporting text, plus the sentence before them."""
    start = origin_text.find(supporting)
    end = start + len(supporting)
    boundaries = [m.end() for m in _SENTENCE_END.finditer(origin_text)]
    before = [b for b in boundaries if b <= start]
    window_start = before[-2] if len(before) >= 2 else 0
    window_end = next((b for b in boundaries if b >= end), len(origin_text))
    return origin_text[window_start:window_end]


def _names_asset(written: str, text: str) -> bool:
    """Matches the asset as written, or its symbol without '$' as a whole word ("jup" for "$JUP")."""
    if asset_is_written_in(written, text):
        return True
    core = written.lstrip("$")
    return bool(core) and re.search(rf"(?<![\w$]){re.escape(core)}(?!\w)", text, re.IGNORECASE) is not None


def _only_names_assets(supporting: str, written: str) -> bool:
    """True when nothing but asset names is left once they are removed ("$SOL", "$SOL 🚀", "$SOL $JUP")."""
    rest = supporting
    for mention in sorted(find_asset_mentions(supporting), key=lambda m: m.start, reverse=True):
        rest = rest[:mention.start] + " " + rest[mention.end:]
    if written:
        rest = re.sub(rf"(?<!\w){re.escape(written)}(?!\w)", " ", rest, flags=re.IGNORECASE)
    return re.search(r"[^\W\d_]", rest) is None


def _evidence_mentions_asset(written: str, supporting: str, origin_text: str, origin: EvidenceOrigin,
                             post: Post) -> bool:
    """The evidence must be about the asset, not merely any verbatim sentence from the post."""
    if _names_asset(written, _evidence_window(origin_text, supporting)):
        return True
    # A reply or quote may endorse an asset that only the parent or quoted post names.
    context = post.context
    return (origin == EvidenceOrigin.POST and context.kind in (PostKind.REPLY, PostKind.QUOTE)
            and not asset_is_written_in(written, post.text)
            and asset_is_written_in(written, context.parent_text, context.quoted_text))


def _check_call(call: ProposedCall, post: Post) -> tuple[Call | None, list[str], str | None]:
    """Returns the checked call (or None), corrections, and the reason code if the call was dropped."""
    corrections: list[str] = []
    supporting = call.supporting_text.strip()
    origin = call.evidence_origin
    origin_text = _origin_text(post, origin)

    if not supporting or not origin_text or supporting not in origin_text:
        found_in = next(
            (o for o in EvidenceOrigin if (t := _origin_text(post, o)) and supporting and supporting in t), None
        )
        if found_in is None:
            return (None, [f"dropped call: supporting text not found verbatim in the source: {supporting[:80]!r}"],
                    "EVIDENCE_NOT_VERIFIABLE")
        corrections.append(f"evidence origin corrected from {origin.value} to {found_in.value}")
        origin = found_in
        origin_text = _origin_text(post, origin)

    written = (call.asset_as_written or "").strip()
    if written and not asset_is_written_in(written, post.text, post.context.parent_text, post.context.quoted_text):
        return None, [f"dropped call: asset '{written}' does not appear in the post or its context"], "ASSET_NOT_IN_SOURCE"
    if written and not _evidence_mentions_asset(written, supporting, origin_text, origin, post):
        return (None, [f"dropped call: supporting text {supporting[:80]!r} does not mention asset '{written}'"],
                "EVIDENCE_NOT_ABOUT_ASSET")
    # A bare ticker is not evidence of a buy, except in a reply or quote, where the post being
    # answered carries the action ("what should I buy?" → "$SOL").
    answers_context = origin == EvidenceOrigin.POST and post.context.kind in (PostKind.REPLY, PostKind.QUOTE)
    if _only_names_assets(supporting, written) and not answers_context:
        return (None, [f"dropped call: supporting text {supporting[:80]!r} only names the asset"],
                "EVIDENCE_ONLY_NAMES_ASSET")

    asset, asset_correction = _resolve_asset(call.asset_as_written)
    if asset_correction:
        corrections.append(asset_correction)

    condition_text = (call.condition_text or "").strip() or None
    sources = (post.text, post.context.parent_text, post.context.quoted_text)
    if condition_text and not any(t and condition_text in t for t in sources):
        corrections.append(f"condition text not found verbatim in the source, replaced by the supporting text: "
                           f"{condition_text[:80]!r}")
        condition_text = None
    if call.conditional and not condition_text:
        condition_text = supporting

    return Call(
        asset=asset,
        supporting_text=supporting,
        evidence_origin=origin,
        explicitness=call.explicitness,
        conditional=call.conditional,
        condition_text=condition_text,
    ), corrections, None


def apply_guard(post: Post, proposal: Proposal) -> Decision:
    reasons = list(proposal.reasons)
    limitations = list(proposal.limitations)
    corrections: list[str] = []
    label = proposal.label
    confidence = proposal.confidence
    calls: list[Call] = []
    author = _resolve_author(post)

    if label == Label.BUY:
        drop_reasons: list[str] = []
        for proposed in proposal.calls:
            checked, call_corrections, drop_reason = _check_call(proposed, post)
            corrections.extend(call_corrections)
            if checked:
                calls.append(checked)
            elif drop_reason:
                drop_reasons.append(drop_reason)

        if not calls:
            label, reasons = Label.ABSTAIN, reasons + (drop_reasons or ["EVIDENCE_NOT_VERIFIABLE"])
        elif confidence < MIN_BUY_CONFIDENCE:
            label, reasons, calls = Label.ABSTAIN, reasons + ["LOW_CONFIDENCE"], []
            limitations.append(f"Backend proposed BUY with confidence {confidence:.2f}, below the {MIN_BUY_CONFIDENCE} floor.")
    elif proposal.calls:
        corrections.append(f"dropped {len(proposal.calls)} call(s) attached to a {label.value} decision")

    if not post.source_id or not post.source_id.strip():
        if label == Label.BUY:
            corrections.append("BUY withdrawn: the input has no source identifier")
        label, calls = Label.ABSTAIN, []
        reasons.append("MISSING_SOURCE_ID")
        limitations.append("The input has no source identifier, so no decision can be traced back to a post.")

    is_manual = bool(post.source_id and post.source_id.startswith(MANUAL_SOURCE_PREFIX))
    if is_manual:
        reasons.append("MANUAL_INPUT")
        limitations.append(
            "Pasted by hand: no platform post stands behind this decision. The id is a local marker, "
            "not a real source, so the decision must not be used for scoring."
        )

    if label == Label.BUY:
        if any(c.asset.status == AssetStatus.UNRESOLVED for c in calls):
            confidence = min(confidence, 0.6)
            limitations.append("At least one call has no identifiable asset.")
        if any(c.asset.status == AssetStatus.SYMBOL for c in calls):
            limitations.append(LIMITATION_UNVERIFIED_ASSET)
        if any(c.asset.status == AssetStatus.ADDRESS for c in calls):
            limitations.append(LIMITATION_UNVERIFIED_ADDRESS)
        if any(c.conditional for c in calls):
            limitations.append("The call is conditional on a trigger; it may never become active.")
        if any(c.evidence_origin != EvidenceOrigin.POST for c in calls):
            limitations.append("Part of the evidence comes from the parent or quoted post, not the author's own text.")
        if author.status == AuthorStatus.UNRESOLVED:
            limitations.append("Author is unresolved; this call must not be attributed to any account.")

    return Decision(
        source=SourceRef(source_id=post.source_id, platform=post.platform, url=post.url, posted_at=post.posted_at,
                         is_manual_input=is_manual),
        author=author,
        label=label,
        calls=tuple(calls),
        confidence=round(confidence, 3),
        reasons=tuple(dict.fromkeys(reasons)),
        limitations=tuple(dict.fromkeys(limitations)),
        guard_corrections=tuple(corrections),
        input_hash=post.content_hash(),
        versions=Versions(code=__version__, backend=proposal.backend, model=proposal.model,
                          prompt=proposal.prompt_version),
        cost=proposal.cost,
    )
