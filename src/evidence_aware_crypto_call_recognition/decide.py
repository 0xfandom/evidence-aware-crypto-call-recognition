"""Turn sentence readings into one contract decision for a case."""
from __future__ import annotations

from dataclasses import dataclass, field

from evidence_aware_crypto_call_recognition import cues
from evidence_aware_crypto_call_recognition.contract import ASSET_MENTION, utf16_length
from evidence_aware_crypto_call_recognition.reading import STRENGTH_CONFIDENCE, SentenceReading, read_sentence
from evidence_aware_crypto_call_recognition.segment import Sentence, split_sentences

CONFLICT_CONFIDENCE = 0.6
SATIRE_CAP = 0.7
UNREFERENCED_CONTEXT_CAP = 0.74
CONTEXT_PENALTY = 0.04
ANAPHORA_PENALTY = 0.03
SPONSORSHIP_PENALTY = 0.03
DROPPED_ASSET_PENALTY = 0.05
MISSING_CONTEXT_KINDS = ("REPLY_PARENT", "LINKED_PAGE", "IMAGE", "VIDEO")

BUY_LIMITATIONS = [
    "A stated or claimed action is not verified execution.",
    "Asset identity is the literal cashtag only; no contract, chain or project identity was checked.",
]


@dataclass
class BuyCandidate:
    asset: str
    strength: str
    decisive: SentenceReading
    asset_sentence: SentenceReading | None = None
    context_span: dict | None = None
    confidence_cap: float = 1.0
    penalties: list[float] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def confidence(self) -> float:
        return min(STRENGTH_CONFIDENCE[self.strength] - sum(self.penalties), self.confidence_cap)


@dataclass
class Decision:
    label: str
    confidence: float
    current_buys: list[dict]
    evidence_ids: list[str]
    explanation: str
    limitations: list[str]
    trace: dict


def _line(reading: SentenceReading) -> int:
    return reading.sentence.line + 1


def _span_ids(case: dict, source_id: str, text: str, start: int, end: int) -> str:
    """Smallest catalogue span on the source that covers [start, end) of the text."""
    start16, end16 = utf16_length(text[:start]), utf16_length(text[:end])
    choices = [span for span in case["evidence_catalogue"] if span["source_id"] == source_id
               and span["start_utf16"] <= start16 and span["end_utf16"] >= end16]
    best = min(choices, key=lambda span: span["end_utf16"] - span["start_utf16"])
    return best["evidence_id"]


def _full_span(case: dict, source: dict) -> str:
    return _span_ids(case, source["source_id"], source["text"], 0, len(source["text"]))


def _sentence_span(case: dict, sentence: Sentence) -> str:
    primary = case["primary"]
    return _span_ids(case, primary["source_id"], primary["text"], sentence.start, sentence.end)


def _primary_span_bounds(case: dict, evidence_id: str) -> tuple[int, int]:
    span = next(s for s in case["evidence_catalogue"] if s["evidence_id"] == evidence_id)
    return span["start_utf16"], span["end_utf16"]


def _context_assets(case: dict) -> dict[str, dict]:
    """Distinct cashtags in context sources, each with the smallest span that contains it."""
    found: dict[str, dict] = {}
    for source in case["context"]:
        for match in ASSET_MENTION.finditer(source["text"]):
            if match.group(0) in found:
                continue
            evidence_id = _span_ids(case, source["source_id"], source["text"], match.start(), match.end())
            found[match.group(0)] = {"evidence_id": evidence_id, "source_id": source["source_id"]}
    return found


def _is_fragment_head(case: dict, reading: SentenceReading) -> bool:
    if reading.sentence.index != 0:
        return False
    primary = case["primary"]
    missing_prefix = any(item["kind"] == "MISSING_PREFIX" for item in case["unavailable_context"])
    starts_cut = primary["text"].lstrip().startswith(("…", "..."))
    return primary["capture_scope"] == "FRAGMENT" and (missing_prefix or starts_cut)


def _dated_by_heading(readings: list[SentenceReading], reading: SentenceReading) -> bool:
    """A heading such as "Two entries I made today:" dates the lines listed under it."""
    for earlier in readings[:reading.sentence.index]:
        if earlier.sentence.paragraph == reading.sentence.paragraph and "CURRENT_TIME" in earlier.flags \
                and "HISTORIC_TIME" not in earlier.flags and earlier.sentence.text.rstrip().endswith(":"):
            return True
    return False


