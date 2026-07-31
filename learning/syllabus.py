"""
Syllabus loading and channel resolution.

Resolution runs in three steps, most specific first:

  1. Explicit map      channels.json, keyed by Discord channel id. Written by
                       `!learn setup`, survives renames, always wins.
  2. Inference         category name gives the semester, channel name gives the
                       subject. Works with zero configuration, breaks on rename.
  3. Fallback          nothing matched, so the channel is ignored — unless
                       LEARNING_WATCH_ALL=1, which is for debugging only.

Because the bootstrap command writes the explicit map at the moment it creates
the channels, in practice you never hand-edit it and renames never break
capture. Inference exists so the engine still does something sensible in a
server that was set up by hand.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from .models import ChannelContext

log = logging.getLogger("learning.syllabus")

DATA_DIR = Path(os.getenv("LEARNING_DATA_DIR", "data/learning"))
SYLLABUS_PATH = Path(os.getenv("LEARNING_SYLLABUS", "data/syllabus.json"))
CHANNEL_MAP_PATH = DATA_DIR / "channels.json"

SEM_RE = re.compile(r"\b(?:sem|semester)[\s_-]?([1-8])\b", re.IGNORECASE)
EXAM_WORDS = {"gate": "gate", "placement": "placement", "interview": "placement",
              "cat": "cat", "gre": "gre", "upsc": "upsc", "net": "net"}
REFERENCE_WORDS = {"reference", "resources", "syllabus", "textbook", "archive", "material"}
STUDY_WORDS = {"study", "learn", "notes", "doubt", "doubts", "revision", "log", "prep"}


# ------------------------------------------------------------------ syllabus
@dataclass
class SubjectEntry:
    key: Optional[str]
    name: str
    channel: str
    context_kind: str
    context_value: str


@dataclass
class Syllabus:
    """Parsed syllabus.json, flattened into something the bootstrap can walk."""

    version: int = 1
    #: category name -> list of channels that belong under it
    categories: Dict[str, List[SubjectEntry]] = field(default_factory=dict)
    path: Optional[Path] = None

    @property
    def channel_count(self) -> int:
        return sum(len(v) for v in self.categories.values())

    def all_entries(self) -> List[SubjectEntry]:
        return [e for entries in self.categories.values() for e in entries]

    def find(self, channel_name: str) -> Optional[SubjectEntry]:
        for entry in self.all_entries():
            if entry.channel == channel_name:
                return entry
        return None


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", (text or "").lower().replace("_", "-")).strip("-")


def load_syllabus(path: Path | str | None = None) -> Syllabus:
    """Read syllabus.json. Returns an empty Syllabus if the file isn't there."""
    p = Path(path) if path else SYLLABUS_PATH
    if not p.exists():
        log.info("no syllabus at %s — relying on channel name inference", p)
        return Syllabus(path=p)

    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        log.error("syllabus.json is not valid JSON: %s", exc)
        return Syllabus(path=p)

    syllabus = Syllabus(version=int(raw.get("version", 1)), path=p)

    for sem in raw.get("semesters", []):
        if not sem.get("active", True):
            continue
        category = sem.get("category") or sem.get("name", sem["id"]).upper()
        entries = []
        for subj in sem.get("subjects", []):
            entries.append(SubjectEntry(
                key=subj.get("key"),
                name=subj.get("name", subj.get("key", "")),
                channel=subj.get("channel") or _slug(subj.get("key", "")),
                context_kind="semester",
                context_value=sem["id"],
            ))
        if entries:
            syllabus.categories[category] = entries

    for exam in raw.get("exams", []):
        if not exam.get("active", True):
            continue
        category = exam.get("category") or exam.get("name", exam["id"]).upper()
        entries = []
        for ch in exam.get("channels", []):
            entries.append(SubjectEntry(
                key=ch.get("key"),
                name=ch.get("name", ch.get("channel", "")),
                channel=ch.get("channel") or _slug(ch.get("name", "")),
                context_kind="exam",
                context_value=exam["id"],
            ))
        if entries:
            syllabus.categories[category] = entries

    ref = raw.get("reference")
    if ref:
        category = ref.get("category", "REFERENCE")
        entries = [
            SubjectEntry(
                key=None,
                name=ch.get("name", ch.get("channel", "")),
                channel=ch.get("channel") or _slug(ch.get("name", "")),
                context_kind="reference",
                context_value="",
            )
            for ch in ref.get("channels", [])
        ]
        if entries:
            syllabus.categories[category] = entries

    log.info("syllabus loaded: %d categories, %d channels",
             len(syllabus.categories), syllabus.channel_count)
    return syllabus


