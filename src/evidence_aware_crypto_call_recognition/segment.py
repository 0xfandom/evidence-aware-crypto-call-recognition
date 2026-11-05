"""Split a source into sentences, and mark quoted speech inside them.

Offsets are Python string indices into the full source text. They are converted to
UTF-16 code units only when an evidence span is chosen.
"""
from __future__ import annotations

from dataclasses import dataclass

TERMINATORS = ".!?"
CLOSING_QUOTES = "'\"’”"


@dataclass(frozen=True)
class Sentence:
    index: int
    start: int
    end: int
    text: str
    line: int
    paragraph: int
    quoted: tuple[tuple[int, int], ...]

    def unquoted(self) -> str:
        """The sentence with quoted speech blanked out; offsets are kept."""
        chars = list(self.text)
        for start, end in self.quoted:
            for position in range(start, end):
                chars[position] = " "
        return "".join(chars)

    @property
    def is_question(self) -> bool:
        return self.text.rstrip().rstrip(CLOSING_QUOTES).rstrip().endswith("?")


def _is_word_char(char: str) -> bool:
    return char.isalnum()


def quoted_ranges(line: str) -> list[tuple[int, int]]:
    """Ranges of quoted speech, including the quote marks themselves.

    A straight single quote between two letters is an apostrophe ("today's"), not a quote.
    """
    ranges: list[tuple[int, int]] = []
    position = 0
    while position < len(line):
        char = line[position]
        closer = None
        if char == '"':
            closer = '"'
        elif char == "“":
            closer = "”"
        elif char == "‘":
            closer = "’"
        elif char == "'":
            before = line[position - 1] if position else " "
            after = line[position + 1] if position + 1 < len(line) else " "
            if not _is_word_char(before) and not after.isspace():
                closer = "'"
        if closer is None:
            position += 1
            continue
        end = _find_closer(line, position + 1, closer)
        if end is None:
            position += 1
            continue
        ranges.append((position, end + 1))
        position = end + 1
    return ranges


def _find_closer(line: str, start: int, closer: str) -> int | None:
    for position in range(start, len(line)):
        if line[position] != closer:
            continue
        if closer in "'’":
            after = line[position + 1] if position + 1 < len(line) else " "
            before = line[position - 1]
            if _is_word_char(after) or before.isspace():
                continue
        return position
    return None


def _inside(position: int, ranges: list[tuple[int, int]]) -> bool:
    return any(start <= position < end for start, end in ranges)


def _sentence_bounds(line: str, quotes: list[tuple[int, int]]) -> list[tuple[int, int]]:
    bounds = []
    start = 0
    position = 0
    while position < len(line):
        char = line[position]
        if char in TERMINATORS and not _inside(position, quotes):
            end = position + 1
            while end < len(line) and (line[end] in TERMINATORS or line[end] in CLOSING_QUOTES):
                end += 1
            if end >= len(line) or line[end].isspace():
                bounds.append((start, end))
                start = end
                position = end
                continue
        if char in CLOSING_QUOTES and _inside(position, quotes) and any(e == position + 1 for _, e in quotes):
            previous = line[position - 1] if position else ""
            end = position + 1
            if previous in TERMINATORS and (end >= len(line) or line[end].isspace()):
                bounds.append((start, end))
                start = end
        position += 1
    if line[start:].strip():
        bounds.append((start, len(line)))
    return bounds


def split_sentences(text: str) -> list[Sentence]:
    sentences: list[Sentence] = []
    cursor = 0
    paragraph = 0
    previous_blank = False
    for line_number, line in enumerate(text.splitlines(keepends=True)):
        body = line.rstrip("\r\n\x0b\x0c\x1c\x1d\x1e\x85  ")
        if not body.strip():
            if sentences:
                previous_blank = True
            cursor += len(line)
            continue
        if previous_blank:
            paragraph += 1
            previous_blank = False
        quotes = quoted_ranges(body)
        for start, end in _sentence_bounds(body, quotes):
            raw = body[start:end]
            lead = len(raw) - len(raw.lstrip())
            stripped = raw.strip()
            if not stripped:
                continue
            absolute = cursor + start + lead
            local = [(max(a - start - lead, 0), min(b - start - lead, len(stripped)))
                     for a, b in quotes if a < end and b > start]
            sentences.append(Sentence(len(sentences), absolute, absolute + len(stripped), stripped,
                                      line_number, paragraph, tuple(r for r in local if r[1] > r[0])))
        cursor += len(line)
    return sentences
