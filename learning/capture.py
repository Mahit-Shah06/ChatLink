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

from .models import IncomingMessage
from .storage.db import Database
from .storage.repository import LearningRepository
from .syllabus import ChannelRegistry, Syllabus, load_syllabus

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
        log.info("capture engine ready (db=%s)", self.db.path)

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
    def capture(self, msg: IncomingMessage) -> Optional[int]:
        """Store a message. Returns its row id, or None if it was filtered out."""
        if not self.should_capture(msg):
            return None
        try:
            return self.repo.save_message(msg)
        except Exception:
            log.exception("failed to store message %s", msg.external_id)
            return None

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
        }


_ENGINE: Optional[CaptureEngine] = None


def get_engine(db_path: Path | str | None = None) -> CaptureEngine:
    """Process-wide singleton, so the cog and the commands share one handle."""
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = CaptureEngine(db_path)
    return _ENGINE
