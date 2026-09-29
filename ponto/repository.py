"""Persistência em SQLite. Datas são guardadas como timestamp Unix (UTC)."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from ponto.models import Adjustment, Session

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id        INTEGER NOT NULL,
    user_id         INTEGER NOT NULL,
    started_at      INTEGER NOT NULL,
    ended_at        INTEGER,
    paused_at       INTEGER,
    paused_seconds  INTEGER NOT NULL DEFAULT 0,
    note            TEXT,
    reminded        INTEGER NOT NULL DEFAULT 0
);
-- no máximo um ponto aberto por pessoa em cada servidor
CREATE UNIQUE INDEX IF NOT EXISTS one_open_session
    ON sessions (guild_id, user_id) WHERE ended_at IS NULL;
CREATE INDEX IF NOT EXISTS sessions_by_start ON sessions (guild_id, started_at);

CREATE TABLE IF NOT EXISTS adjustments (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id    INTEGER NOT NULL,
    user_id     INTEGER NOT NULL,
    seconds     INTEGER NOT NULL,
    reason      TEXT NOT NULL,
    created_by  INTEGER NOT NULL,
    created_at  INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS adjustments_by_date ON adjustments (guild_id, created_at);
"""


def _ts(moment: datetime | None) -> int | None:
    return int(moment.timestamp()) if moment else None


def _dt(ts: int | None) -> datetime | None:
    return datetime.fromtimestamp(ts, tz=timezone.utc) if ts is not None else None


class SQLiteRepository:
    def __init__(self, path: Path | str):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    def close(self) -> None:
        self.conn.close()

    # ----- sessões -----

    @staticmethod
    def _session(row: sqlite3.Row) -> Session:
        return Session(
            id=row["id"], guild_id=row["guild_id"], user_id=row["user_id"],
            started_at=_dt(row["started_at"]), ended_at=_dt(row["ended_at"]),
            paused_at=_dt(row["paused_at"]), paused_seconds=row["paused_seconds"],
            note=row["note"], reminded=bool(row["reminded"]),
        )

    def create_session(self, guild_id: int, user_id: int, started_at: datetime, note: str | None) -> Session:
        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO sessions (guild_id, user_id, started_at, note) VALUES (?, ?, ?, ?)",
                (guild_id, user_id, _ts(started_at), note),
            )
        return Session(cur.lastrowid, guild_id, user_id, started_at, note=note)

    def save_session(self, s: Session) -> None:
        with self.conn:
            self.conn.execute(
                "UPDATE sessions SET ended_at = ?, paused_at = ?, paused_seconds = ?, note = ?, reminded = ? "
                "WHERE id = ?",
                (_ts(s.ended_at), _ts(s.paused_at), s.paused_seconds, s.note, int(s.reminded), s.id),
            )

    def open_session(self, guild_id: int, user_id: int) -> Session | None:
        row = self.conn.execute(
            "SELECT * FROM sessions WHERE guild_id = ? AND user_id = ? AND ended_at IS NULL",
            (guild_id, user_id),
        ).fetchone()
        return self._session(row) if row else None

    def all_open_sessions(self) -> list[Session]:
        rows = self.conn.execute("SELECT * FROM sessions WHERE ended_at IS NULL").fetchall()
        return [self._session(r) for r in rows]

    def closed_sessions(self, guild_id: int, start: datetime, end: datetime,
                        user_id: int | None = None) -> list[Session]:
        """Sessões encerradas que começaram em [start, end)."""
        sql = "SELECT * FROM sessions WHERE guild_id = ? AND ended_at IS NOT NULL AND started_at >= ? AND started_at < ?"
        args: list = [guild_id, _ts(start), _ts(end)]
        if user_id is not None:
            sql += " AND user_id = ?"
            args.append(user_id)
        rows = self.conn.execute(sql + " ORDER BY started_at", args).fetchall()
        return [self._session(r) for r in rows]

    # ----- ajustes -----

    def add_adjustment(self, guild_id: int, user_id: int, seconds: int, reason: str,
                       created_by: int, created_at: datetime) -> Adjustment:
        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO adjustments (guild_id, user_id, seconds, reason, created_by, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (guild_id, user_id, seconds, reason, created_by, _ts(created_at)),
            )
        return Adjustment(cur.lastrowid, guild_id, user_id, seconds, reason, created_by, created_at)

    def adjustments(self, guild_id: int, start: datetime, end: datetime,
                    user_id: int | None = None) -> list[Adjustment]:
        sql = "SELECT * FROM adjustments WHERE guild_id = ? AND created_at >= ? AND created_at < ?"
        args: list = [guild_id, _ts(start), _ts(end)]
        if user_id is not None:
            sql += " AND user_id = ?"
            args.append(user_id)
        rows = self.conn.execute(sql + " ORDER BY created_at", args).fetchall()
        return [Adjustment(r["id"], r["guild_id"], r["user_id"], r["seconds"], r["reason"],
                           r["created_by"], _dt(r["created_at"])) for r in rows]
