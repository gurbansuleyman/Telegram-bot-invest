"""Telegram Bot API üzərində minimal long-polling klienti."""

from __future__ import annotations

import logging
from typing import Iterator

from .http import SESSION

log = logging.getLogger(__name__)

API_URL = "https://api.telegram.org/bot{token}/{method}"
MAX_MESSAGE_LEN = 4096


class TelegramError(RuntimeError):
    """Telegram sorğusunun alınmaması. `kind` səbəbi ayırd etməyə imkan verir."""

    def __init__(self, message: str, kind: str = "api") -> None:
        super().__init__(message)
        self.kind = kind  # "auth" | "network" | "api"


class TelegramClient:
    def __init__(self, token: str, poll_timeout: int = 30) -> None:
        self._token = token
        self._poll_timeout = poll_timeout
        self._offset: int | None = None

    def _redact(self, text: str) -> str:
        """Token URL-in içindədir — xəta mətnində və logda görünməməlidir."""

        return text.replace(self._token, "***") if self._token else text

    def _call(self, method: str, timeout: int, **payload):
        url = API_URL.format(token=self._token, method=method)
        try:
            response = SESSION.post(url, json=payload, timeout=timeout)
            body = response.json()
        except Exception as exc:
            raise TelegramError(
                self._redact(f"{method} sorğusu alınmadı: {exc}"), kind="network"
            ) from exc

        if not body.get("ok"):
            kind = "auth" if body.get("error_code") in (401, 404) else "api"
            message = self._redact(f"{method} xətası: {body.get('description')}")
            raise TelegramError(message, kind=kind)
        return body.get("result")

    def get_me(self) -> dict:
        return self._call("getMe", timeout=15)

    def poll(self) -> Iterator[dict]:
        """Növbəti yeniləmələri gətirir; xəta olarsa boş qaytarır."""

        payload = {
            "timeout": self._poll_timeout,
            "allowed_updates": ["message"],
        }
        if self._offset is not None:
            payload["offset"] = self._offset

        updates = self._call("getUpdates", timeout=self._poll_timeout + 15, **payload)
        for update in updates or []:
            self._offset = update["update_id"] + 1
            yield update

    def send_message(self, chat_id: int, text: str, preview: bool = False) -> None:
        for chunk in _split_message(text):
            self._call(
                "sendMessage",
                timeout=20,
                chat_id=chat_id,
                text=chunk,
                parse_mode="HTML",
                disable_web_page_preview=not preview,
            )

    def send_chat_action(self, chat_id: int, action: str = "typing") -> None:
        try:
            self._call("sendChatAction", timeout=10, chat_id=chat_id, action=action)
        except TelegramError as exc:
            log.debug("chat action göndərilmədi: %s", exc)


def _split_message(text: str, limit: int = MAX_MESSAGE_LEN) -> list[str]:
    """Uzun mesajı sətir sərhədlərindən Telegram limitinə görə bölür."""

    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    current = ""
    for line in text.split("\n"):
        candidate = f"{current}\n{line}" if current else line
        if len(candidate) > limit:
            if current:
                chunks.append(current)
            # Tək sətir limitdən uzundursa, kəsərək bölürük.
            while len(line) > limit:
                chunks.append(line[:limit])
                line = line[limit:]
            current = line
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks
