"""Find asset mentions exactly as written. Nothing here maps a symbol to a contract."""

from __future__ import annotations

import re
from dataclasses import dataclass

from evidence_aware_crypto_call_recognition.contract import Asset, AssetStatus

# Bare tickers are accepted without a "$" only for well-known majors whose symbol
# is not also a common English word. Everything else needs a cashtag.
KNOWN_BARE_TICKERS = frozenset(
    {"BTC", "ETH", "SOL", "XRP", "ADA", "AVAX", "DOT", "DOGE", "BNB", "TRX", "LTC", "ATOM",
     "ARB", "TIA", "INJ", "SUI", "APT", "NEAR", "PEPE", "SHIB", "TAO", "RNDR", "SEI", "WIF",
     "BONK", "JUP", "PENDLE", "ONDO", "LINK"}
)

KNOWN_NAMES = {
    "bitcoin": "BTC",
    "ethereum": "ETH",
    "solana": "SOL",
    "cardano": "ADA",
    "avalanche": "AVAX",
    "polkadot": "DOT",
    "dogecoin": "DOGE",
    "chainlink": "LINK",
    "arbitrum": "ARB",
    "celestia": "TIA",
    "injective": "INJ",
    "bittensor": "TAO",
}

# Fiat / unit tokens that look like cashtags but are not assets.
NOT_ASSETS = frozenset({"USD", "EUR", "GBP", "INR", "K", "M", "B"})

_CASHTAG = re.compile(r"(?<![\w$])\$([A-Za-z][A-Za-z0-9]{1,11})\b")
_BARE = re.compile(r"(?<![\w$])([A-Z][A-Z0-9]{1,6})\b")
_NAME = re.compile(r"\b(" + "|".join(KNOWN_NAMES) + r")\b", re.IGNORECASE)
_EVM_ADDRESS = re.compile(r"\b0x[a-fA-F0-9]{40}\b")
_SOLANA_ADDRESS = re.compile(r"(?<![A-Za-z0-9])[1-9A-HJ-NP-Za-km-z]{32,44}(?![A-Za-z0-9])")


@dataclass(frozen=True)
class AssetMention:
    key: str
    as_written: str
    start: int
    end: int
    is_address: bool

    def to_asset(self) -> Asset:
        if self.is_address:
            return Asset(status=AssetStatus.ADDRESS, address=self.key, as_written=self.as_written)
        return Asset(status=AssetStatus.SYMBOL, symbol=self.key, as_written=self.as_written)


def _looks_like_solana_address(candidate: str) -> bool:
    has_digit = any(c.isdigit() for c in candidate)
    has_upper = any(c.isupper() for c in candidate)
    has_lower = any(c.islower() for c in candidate)
    return has_digit and has_upper and has_lower


def find_asset_mentions(text: str) -> list[AssetMention]:
    mentions: list[AssetMention] = []
    taken: list[tuple[int, int]] = []

    def overlaps(start: int, end: int) -> bool:
        return any(start < t_end and end > t_start for t_start, t_end in taken)

    def add(mention: AssetMention) -> None:
        if not overlaps(mention.start, mention.end):
            mentions.append(mention)
            taken.append((mention.start, mention.end))

    for m in _EVM_ADDRESS.finditer(text):
        add(AssetMention(m.group(0), m.group(0), m.start(), m.end(), is_address=True))
    for m in _SOLANA_ADDRESS.finditer(text):
        if _looks_like_solana_address(m.group(0)):
            add(AssetMention(m.group(0), m.group(0), m.start(), m.end(), is_address=True))
    for m in _CASHTAG.finditer(text):
        symbol = m.group(1).upper()
        if symbol not in NOT_ASSETS:
            add(AssetMention(symbol, m.group(0), m.start(), m.end(), is_address=False))
    for m in _BARE.finditer(text):
        if m.group(1) in KNOWN_BARE_TICKERS:
            add(AssetMention(m.group(1), m.group(0), m.start(), m.end(), is_address=False))
    for m in _NAME.finditer(text):
        add(AssetMention(KNOWN_NAMES[m.group(1).lower()], m.group(0), m.start(), m.end(), is_address=False))

    return sorted(mentions, key=lambda mention: mention.start)


def asset_is_written_in(asset_as_written: str, *texts: str | None) -> bool:
    needle = asset_as_written.strip().lower()
    return bool(needle) and any(t and needle in t.lower() for t in texts)
