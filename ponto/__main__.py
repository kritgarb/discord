"""python -m ponto — inicia o bot de relógio de ponto."""

from __future__ import annotations

import logging
import sys

from feeds.core.config import ConfigError
from ponto.bot import PontoBot
from ponto.config import Settings
from ponto.repository import SQLiteRepository
from ponto.service import TimeClock


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    try:
        settings = Settings.from_env()
    except ConfigError as e:
        print(e, file=sys.stderr)
        return 1

    repo = SQLiteRepository(settings.db_path)
    bot = PontoBot(settings, TimeClock(repo))
    try:
        bot.run(settings.token, log_handler=None)  # usa o logging configurado acima
    finally:
        repo.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
