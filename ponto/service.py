"""Regras do relógio de ponto. Não depende do Discord (testável sem rede)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable

from ponto.models import Adjustment, Session, UserTotal
from ponto.repository import SQLiteRepository
from ponto.timeutil import Period, format_duration, format_moment


class TimeClockError(Exception):
    """Erro de regra de negócio; a mensagem é mostrada ao usuário."""


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TimeClock:
    def __init__(self, repo: SQLiteRepository, now: Callable[[], datetime] = utcnow):
        self.repo = repo
        self.now = now

    # ----- ponto do freela -----

    def clock_in(self, guild_id: int, user_id: int, note: str | None = None) -> Session:
        current = self.repo.open_session(guild_id, user_id)
        if current:
            raise TimeClockError(f"Você já está com o ponto aberto desde {format_moment(current.started_at)}. "
                                 "Use /sair para fechar.")
        return self.repo.create_session(guild_id, user_id, self.now(), note)

    def pause(self, guild_id: int, user_id: int) -> Session:
        s = self._require_open(guild_id, user_id)
        if s.is_paused:
            raise TimeClockError("O ponto já está em pausa. Use /retomar para voltar.")
        s.paused_at = self.now()
        self.repo.save_session(s)
        return s

    def resume(self, guild_id: int, user_id: int) -> Session:
        s = self._require_open(guild_id, user_id)
        if not s.is_paused:
            raise TimeClockError("O ponto não está em pausa.")
        s.paused_seconds += int((self.now() - s.paused_at).total_seconds())
        s.paused_at = None
        self.repo.save_session(s)
        return s

    def clock_out(self, guild_id: int, user_id: int, at: datetime | None = None) -> Session:
        """Fecha o ponto agora ou num horário passado (`at`, usado pelo admin para corrigir esquecimentos)."""
        s = self._require_open(guild_id, user_id)
        now = self.now()
        end = at or now
        if end > now:
            raise TimeClockError("O horário de saída não pode estar no futuro.")
        if end <= s.started_at:
            raise TimeClockError(f"O horário de saída precisa ser depois da entrada ({format_moment(s.started_at)}).")
        if s.is_paused:
            # a pausa em andamento termina junto com o ponto (ou no início dela, se a saída for antes)
            s.paused_seconds += max(0, int((end - s.paused_at).total_seconds()))
            s.paused_at = None
        s.ended_at = end
        self.repo.save_session(s)
        return s

    def current(self, guild_id: int, user_id: int) -> Session | None:
        return self.repo.open_session(guild_id, user_id)

    # ----- consultas -----

    def sessions(self, guild_id: int, period: Period, user_id: int | None = None) -> list[Session]:
        """Sessões encerradas que começaram no período (de todos, ou de uma pessoa)."""
        return self.repo.closed_sessions(guild_id, period.start, period.end, user_id)

    def open_sessions(self, guild_id: int) -> list[Session]:
        return [s for s in self.repo.all_open_sessions() if s.guild_id == guild_id]

    def totals(self, guild_id: int, period: Period, user_id: int | None = None) -> list[UserTotal]:
        """Horas por pessoa no período: sessões encerradas (pela data de entrada) + ajustes.
        Ordenado do maior para o menor total."""
        totals: dict[int, UserTotal] = {}
        for s in self.repo.closed_sessions(guild_id, period.start, period.end, user_id):
            t = totals.setdefault(s.user_id, UserTotal(s.user_id))
            t.worked_seconds += s.worked_seconds(s.ended_at)
            t.sessions += 1
        for a in self.repo.adjustments(guild_id, period.start, period.end, user_id):
            totals.setdefault(a.user_id, UserTotal(a.user_id)).adjusted_seconds += a.seconds
        return sorted(totals.values(), key=lambda t: t.total_seconds, reverse=True)

    def adjustments(self, guild_id: int, period: Period, user_id: int | None = None) -> list[Adjustment]:
        return self.repo.adjustments(guild_id, period.start, period.end, user_id)

    # ----- administração -----

    def adjust(self, guild_id: int, user_id: int, seconds: int, reason: str, by: int) -> Adjustment:
        if seconds == 0:
            raise TimeClockError("O ajuste precisa ser diferente de zero.")
        if not reason.strip():
            raise TimeClockError("Informe o motivo do ajuste.")
        return self.repo.add_adjustment(guild_id, user_id, seconds, reason.strip(), by, self.now())

    # ----- lembretes -----

    def sessions_to_remind(self, after_seconds: int) -> list[Session]:
        """Pontos abertos há mais de `after_seconds` de trabalho que ainda não receberam lembrete."""
        now = self.now()
        return [s for s in self.repo.all_open_sessions()
                if not s.reminded and not s.is_paused and s.worked_seconds(now) >= after_seconds]

    def mark_reminded(self, session: Session) -> None:
        session.reminded = True
        self.repo.save_session(session)

    # ----- auxiliares -----

    def _require_open(self, guild_id: int, user_id: int) -> Session:
        s = self.repo.open_session(guild_id, user_id)
        if not s:
            raise TimeClockError("Você não está com o ponto aberto. Use /entrar para começar.")
        return s


def describe(session: Session, now: datetime) -> str:
    """Resumo curto de uma sessão para as respostas do bot."""
    state = "em pausa" if session.is_paused else ("aberto" if session.is_open else "fechado")
    return f"entrada {format_moment(session.started_at)} · {format_duration(session.worked_seconds(now))} · {state}"
