"""Data de referência das integrações: horário de Brasília."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

BRT = timezone(timedelta(hours=-3))  # Brasília, sem horário de verão


def today() -> date:
    return datetime.now(BRT).date()
