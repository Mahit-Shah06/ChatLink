"""
Phase 1 tests: the schema and connection layer, nothing above it.

These are mostly constraint tests. The point is to prove the database itself
enforces the rules we designed around — one active label per message, no
duplicate ingestion, soft deletes hiding rows from views — rather than trusting
later Python code to remember them.

    python -m pytest tests/test_storage.py -q
"""

from __future__ import annotations

import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from learning.storage import Database, local_parts, to_iso, utcnow

NOW = to_iso(utcnow())


@pytest.fixture
def db(tmp_path):
    return Database(tmp_path / "test.db")


# ------------------------------------------------------------------ helpers
def add_channel(db, external_id="101", label="sem3-computer-networks",
                subject="computer_networks", enabled=1):
    cur = db.execute(
        "INSERT INTO channels (source, external_id, label, context_kind, context_value, "
        "subject_key, enabled, created_at) VALUES ('discord', ?, ?, 'semester', 'sem3', ?, ?, ?)",
        (external_id, label, subject, enabled, NOW),
    )
    return cur.lastrowid


def add_message(db, channel_id=None, content="the OSI model has seven layers",
                external_id="m1", when=None, author="raj", author_id="7"):
    when = when or utcnow()
    date, hour = local_parts(when)
    cur = db.execute(
        "INSERT INTO messages (source, external_id, channel_id, author_id, author_name, "
        "content, content_hash, metadata, created_at, local_date, local_hour, ingested_at) "
        "VALUES ('discord', ?, ?, ?, ?, ?, 'hash', '{}', ?, ?, ?, ?)",
        (external_id, channel_id, author_id, author, content, to_iso(when), date, hour, NOW),
    )
    return cur.lastrowid


def add_classification(db, message_id, label="note", source="auto", active=1):
    cur = db.execute(
        "INSERT INTO classifications (message_id, label, confidence, classifier_name, "
        "classifier_version, label_source, is_active, created_at) "
        "VALUES (?, ?, 0.8, 'rules', '1.0', ?, ?, ?)",
        (message_id, label, source, active, NOW),
    )
    return cur.lastrowid


# ------------------------------------------------------------------- basics
def test_schema_applies_and_reports_version(db):
    assert db.schema_version == 1


def test_schema_is_idempotent(tmp_path):
    path = tmp_path / "twice.db"
    Database(path)
    add_channel(Database(path, apply_schema=False))
    second = Database(path)              # re-applying must not wipe anything
    assert second.scalar("SELECT COUNT(*) FROM channels") == 1


def test_wal_mode_is_enabled(db):
    assert db.scalar("PRAGMA journal_mode").lower() == "wal"


def test_foreign_keys_are_enforced(db):
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO attachments (message_id, filename, created_at) VALUES (99999, 'x.pdf', ?)",
            (NOW,),
        )


def test_expected_tables_exist(db):
    rows = db.query("SELECT name FROM sqlite_master WHERE type='table'")
    names = {r["name"] for r in rows}
    assert {"channels", "messages", "attachments", "classifications",
            "nodes", "edges", "topic_links", "candidate_terms"} <= names


# ------------------------------------------------------------ time handling
def test_local_parts_shifts_into_ist():
    # 20:00 UTC on 1 Jan is 01:30 IST on 2 Jan — the day must roll over.
    dt = datetime(2026, 1, 1, 20, 0, tzinfo=timezone.utc)
    date, hour = local_parts(dt)
    assert date == "2026-01-02" and hour == 1


def test_local_parts_handles_naive_datetime_as_utc():
    assert local_parts(datetime(2026, 1, 1, 20, 0)) == ("2026-01-02", 1)


def test_late_night_message_lands_on_the_right_study_day(db):
    ch = add_channel(db)
    # 22:00 IST on 10 March = 16:30 UTC same day
    add_message(db, ch, when=datetime(2026, 3, 10, 16, 30, tzinfo=timezone.utc))
    row = db.query_one("SELECT local_date, local_hour FROM messages")
    assert row["local_date"] == "2026-03-10" and row["local_hour"] == 22


