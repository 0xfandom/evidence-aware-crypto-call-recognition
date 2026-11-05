"""Constants and byte-level helpers fixed by the published assessment contract."""
from __future__ import annotations

import hashlib
import json
import re

CONTRACT_VERSION = "synthetic-buy-assessment-v1"
CONFIDENCE_GATE = 0.75
LABELS = ("BUY", "NO_NEW_BUY", "UNCLEAR")
ASSET_MENTION = re.compile(r"(?<![A-Za-z0-9$])\$[A-Z][A-Z0-9]{2,11}(?![A-Za-z0-9])")
ASSET_MENTION_EXACT = re.compile(r"\$[A-Z][A-Z0-9]{2,11}")


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def fingerprint(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def utf16_length(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


def utf16_slice(text: str, start: int, end: int) -> str:
    return text.encode("utf-16-le")[2 * start:2 * end].decode("utf-16-le")