def _disclaimer_scopes(readings: list[SentenceReading]) -> list[tuple[str, object]]:
    scopes: list[tuple[str, object]] = []
    for position, reading in enumerate(readings):
        if "DISCLAIMER" not in reading.flags:
            continue
        if reading.own_assets:
            scopes.append(("assets", set(reading.own_assets)))
            continue
        if "POST_SCOPE" in reading.flags and "PARAGRAPH_SCOPE" not in reading.flags:
            scopes.append(("post", None))
            continue
        previous = readings[position - 1] if position else None
        if previous and previous.sentence.paragraph == reading.sentence.paragraph and previous.own_assets \
                and "PARAGRAPH_SCOPE" not in reading.flags:
            scopes.append(("assets", set(previous.own_assets)))
        else:
            scopes.append(("paragraph", reading.sentence.paragraph))
    return scopes


def _is_disclaimed(candidate: BuyCandidate, scopes: list[tuple[str, object]]) -> bool:
    for kind, value in scopes:
        if kind == "post":
            return True
        if kind == "assets" and candidate.asset in value:  # type: ignore[operator]
            return True
        if kind == "paragraph" and candidate.decisive.sentence.paragraph == value:
            return True
    return False


def _later_reversal(candidate: BuyCandidate, readings: list[SentenceReading]) -> bool:
    after = candidate.decisive.sentence.index
    return any(r.sentence.index > after and r.operations.get(candidate.asset, ("NONE",))[0] in ("EXIT", "COVER", "SHORT")
               for r in readings)


def _bind_asset_less(readings: list[SentenceReading], reading: SentenceReading,
                     context_assets: dict[str, dict], all_own: list[str]) -> BuyCandidate | None:
    strength = reading.entry.strength or "implicit"
    for previous in reversed(readings[:reading.sentence.index]):
        if previous.own_assets:
            if len(previous.own_assets) != 1:
                return None
            asset = previous.own_assets[0]
            candidate = BuyCandidate(asset, strength, reading, asset_sentence=previous, penalties=[ANAPHORA_PENALTY])
            if previous.operations.get(asset, ("NONE",))[0] in ("EXIT", "COVER", "SHORT", "PAST"):
                candidate.penalties.append(0.05)
            candidate.notes.append(f"line {_line(reading)} refers back to {asset} on line {_line(previous)}")
            return candidate
    if len(all_own) == 1:
        holder = next(r for r in readings if all_own[0] in r.own_assets)
        candidate = BuyCandidate(all_own[0], strength, reading, asset_sentence=holder, penalties=[ANAPHORA_PENALTY])
        candidate.notes.append(f"line {_line(reading)} refers to {all_own[0]}, the only asset the post names")
        return candidate
    if not all_own and len(context_assets) == 1:
        asset, span = next(iter(context_assets.items()))
        referenced = any(flag in r.flags for r in readings for flag in ("CONTEXT_REFERENCE", "DEIXIS"))
        candidate = BuyCandidate(asset, strength, reading, context_span=span, penalties=[CONTEXT_PENALTY])
        if not referenced:
            candidate.confidence_cap = UNREFERENCED_CONTEXT_CAP
        candidate.notes.append(f"the asset {asset} is identified by the retained context post; the endorsement is the "
                               f"primary author's own wording on line {_line(reading)}")
        return candidate
    return None