# ------------------------------------------------------------ message rules
def test_duplicate_ingestion_is_rejected(db):
    ch = add_channel(db)
    add_message(db, ch, external_id="dup")
    with pytest.raises(sqlite3.IntegrityError):
        add_message(db, ch, external_id="dup")


def test_same_external_id_allowed_across_sources(db):
    """Discord id 5 and a CLI import id 5 are different messages."""
    add_message(db, external_id="5")
    db.execute(
        "INSERT INTO messages (source, external_id, content, content_hash, created_at, "
        "local_date, local_hour, ingested_at) VALUES ('cli', '5', 'x', 'h', ?, '2026-01-01', 9, ?)",
        (NOW, NOW),
    )
    assert db.scalar("SELECT COUNT(*) FROM messages") == 2


def test_soft_deleted_messages_vanish_from_view_but_stay_in_table(db):
    ch = add_channel(db)
    mid = add_message(db, ch)
    db.execute("UPDATE messages SET deleted_at=? WHERE id=?", (NOW, mid))
    assert db.scalar("SELECT COUNT(*) FROM v_entries") == 0
    assert db.scalar("SELECT COUNT(*) FROM messages") == 1


def test_deleting_a_channel_keeps_its_messages(db):
    ch = add_channel(db)
    add_message(db, ch)
    db.execute("DELETE FROM channels WHERE id=?", (ch,))
    row = db.query_one("SELECT channel_id FROM messages")
    assert row["channel_id"] is None      # ON DELETE SET NULL, message survives


# --------------------------------------------------- classification rules
def test_only_one_active_classification_per_message(db):
    mid = add_message(db, add_channel(db))
    add_classification(db, mid, "note")
    with pytest.raises(sqlite3.IntegrityError):
        add_classification(db, mid, "question")


def test_supersede_pattern_preserves_history(db):
    """The reclassify path: deactivate, then insert. Old opinions are kept."""
    mid = add_message(db, add_channel(db))
    add_classification(db, mid, "note")
    with db.transaction() as conn:
        conn.execute("UPDATE classifications SET is_active=0 WHERE message_id=?", (mid,))
        conn.execute(
            "INSERT INTO classifications (message_id, label, confidence, classifier_name, "
            "classifier_version, label_source, is_active, created_at) "
            "VALUES (?, 'revision', 1.0, 'rules', '1.0', 'human', 1, ?)",
            (mid, NOW),
        )
    assert db.scalar("SELECT COUNT(*) FROM classifications WHERE message_id=?", (mid,)) == 2
    active = db.query_one(
        "SELECT label, label_source FROM classifications WHERE message_id=? AND is_active=1", (mid,))
    assert active["label"] == "revision" and active["label_source"] == "human"


def test_classifications_cascade_on_message_delete(db):
    mid = add_message(db, add_channel(db))
    add_classification(db, mid)
    db.execute("DELETE FROM messages WHERE id=?", (mid,))
    assert db.scalar("SELECT COUNT(*) FROM classifications") == 0


# ------------------------------------------------------------------- views
def test_entries_view_joins_channel_and_label(db):
    ch = add_channel(db)
    mid = add_message(db, ch, content="revised the transport layer")
    add_classification(db, mid, "revision")
    row = db.query_one("SELECT * FROM v_entries")
    assert row["label"] == "revision"
    assert row["channel_label"] == "sem3-computer-networks"
    assert row["channel_subject_key"] == "computer_networks"
    assert row["local_hour"] is not None


def test_entries_view_shows_unclassified_messages(db):
    """Phase 2 stores messages with no label at all. They must still be visible."""
    add_message(db, add_channel(db))
    row = db.query_one("SELECT * FROM v_entries")
    assert row is not None and row["label"] is None


def test_entries_view_counts_attachments(db):
    mid = add_message(db, add_channel(db))
    for i, kind in enumerate(["image", "document"]):
        db.execute(
            "INSERT INTO attachments (message_id, filename, kind, created_at) VALUES (?, ?, ?, ?)",
            (mid, f"f{i}", kind, NOW),
        )
    assert db.query_one("SELECT attachment_count FROM v_entries")["attachment_count"] == 2


