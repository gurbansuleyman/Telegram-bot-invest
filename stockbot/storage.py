"""Chat-lara görə izləmə siyahılarının JSON faylında saxlanması."""

from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path


class WatchlistStore:
    def __init__(self, path: str, default: list[str] | None = None) -> None:
        self._path = Path(path)
        self._default = [t.upper() for t in (default or [])]
        self._lock = threading.Lock()
        self._data: dict[str, list[str]] = self._load()

    def _load(self) -> dict[str, list[str]]:
        if not self._path.exists():
            return {}
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
        return {
            str(chat_id): [str(t).upper() for t in tickers]
            for chat_id, tickers in raw.items()
            if isinstance(tickers, list)
        }

    def _flush(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        # Atomik yazı: yarımçıq fayl qalmasın.
        fd, tmp = tempfile.mkstemp(dir=str(self._path.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(self._data, handle, ensure_ascii=False, indent=2)
            os.replace(tmp, self._path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise

    def get(self, chat_id: int) -> list[str]:
        with self._lock:
            return list(self._data.get(str(chat_id), self._default))

    def add(self, chat_id: int, tickers: list[str]) -> list[str]:
        with self._lock:
            current = self._data.get(str(chat_id), list(self._default))
            for ticker in tickers:
                ticker = ticker.upper()
                if ticker not in current:
                    current.append(ticker)
            self._data[str(chat_id)] = current
            self._flush()
            return list(current)

    def remove(self, chat_id: int, tickers: list[str]) -> list[str]:
        with self._lock:
            current = self._data.get(str(chat_id), list(self._default))
            drop = {t.upper() for t in tickers}
            current = [t for t in current if t not in drop]
            self._data[str(chat_id)] = current
            self._flush()
            return list(current)

    def clear(self, chat_id: int) -> None:
        with self._lock:
            self._data[str(chat_id)] = []
            self._flush()
