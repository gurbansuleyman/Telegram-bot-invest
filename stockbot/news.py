"""Xəbər mənbələri: əvvəl Yahoo Finance, o susarsa Google News.

Yahoo bəzi IP-ləri 429 ilə bloklayır. Google News RSS həmin məqalələrin
böyük hissəsini (Yahoo Finance daxil) verir və limit qoymur.
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

from .http import DEFAULT_TIMEOUT, SESSION

log = logging.getLogger(__name__)

GOOGLE_NEWS_URL = "https://news.google.com/rss/search"

# Gündəlik xülasədə köhnə başlıq səs-küydür.
DEFAULT_MAX_AGE_DAYS = 3


@dataclass
class NewsItem:
    title: str
    publisher: str
    link: str
    published: datetime | None
    tickers: list[str]


def get_news(
    ticker: str, limit: int = 4, max_age_days: int = DEFAULT_MAX_AGE_DAYS
) -> list[NewsItem]:
    """Simvol üzrə təzə xəbərlər — hansı mənbə cavab verirsə ondan.

    Filtr hər mənbədən sonra tətbiq olunur: biri yalnız köhnə başlıq
    qaytarsa, növbətisi sınanır.
    """

    from . import yahoo  # dairəvi idxaldan qaçmaq üçün burada

    # Filtr bir hissəsini kəsəcək, ona görə daha çox başlıq götürürük.
    fetch_limit = max(limit * 3, 12)
    for fetch in (yahoo.get_news_rss, google_news, yahoo.get_news_json):
        fresh = recent_only(fetch(ticker, fetch_limit), max_age_days)
        if fresh:
            return newest_first(fresh, limit)
    return []


def recent_only(items: list[NewsItem], max_age_days: int) -> list[NewsItem]:
    """Verilmiş gün sayından köhnə xəbərləri atır. 0 — filtr yoxdur."""

    if not max_age_days:
        return list(items)

    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    # Tarixi olmayan xəbəri atmırıq — yaşını bilmirik.
    return [
        item for item in items if item.published is None or item.published >= cutoff
    ]


def google_news(ticker: str, limit: int = 4) -> list[NewsItem]:
    """Google News RSS — açıqdır, açar tələb etmir, limit qoymur."""

    params = {
        "q": f"{ticker} stock",
        "hl": "en-US",
        "gl": "US",
        "ceid": "US:en",
    }
    try:
        response = SESSION.get(GOOGLE_NEWS_URL, params=params, timeout=DEFAULT_TIMEOUT)
        response.raise_for_status()
    except Exception as exc:
        log.warning("Google News alınmadı (%s): %s", ticker, exc)
        return []

    return parse_rss(response.content, ticker, limit)


def parse_rss(payload: bytes, ticker: str, limit: int) -> list[NewsItem]:
    """RSS 2.0 axınını NewsItem siyahısına çevirir (Yahoo və Google eyni formatdadır)."""

    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        log.warning("RSS oxunmadı (%s): %s", ticker, exc)
        return []

    items: list[NewsItem] = []
    for node in root.iterfind(".//item"):
        title = (node.findtext("title") or "").strip()
        link = (node.findtext("link") or "").strip()
        if not title or not link:
            continue

        publisher = (node.findtext("source") or "").strip()
        items.append(
            NewsItem(
                title=_strip_publisher(title, publisher),
                publisher=publisher or _host(link),
                link=link,
                published=_parse_date(node.findtext("pubDate")),
                tickers=[ticker.upper()],
            )
        )
        if len(items) >= limit:
            break
    return items


def newest_first(items: list[NewsItem], limit: int) -> list[NewsItem]:
    oldest = datetime.min.replace(tzinfo=timezone.utc)
    items.sort(key=lambda item: item.published or oldest, reverse=True)
    return items[:limit]


def _strip_publisher(title: str, publisher: str) -> str:
    """Google başlığa ` - Reuters` əlavə edir; mənbə ayrıca göstərildiyi üçün lazım deyil."""

    suffix = f" - {publisher}"
    if publisher and title.endswith(suffix):
        return title[: -len(suffix)].strip()
    return title


def _host(link: str) -> str:
    return urlparse(link).netloc.replace("www.", "")


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        moment = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)