def decide(case: dict) -> Decision:
    primary = case["primary"]
    sentences = split_sentences(primary["text"])
    readings = [read_sentence(sentence) for sentence in sentences]
    context_assets = _context_assets(case)
    all_own = list(dict.fromkeys(asset for r in readings for asset in r.own_assets))
    unavailable = [item["kind"] for item in case["unavailable_context"]]
    flags = set().union(*(r.flags for r in readings)) if readings else set()

    candidates: list[BuyCandidate] = []
    gaps: list[str] = []
    set_aside: list[str] = []
    for reading in readings:
        head = _is_fragment_head(case, reading)
        if reading.set_aside:
            set_aside.append(f"line {_line(reading)}: entry wording set aside ({reading.set_aside.lower().replace('_', ' ')})")
        for asset, (operation, strength) in reading.operations.items():
            if operation == "ENTRY":
                if head:
                    gaps.append(f"The only entry wording for {asset} is at the start of a fragment whose prefix is "
                                "missing; the missing text could change the speaker or the polarity.")
                    continue
                candidates.append(BuyCandidate(asset, strength or "implicit", reading, asset_sentence=reading))
            elif operation == "NONE" and head and (cues.PRESENT_MARKER.search(reading.sentence.text)
                                                   or cues.MARKET_EVALUATION.search(reading.sentence.text)):
                gaps.append(f"{asset} is evaluated at the start of a fragment whose prefix is missing; the missing "
                            "text could carry the action or reverse its polarity.")
            elif operation == "UNDATED_PURCHASE" and not head and _dated_by_heading(readings, reading):
                candidates.append(BuyCandidate(asset, "purchase_claim", reading, asset_sentence=reading))
            elif operation == "UNDATED_PURCHASE":
                gaps.append(f"The purchase claim for {asset} has no trade time and no current-intent wording; "
                            "publication time does not establish a current entry.")
        if reading.has_asset_less_entry:
            if head:
                gaps.append("Entry wording sits at the start of a fragment whose prefix is missing.")
                continue
            bound = _bind_asset_less(readings, reading, context_assets, all_own)
            if bound:
                candidates.append(bound)
            else:
                missing = [kind for kind in unavailable if kind in MISSING_CONTEXT_KINDS]
                where = f"; the unavailable {', '.join(k.lower().replace('_', ' ') for k in missing)} may hold it" if missing else ""
                gaps.append(f"Line {_line(reading)} states an own entry but no asset can be identified from the "
                            f"supplied text{where}. Unavailable material was not reconstructed.")

    states_operation = any(
        r.entry is not None
        or any(op != "NONE" for op, _ in r.operations.values())
        or bool(r.flags & {"DISCLAIMER", "CONDITIONAL", "NEGATIVE_OPERATION", "HOLD", "PAST"})
        for r in readings)
    if not candidates and not states_operation and flags & {"DEIXIS", "CONTEXT_REFERENCE"} \
            and any(kind in MISSING_CONTEXT_KINDS for kind in unavailable):
        gaps.append("The post answers or points to material that is unavailable, and states no operation of its own; "
                    "the intended action cannot be resolved.")

    scopes = _disclaimer_scopes(readings)
    by_asset: dict[str, BuyCandidate] = {}
    conflicts: list[BuyCandidate] = []
    for candidate in candidates:
        if _is_disclaimed(candidate, scopes) or _later_reversal(candidate, readings):
            conflicts.append(candidate)
            continue
        current = by_asset.get(candidate.asset)
        if current is None or candidate.confidence > current.confidence:
            by_asset[candidate.asset] = candidate

    limitations: list[str] = []
    for kind in unavailable:
        if kind != "MISSING_PREFIX":
            limitations.append(f"Unavailable {kind.lower().replace('_', ' ')} was not reconstructed or inferred.")
    if "INSTRUCTION_TEXT" in flags or any(cues.INSTRUCTION_TEXT.search(s["text"]) for s in case["context"]):
        limitations.append("Source text contains instruction-like wording; it was read as data, not followed.")

    trace = {"sentences": [_trace_reading(r) for r in readings], "gaps": gaps, "set_aside": set_aside,
             "conflicts": [c.asset for c in conflicts]}

    if by_asset:
        return _buy_decision(case, readings, list(by_asset.values()), flags, limitations, gaps, trace)
    if conflicts:
        return _conflict_decision(case, conflicts, limitations, trace)
    if gaps:
        return Decision("UNCLEAR", 0.8, [], [_full_span(case, primary)],
                        "No current own BUY can be established. " + " ".join(dict.fromkeys(gaps)),
                        (list(dict.fromkeys(gaps)) + limitations)[:12], trace)
    return _no_new_buy_decision(case, readings, set_aside, limitations, trace)


