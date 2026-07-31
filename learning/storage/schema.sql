-- ChatLink Learning Engine — schema v1
--
-- Written in full up front. Phase 2 only writes to channels/messages/attachments;
-- the rest sit empty until phases 3-5 fill them. Empty tables cost nothing, and
-- this way there are no migrations to run against a database that already holds
-- real history.
--
-- Two rules the whole design rests on:
--
--   1. Messages are facts. Labels are opinions. Facts are immutable, opinions
--      are versioned. Nothing is ever UPDATEd in classifications or topic_links —
--      a new row is inserted and the old one flagged is_active = 0.
--
--   2. Discord is the write-ahead log; this database is a projection of it.
--      Every row here is rebuildable by replaying channel history, which is why
--      external_id carries a UNIQUE constraint everywhere it appears.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

INSERT OR IGNORE INTO schema_meta (key, value) VALUES ('schema_version', '1');


-- ============================================================== channels
-- A channel is the context prior. #sem3-computer-networks tells the engine the
-- subject before it reads a single word of the message.

CREATE TABLE IF NOT EXISTS channels (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    source        TEXT    NOT NULL DEFAULT 'discord',
    external_id   TEXT    NOT NULL,
    label         TEXT,                            -- channel name as it reads in Discord
    context_kind  TEXT    NOT NULL DEFAULT 'general',  -- semester | exam | general
    context_value TEXT    NOT NULL DEFAULT '',         -- sem3 | gate | ''
    subject_key   TEXT,                            -- taxonomy subject, NULL = infer from text
    enabled       INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT    NOT NULL,
    UNIQUE (source, external_id)
);


-- ============================================================== messages
-- The immutable core. Everything else in this file is derived from these rows
-- and can be thrown away and recomputed.
--
-- local_date and local_hour are denormalised IST values. They are redundant with
-- created_at, deliberately: "which topics do I study at 1am" is a phase 8
-- question, and recomputing timezone offsets inside every analytics query is both
-- slow and a reliable source of off-by-one-day bugs.

CREATE TABLE IF NOT EXISTS messages (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    source       TEXT    NOT NULL DEFAULT 'discord',
    external_id  TEXT,                             -- Discord message id
    channel_id   INTEGER REFERENCES channels(id) ON DELETE SET NULL,
    thread_id    TEXT,                             -- NULL unless posted in a thread
    author_id    TEXT,                             -- first-class: ChatLink is multi-user
    author_name  TEXT,
    content      TEXT    NOT NULL,
    content_hash TEXT    NOT NULL,                 -- sha1 of normalised text
    reply_to     TEXT,                             -- external_id of the message replied to
    metadata     TEXT    NOT NULL DEFAULT '{}',    -- jump_url, guild_id, etc.
    created_at   TEXT    NOT NULL,                 -- ISO8601 UTC, full precision
    local_date   TEXT    NOT NULL,                 -- YYYY-MM-DD in IST
    local_hour   INTEGER NOT NULL,                 -- 0-23 in IST
    ingested_at  TEXT    NOT NULL,
    edited_at    TEXT,
    deleted_at   TEXT,                             -- soft delete; rows are never removed
    UNIQUE (source, external_id)
);

CREATE INDEX IF NOT EXISTS idx_messages_created    ON messages(created_at);
CREATE INDEX IF NOT EXISTS idx_messages_local_date ON messages(local_date);
CREATE INDEX IF NOT EXISTS idx_messages_local_hour ON messages(local_hour);
CREATE INDEX IF NOT EXISTS idx_messages_channel    ON messages(channel_id);
CREATE INDEX IF NOT EXISTS idx_messages_author     ON messages(author_id);
CREATE INDEX IF NOT EXISTS idx_messages_live       ON messages(deleted_at) WHERE deleted_at IS NULL;


-- ============================================================ attachments
-- Own table rather than a JSON column: diagrams and PDFs are a real part of what
-- gets posted, and "every image in DBMS this semester" should be one query.

