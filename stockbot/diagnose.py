"""Məlumat mənbələrini bir-bir yoxlayır: `python -m stockbot.diagnose`

Bot boş cavab verəndə səbəbin hansı API-də olduğunu göstərir.
Token və ya .env lazım deyil — yalnız xarici sorğular yoxlanılır.
"""

from __future__ import annotations

import json
import logging

from . import chart, history, news, tradingview, yahoo
import requests

from .http import (
    DEFAULT_TIMEOUT,
    SESSION,
    TRADINGVIEW_HEADERS,
    USER_AGENT,
    YAHOO_HEADERS,
)

OK = "✅"
FAIL = "❌"


def _line(name: str, ok: bool, detail: str) -> None:
    print(f"{OK if ok else FAIL} {name}: {detail}")


def _excerpt(text: str, limit: int = 160) -> str:
    text = " ".join(text.split())
    return text[:limit] + ("…" if len(text) > limit else "")


def check_tradingview_scan() -> bool:
    """Əsas qiymət mənbəyi — bot bunsuz qiymət göstərə bilmir."""

    payload = {
        "symbols": {"tickers": ["NASDAQ:AAPL"], "query": {"types": []}},
        "columns": ["name", "close", "change", "Perf.W"],
    }
    try:
        response = SESSION.post(
            tradingview.SCAN_URL,
            json=payload,
            headers=TRADINGVIEW_HEADERS,
            timeout=DEFAULT_TIMEOUT,
        )
    except Exception as exc:
        _line("TradingView scanner", False, f"bağlantı alınmadı: {exc}")
        return False

    if not response.ok:
        _line(
            "TradingView scanner",
            False,
            f"HTTP {response.status_code} — {_excerpt(response.text)}",
        )
        return False

    data = response.json().get("data", [])
    if not data:
        _line("TradingView scanner", False, f"boş cavab: {_excerpt(response.text)}")
        return False

    _line("TradingView scanner", True, f"AAPL → {json.dumps(data[0]['d'])}")
    return True


def check_tradingview_search() -> bool:
    """Ad → ticker çevirməsi (`/izle nvidia` bundan asılıdır)."""

    try:
        response = SESSION.get(
            tradingview.SEARCH_URL,
            params={"text": "nvidia", "hl": "false", "lang": "en", "domain": "production"},
            headers=TRADINGVIEW_HEADERS,
            timeout=DEFAULT_TIMEOUT,
        )
    except Exception as exc:
        _line("TradingView axtarış", False, f"bağlantı alınmadı: {exc}")
        return False

    if not response.ok:
        _line(
            "TradingView axtarış",
            False,
            f"HTTP {response.status_code} — {_excerpt(response.text)}",
        )
        return False

    matches = tradingview.search_symbols("nvidia", 3)
    if not matches:
        _line("TradingView axtarış", False, f"uyğunluq yoxdur: {_excerpt(response.text)}")
        return False

    _line("TradingView axtarış", True, ", ".join(m.full for m in matches))
    return True


def check_yahoo_header_variants() -> None:
    """429-un səbəbini ayırd edir: IP blokudur, yoxsa göndərdiyimiz başlıqlar?

    Üç variant sınanır. Hamısı 429 olsa — Yahoo bu IP-ni bloklayıb.
    Yalnız birincisi 429 olsa — günahkar bizim başlıqlarımızdır.
    """

    variants = {
        "botun başlıqları": {**SESSION.headers, **YAHOO_HEADERS},
        "sadə brauzer UA": {"User-Agent": USER_AGENT, "Accept": "*/*"},
        "başlıqsız": {"User-Agent": "curl/8.0"},
    }
    print("   Yahoo RSS başlıq testi:")
    for name, headers in variants.items():
        try:
            response = requests.get(
                yahoo.RSS_URL,
                params={"s": "AAPL", "region": "US", "lang": "en-US"},
                headers=headers,
                timeout=DEFAULT_TIMEOUT,
            )
            print(f"     • {name}: HTTP {response.status_code}")
        except Exception as exc:
            print(f"     • {name}: bağlantı alınmadı ({type(exc).__name__})")


def check_google_news() -> bool:
    """Yahoo bağlı olanda xəbərlərin gəldiyi yol."""

    items = news.google_news("AAPL", 3)
    if not items:
        _line("Google News", False, "boş cavab")
        return False
    _line(
        "Google News",
        True,
        f"{len(items)} xəbər — {_excerpt(items[0].title, 55)} ({items[0].publisher})",
    )
    return True


def check_yahoo_crumb() -> bool:
    yahoo.reset_session()
    crumb = yahoo._ensure_crumb()
    if not crumb:
        _line("Yahoo crumb", False, "alınmadı — xəbərlər 429 verə bilər")
        return False
    _line("Yahoo crumb", True, f"{crumb[:4]}… (cookie qoyuldu)")
    return True


