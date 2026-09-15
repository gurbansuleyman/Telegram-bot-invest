"""Yahoo Finance — xəbərlər və qiymət xülasəsi (TradingView üçün ehtiyat mənbə)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from .http import DEFAULT_TIMEOUT, SESSION

log = logging.getLogger(__name__)

SEARCH_URL = "https://query1.finance.yahoo.com/v1/finance/search"
CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"


@dataclass
class NewsItem:
    title: str
    publisher: str
    link: str
    published: datetime | None
    tickers: list[str]


@dataclass
class Snapshot:
    """Yahoo chart endpoint-indən hesablanan qiymət mənzərəsi."""

    symbol: str
    name: str
    price: float | None
    currency: str | None
    change_1d: float | None
    change_1w: float | None


def get_news(ticker: str, limit: int = 4) -> list[NewsItem]:
    """Simvol üzrə Yahoo Finance xəbərləri (ən yenidən köhnəyə)."""

    params = {
        "q": ticker,
        "quotesCount": 0,
        "newsCount": max(limit * 2, limit),
        "enableFuzzyQuery": "false",
    }
    try:
        response = SESSION.get(SEARCH_URL, params=params, timeout=DEFAULT_TIMEOUT)
        response.raise_for_status()
        raw_items = response.json().get("news", [])
    except Exception as exc:
        log.warning("Yahoo xəbərləri alınmadı (%s): %s", ticker, exc)
        return []

    items: list[NewsItem] = []
    for raw in raw_items:
        title = str(raw.get("title", "")).strip()
        link = str(raw.get("link", "")).strip()
        if not title or not link:
            continue
        items.append(
            NewsItem(
                title=title,
                publisher=str(raw.get("publisher", "")).strip(),
                link=link,
                published=_as_datetime(raw.get("providerPublishTime")),
                tickers=[str(t).upper() for t in raw.get("relatedTickers", []) or []],
            )
        )

    items.sort(key=lambda item: item.published or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return items[:limit]


def get_snapshot(ticker: str) -> Snapshot | None:
    """TradingView cavab vermədikdə istifadə olunan ehtiyat qiymət mənbəyi."""

    params = {"range": "1mo", "interval": "1d"}
    try:
        response = SESSION.get(
            CHART_URL.format(symbol=ticker), params=params, timeout=DEFAULT_TIMEOUT
        )
        response.raise_for_status()
        result = response.json()["chart"]["result"][0]
    except Exception as exc:
        log.warning("Yahoo chart alınmadı (%s): %s", ticker, exc)
        return None

    meta = result.get("meta", {})
    closes = [
        value
        for value in result.get("indicators", {}).get("quote", [{}])[0].get("close", [])
        if isinstance(value, (int, float))
    ]

    price = _as_float(meta.get("regularMarketPrice")) or (closes[-1] if closes else None)
    prev_close = _as_float(meta.get("chartPreviousClose")) or (
        closes[-2] if len(closes) > 1 else None
    )
    # Bir həftə ≈ 5 ticarət günü.
    week_ago = closes[-6] if len(closes) >= 6 else (closes[0] if closes else None)

    return Snapshot(
        symbol=ticker.upper(),
        name=str(meta.get("longName") or meta.get("shortName") or ticker.upper()),
        price=price,
        currency=meta.get("currency"),
        change_1d=_percent(price, prev_close),
        change_1w=_percent(price, week_ago),
    )


def _percent(current: float | None, base: float | None) -> float | None:
    if current is None or not base:
        return None
    return (current - base) / base * 100


def _as_float(value) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _as_datetime(value) -> datetime | None:
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    return None