def test_node_stats_view_aggregates_labels(db):
    ch = add_channel(db)
    db.execute(
        "INSERT INTO nodes (key, kind, name, subject_key, created_at) "
        "VALUES ('osi_model', 'topic', 'OSI Model', 'computer_networks', ?)", (NOW,))
    for i, label in enumerate(["question", "note", "note"]):
        mid = add_message(db, ch, external_id=f"n{i}")
        add_classification(db, mid, label)
        db.execute(
            "INSERT INTO topic_links (message_id, node_key, confidence, extractor_name, "
            "extractor_version, created_at) VALUES (?, 'osi_model', 0.9, 'matcher', '1', ?)",
            (mid, NOW))
    row = db.query_one("SELECT * FROM v_node_stats WHERE node_key='osi_model'")
    assert row["mentions"] == 3 and row["questions"] == 1 and row["notes"] == 2


# --------------------------------------------------------------------- fts
def test_full_text_search_finds_messages(db):
    ch = add_channel(db)
    add_message(db, ch, content="the sliding window protocol controls flow", external_id="f1")
    add_message(db, ch, content="completely unrelated content", external_id="f2")
    rows = db.query(
        "SELECT m.content FROM messages_fts f JOIN messages m ON m.id=f.rowid "
        "WHERE messages_fts MATCH 'sliding'")
    assert len(rows) == 1


def test_fts_stems_words(db):
    add_message(db, add_channel(db), content="revising the OSI model tonight")
    assert len(db.query("SELECT * FROM messages_fts WHERE messages_fts MATCH 'revise'")) == 1


def test_fts_updates_when_content_is_edited(db):
    ch = add_channel(db)
    mid = add_message(db, ch, content="original text about paging")
    db.execute("UPDATE messages SET content='rewritten text about deadlock' WHERE id=?", (mid,))
    assert len(db.query("SELECT * FROM messages_fts WHERE messages_fts MATCH 'paging'")) == 0
    assert len(db.query("SELECT * FROM messages_fts WHERE messages_fts MATCH 'deadlock'")) == 1


# ------------------------------------------------------------ transactions
def test_transaction_rolls_back_on_error(db):
    ch = add_channel(db)
    try:
        with db.transaction() as conn:
            conn.execute(
                "INSERT INTO messages (source, external_id, channel_id, content, content_hash, "
                "created_at, local_date, local_hour, ingested_at) "
                "VALUES ('discord','rb',?,'x','h',?,?,9,?)", (ch, NOW, "2026-01-01", NOW))
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    assert db.scalar("SELECT COUNT(*) FROM messages") == 0


def test_transaction_commits_on_success(db):
    ch = add_channel(db)
    with db.transaction() as conn:
        conn.execute(
            "INSERT INTO messages (source, external_id, channel_id, content, content_hash, "
            "created_at, local_date, local_hour, ingested_at) "
            "VALUES ('discord','ok',?,'x','h',?,?,9,?)", (ch, NOW, "2026-01-01", NOW))
    assert db.scalar("SELECT COUNT(*) FROM messages") == 1


def test_edges_are_unique_per_relation(db):
    for _ in range(2):
        db.execute(
            "INSERT INTO edges (src_key, dst_key, relation, created_at, updated_at) "
            "VALUES ('a','b','co_occurs',?,?) "
            "ON CONFLICT(src_key,dst_key,relation) DO UPDATE SET observations=observations+1",
            (NOW, NOW))
    row = db.query_one("SELECT observations FROM edges")
    assert db.scalar("SELECT COUNT(*) FROM edges") == 1 and row["observations"] == 1


def test_concurrent_writes_from_threads_do_not_corrupt(db):
    """Two threads writing at once should serialise, not raise 'database is locked'."""
    import threading

    ch = add_channel(db)
    errors: list[Exception] = []

    def writer(start: int):
        try:
            for i in range(start, start + 25):
                add_message(db, ch, external_id=f"t{i}")
        except Exception as exc:                      # pragma: no cover
            errors.append(exc)

    threads = [threading.Thread(target=writer, args=(n * 100,)) for n in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors
    assert db.scalar("SELECT COUNT(*) FROM messages") == 100
