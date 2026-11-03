"""Deterministic, offline BUY-call recogniser.

Conservative by design: when a risk signal (promotion, sarcasm, unresolved asset,
unclear quote stance) meets a buy cue, it abstains instead of guessing. Its
confidence also drives escalation in the hybrid backend.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace

from evidence_aware_crypto_call_recognition.assets import AssetMention, find_asset_mentions
from evidence_aware_crypto_call_recognition.contract import EvidenceOrigin, Label, Post, PostKind
from evidence_aware_crypto_call_recognition.proposal import Proposal, ProposedCall

_I = re.IGNORECASE

EXPLICIT_BUY = re.compile(
    r"\b(buy|buying|load(?:ing)?\s+up|loading|accumulat\w*|get(?:ting)?\s+in|ap(?:e|ing)\s+(?:in(?:to)?\s+)?|"
    r"bid(?:ding)?|stack(?:ing)?|add(?:ing)?(?:\s+more)?|grab(?:bing)?)\b"
    r"|\blong(?:ing)?\s+(?=\$|[A-Z]{2,}\b)|\b\d+x\s+long\b"
    r"|\bentry\b(?=\s*(?:at|@|:)?\s*\$?\d)",
    _I,
)
IMPLICIT_BUY = re.compile(
    r"is\s+a\s+gift|\bngmi\b|\bdon'?t\s+fade\b|\bdo\s+not\s+fade\b|\bcheapest\s+it\b|\bbest\s+entry\b"
    r"|\b(?:be\s+a\s+buyer|i'?d\s+buy|would\s+buy)\b|\bi'?m\s+in\b|\bin\s+too\b",
    _I,
)
ROTATION_INTO = re.compile(r"\brotat\w*\b[^.!?]*?\binto\b", _I)
SELL = re.compile(
    r"\b(sell(?:ing)?|sold|dump(?:ing)?|took\s+profits?|taking\s+profits?|out\s+of|exit(?:ed|ing)?|short(?:ing)?|i'?m\s+out)\b",
    _I,
)
NEGATION_BEFORE_CUE = re.compile(r"\b(don'?t|do\s+not|never|not|no|avoid|stop)\b\W*(?:\w+\W+)?$", _I)
WARNING = re.compile(r"\b(scam|honeypot|rug(?:ged|pull)?|avoid)\b", _I)
POST_WARNING = re.compile(r"\b(scam\w*|honeypot|rug(?:ged|pull)?|exploit(?:ed)?|hack(?:ed)?|drainer)\b", _I)
RETROSPECTIVE = re.compile(
    r"\b(called|told\s+(?:you|y'?all|everyone)|best\s+call|bought|last\s+(?:week|month|year|cycle|november|bull))\b", _I
)
HOLDING = re.compile(r"\b(still\s+holding|holding|hodl\w*|my\s+bags?|portfolio|been\s+in|comfy)\b", _I)
FORECAST = re.compile(
    r"\bto\s+\$?\d|\b\d+(?:\.\d+)?k\b|\bby\s+(?:end\s+of|q[1-4]|20\d\d)|\binevitable\b|\bwill\s+(?:hit|reach|outperform)\b"
    r"|\bexpect\b|\bcould\s+see\b|\btarget\b",
    _I,
)
HEDGE = re.compile(r"\b(might|maybe|perhaps|thinking\s+about|considering|not\s+sure|one\s+day|someday|eventually)\b", _I)
CONDITIONAL = re.compile(r"\b(if|once|unless|be\s+a\s+buyer|would\s+buy|i'?d\s+buy)\b", _I)
GENERIC_ADVICE = re.compile(r"\b(buy\s+the\s+dips?|buy\s+dips|dca|buy\s+low|buy\s+and\s+hold)\b", _I)
PROMO = re.compile(r"#ad\b|\bsponsored\b|\bpaid\s+(?:promo|partnership)\b|\bpartner(?:ship|ed)\b|\bpresale\b|#partner", _I)
REFERRAL = re.compile(r"\bcode\b|\bsign\s*up\b|link\s+in\s+bio|\breferral\b|\bref\s+link\b|\bgiveaway\b|\bbonus\b", _I)
SARCASM_CLEAR = re.compile(r"what\s+could\s+(?:possibly\s+)?go\s+wrong|great\s+idea|said\s+no\s+one|/s\b", _I)
SARCASM_POSSIBLE = re.compile(r"🤡|🙃|😂|🤣|\blmf?ao\b|\blol\b|\bjk\b", _I)
ENDORSEMENT = re.compile(r"\b(agree|same|me\s+too|co-?sign|facts|this)\b|\+1|\bi'?m\s+in\b|\bin\s+too\b", _I)
REPLY_ASKS_FOR_PICK = re.compile(
    r"\b(what|which)\b.{0,40}\b(buy|pick|bag|long|accumulate|get\s+into)\b|\btop\s+pick\b|\bbest\s+(?:coin|alt|play)\b", _I
)
# General trading vocabulary. Only used to decide that a post without a known asset is not
# plain chatter; it never makes a call on its own.
MARKET_TALK = re.compile(
    r"\b(trad(?:e|es|ing)|position\w*|siz(?:e|es|ed|ing)|entr(?:y|ies)|bags?|ap(?:e|ed|ing)|pump\w*|moon\w*|"
    r"sends|sending|gift|cheap|undervalued|breakout|chart\w*|support|resistance|levels?|dips?|"
    r"accumulat\w*|load(?:ed|ing)?|bid\w*|long\w*|short\w*|cycle|alts?|altcoins?|coins?|tokens?|ticker|"
    r"presale|airdrop|ath|rally|bull\w*|bear\w*|mcap|market\s*cap|stack\w*|hodl\w*|dca|"
    r"buy\w*|sell\w*|sold|grab\w*|adding|bottom(?:ed)?)\b|\b\d+x\b|\b\d+(?:\.\d+)?k\b",
    _I,
)
# A full stop between digits ("0.30", "61.2k") is a decimal point, not a sentence end.
_SENTENCE = re.compile(r"(?:[^.!?\n]|(?<=\d)\.(?=\d))+[.!?]*", re.MULTILINE)

LONG_POST_CHARS = 600
# Rules are never more confident than this on a post with a known weak spot,
# which keeps such posts below the hybrid escalation threshold.
WEAK_SPOT_CONFIDENCE_CAP = 0.7


@dataclass
class _Scan:
    calls: list[ProposedCall] = field(default_factory=list)
    notes: set[str] = field(default_factory=set)
    unresolved_buy_cue: str | None = None
    mentions: list[AssetMention] = field(default_factory=list)


@dataclass(frozen=True)
class _Cue:
    position: int
    is_buy: bool
    explicitness: str


def _sentences(text: str) -> list[tuple[int, str]]:
    return [(m.start(), m.group(0)) for m in _SENTENCE.finditer(text) if m.group(0).strip()]


def _overlaps_mention(start: int, end: int, mentions: list[AssetMention]) -> bool:
    return any(start < m.end and end > m.start for m in mentions)


def _buy_cues(sentence: str, sentence_mentions: list[AssetMention], offset: int) -> list[_Cue]:
    cues: list[_Cue] = []
    for pattern, explicitness in ((EXPLICIT_BUY, "explicit"), (IMPLICIT_BUY, "implicit")):
        for m in pattern.finditer(sentence):
            if _overlaps_mention(offset + m.start(), offset + m.end(), sentence_mentions):
                continue
            if NEGATION_BEFORE_CUE.search(sentence[: m.start()][-25:]):
                continue
            if not sentence_mentions and GENERIC_ADVICE.search(sentence[m.start():]):
                continue
            cues.append(_Cue(m.start(), True, explicitness))
    # "Rotating out of X into Y": the buy side is whatever follows "into".
    for m in ROTATION_INTO.finditer(sentence):
        cues.append(_Cue(m.end(), True, "implicit"))
    return cues


def _sell_cues(sentence: str) -> list[_Cue]:
    return [_Cue(m.start(), False, "explicit") for m in SELL.finditer(sentence)]


def _nearest_cue(mention_pos: int, cues: list[_Cue]) -> _Cue | None:
    before = [c for c in cues if c.position <= mention_pos]
    if before:
        return max(before, key=lambda c: c.position)
    after = [c for c in cues if c.position > mention_pos]
    return min(after, key=lambda c: c.position) if after else None


def _scan(text: str, origin: EvidenceOrigin) -> _Scan:
    scan = _Scan(mentions=find_asset_mentions(text))
    distinct_keys = {m.key for m in scan.mentions}
    # One call per asset. A sentence that names the asset beats one that only borrowed it.
    calls_by_key: dict[str, tuple[ProposedCall, bool]] = {}

    for offset, raw_sentence in _sentences(text):
        sentence = raw_sentence.strip()
        offset += raw_sentence.index(sentence)
        in_sentence = [m for m in scan.mentions if offset <= m.start < offset + len(sentence)]
        buy = _buy_cues(sentence, in_sentence, offset)

        if not buy:
            for name, pattern in (("FORECAST", FORECAST), ("EXISTING_POSITION", HOLDING), ("RETROSPECTIVE", RETROSPECTIVE)):
                if pattern.search(sentence) and in_sentence:
                    scan.notes.add(name)
            if GENERIC_ADVICE.search(sentence):
                scan.notes.add("GENERIC_ADVICE")
            if WARNING.search(sentence) or re.search(r"\b(don'?t|do\s+not|not)\b", sentence, _I):
                scan.notes.add("NEGATED")
            continue
        if "?" in sentence:
            scan.notes.add("QUESTION")
            continue
        if RETROSPECTIVE.search(sentence):
            scan.notes.add("RETROSPECTIVE")
            continue
        if HEDGE.search(sentence):
            scan.notes.add("HEDGED")
            continue
        if WARNING.search(sentence):
            scan.notes.add("NEGATED")
            continue

        is_conditional = bool(CONDITIONAL.search(sentence))
        cues = buy + _sell_cues(sentence)
        targets: list[tuple[AssetMention, _Cue]] = []
        for mention in in_sentence:
            cue = _nearest_cue(mention.start - offset, cues)
            if cue and cue.is_buy:
                targets.append((mention, cue))
        if in_sentence and not targets:
            scan.notes.add("SELL_SIDE")
            continue
        if not in_sentence:
            if len(distinct_keys) == 1:
                targets.append((scan.mentions[0], buy[0]))
            else:
                scan.unresolved_buy_cue = sentence
                continue

        borrowed = not in_sentence
        for mention, cue in targets:
            existing = calls_by_key.get(mention.key)
            if existing and not (existing[1] and not borrowed):
                continue
            calls_by_key[mention.key] = (
                ProposedCall(
                    asset_as_written=mention.as_written,
                    supporting_text=sentence,
                    explicitness="explicit" if cue.explicitness == "explicit" else "implicit",
                    evidence_origin=origin,
                    conditional=is_conditional,
                    condition_text=sentence if is_conditional else None,
                ),
                borrowed,
            )
    scan.calls = [call for call, _ in calls_by_key.values()]
    return scan


def _confidence_for_buy(calls: list[ProposedCall], text: str) -> float:
    confidence = 0.85 if any(c.explicitness == "explicit" for c in calls) else 0.65
    if any(c.conditional for c in calls):
        confidence -= 0.1
    if len(text) > LONG_POST_CHARS:
        confidence -= 0.05
    return round(confidence, 2)


def _weak_spots(post: Post) -> list[str]:
    """Post shapes where the rules are known to be unreliable, independent of their own score."""
    spots = []
    context_texts = [t for t in (post.context.parent_text, post.context.quoted_text) if t]
    if post.context.kind != PostKind.REPOST and any(find_asset_mentions(t) for t in context_texts):
        spots.append("WEAK_SPOT_CONTEXT_ASSET")
    if POST_WARNING.search(post.text):
        spots.append("WEAK_SPOT_WARNING")
    distinct = {m.key for t in [post.text, *context_texts] for m in find_asset_mentions(t)}
    if len(distinct) > 1:
        spots.append("WEAK_SPOT_MULTIPLE_ASSETS")
    return spots


def classify_with_rules(post: Post) -> Proposal:
    proposal = _classify(post)
    spots = _weak_spots(post)
    if not spots:
        return proposal
    if proposal.label == Label.BUY and "WEAK_SPOT_WARNING" in spots:
        return Proposal(Label.ABSTAIN, 0.5, reasons=(*proposal.reasons, "WARNING_CONTEXT"),
                        limitations=("Buy wording appears in a post that also contains a scam or exploit warning.",))
    return replace(proposal, confidence=min(proposal.confidence, WEAK_SPOT_CONFIDENCE_CAP),
                   reasons=(*proposal.reasons, *spots))


def _classify(post: Post) -> Proposal:
    text = post.text
    context = post.context

    if context.kind == PostKind.REPOST:
        return Proposal(Label.NO_NEW_BUY, 0.85, reasons=("REPOST_NOT_ORIGINAL_AUTHOR",))

    own = _scan(text, EvidenceOrigin.POST)
    calls = list(own.calls)
    reasons: list[str] = []
    limitations: list[str] = []

    if context.kind == PostKind.QUOTE and context.quoted_text and not calls:
        quoted = _scan(context.quoted_text, EvidenceOrigin.QUOTED)
        if quoted.calls:
            if ENDORSEMENT.search(text) and not re.search(r"\b(not|no|don'?t)\b", text, _I):
                calls = [
                    ProposedCall(c.asset_as_written, c.supporting_text, "implicit", EvidenceOrigin.QUOTED,
                                 c.conditional, c.condition_text)
                    for c in quoted.calls
                ]
                reasons.append("QUOTE_ENDORSED")
                limitations.append("The buy wording is in the quoted post; the author's endorsement is inferred from their comment.")
            else:
                return Proposal(Label.ABSTAIN, 0.5, reasons=("QUOTE_STANCE_UNCLEAR",),
                                limitations=("Quoted post contains a buy call; the author's stance on it is unclear.",))

    if context.kind == PostKind.REPLY and not calls and own.mentions and context.parent_text:
        if REPLY_ASKS_FOR_PICK.search(context.parent_text) and not own.notes & {"NEGATED", "QUESTION", "SELL_SIDE"}:
            first = own.mentions[0]
            sentence = next(s.strip() for o, s in _sentences(text) if o <= first.start < o + len(s))
            calls = [ProposedCall(first.as_written, sentence, "implicit", EvidenceOrigin.POST)]
            reasons.append("REPLY_ANSWERS_BUY_REQUEST")
            limitations.append("Read as a call only because the parent post asked for a pick.")

    if calls:
        if PROMO.search(text):
            return Proposal(Label.ABSTAIN, 0.5, reasons=("PROMOTIONAL_CONTENT",),
                            limitations=("Buy wording appears inside paid or promotional content.",))
        if SARCASM_CLEAR.search(text):
            return Proposal(Label.NO_NEW_BUY, 0.6, reasons=("SARCASM",))
        if SARCASM_POSSIBLE.search(text):
            return Proposal(Label.ABSTAIN, 0.45, reasons=("POSSIBLE_SARCASM_OR_JOKE",),
                            limitations=("Buy wording appears next to joke or sarcasm markers.",))
        if all(c.asset_as_written is None for c in calls):
            return Proposal(Label.ABSTAIN, 0.4, reasons=("UNRESOLVED_ASSET",))
        reasons.append("BUY_CUE_WITH_ASSET")
        if len(text) > LONG_POST_CHARS:
            limitations.append("Long post: only the sentences carrying the call were used as evidence.")
        return Proposal(Label.BUY, _confidence_for_buy(calls, text), calls=tuple(calls),
                        reasons=tuple(reasons), limitations=tuple(limitations))

    if own.unresolved_buy_cue:
        return Proposal(Label.ABSTAIN, 0.4, reasons=("UNRESOLVED_ASSET",),
                        limitations=("Buy wording found but no specific asset could be identified.",))

    notes = sorted(own.notes)
    if REFERRAL.search(text):
        notes.append("REFERRAL_OR_GIVEAWAY")
    if not own.mentions:
        # The rules know few bare tickers, so market wording without a known asset may still be a
        # call on a coin they cannot name. Keep the confidence low so the hybrid asks the LLM.
        if MARKET_TALK.search(text):
            return Proposal(Label.NO_NEW_BUY, 0.6, reasons=(*notes, "MARKET_TALK_WITHOUT_KNOWN_ASSET"),
                            limitations=("Market wording but no asset the rules recognise; the post may name "
                                         "a coin they do not know.",))
        return Proposal(Label.NO_NEW_BUY, 0.9, reasons=tuple(notes) or ("NO_ASSET_NO_ACTION",))
    if notes:
        return Proposal(Label.NO_NEW_BUY, 0.75, reasons=tuple(notes))
    return Proposal(Label.NO_NEW_BUY, 0.6, reasons=("ASSET_WITHOUT_RECOGNISED_ACTION",),
                    limitations=("An asset is mentioned but no buy wording was recognised; implicit language may be missed.",))
