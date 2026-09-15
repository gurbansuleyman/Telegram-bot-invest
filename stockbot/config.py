"""Mühit dəyişənlərindən oxunan konfiqurasiya."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _split(raw: str) -> list[str]:
    return [part.strip() for part in raw.replace(";", ",").split(",") if part.strip()]


def _int_set(raw: str) -> set[int]:
    out: set[int] = set()
    for part in _split(raw):
        try:
            out.add(int(part))
        except ValueError:
            raise ValueError(f"chat id rəqəm olmalıdır: {part!r}") from None
    return out


@dataclass
class Config:
    token: str
    allowed_chat_ids: set[int] = field(default_factory=set)
    default_watchlist: list[str] = field(default_factory=list)
    digest_chat_id: int | None = None
    digest_time: str | None = None
    news_per_symbol: int = 4
    state_path: str = "state.json"

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "Config":
        env = dict(os.environ if env is None else env)

        token = env.get("TELEGRAM_BOT_TOKEN", "").strip()
        if not token:
            raise ValueError(
                "TELEGRAM_BOT_TOKEN təyin edilməyib. .env.example faylına bax."
            )

        digest_chat_raw = env.get("DIGEST_CHAT_ID", "").strip()
        digest_time = env.get("DIGEST_TIME", "").strip() or None
        if digest_time:
            _validate_hhmm(digest_time)

        return cls(
            token=token,
            allowed_chat_ids=_int_set(env.get("ALLOWED_CHAT_IDS", "")),
            default_watchlist=[t.upper() for t in _split(env.get("DEFAULT_WATCHLIST", ""))],
            digest_chat_id=int(digest_chat_raw) if digest_chat_raw else None,
            digest_time=digest_time,
            news_per_symbol=int(env.get("NEWS_PER_SYMBOL", "4")),
            state_path=env.get("STATE_PATH", "state.json"),
        )

    def is_allowed(self, chat_id: int) -> bool:
        return not self.allowed_chat_ids or chat_id in self.allowed_chat_ids

    @property
    def digest_enabled(self) -> bool:
        return self.digest_chat_id is not None and self.digest_time is not None


def _validate_hhmm(value: str) -> None:
    hh, _, mm = value.partition(":")
    if not (hh.isdigit() and mm.isdigit() and 0 <= int(hh) < 24 and 0 <= int(mm) < 60):
        raise ValueError(f"DIGEST_TIME HH:MM formatında olmalıdır, alındı: {value!r}")
