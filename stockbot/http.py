"""Bütün xarici sorğular üçün ümumi HTTP sessiyası."""

from __future__ import annotations

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

DEFAULT_TIMEOUT = 15

# Hər iki API brauzerdən gələn sorğu gözləyir; bu başlıqlar olmadan 403 verir.
TRADINGVIEW_HEADERS = {
    "Origin": "https://www.tradingview.com",
    "Referer": "https://www.tradingview.com/",
    "Content-Type": "application/json",
}

YAHOO_HEADERS = {
    "Origin": "https://finance.yahoo.com",
    "Referer": "https://finance.yahoo.com/",
}


def build_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
        }
    )
    # 429 qəsdən siyahıda deyil: təkrar sorğu rate limit-i daha da pisləşdirir,
    # üstəlik hər təkrar istifadəçini gözlədir.
    retry = Retry(
        total=2,
        backoff_factor=0.5,
        status_forcelist=(500, 502, 503, 504),
        allowed_methods=frozenset({"GET", "POST"}),
    )
    adapter = HTTPAdapter(max_retries=retry, pool_maxsize=16)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


SESSION = build_session()
