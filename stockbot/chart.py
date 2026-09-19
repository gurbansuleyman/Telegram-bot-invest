"""30 günlük qiymət qrafikini PNG kimi çəkir.

matplotlib quraşdırılmayıbsa və ya tarixçə yoxdursa, `None` qaytarır —
bot həmin halda yalnız mətn göndərir.
"""

from __future__ import annotations

import io
import logging
from datetime import date

from .history import Candle
from .http import DEFAULT_TIMEOUT, SESSION

log = logging.getLogger(__name__)

# Tarixçə heç bir mənbədən gəlmirsə, hazır qrafik şəkli sonuncu şansdır.
FINVIZ_URL = "https://charts2.finviz.com/chart.ashx"
FINVIZ_HEADERS = {"Referer": "https://finviz.com/", "Accept": "image/png,*/*"}
PNG_MAGIC = b"\x89PNG"

# dataviz palitrası: səth, mətn və status rəngləri.
SURFACE = "#fcfcfb"
TEXT_PRIMARY = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
GRID = "#e4e3df"
UP = "#0ca30c"
DOWN = "#d03b3b"

MIN_POINTS = 5


def render(
    ticker: str,
    name: str,
    candles: list[Candle],
    change_pct: float | None,
    currency: str | None = None,
    price: float | None = None,
) -> bytes | None:
    """Bağlanış qiymətlərinin sahə qrafiki. Uğursuzluqda `None`."""

    if len(candles) < MIN_POINTS:
        return None

    candles = _with_live_price(candles, price)

    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.dates as mdates
        import matplotlib.pyplot as plt
    except ImportError:
        log.info("matplotlib yoxdur — qrafik əvəzinə yalnız mətn göndərilir")
        return None

    days = [candle.day for candle in candles]
    closes = [candle.close for candle in candles]
    rising = (change_pct or 0) >= 0
    color = UP if rising else DOWN

    figure, axes = plt.subplots(figsize=(9, 4.2), dpi=110)
    figure.patch.set_facecolor(SURFACE)
    axes.set_facecolor(SURFACE)

    axes.plot(days, closes, color=color, linewidth=2, solid_capstyle="round")
    axes.fill_between(days, closes, min(closes), color=color, alpha=0.10, linewidth=0)

    # Yalnız son nöqtə işarələnir və birbaşa etiketlənir.
    axes.scatter(
        days[-1], closes[-1], s=64, color=color, zorder=3,
        edgecolors=SURFACE, linewidths=2,
    )
    axes.annotate(
        f"{closes[-1]:,.2f}",
        xy=(days[-1], closes[-1]),
        xytext=(8, 0),
        textcoords="offset points",
        va="center",
        fontsize=11,
        fontweight="bold",
        color=TEXT_PRIMARY,
    )

    _style_axes(axes, mdates, days, closes)
    _add_titles(axes, ticker, name, closes[-1], change_pct, currency, rising, color)

    figure.tight_layout()
    buffer = io.BytesIO()
    figure.savefig(buffer, format="png", facecolor=SURFACE)
    plt.close(figure)
    return buffer.getvalue()


def remote_image(ticker: str) -> bytes | None:
    """Finviz-in hazır günlük qrafiki — öz tarixçəmiz olmayanda.

    Şəkil bizim palitrada deyil, amma boş mətndən yaxşıdır.
    """

    symbol = ticker.split(":")[-1].upper()
    try:
        response = SESSION.get(
            FINVIZ_URL,
            params={"t": symbol, "ty": "c", "ta": "0", "p": "d", "s": "l"},
            headers=FINVIZ_HEADERS,
            timeout=DEFAULT_TIMEOUT,
        )
        response.raise_for_status()
    except Exception as exc:
        log.warning("Finviz qrafiki alınmadı (%s): %s", symbol, exc)
        return None

    if not response.content.startswith(PNG_MAGIC):
        log.warning("Finviz PNG qaytarmadı (%s)", symbol)
        return None
    return response.content


def _with_live_price(candles: list[Candle], price: float | None) -> list[Candle]:
    """Tarixçə dünənlə bitir; canlı qiyməti son nöqtə kimi əlavə edirik.

    Beləliklə qrafikdəki rəqəm altyazıdakı qiymətlə üst-üstə düşür.
    """

    if price is None:
        return candles

    today = date.today()
    if candles[-1].day >= today:
        return candles[:-1] + [Candle(day=candles[-1].day, close=price)]
    return candles + [Candle(day=today, close=price)]


def _style_axes(axes, mdates, days, closes) -> None:
    span = max(closes) - min(closes)
    padding = span * 0.12 if span else max(closes) * 0.01
    axes.set_ylim(min(closes) - padding, max(closes) + padding * 1.6)
    axes.set_xlim(days[0], days[-1])

    axes.grid(axis="y", color=GRID, linewidth=0.8)
    axes.set_axisbelow(True)
    for side in ("top", "right", "left"):
        axes.spines[side].set_visible(False)
    axes.spines["bottom"].set_color(GRID)

    axes.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=3, maxticks=5))
    axes.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    axes.tick_params(colors=TEXT_SECONDARY, labelsize=9, length=0)


def _add_titles(axes, ticker, name, price, change_pct, currency, rising, color) -> None:
    axes.set_title(
        f"{ticker} · {name}",
        loc="left",
        fontsize=13,
        fontweight="bold",
        color=TEXT_PRIMARY,
        pad=26,
    )

    # İstiqamət oxla və işarəli faizlə də verilir — yalnız rənglə deyil.
    arrow = "▲" if rising else "▼"
    change = f"{arrow} {change_pct:+.2f}%" if change_pct is not None else ""
    axes.text(
        0, 1.02,
        f"{price:,.2f} {currency or ''}".strip(),
        transform=axes.transAxes,
        fontsize=11,
        color=TEXT_SECONDARY,
        va="bottom",
    )
    if change:
        axes.text(
            1, 1.02, change,
            transform=axes.transAxes,
            fontsize=11,
            fontweight="bold",
            color=color,
            va="bottom",
            ha="right",
        )
