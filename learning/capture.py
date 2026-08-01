"""
The capture engine. One entry point: `capture(message)`.

Phase 2 does exactly two things — decide whether a message is worth keeping,
then store it. No classification, no topic extraction. Those slot in here later
without any adapter needing to know.

The reason for the deliberate pause at this phase: rules tuned against invented
examples are worth very little. Two weeks of your actual messages makes phase 3
a matter of looking at real data instead of guessing.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

from .classifiers.registry import get_classifier
from .models import IncomingMessage, ProcessedMessage
from .storage.db import Database, to_iso, utcnow
from .storage.repository import LearningRepository
from .syllabus import ChannelRegistry, Syllabus, load_syllabus
from .topics.matcher import TaxonomyTopicExtractor
from .topics.taxonomy import load_taxonomy

log = logging.getLogger("learning.capture")

DB_PATH = Path(os.getenv("LEARNING_DB_PATH", "data/learning/learning.db"))

#: Commands belong to the bot, not to your notes.
IGNORE_PREFIXES = ("!", "/", ".", "?")
MIN_LENGTH = int(os.getenv("LEARNING_MIN_LENGTH", "3"))


class CaptureEngine:
    def __init__(self, db_path: Path | str | None = None,
                 syllabus: Optional[Syllabus] = None):
        self.db = Database(db_path or DB_PATH)
        self.repo = LearningRepository(self.db)
        self.syllabus = syllabus or load_syllabus()
        self.channels = ChannelRegistry(syllabus=self.syllabus)

        self.taxonomy = load_taxonomy()
        self.extractor = TaxonomyTopicExtractor(self.taxonomy)
        self.classifier = get_classifier(os.getenv("LEARNING_CLASSIFIER", "rules"))
        self.repo.sync_taxonomy(self.taxonomy)

        log.info("engine ready: db=%s classifier=%s@%s taxonomy=%s",
                 self.db.path, self.classifier.name, self.classifier.version,
                 self.taxonomy.version)

    # ------------------------------------------------------------- filtering
    def should_capture(self, msg: IncomingMessage) -> bool:
        """Cheap checks only. This runs on every message in every watched channel."""
        if not msg.channel.captured:
            return False
        if msg.attachments:
            return True                       # a diagram with no caption still counts
        text = (msg.content or "").strip()
        if len(text) < MIN_LENGTH:
            return False
        if text.startswith(IGNORE_PREFIXES):
            return False
        return True

    # --------------------------------------------------------------- capture
    def process(self, msg: IncomingMessage) -> ProcessedMessage:
        """Classify and extract topics without touching the database."""
        topics, candidates = self.extractor.extract(msg)
        classification = self.classifier.classify(msg, topics)
        return ProcessedMessage(message=msg, classification=classification,
                                topics=topics, candidate_terms=candidates)

    def capture(self, msg: IncomingMessage) -> Optional[ProcessedMessage]:
        """Full path: classify, extract topics, persist.

        Returns None if the message was filtered out.
        """
        if not self.should_capture(msg):
            return None
        try:
            processed = self.process(msg)
            self.repo.save_processed(processed)
            return processed
        except Exception:
            log.exception("failed to store message %s", msg.external_id)
            return None

    def reclassify_all(self, classifier_name: Optional[str] = None, batch: int = 500) -> dict:
        """Re-run classification over all stored history.

        This is the payoff of keeping raw content: the day a better classifier
        exists, run this once and every past message is re-labelled, without
        losing the original verdicts.
        """
        from .models import ChannelContext

        classifier = get_classifier(classifier_name or self.classifier.name)
        offset = updated = 0
        while True:
            rows = self.repo.messages_for_reclassification(batch=batch, offset=offset)
            if not rows:
                break
            for row in rows:
                msg = IncomingMessage(
                    content=row["content"], source=row["source"],
                    external_id=row["external_id"],
                    channel=ChannelContext(
                        external_id=str(row.get("channel_external_id") or ""),
                        label=row.get("channel_label") or "",
                        context_kind=row.get("context_kind") or "general",
                        context_value=row.get("context_value") or "",
                        subject_key=row.get("subject_key")))
                topics, candidates = self.extractor.extract(msg)
                classification = classifier.classify(msg, topics)
                now = to_iso(utcnow())
                with self.db.transaction() as conn:
                    self.repo._write_classification(conn, row["id"], classification, now)
                    if topics:
                        self.repo._write_topics(conn, row["id"], topics, now)
                updated += 1
            offset += batch
        return {"reclassified": updated, "classifier": classifier.name,
                "version": classifier.version}

    def forget(self, source: str, external_id: str) -> bool:
        try:
            return self.repo.mark_deleted(source, external_id)
        except Exception:
            log.exception("failed to soft-delete %s", external_id)
            return False

    # ----------------------------------------------------------------- stats
    def stats(self) -> dict:
        return {
            "summary": self.repo.summary(),
            "channels": self.repo.per_channel(),
            "syllabus_channels": self.syllabus.channel_count,
            "mapped_channels": len(self.channels.all()),
            "db_path": str(self.db.path.resolve()),
            "labels": self.repo.label_counts(),
            "streak": self.repo.streak(),
            "classifier": f"{self.classifier.name}@{self.classifier.version}",
            "taxonomy": self.taxonomy.version,
        }


_ENGINE: Optional[CaptureEngine] = None


def get_engine(db_path: Path | str | None = None) -> CaptureEngine:
    """Process-wide singleton, so the cog and the commands share one handle."""
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = CaptureEngine(db_path)
    return _ENGINE
