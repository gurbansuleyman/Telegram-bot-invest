"""Günlük qiymət tarixçəsi — qrafik çəkmək üçün.

Stooq açıq CSV verir: açar, cookie və limit yoxdur. Yahoo chart ehtiyatdır,
amma o, bəzi IP-ləri bloklayır.
"""

from __future__ import annotations

import csv
import io
import logging
import time
from dataclasses import dataclass
from datetime import date, datetime

from .http import DEFAULT_TIMEOUT, SESSION

log = logging.getLogger(__name__)

STOOQ_URL = "https://stooq.com/q/d/l/"
CACHE_SECONDS = 900

# Stooq simvolları birja şəkilçisi ilə işləyir.
EXCHANGE_SUFFIX = {
    "NASDAQ": "us",
    "NYSE": "us",
    "AMEX": "us",
    "NYSE ARCA": "us",
    "BATS": "us",
    "LSE": "uk",
    "XETR": "de",
}

_cache: dict[str, tuple[float, list["Candle"]]] = {}


@dataclass
class Candle:
    day: date
    close: float


def stooq_symbol(ticker: str, exchange: str | None = None) -> str:
    """`NVDA` + `NASDAQ` -> `nvda.us`. Şəkilçi bilinmirsə ABŞ götürülür."""

    symbol = ticker.split(":")[-1].strip().lower()
    suffix = EXCHANGE_SUFFIX.get((exchange or "").upper(), "us")
    return f"{symbol}.{suffix}"


def daily_closes(
    ticker: str, exchange: str | None = None, days: int = 30
) -> list[Candle]:
    """Son `days` ticarət gününün bağlanış qiymətləri (köhnədən yeniyə)."""

    symbol = stooq_symbol(ticker, exchange)
    cached = _cache.get(symbol)
    if cached and time.monotonic() - cached[0] < CACHE_SECONDS:
        return cached[1][-days:]

    try:
        response = SESSION.get(
            STOOQ_URL, params={"s": symbol, "i": "d"}, timeout=DEFAULT_TIMEOUT
        )
        response.raise_for_status()
    except Exception as exc:
        log.warning("Stooq tarixçəsi alınmadı (%s): %s", symbol, exc)
        return []

    candles = _parse_csv(response.text, symbol)
    if candles:
        _cache[symbol] = (time.monotonic(), candles)
    return candles[-days:]


def _parse_csv(payload: str, symbol: str) -> list[Candle]:
    reader = csv.DictReader(io.StringIO(payload))
    if not reader.fieldnames or "Close" not in reader.fieldnames:
        # Simvol tapılmayanda Stooq CSV yerinə mətn qaytarır.
        log.warning("Stooq cavabı CSV deyil (%s): %s", symbol, payload[:60].strip())
        return []

    candles: list[Candle] = []
    for row in reader:
        try:
            candles.append(
                Candle(
                    day=datetime.strptime(row["Date"], "%Y-%m-%d").date(),
                    close=float(row["Close"]),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return candles
