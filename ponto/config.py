from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from feeds.core.config import ConfigError, load_dotenv, require_env

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    token: str
    guild_id: int | None        # com servidor definido, os comandos aparecem na hora (sync por servidor)
    db_path: Path
    remind_after_hours: float   # lembrete por DM quando o ponto fica aberto por tanto tempo (0 desliga)

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv(ROOT / ".env")
        guild = os.environ.get("PONTO_GUILD_ID", "").strip()
        try:
            return cls(
                token=require_env("PONTO_BOT_TOKEN"),
                guild_id=int(guild) if guild else None,
                db_path=Path(os.environ.get("PONTO_DB", ROOT / "data" / "ponto.db")),
                remind_after_hours=float(os.environ.get("PONTO_LEMBRETE_HORAS", "8")),
            )
        except ValueError as e:
            raise ConfigError(f"Configuração inválida do bot de ponto: {e}") from e
