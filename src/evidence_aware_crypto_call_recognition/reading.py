"""Read one sentence: which assets it names and what the author says about each.

Operations, per asset:
  ENTRY        a present own entry or endorsement (strength says how it was worded)
  EXIT, COVER, SHORT, HOLD, PAST, UNDATED_PURCHASE
  NONE         named, but no operation recognised

Entry wording that the policy does not accept as the author's own current BUY is not
an ENTRY; it is recorded as the reason it was set aside (CONDITIONAL, IMITATION,
THIRD_PARTY, QUESTION).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from evidence_aware_crypto_call_recognition import cues
from evidence_aware_crypto_call_recognition.contract import ASSET_MENTION
from evidence_aware_crypto_call_recognition.segment import Sentence

STRENGTH_CONFIDENCE = {
    "explicit": 0.9,
    "recommended": 0.9,
    "imperative": 0.85,
    "implicit": 0.82,
    "purchase_claim": 0.78,
    "rhetorical": 0.72,
}


@dataclass(frozen=True)
class Cue:
    kind: str
    start: int
    end: int
    strength: str | None = None


@dataclass
class SentenceReading:
    sentence: Sentence
    own_assets: list[str]
    quoted_assets: list[str]
    entry: Cue | None
    set_aside: str | None
    operations: dict[str, tuple[str, str | None]]
    flags: set[str] = field(default_factory=set)

    @property
    def has_asset_less_entry(self) -> bool:
        return self.entry is not None and not self.own_assets


def _ordered_unique(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


def _clause_before(view: str, position: int) -> str:
    head = view[:position]
    breaks = list(cues.CLAUSE_BREAK.finditer(head))
    return head[breaks[-1].end():] if breaks else head


def _is_negated(view: str, match: re.Match) -> bool:
    return bool(cues.NEGATION.search(_clause_before(view, match.start())))


def _entry_cues(view: str, has_asset: bool) -> tuple[list[Cue], bool]:
    found: list[Cue] = []
    negated = bool(cues.NEGATED_ENTRY.search(view))
    for pattern, strength in ((cues.RECOMMENDED_ENTRY, "recommended"), (cues.EXPLICIT_ENTRY, "explicit"),
                              (cues.BUYER_STANCE, "explicit")):
        for match in pattern.finditer(view):
            if _is_negated(view, match):
                negated = True
                continue
            found.append(Cue("ENTRY", match.start(), match.end(), strength))
    for match in cues.CONJOINED_ENTRY.finditer(view):
        if _is_negated(view, match):
            negated = True
            continue
        found.append(Cue("ENTRY", match.start(), match.end(), "explicit"))
    leading = cues.LEADING_ENTRY.search(view)
    if leading:
        found.append(Cue("ENTRY", leading.start(), leading.end(), "explicit"))
    imperative = cues.IMPERATIVE_ENTRY.search(view)
    if imperative and has_asset:
        found.append(Cue("ENTRY", imperative.start(), imperative.end(), "imperative"))
    has_present_marker = bool(cues.PRESENT_MARKER.search(view))
    for match in cues.IMPLICIT_ENTRY.finditer(view):
        if _is_negated(view, match):
            negated = True
            continue
        if has_present_marker or re.search(r"sense|worth|time\s+to|earn|deserve|place|opportunit", match.group(0), re.I):
            found.append(Cue("ENTRY", match.start(), match.end(), "implicit"))
    for match in cues.SLANG_ENTRY.finditer(view):
        if _is_negated(view, match):
            negated = True
            continue
        found.append(Cue("ENTRY", match.start(), match.end(), "implicit"))
    found.extend(Cue("ENTRY", m.start(), m.end(), "implicit") for m in cues.SLANG_NEGATIVE_FORM.finditer(view))
    for match in cues.ROTATION_INTO.finditer(view):
        if not _is_negated(view, match):
            found.append(Cue("ENTRY", match.end() - len("into"), match.end(), "explicit"))
    return found, negated


def _drop_overlaps(entries: list[Cue], blockers: list[Cue]) -> list[Cue]:
    """An entry verb that opens a short or buys back a short is not a long entry."""
    kept = []
    for entry in entries:
        if any(blocker.start <= entry.end + 25 and blocker.end >= entry.start for blocker in blockers):
            continue
        kept.append(entry)
    return kept


def _matches(pattern: re.Pattern, view: str, kind: str, skip_negated: bool = True) -> list[Cue]:
    return [Cue(kind, m.start(), m.end()) for m in pattern.finditer(view)
            if not (skip_negated and _is_negated(view, m))]


def _nearest(cue_list: list[Cue], position: int) -> Cue | None:
    before = [c for c in cue_list if c.start <= position]
    if before:
        return max(before, key=lambda c: c.start)
    after = [c for c in cue_list if c.start > position]
    return min(after, key=lambda c: c.start) if after else None


def _disclaims(view: str) -> bool:
    for match in cues.DISCLAIMER.finditer(view):
        text = match.group(0)
        if cues.BOILERPLATE_DISCLAIMER.search(text) or cues.OTHER_PARTY_POSSESSIVE.search(text):
            continue
        return True
    return False


def read_sentence(sentence: Sentence) -> SentenceReading:
    view = sentence.unquoted()
    own = [(m.group(0), m.start()) for m in ASSET_MENTION.finditer(view)]
    own_assets = _ordered_unique([asset for asset, _ in own])
    quoted_assets = _ordered_unique([m.group(0) for start, end in sentence.quoted
                                     for m in ASSET_MENTION.finditer(sentence.text[start:end])])

    flags: set[str] = set()
    for name, pattern in (("CONDITIONAL", cues.CONDITIONAL), ("FORECAST", cues.FORECAST),
                          ("THIRD_PARTY", cues.THIRD_PARTY), ("CONTEXT_REFERENCE", cues.CONTEXT_REFERENCE),
                          ("SATIRE_FRAME", cues.SATIRE_FRAME), ("SINCERITY", cues.SINCERITY),
                          ("SPONSORSHIP", cues.SPONSORSHIP), ("NON_TOKEN", cues.NON_TOKEN_PURCHASE),
                          ("DEIXIS", cues.DEIXIS), ("INSTRUCTION_TEXT", cues.INSTRUCTION_TEXT),
                          ("POST_SCOPE", cues.POST_SCOPE), ("HISTORIC_TIME", cues.HISTORIC_TIME),
                          ("CURRENT_TIME", cues.CURRENT_TIME), ("HEDGE", cues.HEDGE), ("JOKE_MARKER", cues.JOKE_MARKER)):
        if pattern.search(view):
            flags.add(name)
    if re.search(r"\bthis\s+(?:paragraph|section|part)\b", view, re.I):
        flags.add("PARAGRAPH_SCOPE")
    if sentence.quoted:
        flags.add("HAS_QUOTE")
    if sentence.is_question:
        flags.add("QUESTION")

    covers = _matches(cues.COVER_SHORT, view, "COVER")
    shorts = [c for c in _matches(cues.OPEN_SHORT, view, "SHORT")
              if not any(c.start < k.end and c.end > k.start for k in covers)]
    exits = [c for c in _matches(cues.EXIT, view, "EXIT") + _matches(cues.RECOMMENDED_EXIT, view, "EXIT")
             if not any(c.start < k.end and c.end > k.start for k in covers)]
    entries, negated_entry = _entry_cues(view, bool(own_assets))
    entries = _drop_overlaps(entries, covers + shorts)
    if negated_entry or _disclaims(view):
        flags.add("DISCLAIMER")

    set_aside = None
    if entries:
        if "QUESTION" in flags:
            set_aside = "QUESTION"
        elif "CONDITIONAL" in flags:
            set_aside = "CONDITIONAL"
        elif "SATIRE_FRAME" in flags and "SINCERITY" not in flags:
            set_aside = "IMITATION"
        elif "THIRD_PARTY" in flags and not any(c.strength in ("explicit", "recommended") for c in entries):
            set_aside = "THIRD_PARTY"
        elif "NON_TOKEN" in flags and not own_assets:
            set_aside = "NON_TOKEN"
    if set_aside:
        entries = []
    elif "QUESTION" in flags and cues.RHETORICAL_ENDORSEMENT.search(view) and own_assets:
        entries = [Cue("ENTRY", 0, len(view), "rhetorical")]

    past = []
    for match in cues.PAST_ACQUISITION.finditer(view):
        if _is_negated(view, match):
            continue
        if cues.COUNTERFACTUAL.search(_clause_before(view, match.start())):
            flags.add("COUNTERFACTUAL")
            continue
        if "CURRENT_TIME" in flags and "HISTORIC_TIME" not in flags:
            if not set_aside:
                entries.append(Cue("ENTRY", match.start(), match.end(), "purchase_claim"))
        else:
            past.append(Cue("PAST", match.start(), match.end()))
    holds = _matches(cues.HOLD, view, "HOLD")

    if "HEDGE" in flags:
        hedges = [Cue("HEDGE", m.start(), m.end()) for m in cues.HEDGE.finditer(view)]
        entries = [c for c in entries if c.strength != "purchase_claim"]
        past = []
        exits = exits + hedges
    actions = entries + exits + covers + shorts
    states = past + holds
    operations: dict[str, tuple[str, str | None]] = {}
    for asset, position in own:
        if asset in operations and operations[asset][0] == "ENTRY":
            continue
        cue = _nearest(actions, position) or _nearest(states, position)
        if cue is not None and cue.kind == "ENTRY":
            cue = max(entries, key=lambda c: STRENGTH_CONFIDENCE[c.strength or "implicit"])
        if cue is None:
            operations[asset] = ("NONE", None)
        elif cue.kind == "PAST" and "HISTORIC_TIME" not in flags:
            operations[asset] = ("UNDATED_PURCHASE", None)
        else:
            operations[asset] = (cue.kind, cue.strength)
        if "THIRD_PARTY" in flags and operations[asset][0] == "ENTRY" and operations[asset][1] not in ("explicit", "recommended"):
            operations[asset] = ("NONE", None)

    best = max(entries, key=lambda c: STRENGTH_CONFIDENCE[c.strength or "implicit"], default=None)
    if exits or covers or shorts:
        flags.add("NEGATIVE_OPERATION")
    if holds:
        flags.add("HOLD")
    if past:
        flags.add("PAST")
    return SentenceReading(sentence, own_assets, quoted_assets, best, set_aside, operations, flags)
