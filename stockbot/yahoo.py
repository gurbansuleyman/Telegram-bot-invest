"""Yahoo Finance — xəbərlər və qiymət xülasəsi (TradingView üçün ehtiyat mənbə)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from .http import DEFAULT_TIMEOUT, SESSION, YAHOO_HEADERS
from .symbols import SymbolMatch

log = logging.getLogger(__name__)

SEARCH_URL = "https://query2.finance.yahoo.com/v1/finance/search"
CHART_URL = "https://query2.finance.yahoo.com/v8/finance/chart/{symbol}"
COOKIE_URLS = ("https://fc.yahoo.com", "https://finance.yahoo.com")
CRUMB_URL = "https://query2.finance.yahoo.com/v1/test/getcrumb"

_crumb: str | None = None
_crumb_tried = False


def _ensure_crumb() -> str | None:
    """Yahoo cookie + crumb tələb edir; onsuz sorğular 429/401 qaytarır.

    Bir dəfə alınır, sonra sessiyada saxlanılır.
    """

    global _crumb, _crumb_tried
    if _crumb or _crumb_tried:
        return _crumb

    _crumb_tried = True
    for url in COOKIE_URLS:
        try:
            # Cavab 404 ola bilər — bizə lazım olan yalnız qoyduğu cookie-dir.
            SESSION.get(url, headers=YAHOO_HEADERS, timeout=DEFAULT_TIMEOUT)
        except Exception as exc:
            log.debug("Yahoo cookie alınmadı (%s): %s", url, exc)
            continue

        try:
            response = SESSION.get(
                CRUMB_URL, headers=YAHOO_HEADERS, timeout=DEFAULT_TIMEOUT
            )
            crumb = response.text.strip()
        except Exception as exc:
            log.debug("Yahoo crumb alınmadı: %s", exc)
            continue

        if response.ok and crumb and "<" not in crumb:
            _crumb = crumb
            log.info("Yahoo sessiyası hazırdır")
            return _crumb

    log.warning("Yahoo crumb alınmadı — sorğular limitə düşə bilər")
    return None


def reset_session() -> None:
    """Crumb köhnəldikdə yenidən almağa imkan verir."""

    global _crumb, _crumb_tried
    _crumb = None
    _crumb_tried = False


def _get(url: str, params: dict, what: str) -> dict | None:
    """Yahoo sorğusu: crumb əlavə edir, 429-u ayrıca bildirir."""

    crumb = _ensure_crumb()
    if crumb:
        params = {**params, "crumb": crumb}

    try:
        response = SESSION.get(
            url, params=params, headers=YAHOO_HEADERS, timeout=DEFAULT_TIMEOUT
        )
    except Exception as exc:
        log.warning("%s alınmadı: %s", what, exc)
        return None

    if response.status_code == 429:
        log.warning("%s: Yahoo limit qoydu (429) — bir azdan yenidən yoxla", what)
        return None
    if response.status_code in (401, 403):
        # Crumb köhnəlib; növbəti sorğuda yenisini alacağıq.
        reset_session()
        log.warning("%s: Yahoo icazə vermədi (%s)", what, response.status_code)
        return None

    try:
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        log.warning("%s cavabı oxunmadı: %s", what, exc)
        return None


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
    prev_close: float | None = None
    week_ago: float | None = None


def search_symbols(text: str, limit: int = 8) -> list[SymbolMatch]:
    """TradingView axtarışı cavab verməyəndə ehtiyat ad/ticker axtarışı."""

    params = {"q": text.strip(), "quotesCount": limit, "newsCount": 0}
    body = _get(SEARCH_URL, params, f"Yahoo axtarışı ({text})")
    if not body:
        return []
    quotes = body.get("quotes", [])

    matches: list[SymbolMatch] = []
    for raw in quotes[:limit]:
        symbol = str(raw.get("symbol", "")).strip()
        if not symbol:
            continue
        matches.append(
            SymbolMatch(
                symbol=symbol.upper(),
                exchange=str(raw.get("exchDisp") or raw.get("exchange") or "").upper(),
                description=str(raw.get("longname") or raw.get("shortname") or "").strip(),
                kind=str(raw.get("quoteType") or "").lower(),
                source="yahoo",
            )
        )
    return matches


def get_news(ticker: str, limit: int = 4) -> list[NewsItem]:
    """Simvol üzrə Yahoo Finance xəbərləri (ən yenidən köhnəyə)."""

    params = {
        "q": ticker,
        "quotesCount": 0,
        "newsCount": max(limit * 2, limit),
        "enableFuzzyQuery": "false",
    }
    body = _get(SEARCH_URL, params, f"Yahoo xəbərləri ({ticker})")
    if not body:
        return []
    raw_items = body.get("news", [])

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
    body = _get(CHART_URL.format(symbol=ticker), params, f"Yahoo chart ({ticker})")
    try:
        result = body["chart"]["result"][0]
    except (TypeError, KeyError, IndexError):
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
        prev_close=prev_close,
        week_ago=week_ago,
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
