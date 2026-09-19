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
from datetime import date, datetime, timezone

from .http import DEFAULT_TIMEOUT, SESSION

log = logging.getLogger(__name__)

# Stooq eyni CSV-ni iki domendə verir; biri anti-bot səhifəsi qaytara bilər.
STOOQ_URLS = ("https://stooq.com/q/d/l/", "https://stooq.pl/q/d/l/")
STOOQ_HEADERS = {
    "Accept": "text/csv,text/plain,*/*",
    "Referer": "https://stooq.com/",
}
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
    """Son `days` ticarət gününün bağlanış qiymətləri (köhnədən yeniyə).

    Mənbələr növbə ilə sınanır: Stooq-un iki domeni, sonra Yahoo chart.
    Hamısı susarsa boş siyahı qayıdır və bot qrafiksiz mətn göndərir.
    """

    symbol = stooq_symbol(ticker, exchange)
    cached = _cache.get(symbol)
    if cached and time.monotonic() - cached[0] < CACHE_SECONDS:
        return cached[1][-days:]

    candles = _from_stooq(symbol) or _from_yahoo(ticker)
    if candles:
        _cache[symbol] = (time.monotonic(), candles)
    return candles[-days:]


def _from_stooq(symbol: str) -> list[Candle]:
    for url in STOOQ_URLS:
        try:
            response = SESSION.get(
                url,
                params={"s": symbol, "i": "d"},
                headers=STOOQ_HEADERS,
                timeout=DEFAULT_TIMEOUT,
            )
            response.raise_for_status()
        except Exception as exc:
            log.warning("Stooq alınmadı (%s, %s): %s", symbol, url, exc)
            continue

        candles = _parse_csv(response.text, symbol)
        if candles:
            return candles
    return []


def _from_yahoo(ticker: str) -> list[Candle]:
    """Stooq susanda ehtiyat mənbə — Yahoo bağlı deyilsə işləyir."""

    from . import yahoo  # dairəvi idxaldan qaçmaq üçün burada

    pairs = yahoo.daily_closes(ticker.split(":")[-1])
    return [
        Candle(day=datetime.fromtimestamp(stamp, tz=timezone.utc).date(), close=close)
        for stamp, close in pairs
    ]


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
