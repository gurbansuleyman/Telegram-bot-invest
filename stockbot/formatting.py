"""Telegram mesajlarının HTML formatlaşdırılması."""

from __future__ import annotations

from datetime import datetime, timezone
from html import escape

from .tradingview import Quote
from .yahoo import NewsItem, Snapshot

UP = "🟢"
DOWN = "🔴"
FLAT = "⚪️"


def pct(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:+.2f}%"


def marker(value: float | None) -> str:
    if value is None:
        return FLAT
    if value > 0.05:
        return UP
    if value < -0.05:
        return DOWN
    return FLAT


def money(value: float | None, currency: str | None = None) -> str:
    if value is None:
        return "—"
    text = f"{value:,.2f}"
    return f"{text} {currency}" if currency else text


def compact(value: float | None) -> str:
    """1_234_567 -> 1.23M"""

    if value is None:
        return "—"
    for limit, suffix in ((1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")):
        if abs(value) >= limit:
            return f"{value / limit:.2f}{suffix}"
    return f"{value:,.0f}"


def format_quote(ticker: str, quote: Quote) -> str:
    exchange = f" · {escape(quote.exchange)}" if quote.exchange else ""
    lines = [
        f"{marker(quote.change_1d)} <b>{escape(ticker)}</b> — {escape(quote.display)}{exchange}",
        f"Qiymət: <b>{money(quote.price, quote.currency)}</b>",
        f"1 gün: <b>{pct(quote.change_1d)}</b>",
        f"1 həftə: <b>{pct(quote.change_1w)}</b>",
    ]
    if quote.change_1m is not None:
        lines.append(f"1 ay: {pct(quote.change_1m)}")
    if quote.volume is not None:
        lines.append(f"Həcm: {compact(quote.volume)}")
    if quote.market_cap is not None:
        lines.append(f"Kapitallaşma: {compact(quote.market_cap)}")
    return "\n".join(lines)


def format_snapshot(ticker: str, snapshot: Snapshot) -> str:
    return "\n".join(
        [
            f"{marker(snapshot.change_1d)} <b>{escape(ticker)}</b> — {escape(snapshot.name)} · Yahoo",
            f"Qiymət: <b>{money(snapshot.price, snapshot.currency)}</b>",
            f"1 gün: <b>{pct(snapshot.change_1d)}</b>",
            f"1 həftə: <b>{pct(snapshot.change_1w)}</b>",
        ]
    )


def format_news(ticker: str, items: list[NewsItem]) -> str:
    if not items:
        return f"📰 <b>{escape(ticker)}</b> üzrə yeni xəbər tapılmadı."

    lines = [f"📰 <b>{escape(ticker)}</b> — Yahoo Finance xəbərləri"]
    for item in items:
        meta = " · ".join(
            part for part in (escape(item.publisher), _ago(item.published)) if part
        )
        lines.append(f"• <a href=\"{escape(item.link, quote=True)}\">{escape(item.title)}</a>")
        if meta:
            lines.append(f"  <i>{meta}</i>")
    return "\n".join(lines)


def format_digest(
    quotes: dict[str, Quote],
    missing: list[str],
    news_by_ticker: dict[str, list[NewsItem]],
) -> str:
    """İzləmə siyahısının xülasəsi + ən çox hərəkət edən kağızların xəbərləri."""

    now = datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M UTC")
    lines = [f"🗞 <b>Gündəlik xülasə</b> · {now}", ""]

    ranked = sorted(
        quotes.items(),
        key=lambda pair: pair[1].change_1d if pair[1].change_1d is not None else 0,
        reverse=True,
    )
    for ticker, quote in ranked:
        lines.append(
            f"{marker(quote.change_1d)} <b>{escape(ticker)}</b>  "
            f"{money(quote.price, quote.currency)}  "
            f"1g {pct(quote.change_1d)} · 1h {pct(quote.change_1w)}"
        )

    if missing:
        lines.append("")
        lines.append(f"<i>Tapılmadı: {escape(', '.join(missing))}</i>")

    if news_by_ticker:
        lines.append("")
        lines.append("<b>Önəmli xəbərlər</b>")
        for ticker, items in news_by_ticker.items():
            if not items:
                continue
            lines.append("")
            lines.append(format_news(ticker, items))

    return "\n".join(lines)


def _ago(moment: datetime | None) -> str:
    if moment is None:
        return ""
    delta = datetime.now(timezone.utc) - moment
    minutes = int(delta.total_seconds() // 60)
    if minutes < 1:
        return "indicə"
    if minutes < 60:
        return f"{minutes} dəq əvvəl"
    hours = minutes // 60
    if hours < 24:
        return f"{hours} saat əvvəl"
    return f"{hours // 24} gün əvvəl"
