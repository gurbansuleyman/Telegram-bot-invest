"""Şəbəkəsiz işləyən vahid testlər."""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from stockbot import formatting  # noqa: E402
from stockbot.bot import _parse, _seconds_until  # noqa: E402
from stockbot.symbols import SymbolMatch, looks_like_ticker, rank  # noqa: E402
from stockbot.config import Config  # noqa: E402
from stockbot.storage import WatchlistStore  # noqa: E402
from stockbot.telegram import _split_message  # noqa: E402
from stockbot.tradingview import Quote  # noqa: E402
from stockbot.news import NewsItem  # noqa: E402


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
    # Nədən nəyə: 232.40 - 3.40 = 229.00
    assert "1 gün: 229.00 → <b>232.40</b> (+1.50%)" in text
    assert "1 həftə: 237.14 → <b>232.40</b> (-2.00%)" in text


def test_move_falls_back_to_percent_only():
    assert formatting.move(None, 100.0, 1.5) == "<b>+1.50%</b>"
    assert formatting.move(98.0, 100.0, 2.04) == "98.00 → <b>100.00</b> (+2.04%)"


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


def test_telegram_error_redacts_token():
    from stockbot.telegram import TelegramClient

    client = TelegramClient("8123456789:SECRET-TOKEN")
    message = client._redact(
        "getMe sorğusu alınmadı: url /bot8123456789:SECRET-TOKEN/getMe"
    )
    assert "SECRET-TOKEN" not in message
    assert "***" in message


def test_startup_hint_by_kind():
    from stockbot.__main__ import _startup_hint
    from stockbot.telegram import TelegramError

    auth = _startup_hint(TelegramError("getMe xətası: Unauthorized", kind="auth"))
    assert "TELEGRAM_BOT_TOKEN" in auth and "BotFather" in auth

    network = _startup_hint(TelegramError("bağlantı yoxdur", kind="network"))
    assert "api.telegram.org" in network


def test_log_filter_redacts_token():
    import logging

    from stockbot.__main__ import TokenRedactor

    redactor = TokenRedactor("8123456789:SECRET")
    record = logging.LogRecord(
        "urllib3", logging.WARNING, __file__, 1,
        "Retrying after %s", ("/bot8123456789:SECRET/getMe",), None,
    )
    redactor.filter(record)
    assert "SECRET" not in record.getMessage()
    assert "***" in record.getMessage()


def _fake_response(body):
    response = MagicMock()
    response.json.return_value = body
    return response


def test_poll_posts_valid_payload_and_advances_offset():
    """Telegram-ın `timeout` sahəsi HTTP timeout-u ilə toqquşmamalıdır."""

    from stockbot.telegram import TelegramClient

    client = TelegramClient("token", poll_timeout=30)
    with patch("stockbot.telegram.SESSION") as session:
        session.post.return_value = _fake_response(
            {"ok": True, "result": [{"update_id": 7, "message": {}}]}
        )
        updates = list(client.poll())

        args, kwargs = session.post.call_args
        assert kwargs["json"]["timeout"] == 30           # Telegram sahəsi
        assert kwargs["timeout"] == 45                   # HTTP timeout-u
        assert "offset" not in kwargs["json"]
        assert len(updates) == 1

        session.post.return_value = _fake_response({"ok": True, "result": []})
        list(client.poll())
        assert session.post.call_args[1]["json"]["offset"] == 8


def test_send_message_posts_each_chunk():
    from stockbot.telegram import TelegramClient

    client = TelegramClient("token")
    with patch("stockbot.telegram.SESSION") as session:
        session.post.return_value = _fake_response({"ok": True, "result": {}})
        client.send_message(42, "x" * 5000)

        assert session.post.call_count == 2
        payload = session.post.call_args[1]["json"]
        assert payload["chat_id"] == 42
        assert payload["parse_mode"] == "HTML"


def test_chat_action_failure_is_swallowed():
    from stockbot.telegram import TelegramClient

    client = TelegramClient("token")
    with patch("stockbot.telegram.SESSION") as session:
        session.post.side_effect = RuntimeError("şəbəkə yoxdur")
        client.send_chat_action(42)  # xəta atmamalıdır


