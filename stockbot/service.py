"""Mənbələri birləşdirən məntiq: TradingView qiymətləri + Yahoo xəbərləri."""

from __future__ import annotations

import logging

from . import formatting, yahoo
from .tradingview import Quote, TradingViewError, get_quotes
from .yahoo import NewsItem

log = logging.getLogger(__name__)

MAX_TICKERS = 15


def collect_quotes(tickers: list[str]) -> tuple[dict[str, Quote], dict[str, yahoo.Snapshot], list[str]]:
    """TradingView-dan gətirir; alınmayanları Yahoo ilə tamamlayır.

    Qaytarır: (tradingview nəticələri, yahoo ehtiyat nəticələri, heç bir yerdə tapılmayanlar)
    """

    tickers = [t.upper() for t in tickers][:MAX_TICKERS]
    try:
        quotes = get_quotes(tickers)
    except TradingViewError as exc:
        log.warning("TradingView əlçatmazdır, Yahoo-ya keçilir: %s", exc)
        quotes = {}

    fallbacks: dict[str, yahoo.Snapshot] = {}
    missing: list[str] = []
    for ticker in tickers:
        if ticker in quotes:
            continue
        snapshot = yahoo.get_snapshot(ticker)
        if snapshot and snapshot.price is not None:
            fallbacks[ticker] = snapshot
        else:
            missing.append(ticker)

    return quotes, fallbacks, missing


def quotes_report(tickers: list[str]) -> str:
    """`/s AAPL MSFT` üçün mətn: hər simvolun 1 günlük və 1 həftəlik vəziyyəti."""

    if not tickers:
        return "Simvol yazmalısan. Məsələn: <code>/s AAPL MSFT NVDA</code>"

    quotes, fallbacks, missing = collect_quotes(tickers)

    blocks: list[str] = []
    for ticker in [t.upper() for t in tickers][:MAX_TICKERS]:
        if ticker in quotes:
            blocks.append(formatting.format_quote(ticker, quotes[ticker]))
        elif ticker in fallbacks:
            blocks.append(formatting.format_snapshot(ticker, fallbacks[ticker]))

    if missing:
        blocks.append(f"<i>Tapılmadı: {', '.join(missing)}</i>")

    return "\n\n".join(blocks) if blocks else "Heç bir simvol üzrə məlumat alınmadı."


def news_report(tickers: list[str], limit: int) -> str:
    if not tickers:
        return "Simvol yazmalısan. Məsələn: <code>/xeber AAPL</code>"

    blocks = [
        formatting.format_news(ticker.upper(), yahoo.get_news(ticker, limit))
        for ticker in tickers[:MAX_TICKERS]
    ]
    return "\n\n".join(blocks)


def digest_report(tickers: list[str], news_limit: int, movers: int = 3) -> str:
    """İzləmə siyahısının xülasəsi + ən çox hərəkət edən kağızların xəbərləri."""

    if not tickers:
        return (
            "İzləmə siyahın boşdur. <code>/izle AAPL MSFT</code> ilə simvol əlavə et."
        )

    quotes, fallbacks, missing = collect_quotes(tickers)

    # Yahoo ehtiyat nəticələrini eyni cədvələ salırıq.
    merged: dict[str, Quote] = dict(quotes)
    for ticker, snapshot in fallbacks.items():
        merged[ticker] = Quote(
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

    top = _top_movers(merged, movers)
    news_by_ticker: dict[str, list[NewsItem]] = {
        ticker: yahoo.get_news(ticker, news_limit) for ticker in top
    }

    return formatting.format_digest(merged, missing, news_by_ticker)


def _top_movers(quotes: dict[str, Quote], count: int) -> list[str]:
    """Mütləq 1 günlük dəyişiminə görə ən çox hərəkət edən simvollar."""

    ranked = sorted(
        (t for t in quotes if quotes[t].change_1d is not None),
        key=lambda ticker: abs(quotes[ticker].change_1d or 0),
        reverse=True,
    )
    return ranked[:count]
