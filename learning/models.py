"""
Data contracts for the Learning Engine.

Nothing here imports discord or sqlite3. Any adapter — the Discord cog, a CLI
importer, a future Telegram bot — produces these, and the storage layer consumes
them. That's what keeps the pieces swappable.

Phase 2 is capture only. Classification and TopicMatch models arrive in phases
3 and 4; the database columns for them already exist.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

DOC_EXTS = (".pdf", ".doc", ".docx", ".ppt", ".pptx", ".txt", ".md", ".epub", ".xlsx", ".csv")
IMG_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".svg", ".heic")
AUD_EXTS = (".mp3", ".wav", ".ogg", ".m4a", ".flac")
VID_EXTS = (".mp4", ".mov", ".webm", ".mkv", ".avi")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class ChannelContext:
    """What a channel implies before a single word is read.

    A message in #computer-networks under the SEMESTER 3 category is already
    most of the way classified by location alone. Phase 4 uses subject_key as a
    prior for topic detection — never as an override, since a message can always
    be about something else.
    """

    external_id: str = ""
    source: str = "discord"
    label: str = ""                       # channel name
    category: str = ""                    # Discord category name
    context_kind: str = "general"         # semester | exam | reference | general
    context_value: str = ""               # sem3 | gate | ''
    subject_key: Optional[str] = None
    enabled: bool = True
    origin: str = "inferred"              # syllabus | inferred | manual

    @property
    def captured(self) -> bool:
        """Reference channels exist for stable material and are never captured."""
        return self.enabled and self.context_kind != "reference"


@dataclass
class Attachment:
    filename: str = ""
    url: str = ""
    content_type: str = ""
    size_bytes: int = 0

    @property
    def kind(self) -> str:
        name = (self.filename or "").lower()
        ctype = (self.content_type or "").lower()
        if name.endswith(IMG_EXTS) or ctype.startswith("image/"):
            return "image"
        if name.endswith(DOC_EXTS) or "pdf" in ctype or "document" in ctype:
            return "document"
        if name.endswith(AUD_EXTS) or ctype.startswith("audio/"):
            return "audio"
        if name.endswith(VID_EXTS) or ctype.startswith("video/"):
            return "video"
        return "other"


@dataclass
class IncomingMessage:
    """One unit of input. Every adapter must produce this shape."""

    content: str
    source: str = "discord"
    external_id: Optional[str] = None
    author_id: Optional[str] = None
    author_name: Optional[str] = None
    thread_id: Optional[str] = None
    reply_to: Optional[str] = None
    channel: ChannelContext = field(default_factory=ChannelContext)
    attachments: List[Attachment] = field(default_factory=list)
    created_at: datetime = field(default_factory=utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_empty(self) -> bool:
        return not (self.content or "").strip() and not self.attachments