def _buy_decision(case: dict, readings: list[SentenceReading], chosen: list[BuyCandidate], flags: set[str],
                  limitations: list[str], gaps: list[str], trace: dict) -> Decision:
    chosen.sort(key=lambda c: c.decisive.sentence.start)
    satire_elsewhere = "SATIRE_FRAME" in flags
    joke_marker = "JOKE_MARKER" in flags
    entries: list[tuple[BuyCandidate, list[str]]] = []
    used_spans: list[tuple[int, int]] = []
    dropped: list[str] = []
    for candidate in chosen:
        ids = [_sentence_span(case, candidate.decisive.sentence)]
        if candidate.asset_sentence and candidate.asset_sentence is not candidate.decisive:
            ids.append(_sentence_span(case, candidate.asset_sentence.sentence))
        if candidate.context_span:
            ids.append(candidate.context_span["evidence_id"])
        ids = list(dict.fromkeys(ids))
        primary_bounds = [_primary_span_bounds(case, i) for i in ids if i != (candidate.context_span or {}).get("evidence_id")]
        if any(a < d and c < b for a, b in primary_bounds for c, d in used_spans):
            dropped.append(candidate.asset)
            continue
        used_spans.extend(primary_bounds)
        if (satire_elsewhere or joke_marker) and "SINCERITY" not in candidate.decisive.flags:
            candidate.confidence_cap = min(candidate.confidence_cap, SATIRE_CAP)
        if "SPONSORSHIP" in flags:
            candidate.penalties.append(SPONSORSHIP_PENALTY)
        entries.append((candidate, ids))

    confidence = min(c.confidence for c, _ in entries)
    notes = []
    if dropped:
        confidence -= DROPPED_ASSET_PENALTY
        notes.append(f"{', '.join(dropped)} also reads as an entry but shares the same citable line, so it cannot be "
                     "given separate evidence and is not reported.")
    current_buys = [{"asset_mention": c.asset, "evidence_ids": ids} for c, ids in entries]
    evidence_ids = list(dict.fromkeys(i for _, ids in entries for i in ids))

    parts = []
    for candidate, _ in entries:
        wording = {"explicit": "an explicit present own entry", "recommended": "the author's own current recommendation to enter",
                   "imperative": "a present instruction to enter", "implicit": "an implicit present endorsement",
                   "purchase_claim": "a same-day own purchase claim", "rhetorical": "a rhetorical question read as an endorsement"}
        line = _line(candidate.decisive)
        detail = f"; {'; '.join(candidate.notes)}" if candidate.notes else ""
        parts.append(f"{candidate.asset}: line {line} carries {wording[candidate.strength]}{detail}.")
    others = [f"Not a BUY: {reason}" for reason in _asset_reasons(readings, {c.asset for c, _ in entries})]
    explanation = "Current own BUY. " + " ".join(parts + notes + others)
    if "SPONSORSHIP" in flags:
        explanation += " The post is sponsored; sponsorship is treated as context, not as proof or disproof."
    if satire_elsewhere:
        explanation += " The post also contains satire or imitation framing, so confidence is reduced."
    elif joke_marker:
        explanation += " The post carries joke or sarcasm markers, so a sincere call cannot be confirmed and confidence is reduced."
    limits = BUY_LIMITATIONS + notes + limitations + [g for g in dict.fromkeys(gaps)]
    return Decision("BUY", round(max(confidence, 0.0), 2), current_buys, evidence_ids, explanation[:3000], limits[:12], trace)


OPERATION_WORDS = {
    "EXIT": "an exit, sale or reduction", "COVER": "a short cover, not a new long", "SHORT": "a short, not a long entry",
    "HOLD": "an existing position without a new entry", "PAST": "completed past activity",
    "UNDATED_PURCHASE": "an undated purchase claim", "HEDGE": "a hedge, not new long exposure", "ENTRY": "entry wording that was not accepted",
    "NONE": "mentioned without a current own entry",
}


def _asset_reasons(readings: list[SentenceReading], exclude: set[str]) -> list[str]:
    """One plain reason per asset that is not a BUY, from the first sentence naming it."""
    reasons: list[str] = []
    seen = set(exclude)
    for reading in readings:
        for asset, (operation, _) in reading.operations.items():
            if asset in seen:
                continue
            seen.add(asset)
            reason = OPERATION_WORDS[operation]
            if operation == "NONE" and "THIRD_PARTY" in reading.flags:
                reason = "attributed to someone other than the author"
            elif operation == "NONE" and "CONDITIONAL" in reading.flags:
                reason = "subject to a future condition that the post does not say has occurred"
            elif operation == "NONE" and "FORECAST" in reading.flags:
                reason = "the subject of a forecast or scenario, not an entry"
            elif operation == "NONE" and "QUESTION" in reading.flags:
                reason = "raised in a question, not an own entry"
            reasons.append(f"{asset} is {reason} (line {_line(reading)}).")
        for asset in reading.quoted_assets:
            if asset not in seen:
                seen.add(asset)
                reasons.append(f"{asset} appears only inside quoted or imitated speech (line {_line(reading)}).")
    return reasons


