from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class Session:
    """Um período de trabalho: do /entrar ao /sair, descontando as pausas."""

    id: int
    guild_id: int
    user_id: int
    started_at: datetime
    ended_at: datetime | None = None
    paused_at: datetime | None = None   # preenchido enquanto está em pausa
    paused_seconds: int = 0             # pausas já encerradas
    note: str | None = None
    reminded: bool = False

    @property
    def is_open(self) -> bool:
        return self.ended_at is None

    @property
    def is_paused(self) -> bool:
        return self.paused_at is not None

    def worked_seconds(self, now: datetime) -> int:
        """Tempo trabalhado até `now` (ou até o fim), sem contar as pausas."""
        end = self.ended_at or now
        paused = self.paused_seconds
        if self.paused_at is not None:
            paused += int((end - self.paused_at).total_seconds())
        return max(0, int((end - self.started_at).total_seconds()) - paused)


@dataclass
class Adjustment:
    """Correção manual feita por um admin (ex.: ponto esquecido). Pode ser negativa."""

    id: int
    guild_id: int
    user_id: int
    seconds: int
    reason: str
    created_by: int
    created_at: datetime


@dataclass
class UserTotal:
    user_id: int
    worked_seconds: int = 0      # sessões encerradas no período
    adjusted_seconds: int = 0    # ajustes no período
    sessions: int = 0

    @property
    def total_seconds(self) -> int:
        return self.worked_seconds + self.adjusted_seconds
