"""Períodos (no horário de Brasília) e conversão de durações."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from feeds.core.clock import BRT


@dataclass(frozen=True)
class Period:
    label: str
    start: datetime  # inclusivo, com fuso
    end: datetime    # exclusivo, com fuso


PERIODS = {
    "hoje": "Hoje",
    "semana": "Esta semana",
    "semana-passada": "Semana passada",
    "mes": "Este mês",
    "mes-passado": "Mês passado",
}


def _midnight(d: date) -> datetime:
    return datetime.combine(d, time.min, tzinfo=BRT)


def period(name: str, now: datetime) -> Period:
    """Período nomeado relativo a `now`. Semanas começam na segunda-feira."""
    today = now.astimezone(BRT).date()
    if name == "hoje":
        start, end = today, today + timedelta(days=1)
    elif name in ("semana", "semana-passada"):
        start = today - timedelta(days=today.weekday())
        if name == "semana-passada":
            start -= timedelta(days=7)
        end = start + timedelta(days=7)
    elif name in ("mes", "mes-passado"):
        start = today.replace(day=1)
        if name == "mes-passado":
            start = (start - timedelta(days=1)).replace(day=1)
        end = (start + timedelta(days=32)).replace(day=1)
    else:
        raise ValueError(f"período desconhecido: {name}")
    return Period(PERIODS[name], _midnight(start), _midnight(end))


DURATION_RE = re.compile(r"^\s*([+-])?\s*(?:(\d+)\s*h)?\s*(?:(\d+)\s*(?:m|min)?)?\s*$", re.IGNORECASE)


def parse_duration(text: str) -> int:
    """'1h30', '2h', '45m', '-0h15', '+3h' → segundos (com sinal)."""
    m = DURATION_RE.match(text or "")
    if not m or not (m[2] or m[3]):
        raise ValueError(f"duração inválida: {text!r} (use algo como 1h30, 45m ou -0h15)")
    seconds = int(m[2] or 0) * 3600 + int(m[3] or 0) * 60
    return -seconds if m[1] == "-" else seconds


def parse_clock_time(text: str, reference: datetime) -> datetime:
    """'18:30' → datetime nesse horário (Brasília), no dia de `reference`; se ficar no futuro, usa o dia anterior."""
    m = re.match(r"^\s*(\d{1,2})[:h](\d{2})\s*$", text or "")
    if not m or int(m[1]) > 23 or int(m[2]) > 59:
        raise ValueError(f"horário inválido: {text!r} (use HH:MM, ex.: 18:30)")
    ref = reference.astimezone(BRT)
    moment = ref.replace(hour=int(m[1]), minute=int(m[2]), second=0, microsecond=0)
    return moment - timedelta(days=1) if moment > ref else moment


def format_duration(seconds: int) -> str:
    """3725 → '1h 02min'; -900 → '-0h 15min'."""
    sign = "-" if seconds < 0 else ""
    minutes = abs(int(seconds)) // 60
    return f"{sign}{minutes // 60}h {minutes % 60:02d}min"


def format_moment(moment: datetime) -> str:
    return moment.astimezone(BRT).strftime("%d/%m %H:%M")