RSS_SAMPLE = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <item>
    <title>Apple beats expectations</title>
    <link>https://finance.yahoo.com/news/apple-beats.html</link>
    <pubDate>Fri, 19 Sep 2026 10:30:00 +0000</pubDate>
    <source>Reuters</source>
  </item>
  <item>
    <title>Analysts raise price target</title>
    <link>https://www.marketwatch.com/story/aapl-target</link>
    <pubDate>Fri, 19 Sep 2026 08:00:00 +0000</pubDate>
  </item>
</channel></rss>"""


def test_rss_news_parsed_newest_first():
    from stockbot import yahoo

    response = MagicMock(content=RSS_SAMPLE)
    response.raise_for_status.return_value = None
    with patch("stockbot.yahoo.SESSION") as session:
        session.get.return_value = response
        items = yahoo.get_news_rss("AAPL", 5)

    assert [item.title for item in items] == [
        "Apple beats expectations",
        "Analysts raise price target",
    ]
    assert items[0].publisher == "Reuters"
    # <source> yoxdursa, link-in domeni istifadə olunur.
    assert items[1].publisher == "marketwatch.com"
    assert items[0].published.year == 2026


def test_yahoo_cooldown_skips_requests_after_429():
    from stockbot import yahoo

    yahoo.reset_session()
    with patch("stockbot.yahoo.SESSION") as session, \
         patch("stockbot.yahoo._ensure_crumb", return_value=None):
        session.get.return_value = MagicMock(status_code=429, text="Too Many Requests")
        assert yahoo._get("https://x", {}, "sınaq") is None
        calls_after_first = session.get.call_count

        # Soyuma müddətində ikinci sorğu ümumiyyətlə göndərilmir.
        assert yahoo._get("https://x", {}, "sınaq") is None
        assert session.get.call_count == calls_after_first

    yahoo.reset_session()


GOOGLE_SAMPLE = b"""<?xml version="1.0"?>
<rss version="2.0"><channel>
  <item>
    <title>Nvidia rallies on AI demand - Reuters</title>
    <link>https://news.google.com/rss/articles/abc</link>
    <pubDate>Fri, 19 Sep 2026 11:00:00 GMT</pubDate>
    <source url="https://reuters.com">Reuters</source>
  </item>
</channel></rss>"""


def test_google_news_strips_publisher_suffix():
    from stockbot import news

    response = MagicMock(content=GOOGLE_SAMPLE)
    response.raise_for_status.return_value = None
    with patch("stockbot.news.SESSION") as session:
        session.get.return_value = response
        items = news.google_news("NVDA", 3)

    assert items[0].title == "Nvidia rallies on AI demand"
    assert items[0].publisher == "Reuters"


def test_get_news_falls_back_when_yahoo_is_empty():
    """Yahoo 429 verəndə Google News-a keçməlidir."""

    from stockbot import news

    google_item = news.NewsItem("x", "Reuters", "https://r.com/x", None, ["NVDA"])
    with patch("stockbot.yahoo.get_news_rss", return_value=[]) as rss, \
         patch("stockbot.news.google_news", return_value=[google_item]) as google, \
         patch("stockbot.yahoo.get_news_json", return_value=[]) as json_api:
        items = news.get_news("NVDA", 3)

    assert items == [google_item]
    assert rss.called and google.called
    assert not json_api.called  # Google cavab verdi, JSON-a ehtiyac qalmadı


def test_yahoo_rss_cooldown_skips_next_call():
    """429-dan sonra RSS də ötürülməlidir ki, hər sorğuda vaxt itməsin."""

    from stockbot import yahoo

    yahoo.reset_session()
    with patch("stockbot.yahoo.SESSION") as session:
        session.get.return_value = MagicMock(status_code=429, ok=False)
        assert yahoo.get_news_rss("AAPL", 3) == []
        assert session.get.call_count == 1

        assert yahoo.get_news_rss("MSFT", 3) == []
        assert session.get.call_count == 1  # ikinci sorğu göndərilmədi

    yahoo.reset_session()
