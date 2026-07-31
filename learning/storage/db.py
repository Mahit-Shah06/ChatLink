"""
SQLite connection handling for the Learning Engine.

Phase 1: this file and schema.sql are the entire storage layer. No repository,
no models, no pipeline yet — those arrive in phase 2 and build on top of this.

Three things worth knowing about the setup:

  WAL mode is on, so the dashboard can read while the bot writes. Without it,
  a read would block a write and vice versa.

  Connections are per-thread. ChatLink runs one asyncio event loop, but every
  SQLite call from a cog goes through asyncio.to_thread, and the read API will
  eventually serve from its own threads. sqlite3 connections are not safe to
  share across threads, so each gets its own.

  Writes are serialised through a process-level lock. SQLite handles concurrent
  writers by making one of them fail with 'database is locked'; taking the lock
  ourselves turns that into a short wait instead of an exception.
"""

from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence

SCHEMA_PATH = Path(__file__).parent / "schema.sql"
SCHEMA_VERSION = 1

#: IST. A study day should roll over at your midnight, not UTC's — otherwise
#: everything you post after 5:30am IST lands on the wrong calendar day.
IST_OFFSET_MINUTES = 330


# --------------------------------------------------------------------- time
def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def to_iso(dt: Optional[datetime]) -> Optional[str]:
    """Normalise any datetime to a UTC ISO8601 string. Naive input is assumed UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def local_parts(dt: datetime, offset_minutes: int = IST_OFFSET_MINUTES) -> tuple[str, int]:
    """Return (YYYY-MM-DD, hour) in local time.

    Denormalised into every message row so analytics never has to do timezone
    arithmetic in SQL.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    local = dt.astimezone(timezone.utc) + timedelta(minutes=offset_minutes)
    return local.strftime("%Y-%m-%d"), local.hour


# ----------------------------------------------------------------- database
class Database:
    """Thin wrapper over a SQLite file. Owns connections, not meaning."""

    def __init__(self, path: Path | str, apply_schema: bool = True):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._write_lock = threading.RLock()
        if apply_schema:
            self.init_schema()

    # ---------------------------------------------------------- connection
    def connect(self) -> sqlite3.Connection:
        conn: Optional[sqlite3.Connection] = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(
                str(self.path),
                timeout=15.0,
                isolation_level=None,      # autocommit; transactions are explicit
                check_same_thread=False,
            )
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA busy_timeout=15000")
            self._local.conn = conn
        return conn

    def init_schema(self) -> None:
        """Apply schema.sql. Every statement is IF NOT EXISTS, so this is safe
        to run on every boot and is how the database gets created on first run."""
        with self._write_lock:
            conn = self.connect()
            conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))

    @property
    def schema_version(self) -> int:
        row = self.query_one("SELECT value FROM schema_meta WHERE key='schema_version'")
        return int(row["value"]) if row else 0

    # --------------------------------------------------------------- reads
    def query(self, sql: str, params: Sequence[Any] | dict = ()) -> list[sqlite3.Row]:
        return self.connect().execute(sql, params).fetchall()

    def query_one(self, sql: str, params: Sequence[Any] | dict = ()) -> Optional[sqlite3.Row]:
        return self.connect().execute(sql, params).fetchone()

    def scalar(self, sql: str, params: Sequence[Any] | dict = ()) -> Any:
        row = self.query_one(sql, params)
        return row[0] if row else None

    # -------------------------------------------------------------- writes
    def execute(self, sql: str, params: Sequence[Any] | dict = ()) -> sqlite3.Cursor:
        with self._write_lock:
            return self.connect().execute(sql, params)

    def executemany(self, sql: str, rows: Iterable[Sequence[Any]]) -> sqlite3.Cursor:
        with self._write_lock:
            return self.connect().executemany(sql, rows)

    def transaction(self) -> "_Transaction":
        """Write transaction held under the process lock.

            with db.transaction() as conn:
                conn.execute(...)
                conn.execute(...)

        Commits on clean exit, rolls back on exception.
        """
        return _Transaction(self)

    # ------------------------------------------------------------ lifecycle
    def vacuum(self) -> None:
        with self._write_lock:
            self.connect().execute("VACUUM")

    def close(self) -> None:
        conn: Optional[sqlite3.Connection] = getattr(self._local, "conn", None)
        if conn is not None:
            conn.close()
            self._local.conn = None

    def __repr__(self) -> str:
        return f"<Database {self.path} schema=v{self.schema_version}>"


class _Transaction:
    def __init__(self, db: Database):
        self.db = db
        self.conn: Optional[sqlite3.Connection] = None

    def __enter__(self) -> sqlite3.Connection:
        self.db._write_lock.acquire()
        self.conn = self.db.connect()
        self.conn.execute("BEGIN IMMEDIATE")
        return self.conn

    def __exit__(self, exc_type, exc, tb) -> bool:
        try:
            if exc_type is None:
                self.conn.execute("COMMIT")
            else:
                self.conn.execute("ROLLBACK")
        finally:
            self.db._write_lock.release()
        return False  # never swallow exceptions
