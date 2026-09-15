"""TradingView scanner API — 1 günlük və 1 həftəlik dəyişim."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from .http import DEFAULT_TIMEOUT, SESSION
from .symbols import SymbolMatch

log = logging.getLogger(__name__)

SCAN_URL = "https://scanner.tradingview.com/global/scan"
SEARCH_URL = "https://symbol-search.tradingview.com/symbol_search/"

COLUMNS = [
    "name",
    "description",
    "close",
    "currency",
    "change",
    "change_abs",
    "Perf.W",
    "Perf.1M",
    "Perf.YTD",
    "volume",
    "market_cap_basic",
    "exchange",
]


@dataclass
class Quote:
    """TradingView-dan gələn bir simvolun anlıq vəziyyəti."""

    symbol: str
    name: str
    description: str
    price: float | None
    currency: str | None
    change_1d: float | None
    change_1d_abs: float | None
    change_1w: float | None
    change_1m: float | None
    change_ytd: float | None
    volume: float | None
    market_cap: float | None
    exchange: str | None

    @property
    def display(self) -> str:
        return self.description or self.name


class TradingViewError(RuntimeError):
    pass


_symbol_cache: dict[str, str] = {}


def search_symbols(text: str, limit: int = 8) -> list[SymbolMatch]:
    """Ad və ya ticker üzrə axtarış: `nvidia` -> NVDA, `AAPL` -> NASDAQ:AAPL."""

    params = {
        "text": text.strip(),
        "hl": "false",
        "lang": "en",
        "domain": "production",
    }
    try:
        response = SESSION.get(SEARCH_URL, params=params, timeout=DEFAULT_TIMEOUT)
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        log.warning("TradingView axtarışı alınmadı (%s): %s", text, exc)
        return []

    if isinstance(payload, dict):  # API bəzən {"symbols": [...]} qaytarır
        payload = payload.get("symbols", [])

    matches: list[SymbolMatch] = []
    for raw in payload[:limit]:
        symbol = _strip_tags(raw.get("symbol", ""))
        if not symbol:
            continue
        matches.append(
            SymbolMatch(
                symbol=symbol.upper(),
                exchange=str(raw.get("exchange") or raw.get("prefix") or "").upper(),
                description=_strip_tags(raw.get("description", "")),
                kind=str(raw.get("type") or ""),
                source="tradingview",
            )
        )
    return matches


def _strip_tags(value) -> str:
    """Axtarış nəticəsi uyğun gələn hissəni <em> ilə işarələyir."""

    return re.sub(r"<[^>]+>", "", str(value or "")).strip()


def resolve_symbol(ticker: str) -> str:
    """`AAPL` -> `NASDAQ:AAPL`. Artıq tam formatda olan simvol toxunulmaz qalır."""

    ticker = ticker.strip().upper()
    if ":" in ticker:
        return ticker
    if ticker in _symbol_cache:
        return _symbol_cache[ticker]

    for match in search_symbols(ticker):
        if match.symbol.upper() == ticker:
            resolved = match.full.upper()
            _symbol_cache[ticker] = resolved
            return resolved

    # Tapılmadısa ən çox yayılmış birjanı sınayırıq; scan yenə boş qaytara bilər.
    fallback = f"NASDAQ:{ticker}"
    _symbol_cache[ticker] = fallback
    return fallback


def remember_symbol(ticker: str, full_symbol: str) -> None:
    """Ad axtarışından gələn nəticəni yaddaşa yazır ki, təkrar sorğu getməsin."""

    _symbol_cache[ticker.strip().upper()] = full_symbol.strip().upper()


def _cell(row: list, index: int) -> float | str | None:
    try:
        return row[index]
    except IndexError:
        return None


def get_quotes(tickers: list[str]) -> dict[str, Quote]:
    """Verilmiş simvollar üçün TradingView məlumatını gətirir.

    Nəticə açarları istifadəçinin yazdığı orijinal ticker-lərdir (böyük hərflə).
    """

    if not tickers:
        return {}

    wanted = [t.strip().upper() for t in tickers if t.strip()]
    resolved = {ticker: resolve_symbol(ticker) for ticker in wanted}

    payload = {
        "symbols": {"tickers": sorted(set(resolved.values())), "query": {"types": []}},
        "columns": COLUMNS,
    }

    try:
        response = SESSION.post(SCAN_URL, json=payload, timeout=DEFAULT_TIMEOUT)
        response.raise_for_status()
        data = response.json().get("data", [])
    except Exception as exc:
        raise TradingViewError(f"TradingView sorğusu alınmadı: {exc}") from exc

    by_symbol: dict[str, Quote] = {}
    for row in data:
        values = row.get("d", [])
        symbol = str(row.get("s", "")).upper()
        by_symbol[symbol] = Quote(
            symbol=symbol,
            name=str(_cell(values, 0) or symbol.split(":")[-1]),
            description=str(_cell(values, 1) or ""),
            price=_as_float(_cell(values, 2)),
            currency=_as_str(_cell(values, 3)),
            change_1d=_as_float(_cell(values, 4)),
            change_1d_abs=_as_float(_cell(values, 5)),
            change_1w=_as_float(_cell(values, 6)),
            change_1m=_as_float(_cell(values, 7)),
            change_ytd=_as_float(_cell(values, 8)),
            volume=_as_float(_cell(values, 9)),
            market_cap=_as_float(_cell(values, 10)),
            exchange=_as_str(_cell(values, 11)),
        )

    return {
        ticker: by_symbol[symbol]
        for ticker, symbol in resolved.items()
        if symbol in by_symbol
    }


def _as_float(value) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _as_str(value) -> str | None:
    if isinstance(value, str) and value:
        return value
    return None
