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

from ..models import (Attachment, ChannelContext, Classification, IncomingMessage,
                      Label, ProcessedMessage, TopicMatch)
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


    # ==================================================== phase 3/4 : labels
    def save_processed(self, processed: ProcessedMessage) -> int:
        """Persist a message together with its label and topic links."""
        message_id = self.save_message(processed.message)
        processed.message_id = message_id
        now = to_iso(utcnow())

        with self.db.transaction() as conn:
            if processed.classification:
                self._write_classification(conn, message_id, processed.classification, now)
            if processed.topics:
                self._write_topics(conn, message_id, processed.topics, now)
                self._write_cooccurrence(conn, processed.topics, now)
            if processed.candidate_terms:
                self._write_candidates(conn, processed.candidate_terms, now)

        return message_id

    def _write_classification(self, conn, message_id: int, c: Classification, now: str) -> None:
        """Supersede, never update. Old opinions stay for comparison."""
        conn.execute("UPDATE classifications SET is_active=0 WHERE message_id=? AND is_active=1",
                     (message_id,))
        conn.execute(
            """
            INSERT INTO classifications (message_id, label, secondary_label, confidence,
                                         scores, evidence, classifier_name, classifier_version,
                                         label_source, is_active, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
            """,
            (message_id, c.label.value,
             c.secondary_label.value if c.secondary_label else None,
             float(c.confidence), json.dumps(c.scores), json.dumps(c.evidence),
             c.classifier_name, c.classifier_version, c.label_source, now),
        )

    def _write_topics(self, conn, message_id: int, topics, now: str) -> None:
        conn.execute("UPDATE topic_links SET is_active=0 WHERE message_id=?", (message_id,))
        for t in topics:
            if not conn.execute("SELECT 1 FROM nodes WHERE key=?", (t.node_key,)).fetchone():
                conn.execute(
                    "INSERT INTO nodes (key, kind, name, parent_key, subject_key, "
                    "taxonomy_version, metadata, created_at) VALUES (?,?,?,?,?,'runtime','{}',?)",
                    (t.node_key, t.node_kind.value, t.name, t.parent_key, t.subject_key, now))
            conn.execute(
                """
                INSERT INTO topic_links (message_id, node_key, confidence, matched_text,
                                         extractor_name, extractor_version, is_active, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 1, ?)
                ON CONFLICT(message_id, node_key, extractor_name) DO UPDATE SET
                    confidence=excluded.confidence, matched_text=excluded.matched_text,
                    extractor_version=excluded.extractor_version, is_active=1
                """,
                (message_id, t.node_key, float(t.confidence), t.matched_text,
                 "taxonomy-matcher", "current", now))

    def _write_cooccurrence(self, conn, topics, now: str) -> None:
        """Two topics in one message is weak evidence they connect. Accumulate."""
        keys = sorted({t.node_key for t in topics if t.confidence >= 0.6})
        for i, a in enumerate(keys):
            for b in keys[i + 1:]:
                conn.execute(
                    """
                    INSERT INTO edges (src_key, dst_key, relation, weight, observations,
                                       created_at, updated_at)
                    VALUES (?, ?, 'co_occurs', 1.0, 1, ?, ?)
                    ON CONFLICT(src_key, dst_key, relation) DO UPDATE SET
                        observations = edges.observations + 1,
                        weight = edges.weight + 1.0,
                        updated_at = excluded.updated_at
                    """, (a, b, now, now))

    def _write_candidates(self, conn, terms, now: str) -> None:
        for term in terms:
            conn.execute(
                """
                INSERT INTO candidate_terms (term, occurrences, first_seen, last_seen, status)
                VALUES (?, 1, ?, ?, 'new')
                ON CONFLICT(term) DO UPDATE SET
                    occurrences = candidate_terms.occurrences + 1,
                    last_seen = excluded.last_seen
                """, (term, now, now))

    def sync_taxonomy(self, taxonomy) -> dict:
        """Upsert taxonomy nodes and structural edges. Safe on every boot."""
        now = to_iso(utcnow())
        with self.db.transaction() as conn:
            for node in taxonomy.nodes.values():
                conn.execute(
                    """
                    INSERT INTO nodes (key, kind, name, parent_key, subject_key,
                                       taxonomy_version, metadata, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, '{}', ?)
                    ON CONFLICT(key) DO UPDATE SET
                        kind=excluded.kind, name=excluded.name,
                        parent_key=excluded.parent_key, subject_key=excluded.subject_key,
                        taxonomy_version=excluded.taxonomy_version
                    """,
                    (node.key, node.kind.value, node.name, node.parent_key,
                     node.subject_key, taxonomy.version, now))
            for src, dst, rel in taxonomy.edges:
                conn.execute(
                    "INSERT INTO edges (src_key, dst_key, relation, weight, observations, "
                    "created_at, updated_at) VALUES (?,?,?,1.0,0,?,?) "
                    "ON CONFLICT(src_key,dst_key,relation) DO UPDATE SET updated_at=excluded.updated_at",
                    (src, dst, rel.value, now, now))
        return {"nodes": len(taxonomy.nodes), "edges": len(taxonomy.edges)}

    def relabel(self, message_id: int, label: str, source: str = "human") -> bool:
        """A human correction. This is the training signal for a future model."""
        row = self.db.query_one(
            "SELECT classifier_name, classifier_version FROM classifications "
            "WHERE message_id=? ORDER BY id DESC LIMIT 1", (message_id,))
        if not row:
            return False
        now = to_iso(utcnow())
        with self.db.transaction() as conn:
            conn.execute("UPDATE classifications SET is_active=0 WHERE message_id=? AND is_active=1",
                         (message_id,))
            conn.execute(
                "INSERT INTO classifications (message_id, label, confidence, scores, evidence, "
                "classifier_name, classifier_version, label_source, is_active, created_at) "
                "VALUES (?, ?, 1.0, '{}', '[]', ?, ?, ?, 1, ?)",
                (message_id, Label.parse(label).value, row["classifier_name"],
                 row["classifier_version"], source, now))
        return True

    # ------------------------------------------------------------- analytics
    def label_counts(self, days: Optional[int] = None):
        where, params = "WHERE m.deleted_at IS NULL", []
        if days:
            where += " AND m.local_date >= date('now', ?, '+330 minutes')"
            params.append(f"-{days} days")
        rows = self.db.query(
            f"SELECT c.label, COUNT(*) AS count, AVG(c.confidence) AS avg_confidence "
            f"FROM messages m JOIN classifications c ON c.message_id=m.id AND c.is_active=1 "
            f"{where} GROUP BY c.label ORDER BY count DESC", tuple(params))
        return [dict(r) for r in rows]

    def daily_activity(self, days: int = 30):
        rows = self.db.query(
            "SELECT m.local_date AS date, c.label, COUNT(*) AS count FROM messages m "
            "LEFT JOIN classifications c ON c.message_id=m.id AND c.is_active=1 "
            "WHERE m.deleted_at IS NULL GROUP BY m.local_date, c.label "
            "ORDER BY m.local_date DESC LIMIT ?", (days * 8,))
        buckets = {}
        for r in rows:
            entry = buckets.setdefault(r["date"], {"date": r["date"], "total": 0})
            entry[r["label"] or "unclassified"] = r["count"]
            entry["total"] += r["count"]
        return sorted(buckets.values(), key=lambda x: x["date"])[-days:]

    def hourly_pattern(self):
        rows = self.db.query(
            "SELECT local_hour AS hour, COUNT(*) AS count FROM messages "
            "WHERE deleted_at IS NULL GROUP BY local_hour ORDER BY local_hour")
        return [dict(r) for r in rows]

    def topic_stats(self, kind=None, limit: int = 60):
        where = ["tl.is_active = 1", "m.deleted_at IS NULL"]
        params = []
        if kind:
            where.append("n.kind = ?")
            params.append(kind)
        params.append(limit)
        rows = self.db.query(
            f"""
            SELECT n.key AS node_key, n.name, n.kind, n.parent_key, n.subject_key,
                   COUNT(DISTINCT m.id) AS mentions,
                   SUM(CASE WHEN c.label='question' THEN 1 ELSE 0 END) AS questions,
                   SUM(CASE WHEN c.label='note'     THEN 1 ELSE 0 END) AS notes,
                   SUM(CASE WHEN c.label='idea'     THEN 1 ELSE 0 END) AS ideas,
                   SUM(CASE WHEN c.label='progress' THEN 1 ELSE 0 END) AS progress,
                   SUM(CASE WHEN c.label='revision' THEN 1 ELSE 0 END) AS revisions,
                   SUM(CASE WHEN c.label='resource' THEN 1 ELSE 0 END) AS resources,
                   MIN(m.local_date) AS first_seen, MAX(m.local_date) AS last_seen
            FROM topic_links tl
            JOIN nodes n ON n.key = tl.node_key
            JOIN messages m ON m.id = tl.message_id
            LEFT JOIN classifications c ON c.message_id = m.id AND c.is_active = 1
            WHERE {' AND '.join(where)}
            GROUP BY n.key ORDER BY mentions DESC LIMIT ?
            """, tuple(params))
        out = []
        for r in rows:
            d = dict(r)
            asked = d.get("questions") or 0
            settled = (d.get("notes") or 0) + (d.get("revisions") or 0) + (d.get("progress") or 0)
            d["open_ratio"] = round(asked / (asked + settled), 3) if (asked + settled) else 0.0
            out.append(d)
        return out

    def weak_topics(self, min_mentions: int = 2, limit: int = 10):
        """Questions asked but little understanding recorded."""
        stats = [s for s in self.topic_stats(limit=400)
                 if s["mentions"] >= min_mentions and s["questions"] > 0]
        stats.sort(key=lambda s: (-s["open_ratio"], -s["questions"]))
        return stats[:limit]

    def stale_topics(self, days_since: int = 14, limit: int = 10):
        """Studied once, never revisited."""
        from datetime import timedelta
        cutoff = (utcnow() + timedelta(minutes=330) - timedelta(days=days_since)).strftime("%Y-%m-%d")
        stale = [s for s in self.topic_stats(limit=400)
                 if s["last_seen"] and s["last_seen"] < cutoff
                 and s["mentions"] >= 2 and (s["revisions"] or 0) == 0]
        stale.sort(key=lambda s: (s["last_seen"], -s["mentions"]))
        return stale[:limit]

    def entries(self, label=None, node_key=None, query=None, needs_review=False,
                limit: int = 50, offset: int = 0):
        where = ["m.deleted_at IS NULL"]
        params, joins = [], ""
        if node_key:
            joins += " JOIN topic_links tl ON tl.message_id=m.id AND tl.is_active=1 AND tl.node_key=?"
            params.append(node_key)
        if query:
            joins += " JOIN messages_fts fts ON fts.rowid = m.id"
            where.append("messages_fts MATCH ?")
            params.append(query)
        if label:
            where.append("c.label = ?")
            params.append(label)
        if needs_review:
            where.append("c.label_source='auto' AND c.confidence < 0.5")
        params.extend([limit, offset])
        rows = self.db.query(
            f"""
            SELECT m.id AS message_id, m.content, m.created_at, m.local_date, m.local_hour,
                   m.author_name, ch.label AS channel_label,
                   c.label, c.confidence, c.label_source, c.secondary_label,
                   (SELECT COUNT(*) FROM attachments a WHERE a.message_id=m.id) AS attachment_count,
                   (SELECT GROUP_CONCAT(n2.name, ' - ') FROM topic_links t2
                      JOIN nodes n2 ON n2.key=t2.node_key
                     WHERE t2.message_id=m.id AND t2.is_active=1 AND n2.kind!='subject') AS topics
            FROM messages m
            LEFT JOIN channels ch ON ch.id = m.channel_id
            LEFT JOIN classifications c ON c.message_id = m.id AND c.is_active = 1
            {joins}
            WHERE {' AND '.join(where)}
            ORDER BY m.created_at DESC LIMIT ? OFFSET ?
            """, tuple(params))
        return [dict(r) for r in rows]

    def graph(self, limit_nodes: int = 120):
        node_rows = self.db.query(
            "SELECT n.key, n.name, n.kind, n.parent_key, n.subject_key, "
            "COUNT(DISTINCT tl.message_id) AS mentions FROM nodes n "
            "LEFT JOIN topic_links tl ON tl.node_key=n.key AND tl.is_active=1 "
            "GROUP BY n.key HAVING mentions > 0 ORDER BY mentions DESC LIMIT ?", (limit_nodes,))
        nodes = [dict(r) for r in node_rows]
        keys = {n["key"] for n in nodes}
        if not keys:
            return {"nodes": [], "edges": []}
        ph = ",".join("?" * len(keys))
        edge_rows = self.db.query(
            f"SELECT src_key, dst_key, relation, weight, observations FROM edges "
            f"WHERE src_key IN ({ph}) AND dst_key IN ({ph})", (*keys, *keys))
        return {"nodes": nodes, "edges": [dict(r) for r in edge_rows]}

    def candidates(self, limit: int = 30, min_occurrences: int = 2):
        rows = self.db.query(
            "SELECT term, occurrences, last_seen FROM candidate_terms "
            "WHERE status='new' AND occurrences >= ? ORDER BY occurrences DESC LIMIT ?",
            (min_occurrences, limit))
        return [dict(r) for r in rows]

    def streak(self) -> int:
        from datetime import datetime as _dt, timedelta as _td
        rows = self.db.query("SELECT DISTINCT local_date FROM messages "
                             "WHERE deleted_at IS NULL ORDER BY local_date DESC LIMIT 400")
        if not rows:
            return 0
        days = [r["local_date"] for r in rows]
        today = (utcnow() + _td(minutes=330)).date()
        first = _dt.strptime(days[0], "%Y-%m-%d").date()
        if (today - first).days > 1:
            return 0
        streak, expected = 0, first
        for d in days:
            dd = _dt.strptime(d, "%Y-%m-%d").date()
            if dd == expected:
                streak += 1
                expected -= _td(days=1)
            elif dd < expected:
                break
        return streak

    def messages_for_reclassification(self, batch: int = 500, offset: int = 0):
        rows = self.db.query(
            "SELECT m.id, m.content, m.source, m.external_id, ch.external_id AS channel_external_id, "
            "ch.subject_key, ch.label AS channel_label, ch.context_kind, ch.context_value "
            "FROM messages m LEFT JOIN channels ch ON ch.id=m.channel_id "
            "WHERE m.deleted_at IS NULL ORDER BY m.id LIMIT ? OFFSET ?", (batch, offset))
        return [dict(r) for r in rows]

    # ------------------------------------------------- dashboard: coverage
    def all_node_stats(self) -> dict:
        """Stats for every node that has ever been linked, keyed by node key.

        Deliberately returns only what exists in the database. The caller merges
        this against the taxonomy so that untouched syllabus topics still appear
        — a coverage view that hides what you haven't done is useless.
        """
        rows = self.db.query(
            """
            SELECT tl.node_key,
                   COUNT(DISTINCT m.id) AS mentions,
                   SUM(CASE WHEN c.label='question' THEN 1 ELSE 0 END) AS questions,
                   SUM(CASE WHEN c.label='note'     THEN 1 ELSE 0 END) AS notes,
                   SUM(CASE WHEN c.label='idea'     THEN 1 ELSE 0 END) AS ideas,
                   SUM(CASE WHEN c.label='progress' THEN 1 ELSE 0 END) AS progress,
                   SUM(CASE WHEN c.label='revision' THEN 1 ELSE 0 END) AS revisions,
                   SUM(CASE WHEN c.label='resource' THEN 1 ELSE 0 END) AS resources,
                   MIN(m.local_date) AS first_seen,
                   MAX(m.local_date) AS last_seen
            FROM topic_links tl
            JOIN messages m ON m.id = tl.message_id AND m.deleted_at IS NULL
            LEFT JOIN classifications c ON c.message_id = m.id AND c.is_active = 1
            WHERE tl.is_active = 1
            GROUP BY tl.node_key
            """)
        return {r["node_key"]: dict(r) for r in rows}

    def heatmap(self, days: int = 182) -> list:
        """One cell per day for the last N days, including days with nothing.

        A contribution grid is only readable if the empty days are there too —
        the gaps are the information.
        """
        from datetime import date, timedelta

        rows = self.db.query(
            "SELECT local_date, COUNT(*) AS count FROM messages "
            "WHERE deleted_at IS NULL GROUP BY local_date")
        counts = {r["local_date"]: r["count"] for r in rows}

        today = (utcnow() + timedelta(minutes=330)).date()
        start = today - timedelta(days=days - 1)
        out = []
        for i in range(days):
            d = start + timedelta(days=i)
            key = d.strftime("%Y-%m-%d")
            out.append({"date": key, "count": counts.get(key, 0),
                        "weekday": d.weekday()})
        return out

    def timeline(self, limit: int = 60, offset: int = 0) -> list:
        """Reverse-chronological feed with full timestamps, like a commit log."""
        rows = self.db.query(
            """
            SELECT m.id AS message_id, m.content, m.created_at, m.local_date,
                   m.local_hour, m.author_name, m.thread_id,
                   ch.label AS channel_label, ch.subject_key,
                   c.label, c.confidence, c.label_source,
                   (SELECT COUNT(*) FROM attachments a WHERE a.message_id=m.id)
                       AS attachment_count,
                   (SELECT GROUP_CONCAT(n2.name, ' · ') FROM topic_links t2
                      JOIN nodes n2 ON n2.key=t2.node_key
                     WHERE t2.message_id=m.id AND t2.is_active=1
                       AND n2.kind != 'subject') AS topics
            FROM messages m
            LEFT JOIN channels ch ON ch.id = m.channel_id
            LEFT JOIN classifications c ON c.message_id = m.id AND c.is_active = 1
            WHERE m.deleted_at IS NULL
            ORDER BY m.created_at DESC
            LIMIT ? OFFSET ?
            """, (limit, offset))
        return [dict(r) for r in rows]
