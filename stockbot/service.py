"""Mənbələri birləşdirən məntiq: TradingView qiymətləri + Yahoo xəbərləri."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from html import escape

from . import chart, formatting, history, news, tradingview, yahoo
from .symbols import SymbolMatch, looks_like_ticker, rank
from .tradingview import Quote, TradingViewError, get_quotes
from .news import NewsItem
from .yahoo import Snapshot

log = logging.getLogger(__name__)

MAX_TICKERS = 15


@dataclass
class Entry:
    """Bir sorğunun nəticəsi: istifadəçinin yazdığı mətn + tapılan məlumat."""

    query: str
    ticker: str
    quote: Quote | None = None
    snapshot: Snapshot | None = None

    @property
    def found(self) -> bool:
        return self.quote is not None or self.snapshot is not None


def resolve_query(query: str, limit: int = 6) -> list[SymbolMatch]:
    """Ad və ya ticker üzrə uyğunluqlar — ən yaxşısı birinci.

    Əvvəl TradingView axtarışı, o cavab verməsə Yahoo axtarışı işləyir.
    """

    query = query.strip()
    if not query:
        return []

    matches = tradingview.search_symbols(query, limit)
    if not matches:
        matches = yahoo.search_symbols(query, limit)
    return rank(matches, query)[:limit]


def find_symbol(query: str) -> tuple[SymbolMatch | None, list[SymbolMatch]]:
    """İzləmə siyahısına salmazdan əvvəl simvolu təsdiqləyir.

    Qaytarır: (ən uyğun nəticə və ya None, digər ehtimallar).
    """

    query = query.strip().upper()
    if not query:
        return None, []

    if ":" in query:  # İstifadəçi birjanı özü yazıb — birbaşa yoxlayırıq.
        try:
            found = get_quotes([query])
        except TradingViewError:
            found = {}
        quote = found.get(query)
        if not quote:
            return None, []
        exchange, _, symbol = query.partition(":")
        return (
            SymbolMatch(
                symbol=symbol,
                exchange=exchange,
                description=quote.display,
                kind="stock",
                source="tradingview",
            ),
            [],
        )

    matches = resolve_query(query, limit=4)
    if not matches:
        return None, []
    return matches[0], matches[1:]


def collect(queries: list[str]) -> tuple[list[Entry], list[str]]:
    """Sorğuları qiymət məlumatına çevirir; tapılmayanları ayrıca qaytarır."""

    queries = [q.strip().upper() for q in queries if q.strip()][:MAX_TICKERS]
    if not queries:
        return [], []

    direct = [q for q in queries if looks_like_ticker(q)]
    try:
        quotes = get_quotes(direct) if direct else {}
    except TradingViewError as exc:
        log.warning("TradingView əlçatmazdır, Yahoo-ya keçilir: %s", exc)
        quotes = {}

    entries: list[Entry] = []
    missing: list[str] = []
    for query in queries:
        entry = Entry(query=query, ticker=query, quote=quotes.get(query))
        if entry.found:
            entries.append(entry)
            continue

        resolved = _resolve_one(query)
        if resolved.found:
            entries.append(resolved)
        else:
            missing.append(query)

    return entries, missing


def _resolve_one(query: str) -> Entry:
    """Tək sorğu üçün bütün yolları sınayır: ad axtarışı, sonra Yahoo qiyməti."""

    # 1) Ad və ya tanınmayan ticker — axtarışla dəqiq simvolu tapırıq.
    for match in resolve_query(query, limit=3):
        try:
            found = get_quotes([match.full])
        except TradingViewError:
            found = {}
        if match.full in found:
            tradingview.remember_symbol(match.symbol, match.full)
            return Entry(query=query, ticker=match.symbol, quote=found[match.full])

    # 2) TradingView susursa, Yahoo-nun öz qiymətinə keçirik.
    snapshot = yahoo.get_snapshot(query)
    if snapshot and snapshot.price is not None:
        return Entry(query=query, ticker=query, snapshot=snapshot)

    return Entry(query=query, ticker=query)


def quote_card(query: str, exchange: str | None = None) -> tuple[str, bytes | None]:
    """Bir simvolun qiymət mətni və 30 günlük qrafiki.

    Qrafik tarixçə tapılmasa və ya matplotlib yoxdursa `None` olur —
    o halda yalnız mətn göndərilir.
    """

    entries, _ = collect([query])
    if not entries:
        return f"<i>Tapılmadı: {escape(query)}</i>", None

    entry = entries[0]
    if entry.quote:
        text = formatting.format_quote(entry.ticker, entry.quote)
        name = entry.quote.display
        change = entry.quote.change_1d
        currency = entry.quote.currency
        exchange = exchange or entry.quote.exchange
    else:
        snapshot = entry.snapshot
        text = formatting.format_snapshot(entry.ticker, snapshot)
        name = snapshot.name
        change = snapshot.change_1d
        currency = snapshot.currency

    candles = history.daily_closes(entry.ticker, exchange)
    price = entry.quote.price if entry.quote else entry.snapshot.price
    png = chart.render(entry.ticker, name, candles, change, currency, price)
    if png is None:
        png = chart.remote_image(entry.ticker)
    return text, png


def quotes_report(queries: list[str]) -> str:
    """`/s AAPL nvidia` üçün mətn: hər simvolun 1 günlük və 1 həftəlik vəziyyəti."""

    if not queries:
        return "Simvol yazmalısan. Məsələn: <code>/s AAPL MSFT NVDA</code>"

    entries, missing = collect(queries)

    blocks: list[str] = []
    for entry in entries:
        if entry.quote:
            blocks.append(formatting.format_quote(entry.ticker, entry.quote))
        elif entry.snapshot:
            blocks.append(formatting.format_snapshot(entry.ticker, entry.snapshot))

    if missing:
        blocks.append(f"<i>Tapılmadı: {', '.join(missing)}</i>")

    return "\n\n".join(blocks) if blocks else "Heç bir simvol üzrə məlumat alınmadı."


def news_report(queries: list[str], limit: int, max_age_days: int = 3) -> str:
    if not queries:
        return "Simvol yazmalısan. Məsələn: <code>/xeber AAPL</code>"

    blocks = []
    for query in queries[:MAX_TICKERS]:
        ticker = query.upper()
        if not looks_like_ticker(ticker):
            matches = resolve_query(query, limit=1)
            if matches:
                ticker = matches[0].symbol
        items = news.get_news(ticker, limit, max_age_days)
        blocks.append(formatting.format_news(ticker, items, max_age_days))
    return "\n\n".join(blocks)


def digest_report(
    tickers: list[str],
    news_limit: int,
    movers: int = 3,
    max_age_days: int = 3,
) -> str:
    """İzləmə siyahısının xülasəsi + ən çox hərəkət edən kağızların xəbərləri."""

    if not tickers:
        return "İzləmə siyahın boşdur. <code>/izle AAPL MSFT</code> ilə simvol əlavə et."

    entries, missing = collect(tickers)

    merged: dict[str, Quote] = {}
    for entry in entries:
        if entry.quote:
            merged[entry.ticker] = entry.quote
        elif entry.snapshot:
            merged[entry.ticker] = _as_quote(entry.snapshot)

    top = _top_movers(merged, movers)
    news_by_ticker: dict[str, list[NewsItem]] = {
        ticker: news.get_news(ticker, news_limit, max_age_days) for ticker in top
    }

    return formatting.format_digest(merged, missing, news_by_ticker, max_age_days)


def _as_quote(snapshot: Snapshot) -> Quote:
    """Yahoo nəticəsini eyni cədvəldə göstərmək üçün Quote formasına salır."""

    return Quote(
        symbol=snapshot.symbol,
        name=snapshot.symbol,
        description=snapshot.name,
        price=snapshot.price,
        currency=snapshot.currency,
        change_1d=snapshot.change_1d,
        change_1d_abs=None,
        change_1w=snapshot.change_1w,
        change_1m=None,
        change_ytd=None,
        volume=None,
        market_cap=None,
        exchange="Yahoo",
    )


def _top_movers(quotes: dict[str, Quote], count: int) -> list[str]:
    """Mütləq 1 günlük dəyişiminə görə ən çox hərəkət edən simvollar."""

    ranked = sorted(
        (t for t in quotes if quotes[t].change_1d is not None),
        key=lambda ticker: abs(quotes[ticker].change_1d or 0),
        reverse=True,
    )
    return ranked[:count]