CREATE TABLE IF NOT EXISTS attachments (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id   INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    filename     TEXT,
    url          TEXT,
    content_type TEXT,
    kind         TEXT,                             -- image | document | audio | video | other
    size_bytes   INTEGER DEFAULT 0,
    created_at   TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_attachments_message ON attachments(message_id);
CREATE INDEX IF NOT EXISTS idx_attachments_kind    ON attachments(kind);


-- ======================================================= classifications
-- Phase 3 onwards. One active row per message; supersede, never overwrite.
--
-- scores and evidence record *why* a label was chosen. That is what makes the
-- rules tunable, and it is the training signal a future model learns from.
-- label_source = 'human' marks your manual corrections, which are the only rows
-- in this database that cannot be regenerated by replaying Discord.

CREATE TABLE IF NOT EXISTS classifications (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id         INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    label              TEXT    NOT NULL,           -- question|note|idea|progress|revision|resource|random
    secondary_label    TEXT,
    confidence         REAL    NOT NULL DEFAULT 0,
    scores             TEXT    NOT NULL DEFAULT '{}',
    evidence           TEXT    NOT NULL DEFAULT '[]',
    classifier_name    TEXT    NOT NULL,
    classifier_version TEXT    NOT NULL,
    label_source       TEXT    NOT NULL DEFAULT 'auto',  -- auto | human | imported
    is_active          INTEGER NOT NULL DEFAULT 1,
    created_at         TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_class_active  ON classifications(message_id, is_active);
CREATE INDEX IF NOT EXISTS idx_class_label   ON classifications(label, is_active);
CREATE INDEX IF NOT EXISTS idx_class_engine  ON classifications(classifier_name, classifier_version);
CREATE INDEX IF NOT EXISTS idx_class_human   ON classifications(label_source) WHERE label_source = 'human';

-- At most one active classification per message.
CREATE UNIQUE INDEX IF NOT EXISTS uniq_class_one_active
    ON classifications(message_id) WHERE is_active = 1;


-- ================================================================ graph
-- Generic on purpose. A node is anything nameable; an edge is any typed
-- relationship. Adding "prereq_of" or "confused_with" later is a string, not a
-- schema change.

CREATE TABLE IF NOT EXISTS nodes (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    key              TEXT    NOT NULL UNIQUE,      -- stable identity, e.g. 'osi_model'
    kind             TEXT    NOT NULL,             -- subject | topic | subtopic | tag
    name             TEXT    NOT NULL,
    parent_key       TEXT,
    subject_key      TEXT,
    taxonomy_version TEXT,
    metadata         TEXT    NOT NULL DEFAULT '{}',
    created_at       TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_nodes_kind    ON nodes(kind);
CREATE INDEX IF NOT EXISTS idx_nodes_parent  ON nodes(parent_key);
CREATE INDEX IF NOT EXISTS idx_nodes_subject ON nodes(subject_key);

CREATE TABLE IF NOT EXISTS edges (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    src_key      TEXT    NOT NULL,
    dst_key      TEXT    NOT NULL,
    relation     TEXT    NOT NULL,                 -- contains | related_to | prereq_of | co_occurs
    weight       REAL    NOT NULL DEFAULT 1.0,
    observations INTEGER NOT NULL DEFAULT 0,       -- how many messages produced this edge
    created_at   TEXT    NOT NULL,
    updated_at   TEXT    NOT NULL,
    UNIQUE (src_key, dst_key, relation)
);

CREATE INDEX IF NOT EXISTS idx_edges_src ON edges(src_key, relation);
CREATE INDEX IF NOT EXISTS idx_edges_dst ON edges(dst_key, relation);


-- ========================================================== topic_links
-- Phase 4 onwards. Versioned like classifications, because the topic extractor
-- is a separate seam and will be replaced on its own schedule.

CREATE TABLE IF NOT EXISTS topic_links (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id        INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    node_key          TEXT    NOT NULL,
    confidence        REAL    NOT NULL DEFAULT 0,
    matched_text      TEXT,                        -- the span that triggered the match
    extractor_name    TEXT    NOT NULL,
    extractor_version TEXT    NOT NULL,
    is_active         INTEGER NOT NULL DEFAULT 1,
    created_at        TEXT    NOT NULL,
    UNIQUE (message_id, node_key, extractor_name)
);

CREATE INDEX IF NOT EXISTS idx_links_message ON topic_links(message_id, is_active);
CREATE INDEX IF NOT EXISTS idx_links_node    ON topic_links(node_key, is_active);


-- ====================================================== candidate_terms
-- Terms that keep appearing but aren't in the taxonomy yet. The system's way of
-- telling you what to add next, instead of you guessing.

CREATE TABLE IF NOT EXISTS candidate_terms (
    term        TEXT PRIMARY KEY,
    occurrences INTEGER NOT NULL DEFAULT 1,
    first_seen  TEXT    NOT NULL,
    last_seen   TEXT    NOT NULL,
    status      TEXT    NOT NULL DEFAULT 'new'     -- new | promoted | ignored
);

CREATE INDEX IF NOT EXISTS idx_candidates ON candidate_terms(status, occurrences DESC);


-- ================================================================ views

DROP VIEW IF EXISTS v_entries;
CREATE VIEW v_entries AS
SELECT
    m.id                 AS message_id,
    m.source             AS source,
    m.external_id        AS external_id,
    m.content            AS content,
    m.author_id          AS author_id,
    m.author_name        AS author_name,
    m.thread_id          AS thread_id,
    m.created_at         AS created_at,
    m.local_date         AS local_date,
    m.local_hour         AS local_hour,
    m.edited_at          AS edited_at,
    ch.external_id       AS channel_external_id,
    ch.label             AS channel_label,
    ch.context_kind      AS context_kind,
    ch.context_value     AS context_value,
    ch.subject_key       AS channel_subject_key,
    c.label              AS label,
    c.secondary_label    AS secondary_label,
    c.confidence         AS confidence,
    c.label_source       AS label_source,
    c.classifier_name    AS classifier_name,
    c.classifier_version AS classifier_version,
    (SELECT COUNT(*) FROM attachments a WHERE a.message_id = m.id) AS attachment_count
FROM messages m
LEFT JOIN channels ch       ON ch.id = m.channel_id
LEFT JOIN classifications c ON c.message_id = m.id AND c.is_active = 1
WHERE m.deleted_at IS NULL;


DROP VIEW IF EXISTS v_node_stats;
CREATE VIEW v_node_stats AS
SELECT
    n.key         AS node_key,
    n.name        AS name,
    n.kind        AS kind,
    n.parent_key  AS parent_key,
    n.subject_key AS subject_key,
    COUNT(DISTINCT tl.message_id) AS mentions,
    SUM(CASE WHEN c.label = 'question' THEN 1 ELSE 0 END) AS questions,
    SUM(CASE WHEN c.label = 'note'     THEN 1 ELSE 0 END) AS notes,
    SUM(CASE WHEN c.label = 'idea'     THEN 1 ELSE 0 END) AS ideas,
    SUM(CASE WHEN c.label = 'progress' THEN 1 ELSE 0 END) AS progress,
    SUM(CASE WHEN c.label = 'revision' THEN 1 ELSE 0 END) AS revisions,
    SUM(CASE WHEN c.label = 'resource' THEN 1 ELSE 0 END) AS resources,
    MIN(m.local_date) AS first_seen,
    MAX(m.local_date) AS last_seen
FROM nodes n
LEFT JOIN topic_links tl    ON tl.node_key = n.key AND tl.is_active = 1
LEFT JOIN messages m        ON m.id = tl.message_id AND m.deleted_at IS NULL
LEFT JOIN classifications c ON c.message_id = m.id AND c.is_active = 1
GROUP BY n.key;


-- ====================================================== full text search
-- External-content FTS5: the index stores no copy of the text, it points back
-- into messages. Triggers keep it in sync.

CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts
USING fts5(content, content='messages', content_rowid='id', tokenize='porter unicode61');

CREATE TRIGGER IF NOT EXISTS messages_fts_ai AFTER INSERT ON messages BEGIN
    INSERT INTO messages_fts(rowid, content) VALUES (new.id, new.content);
END;

CREATE TRIGGER IF NOT EXISTS messages_fts_ad AFTER DELETE ON messages BEGIN
    INSERT INTO messages_fts(messages_fts, rowid, content) VALUES ('delete', old.id, old.content);
END;

CREATE TRIGGER IF NOT EXISTS messages_fts_au AFTER UPDATE OF content ON messages BEGIN
    INSERT INTO messages_fts(messages_fts, rowid, content) VALUES ('delete', old.id, old.content);
    INSERT INTO messages_fts(rowid, content) VALUES (new.id, new.content);
END;