# ----------------------------------------------------------------- inference
def infer_context(channel_name: str, category_name: str = "") -> Optional[ChannelContext]:
    """Guess a channel's meaning from its name and its category's name.

    Category carries the semester or exam; channel carries the subject. That
    mirrors the server layout, so a hand-built server still works.
    """
    if not channel_name:
        return None

    chan = channel_name.lower()
    cat = (category_name or "").lower()

    if any(w in chan for w in REFERENCE_WORDS) or any(w in cat for w in REFERENCE_WORDS):
        return ChannelContext(
            label=channel_name, category=category_name,
            context_kind="reference", origin="inferred",
        )

    sem = SEM_RE.search(cat) or SEM_RE.search(chan)
    exam = next((v for k, v in EXAM_WORDS.items() if k in cat or k in chan), None)
    studyish = any(w in chan for w in STUDY_WORDS)

    if not (sem or exam or studyish):
        return None

    subject_key = _slug(channel_name).replace("-", "_") or None

    if sem:
        return ChannelContext(
            label=channel_name, category=category_name,
            context_kind="semester", context_value=f"sem{sem.group(1)}",
            subject_key=subject_key, origin="inferred",
        )
    if exam:
        return ChannelContext(
            label=channel_name, category=category_name,
            context_kind="exam", context_value=exam,
            subject_key=subject_key, origin="inferred",
        )
    return ChannelContext(
        label=channel_name, category=category_name,
        context_kind="general", subject_key=subject_key, origin="inferred",
    )


# ------------------------------------------------------------------ registry
class ChannelRegistry:
    """Holds the explicit map and answers 'should I capture this channel'."""

    def __init__(self, map_path: Path | str | None = None,
                 syllabus: Optional[Syllabus] = None,
                 watch_all: Optional[bool] = None):
        self.map_path = Path(map_path) if map_path else CHANNEL_MAP_PATH
        self.syllabus = syllabus or load_syllabus()
        self.watch_all = (
            watch_all if watch_all is not None
            else os.getenv("LEARNING_WATCH_ALL", "0") == "1"
        )
        self._explicit: Dict[str, ChannelContext] = {}
        self.load()

    # ------------------------------------------------------------- file I/O
    def load(self) -> None:
        if not self.map_path.exists():
            return
        try:
            raw = json.loads(self.map_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            log.error("channels.json is corrupt (%s) — falling back to inference", exc)
            return
        for entry in raw.get("channels", []):
            ctx = ChannelContext(
                external_id=str(entry["id"]),
                source=entry.get("source", "discord"),
                label=entry.get("label", ""),
                category=entry.get("category", ""),
                context_kind=entry.get("context_kind", "general"),
                context_value=entry.get("context_value", ""),
                subject_key=entry.get("subject_key"),
                enabled=entry.get("enabled", True),
                origin=entry.get("origin", "syllabus"),
            )
            self._explicit[ctx.external_id] = ctx

    def save(self) -> None:
        self.map_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "_comment": "Written by !learn setup. Channel ids survive renames.",
            "channels": [
                {
                    "id": c.external_id, "source": c.source, "label": c.label,
                    "category": c.category, "context_kind": c.context_kind,
                    "context_value": c.context_value, "subject_key": c.subject_key,
                    "enabled": c.enabled, "origin": c.origin,
                }
                for c in sorted(self._explicit.values(), key=lambda x: x.label)
            ],
        }
        self.map_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    # ------------------------------------------------------------ operations
    def register(self, ctx: ChannelContext, persist: bool = True) -> None:
        self._explicit[str(ctx.external_id)] = ctx
        if persist:
            self.save()

    def forget(self, channel_id) -> bool:
        removed = self._explicit.pop(str(channel_id), None) is not None
        if removed:
            self.save()
        return removed

    def all(self) -> List[ChannelContext]:
        return list(self._explicit.values())

    def resolve(self, channel_id, channel_name: str = "",
                category_name: str = "") -> Optional[ChannelContext]:
        """Explicit map first, then inference, then nothing."""
        explicit = self._explicit.get(str(channel_id))
        if explicit:
            return explicit

        inferred = infer_context(channel_name, category_name)
        if inferred:
            inferred.external_id = str(channel_id)
            return inferred

        if self.watch_all:
            return ChannelContext(
                external_id=str(channel_id), label=channel_name,
                category=category_name, context_kind="general", origin="inferred",
            )
        return None
