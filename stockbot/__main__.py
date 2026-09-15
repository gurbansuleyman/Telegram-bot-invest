"""`python -m stockbot` giriş nöqtəsi."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from .bot import Bot
from .config import Config


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

    bot = Bot(config)
    try:
        bot.run()
    except KeyboardInterrupt:
        bot.stop()
        print("Dayandırıldı.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
