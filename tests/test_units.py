"""Şəbəkəsiz işləyən vahid testlər."""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from stockbot import formatting  # noqa: E402
from stockbot.bot import _parse, _seconds_until  # noqa: E402
from stockbot.symbols import SymbolMatch, looks_like_ticker, rank  # noqa: E402
from stockbot.config import Config  # noqa: E402
from stockbot.storage import WatchlistStore  # noqa: E402
from stockbot.telegram import _split_message  # noqa: E402
from stockbot.tradingview import Quote  # noqa: E402
from stockbot.yahoo import NewsItem  # noqa: E402


def test_parse_command():
    assert _parse("/s AAPL msft") == ("/s", ["AAPL", "MSFT"])
    assert _parse("/s@InvestBot AAPL") == ("/s", ["AAPL"])
    assert _parse("AAPL, MSFT") == (None, ["AAPL", "MSFT"])
    assert _parse("$aapl $msft") == (None, ["AAPL", "MSFT"])
    assert _parse("NASDAQ:AAPL") == (None, ["NASDAQ:AAPL"])
    # Adi söhbət ticker sayılmır.
    assert _parse("salam necəsən") == (None, [])
    assert _parse("bu gün nə var") == (None, [])


def test_parse_keywords():
    # Açar söz həm əvvəldə, həm sonda işləyir; ad da qəbul olunur.
    assert _parse("nvidia izlə") == ("/izle", ["NVIDIA"])
    assert _parse("izle nvidia") == ("/izle", ["NVIDIA"])
    assert _parse("NVDA dayan") == ("/sil", ["NVDA"])
    assert _parse("tesla stop") == ("/sil", ["TESLA"])
    # Tək açar söz komanda deyil.
    assert _parse("izlə") == (None, [])


def test_rank_prefers_exact_symbol_on_major_exchange():
    matches = [
        SymbolMatch("NVDA34", "BMV", "NVIDIA Corporation", "dr", "tradingview"),
        SymbolMatch("NVDA", "NASDAQ", "NVIDIA Corporation", "stock", "tradingview"),
        SymbolMatch("NVDA", "NASDAQ", "NVIDIA Corporation", "stock", "yahoo"),
    ]
    ranked = rank(matches, "NVIDIA")
    assert ranked[0].symbol == "NVDA"
    assert ranked[0].exchange == "NASDAQ"
    assert len(ranked) == 2  # eyni simvol iki dəfə sayılmır
    assert ranked[0].full == "NASDAQ:NVDA"


def test_looks_like_ticker():
    assert looks_like_ticker("AAPL")
    assert looks_like_ticker("BRK.B")
    assert looks_like_ticker("NASDAQ:AAPL")
    assert not looks_like_ticker("nvidia corporation")
    assert not looks_like_ticker("VERYLONGNAME")


def test_percent_and_marker():
    assert formatting.pct(1.234) == "+1.23%"
    assert formatting.pct(-0.5) == "-0.50%"
    assert formatting.pct(None) == "—"
    assert formatting.marker(2) == formatting.UP
    assert formatting.marker(-2) == formatting.DOWN
    assert formatting.marker(0) == formatting.FLAT


def test_compact():
    assert formatting.compact(1_500_000) == "1.50M"
    assert formatting.compact(2_400_000_000) == "2.40B"
    assert formatting.compact(None) == "—"


def test_format_quote_escapes_html():
    quote = Quote(
        symbol="NASDAQ:AAPL",
        name="AAPL",
        description="Apple <Inc>",
        price=232.4,
        currency="USD",
        change_1d=1.5,
        change_1d_abs=3.4,
        change_1w=-2.0,
        change_1m=4.0,
        change_ytd=10.0,
        volume=48_200_000,
        market_cap=3_400_000_000_000,
        exchange="NASDAQ",
    )
    text = formatting.format_quote("AAPL", quote)
    assert "Apple &lt;Inc&gt;" in text
    assert "1 gün: <b>+1.50%</b>" in text
    assert "1 həftə: <b>-2.00%</b>" in text


def test_format_news_links():
    item = NewsItem(
        title="Apple & Co",
        publisher="Reuters",
        link="https://example.com/a?b=1&c=2",
        published=datetime.now(timezone.utc) - timedelta(hours=3),
        tickers=["AAPL"],
    )
    text = formatting.format_news("AAPL", [item])
    assert "Apple &amp; Co" in text
    assert "b=1&amp;c=2" in text
    assert "3 saat əvvəl" in text


def test_split_message_respects_limit():
    text = "\n".join(f"sətir {i}" * 20 for i in range(400))
    chunks = _split_message(text, limit=4096)
    assert len(chunks) > 1
    assert all(len(chunk) <= 4096 for chunk in chunks)
    assert "".join(chunks).replace("\n", "") == text.replace("\n", "")


def test_watchlist_store_roundtrip(tmp_path):
    store = WatchlistStore(str(tmp_path / "state.json"), default=["AAPL"])
    assert store.get(1) == ["AAPL"]
    assert store.add(1, ["msft", "NVDA"]) == ["AAPL", "MSFT", "NVDA"]
    assert store.remove(1, ["aapl"]) == ["MSFT", "NVDA"]

    reopened = WatchlistStore(str(tmp_path / "state.json"), default=["AAPL"])
    assert reopened.get(1) == ["MSFT", "NVDA"]


def test_config_from_env():
    config = Config.from_env(
        {
            "TELEGRAM_BOT_TOKEN": "abc",
            "ALLOWED_CHAT_IDS": "10, 20",
            "DEFAULT_WATCHLIST": "aapl,msft",
            "DIGEST_CHAT_ID": "10",
            "DIGEST_TIME": "07:30",
        }
    )
    assert config.allowed_chat_ids == {10, 20}
    assert config.default_watchlist == ["AAPL", "MSFT"]
    assert config.is_allowed(10) and not config.is_allowed(99)
    assert config.digest_enabled


def test_seconds_until_is_within_a_day():
    assert 0 < _seconds_until("00:01") <= 24 * 3600
