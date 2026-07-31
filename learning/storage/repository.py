"""
Storage access. The only module in the engine that writes SQL.

If SQLite is ever outgrown, this class gets reimplemented against something else
and nothing above it changes.

Phase 2 writes messages, channels and attachments. The classification and
topic_link methods will land in phases 3 and 4 — the tables are already there.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional

from ..models import Attachment, ChannelContext, IncomingMessage
from .db import Database, local_parts, to_iso, utcnow


def content_hash(text: str) -> str:
    normalised = " ".join((text or "").lower().split())
    return hashlib.sha1(normalised.encode("utf-8")).hexdigest()


class LearningRepository:
    def __init__(self, db: Database):
        self.db = db

    # ------------------------------------------------------------- channels
    def upsert_channel(self, ctx: ChannelContext) -> int:
        now = to_iso(utcnow())
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO channels (source, external_id, label, context_kind,
                                      context_value, subject_key, enabled, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source, external_id) DO UPDATE SET
                    label         = excluded.label,
                    context_kind  = excluded.context_kind,
                    context_value = excluded.context_value,
                    subject_key   = excluded.subject_key,
                    enabled       = excluded.enabled
                """,
                (ctx.source, str(ctx.external_id), ctx.label, ctx.context_kind,
                 ctx.context_value, ctx.subject_key, 1 if ctx.enabled else 0, now),
            )
            row = conn.execute(
                "SELECT id FROM channels WHERE source=? AND external_id=?",
                (ctx.source, str(ctx.external_id)),
            ).fetchone()
        return int(row["id"])

    # -------------------------------------------------------------- capture
    def save_message(self, msg: IncomingMessage) -> int:
        """Insert or update one message. Idempotent on (source, external_id).

        Re-ingesting the same Discord message — which happens on edit, and on
        every backfill — updates the content and stamps edited_at rather than
        creating a duplicate. That's what makes replay-from-Discord safe to run
        as many times as you like.
        """
        now = to_iso(utcnow())
        created = to_iso(msg.created_at)
        date, hour = local_parts(msg.created_at)
        channel_id = self.upsert_channel(msg.channel) if msg.channel.external_id else None

        with self.db.transaction() as conn:
            cur = conn.execute(
                """
                INSERT INTO messages (source, external_id, channel_id, thread_id, author_id,
                                      author_name, content, content_hash, reply_to, metadata,
                                      created_at, local_date, local_hour, ingested_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source, external_id) DO UPDATE SET
                    content      = excluded.content,
                    content_hash = excluded.content_hash,
                    edited_at    = CASE WHEN messages.content_hash != excluded.content_hash
                                        THEN excluded.ingested_at ELSE messages.edited_at END
                RETURNING id
                """,
                (msg.source, msg.external_id, channel_id, msg.thread_id,
                 str(msg.author_id) if msg.author_id else None, msg.author_name,
                 msg.content, content_hash(msg.content), msg.reply_to,
                 json.dumps(msg.metadata, default=str), created, date, hour, now),
            )
            message_id = int(cur.fetchone()[0])

            if msg.attachments:
                conn.execute("DELETE FROM attachments WHERE message_id=?", (message_id,))
                conn.executemany(
                    "INSERT INTO attachments (message_id, filename, url, content_type, "
                    "kind, size_bytes, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    [(message_id, a.filename, a.url, a.content_type, a.kind,
                      a.size_bytes, now) for a in msg.attachments],
                )

        return message_id

    def mark_deleted(self, source: str, external_id: str) -> bool:
        cur = self.db.execute(
            "UPDATE messages SET deleted_at=? WHERE source=? AND external_id=? "
            "AND deleted_at IS NULL",
            (to_iso(utcnow()), source, str(external_id)),
        )
        return cur.rowcount > 0

    # ----------------------------------------------------------------- reads
    def summary(self) -> Dict[str, Any]:
        row = self.db.query_one(
            "SELECT COUNT(*) AS messages, COUNT(DISTINCT local_date) AS active_days, "
            "COUNT(DISTINCT author_id) AS authors, MIN(local_date) AS first_day, "
            "MAX(local_date) AS last_day FROM messages WHERE deleted_at IS NULL"
        )
        return {
            "messages": row["messages"],
            "active_days": row["active_days"],
            "authors": row["authors"],
            "first_day": row["first_day"],
            "last_day": row["last_day"],
            "attachments": self.db.scalar(
                "SELECT COUNT(*) FROM attachments a JOIN messages m ON m.id=a.message_id "
                "WHERE m.deleted_at IS NULL"
            ),
            "channels": self.db.scalar("SELECT COUNT(*) FROM channels WHERE enabled=1"),
        }

    def per_channel(self) -> List[Dict[str, Any]]:
        rows = self.db.query(
            """
            SELECT ch.label, ch.context_kind, ch.context_value, ch.subject_key,
                   COUNT(m.id) AS messages, MAX(m.local_date) AS last_seen
            FROM channels ch
            LEFT JOIN messages m ON m.channel_id = ch.id AND m.deleted_at IS NULL
            WHERE ch.enabled = 1
            GROUP BY ch.id
            ORDER BY messages DESC
            """
        )
        return [dict(r) for r in rows]

    def recent(self, limit: int = 20) -> List[Dict[str, Any]]:
        rows = self.db.query(
            "SELECT message_id, content, author_name, channel_label, created_at, "
            "local_date, local_hour, attachment_count FROM v_entries "
            "ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
        return [dict(r) for r in rows]

    def daily_counts(self, days: int = 30) -> List[Dict[str, Any]]:
        rows = self.db.query(
            "SELECT local_date, COUNT(*) AS count FROM messages "
            "WHERE deleted_at IS NULL GROUP BY local_date "
            "ORDER BY local_date DESC LIMIT ?",
            (days,),
        )
        return [dict(r) for r in reversed(rows)]

    def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        rows = self.db.query(
            "SELECT m.id AS message_id, m.content, m.author_name, m.local_date, "
            "ch.label AS channel_label FROM messages_fts f "
            "JOIN messages m ON m.id = f.rowid "
            "LEFT JOIN channels ch ON ch.id = m.channel_id "
            "WHERE messages_fts MATCH ? AND m.deleted_at IS NULL "
            "ORDER BY rank LIMIT ?",
            (query, limit),
        )
        return [dict(r) for r in rows]