def _conflict_decision(case: dict, conflicts: list[BuyCandidate], limitations: list[str], trace: dict) -> Decision:
    """Entry wording that the same post also disclaims or reverses: proposed, but below the gate."""
    chosen: dict[str, BuyCandidate] = {}
    for candidate in conflicts:
        chosen.setdefault(candidate.asset, candidate)
    candidate = next(iter(chosen.values()))
    ids = [_sentence_span(case, candidate.decisive.sentence)]
    if candidate.context_span:
        ids.append(candidate.context_span["evidence_id"])
    if candidate.asset_sentence and candidate.asset_sentence is not candidate.decisive:
        ids.append(_sentence_span(case, candidate.asset_sentence.sentence))
    ids = list(dict.fromkeys(ids))
    note = (f"Entry wording for {candidate.asset} on line {_line(candidate.decisive)} conflicts with a disclaimer or a "
            "later exit in the same post; the reading is left below the confidence gate.")
    return Decision("BUY", CONFLICT_CONFIDENCE, [{"asset_mention": candidate.asset, "evidence_ids": ids}], ids,
                    note, (BUY_LIMITATIONS + [note] + limitations)[:12], trace)


def _no_new_buy_decision(case: dict, readings: list[SentenceReading], set_aside: list[str],
                         limitations: list[str], trace: dict) -> Decision:
    reasons: list[str] = []
    strong = False
    for reading in readings:
        for asset, (operation, _) in reading.operations.items():
            if operation in ("EXIT", "COVER", "SHORT", "HOLD", "PAST", "HEDGE"):
                strong = True
        flags = reading.flags
        if flags & {"DISCLAIMER", "NEGATIVE_OPERATION", "HOLD", "PAST", "THIRD_PARTY", "CONDITIONAL", "NON_TOKEN",
                    "COUNTERFACTUAL", "HEDGE"}:
            strong = True
    if set_aside:
        strong = True
    reasons.extend(_asset_reasons(readings, set()))
    seen = {asset for r in readings for asset in [*r.own_assets, *r.quoted_assets]}
    if any("DISCLAIMER" in r.flags for r in readings):
        reasons.append("The author explicitly disclaims a new entry or recommendation.")
    if any("COUNTERFACTUAL" in r.flags for r in readings):
        reasons.append("Purchase wording is counterfactual (what the author would have or almost did), not an action.")
    if any("NON_TOKEN" in r.flags for r in readings):
        reasons.append("Purchase wording refers to a product, service or claim, not a token entry.")
    if any("THIRD_PARTY" in r.flags for r in readings) or case["context"]:
        reasons.append("Calls by other speakers or in older context posts are not the author's current call.")
    reasons.extend(s[0].upper() + s[1:] + "." for s in set_aside)
    if not seen and not strong:
        confidence = 0.85 if not any(r.entry for r in readings) else 0.78
        reasons.insert(0, "The post names no asset with a current own entry.")
    elif strong:
        confidence = 0.88
    elif any("FORECAST" in r.flags for r in readings):
        confidence = 0.82
    else:
        confidence = 0.78
    explanation = "No new own BUY. " + " ".join(dict.fromkeys(reasons))
    return Decision("NO_NEW_BUY", confidence, [], [_full_span(case, case["primary"])], explanation[:3000],
                    limitations[:12], trace)


def _trace_reading(reading: SentenceReading) -> dict:
    return {
        "line": _line(reading),
        "text": reading.sentence.text,
        "own_assets": reading.own_assets,
        "quoted_assets": reading.quoted_assets,
        "entry": reading.entry.strength if reading.entry else None,
        "set_aside": reading.set_aside,
        "operations": {asset: op for asset, (op, _) in reading.operations.items()},
        "flags": sorted(reading.flags),
    }