def check_yahoo_rss() -> bool:
    """Xəbərlərin əsas mənbəyi — crumb tələb etmir."""

    try:
        response = SESSION.get(
            yahoo.RSS_URL,
            params={"s": "AAPL", "region": "US", "lang": "en-US"},
            headers=YAHOO_HEADERS,
            timeout=DEFAULT_TIMEOUT,
        )
    except Exception as exc:
        _line("Yahoo RSS", False, f"bağlantı alınmadı: {exc}")
        return False

    if not response.ok:
        _line("Yahoo RSS", False, f"HTTP {response.status_code} — {_excerpt(response.text)}")
        return False

    items = yahoo.get_news_rss("AAPL", 3)
    if not items:
        _line("Yahoo RSS", False, f"boş axın: {_excerpt(response.text)}")
        return False

    _line("Yahoo RSS", True, f"{len(items)} xəbər — {_excerpt(items[0].title, 60)}")
    return True


def check_yahoo_news() -> bool:
    try:
        response = SESSION.get(
            yahoo.SEARCH_URL,
            params={"q": "AAPL", "quotesCount": 0, "newsCount": 3},
            headers=YAHOO_HEADERS,
            timeout=DEFAULT_TIMEOUT,
        )
    except Exception as exc:
        _line("Yahoo xəbərlər", False, f"bağlantı alınmadı: {exc}")
        return False

    if not response.ok:
        _line(
            "Yahoo xəbərlər",
            False,
            f"HTTP {response.status_code} — {_excerpt(response.text)}",
        )
        return False

    items = yahoo.get_news("AAPL", 3)
    if not items:
        _line("Yahoo xəbərlər", False, f"boş siyahı: {_excerpt(response.text)}")
        return False

    _line("Yahoo xəbərlər", True, f"{len(items)} xəbər — {_excerpt(items[0].title, 60)}")
    return True


def check_yahoo_chart() -> bool:
    snapshot = yahoo.get_snapshot("AAPL")
    if not snapshot or snapshot.price is None:
        _line("Yahoo chart", False, "qiymət alınmadı (ehtiyat mənbə işləmir)")
        return False
    _line("Yahoo chart", True, f"AAPL {snapshot.price:.2f} {snapshot.currency or ''}")
    return True


def check_history() -> bool:
    """Qrafiklər üçün günlük tarixçə (Stooq)."""

    candles = history.daily_closes("AAPL", "NASDAQ")
    if len(candles) < chart.MIN_POINTS:
        _line("Stooq tarixçəsi", False, f"{len(candles)} gün — qrafik çəkilməyəcək")
        return False
    _line(
        "Stooq tarixçəsi",
        True,
        f"{len(candles)} gün, son bağlanış {candles[-1].close:,.2f}"
        f" ({candles[-1].day})",
    )
    return True


def check_chart() -> bool:
    """matplotlib quraşdırılıbmı — şəkil çəkilə bilirmi?"""

    candles = history.daily_closes("AAPL", "NASDAQ")
    png = chart.render("AAPL", "Apple Inc.", candles, 1.0, "USD")
    if not png:
        _line("Qrafik (matplotlib)", False, "çəkilmədi — bot yalnız mətn göndərəcək")
        return False
    _line("Qrafik (matplotlib)", True, f"PNG hazırlandı ({len(png) // 1024} KB)")
    return True


def main() -> int:
    logging.basicConfig(level=logging.WARNING, format="   %(levelname)s %(message)s")

    print("Məlumat mənbələri yoxlanılır...\n")
    results = {
        "TradingView scanner": check_tradingview_scan(),
        "TradingView axtarış": check_tradingview_search(),
        "Yahoo RSS": check_yahoo_rss(),
        "Google News": check_google_news(),
        "Yahoo crumb": check_yahoo_crumb(),
        "Yahoo xəbərlər (JSON)": check_yahoo_news(),
        "Yahoo chart": check_yahoo_chart(),
        "Stooq tarixçəsi": check_history(),
        "Qrafik (matplotlib)": check_chart(),
    }

    if not results["Yahoo RSS"]:
        check_yahoo_header_variants()

    chart_ok = results["Stooq tarixçəsi"] and results["Qrafik (matplotlib)"]

    print()
    # Yalnız RSS və ya JSON-dan biri işləsə, xəbərlər gəlir — ikisi də şərt deyil.
    news_ok = (
        results["Yahoo RSS"]
        or results["Google News"]
        or results["Yahoo xəbərlər (JSON)"]
    )
    price_ok = results["TradingView scanner"] or results["Yahoo chart"]

    if results["TradingView scanner"]:
        print("Qiymətlər işləyir.")
    elif results["Yahoo chart"]:
        print("TradingView bağlıdır, amma Yahoo ehtiyat mənbəyi qiymət verir.")
    else:
        print("Qiymət mənbəyi yoxdur — /s və /xulase boş qayıdacaq.")

    if results["Yahoo RSS"]:
        print("Xəbərlər Yahoo RSS axını ilə işləyir.")
    elif results["Google News"]:
        print("Yahoo bu IP-ni bloklayıb — xəbərlər Google News ilə gəlir.")
    elif results["Yahoo xəbərlər (JSON)"]:
        print("Xəbərlər Yahoo JSON API ilə gəlir.")
    else:
        print("Xəbərlər işləmir — /xeber boş qayıdacaq.")

    if not chart_ok:
        print("Qrafik göndərilməyəcək — /izle və /s yalnız mətn qaytaracaq.")

    return 0 if (price_ok and news_ok) else 1


if __name__ == "__main__":
    raise SystemExit(main())
