"""Məlumat mənbələrini bir-bir yoxlayır: `python -m stockbot.diagnose`

Bot boş cavab verəndə səbəbin hansı API-də olduğunu göstərir.
Token və ya .env lazım deyil — yalnız xarici sorğular yoxlanılır.
"""

from __future__ import annotations

import json
import logging

from . import tradingview, yahoo
from .http import DEFAULT_TIMEOUT, SESSION, TRADINGVIEW_HEADERS, YAHOO_HEADERS

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


def check_yahoo_crumb() -> bool:
    yahoo.reset_session()
    crumb = yahoo._ensure_crumb()
    if not crumb:
        _line("Yahoo crumb", False, "alınmadı — xəbərlər 429 verə bilər")
        return False
    _line("Yahoo crumb", True, f"{crumb[:4]}… (cookie qoyuldu)")
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


def main() -> int:
    logging.basicConfig(level=logging.WARNING, format="   %(levelname)s %(message)s")

    print("Məlumat mənbələri yoxlanılır...\n")
    results = {
        "TradingView scanner": check_tradingview_scan(),
        "TradingView axtarış": check_tradingview_search(),
        "Yahoo crumb": check_yahoo_crumb(),
        "Yahoo xəbərlər": check_yahoo_news(),
        "Yahoo chart": check_yahoo_chart(),
    }

    print()
    if results["TradingView scanner"]:
        print("Qiymətlər işləyir.")
    elif results["Yahoo chart"]:
        print("TradingView bağlıdır, amma Yahoo ehtiyat mənbəyi qiymət verir.")
    else:
        print("Qiymət mənbəyi yoxdur — /s və /xulase boş qayıdacaq.")

    if not results["Yahoo xəbərlər"]:
        print("Xəbərlər işləmir — /xeber boş qayıdacaq.")

    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
