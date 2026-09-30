"""python -m ponto — inicia o bot de relógio de ponto."""

from __future__ import annotations

import logging
import os
import sys

import discord

from feeds.core.config import ConfigError, load_dotenv
from ponto.bot.client import PontoBot, SetupError
from ponto.config import ROOT, Settings
from ponto.repository import SQLiteRepository
from ponto.service import TimeClock


def main() -> int:
    load_dotenv(ROOT / ".env")  # antes do logging, pra PONTO_LOG_LEVEL do .env valer também fora do Docker
    level = os.environ.get("PONTO_LOG_LEVEL", "INFO").upper()  # DEBUG mostra cada requisição ao Discord
    logging.basicConfig(level=getattr(logging, level, logging.INFO),
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    try:
        settings = Settings.from_env()
    except ConfigError as e:
        print(e, file=sys.stderr)
        return 1

    repo = SQLiteRepository(settings.db_path)
    bot = PontoBot(settings, TimeClock(repo))
    try:
        bot.run(settings.token, log_handler=None)  # usa o logging configurado acima
    except SetupError as e:
        logging.getLogger("ponto").error("%s", e)
        return 2
    except discord.LoginFailure:
        logging.getLogger("ponto").error("Token inválido: confira PONTO_BOT_TOKEN (Developer Portal → Bot → Reset Token).")
        return 2
    finally:
        repo.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
