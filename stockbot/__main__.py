"""`python -m stockbot` giriş nöqtəsi."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from .bot import Bot
from .config import Config
from .telegram import TelegramError


def load_dotenv(path: str = ".env") -> None:
    """Xarici asılılıq olmadan sadə .env oxuyucusu."""

    env_file = Path(path)
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


class TokenRedactor(logging.Filter):
    """Tokeni bütün loglardan silir — o, URL-in içindədir və journald-a düşür."""

    def __init__(self, token: str) -> None:
        super().__init__()
        self._token = token

    def filter(self, record: logging.LogRecord) -> bool:
        if not self._token:
            return True
        if isinstance(record.msg, str):
            record.msg = record.msg.replace(self._token, "***")
        if isinstance(record.args, tuple):
            record.args = tuple(
                arg.replace(self._token, "***") if isinstance(arg, str) else arg
                for arg in record.args
            )
        return True


def main() -> int:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    load_dotenv()

    try:
        config = Config.from_env()
    except ValueError as exc:
        print(f"Konfiqurasiya xətası: {exc}", file=sys.stderr)
        return 2

    for handler in logging.getLogger().handlers:
        handler.addFilter(TokenRedactor(config.token))

    bot = Bot(config)
    try:
        bot.run()
    except KeyboardInterrupt:
        bot.stop()
        print("Dayandırıldı.")
    except TelegramError as exc:
        # İlk işə salmada ən çox rast gəlinən iki hal: səhv token, bağlı şəbəkə.
        print(_startup_hint(exc), file=sys.stderr)
        return 1
    return 0


def _startup_hint(exc: TelegramError) -> str:
    if exc.kind == "auth":
        return (
            "Telegram tokeni qəbul etmədi.\n"
            "  • .env faylındakı TELEGRAM_BOT_TOKEN-i yoxla (tam sətir, boşluqsuz)\n"
            "  • @BotFather → /mybots → botun → API Token ilə tutuşdur\n"
            f"  • Telegram-ın cavabı: {exc}"
        )
    if exc.kind == "network":
        return (
            "Telegram-a çıxış yoxdur.\n"
            "  • İnternet bağlantısını yoxla\n"
            "  • api.telegram.org firewall/proxy arxasında bağlı ola bilər\n"
            f"  • Texniki detal: {exc}"
        )
    return f"Telegram xətası: {exc}"


if __name__ == "__main__":
    raise SystemExit(main())
