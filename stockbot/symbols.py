"""Simvol uyğunluqları: axtarış nəticələrinin ümumi formatı və sıralanması."""

from __future__ import annotations

import re
from dataclasses import dataclass

# Ad axtarışında üstünlük verilən birjalar (sıra əhəmiyyətlidir).
MAJOR_EXCHANGES = (
    "NASDAQ",
    "NYSE",
    "AMEX",
    "NYSE ARCA",
    "BATS",
    "LSE",
    "XETR",
    "EURONEXT",
    "BIST",
)

PREFERRED_KINDS = {"stock": 20, "dr": 15, "fund": 10, "etf": 10}

# Ticker forması: AAPL, BRK.B, NASDAQ:AAPL. Buna uymayan mətn ad sayılır.
TICKER_RE = re.compile(r"^[A-Z0-9][A-Z0-9.\-]{0,9}(:[A-Z0-9.\-]{1,12})?$")


def looks_like_ticker(text: str) -> bool:
    return bool(TICKER_RE.match(text.strip().upper()))


@dataclass
class SymbolMatch:
    """TradingView və ya Yahoo axtarışından gələn bir uyğunluq."""

    symbol: str
    exchange: str
    description: str
    kind: str
    source: str

    @property
    def full(self) -> str:
        """TradingView-in qəbul etdiyi tam simvol: `NASDAQ:NVDA`."""

        return f"{self.exchange}:{self.symbol}" if self.exchange else self.symbol

    @property
    def label(self) -> str:
        name = self.description or self.symbol
        return f"{self.symbol} — {name}" + (f" ({self.exchange})" if self.exchange else "")


def rank(matches: list[SymbolMatch], query: str) -> list[SymbolMatch]:
    """Ən uyğun nəticə birinci olacaq şəkildə sıralayır və təkrarları atır."""

    query = query.strip().upper()
    seen: set[str] = set()
    unique: list[SymbolMatch] = []
    for match in matches:
        if not match.symbol or match.full in seen:
            continue
        seen.add(match.full)
        unique.append(match)

    def score(item: tuple[int, SymbolMatch]) -> tuple:
        index, match = item
        points = 0
        if match.symbol.upper() == query:
            points += 100
        elif query in match.symbol.upper():
            points += 30
        points += PREFERRED_KINDS.get(match.kind.lower(), 0)
        if match.exchange.upper() in MAJOR_EXCHANGES:
            points += 20 - MAJOR_EXCHANGES.index(match.exchange.upper())
        if _words(query) & _words(match.description):
            points += 15
        if match.source == "tradingview":
            points += 2
        return (-points, index)

    return [match for _, match in sorted(enumerate(unique), key=score)]


def _words(text: str) -> set[str]:
    return {word for word in re.split(r"[^A-Z0-9]+", text.upper()) if len(word) > 2}
