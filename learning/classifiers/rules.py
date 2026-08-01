"""
Rule-based classifier. No AI, no API, no model file.

Every label collects weighted *evidence* from independent detectors. Highest
total wins, runner-up is kept, and confidence comes from the margin between
them. All raw scores are persisted, so when a real classifier arrives you have
both the decision and the reasoning behind every historical row.

The entire tuning surface is the WEIGHTS dict below. Changing behaviour should
never require touching the logic.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from ..models import LABEL_PRIORITY, Classification, IncomingMessage, Label, TopicMatch
from ..text_utils import (
    FRACTION_RE,
    PERCENT_RE,
    bullet_line_count,
    extract_urls,
    has_code_block,
    normalize,
    quantity_mentions,
    strip_noise,
    tokenize,
    word_count,
)
from .base import BaseClassifier

# --------------------------------------------------------------------------
# Lexicons. Plain data — edit freely, no logic depends on their size.
# --------------------------------------------------------------------------

INTERROGATIVES = {
    "what", "why", "how", "when", "where", "which", "who", "whose", "whom",
    "can", "could", "should", "would", "is", "are", "am", "do", "does", "did",
    "will", "shall", "any", "anyone", "anybody", "explain", "define", "difference",
}

DOUBT_PHRASES = [
    "doubt", "confused", "confusing", "stuck", "not getting", "cant understand",
    "can't understand", "cannot understand", "dont understand", "don't understand",
    "unclear", "no idea", "clarify", "clarification", "help me", "pls explain",
    "please explain", "eli5", "makes no sense", "not clear", "how come",
    "difference between", "diff between", " vs ", "vs.", "samajh nahi",
    "kaise", "why is it", "anyone knows", "someone explain",
]

NOTE_PHRASES = [
    "is defined as", "is called", "refers to", "stands for", "means that",
    "consists of", "comprises", "note:", "note that", "important:", "key point",
    "remember that", "keep in mind", "definition", "theorem", "formula",
    "in short", "tldr", "summary:", "the idea is", "works by", "responsible for",
    "used for", "example:", "e.g.", "i.e.", "basically", "so basically",
]

IDEA_PHRASES = [
    "what if", "idea:", "idea -", "project idea", "thinking of", "thinking about",
    "planning to", "plan to", "we could", "i could", "maybe i", "maybe we",
    "should i build", "wanna build", "want to build", "could try", "brainstorm",
    "would be cool", "would be nice", "concept for", "prototype", "side project",
    "what about building", "im gonna build", "i'm gonna build", "gonna make",
]

PROGRESS_VERBS = [
    "done", "finished", "completed", "solved", "submitted", "cleared", "wrapped up",
    "watched", "attended", "wrote", "built", "implemented", "practiced", "practised",
    "covered", "studied", "read through", "went through", "cracked", "aced",
    "knocked out", "closed out", "got through", "made it through",
]

PROGRESS_MARKERS = ["✅", "✔", "☑", "[x]", "[X]", "🎯", "💯"]

REVISION_PHRASES = [
    "revise", "revised", "revising", "revision", "revisit", "revisited",
    "went over again", "going over again", "second pass", "third pass",
    "re-read", "reread", "rewatch", "rewatched", "recap", "quick recap",
    "brushing up", "brush up", "refresher", "active recall", "flashcard",
    "flash card", "anki", "spaced repetition", "back to basics", "forgot",
    "forgetting", "relearn", "relearning", "one more time", "did it again",
    "doing it again", "revisi",
]

RESOURCE_PHRASES = [
    "playlist", "cheatsheet", "cheat sheet", "reference", "resource", "textbook",
    "handbook", "syllabus", "question bank", "previous year", "lecture series",
    "free course", "found this", "sharing this", "check this out", "bookmark",
    "worth reading", "good notes", "notes link", "slides", "here's the",
    "heres the", "sharing the",
]

RESOURCE_DOMAINS = [
    "youtube.com", "youtu.be", "drive.google", "docs.google", "github.com",
    "nptel", "gateoverflow", "geeksforgeeks", "w3schools", "arxiv.org",
    "medium.com", "stackoverflow", "coursera", "udemy", "khanacademy",
    "leetcode", "hackerrank", "notion.so", "wikipedia.org", "scaler.com",
    "kaggle.com", "towardsdatascience",
]

DOC_EXTENSIONS = (".pdf", ".doc", ".docx", ".ppt", ".pptx", ".txt", ".md", ".epub", ".xlsx")
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".gif")

FILLER_TOKENS = {
    "lol", "lmao", "lmfao", "rofl", "bruh", "bro", "bhai", "gm", "gn", "hi", "hello",
    "hey", "yo", "sup", "ok", "okay", "k", "kk", "thanks", "thx", "ty", "np", "nice",
    "cool", "damn", "fr", "ikr", "wtf", "oof", "rip", "same", "true", "yep", "yeah",
    "nah", "hmm", "haha", "hahaha", "xd", "based", "sheesh", "arre", "acha", "theek",
}

FILLER_PHRASES = ["good morning", "good night", "brb", "gtg", "any plans", "wassup"]

# --------------------------------------------------------------------------
# Weights — the entire tuning surface.
# --------------------------------------------------------------------------

WEIGHTS: Dict[str, float] = {
    "q.ends_with_qmark": 4.0,
    "q.contains_qmark": 2.0,
    "q.leading_interrogative": 2.8,
    "q.interrogative_inline": 1.0,
    "q.doubt_phrase": 2.0,
    "q.doubt_phrase_extra": 0.8,

    "n.definition_phrase": 2.2,
    "n.bullet_list": 2.0,
    "n.long_form": 1.5,
    "n.very_long_form": 1.4,
    "n.code_block": 1.5,
    "n.notation": 1.0,
    "n.colon_structure": 1.0,
    "n.copular_definition": 2.2,
    "n.substantive_default": 1.3,

    "i.idea_phrase": 3.0,
    "i.idea_phrase_extra": 1.0,
    "i.leading_idea": 1.6,
    "i.speculative_modal": 1.0,

    "p.completion_verb": 2.4,
    "p.completion_verb_extra": 0.8,
    "p.quantity": 3.0,
    "p.fraction_or_percent": 1.5,
    "p.marker": 2.0,
    "p.today_frame": 1.0,

    "r.revision_phrase": 3.5,
    "r.revision_phrase_extra": 1.0,
    "r.again_adverb": 1.2,

    "s.url": 3.5,
    "s.known_domain": 1.5,
    "s.doc_attachment": 3.0,
    "s.image_attachment": 1.2,
    "s.resource_phrase": 1.6,
    "s.resource_phrase_extra": 0.6,

    "x.baseline": 0.9,
    "x.filler_token": 2.5,
    "x.filler_phrase": 2.0,
    "x.very_short": 1.6,
    "x.no_topic_penalty": -1.5,
    "x.topic_bonus_others": 0.5,
}

MIN_DECISIVE_SCORE = 1.6


class RuleBasedClassifier(BaseClassifier):
    name = "rules"
    version = "1.0"

    def classify(self, message: IncomingMessage,
                 topics: Optional[List[TopicMatch]] = None) -> Classification:
        try:
            return self._classify(message, topics or [])
        except Exception as exc:      # a classifier must never break capture
            c = self._empty()
            c.evidence = [f"classifier_error:{type(exc).__name__}"]
            return c

    # ------------------------------------------------------------------
    def _classify(self, message: IncomingMessage, topics: List[TopicMatch]) -> Classification:
        raw = message.content or ""
        body = strip_noise(raw)
        norm = normalize(body)
        padded = f" {norm} "
        tokens = tokenize(body)
        urls = extract_urls(raw)
        wc = word_count(body)

        scores: Dict[Label, float] = {label: 0.0 for label in Label}
        evidence: List[str] = []

        def add(label: Label, key: str, times: int = 1, note: str = "") -> None:
            if times <= 0:
                return
            scores[label] += WEIGHTS[key] * times
            suffix = f"x{times}" if times > 1 else ""
            evidence.append(f"{key}{suffix}{':' + note if note else ''}")

        # ---------------- question ----------------
        # Check the prose, not the raw text: "is this good? <link>" is still a
        # question even though a URL follows the question mark.
        prose = body.strip()
        if prose.endswith("?"):
            add(Label.QUESTION, "q.ends_with_qmark")
        elif "?" in prose:
            add(Label.QUESTION, "q.contains_qmark")

        if tokens and tokens[0] in INTERROGATIVES:
            add(Label.QUESTION, "q.leading_interrogative", note=tokens[0])
        elif any(t in INTERROGATIVES for t in tokens[:4]):
            add(Label.QUESTION, "q.interrogative_inline")

        doubt_hits = self._count(padded, DOUBT_PHRASES)
        if doubt_hits:
            add(Label.QUESTION, "q.doubt_phrase")
            add(Label.QUESTION, "q.doubt_phrase_extra", doubt_hits - 1)

        # ---------------- note ----------------
        note_hits = self._count(padded, NOTE_PHRASES)
        if note_hits:
            add(Label.NOTE, "n.definition_phrase", note_hits)

        bullets = bullet_line_count(raw)
        if bullets >= 2:
            add(Label.NOTE, "n.bullet_list", note=f"{bullets}lines")
        if wc >= 25:
            add(Label.NOTE, "n.long_form")
        if wc >= 60:
            add(Label.NOTE, "n.very_long_form")
        if has_code_block(raw):
            add(Label.NOTE, "n.code_block")
        if re.search(r"[=→⇒<>≤≥±∑∫]|O\(|\bthen\b.*\belse\b", body):
            add(Label.NOTE, "n.notation")
        if re.search(r"\w+\s*:\s*\w+", body) and wc >= 8:
            add(Label.NOTE, "n.colon_structure")
        if re.search(
            r"\b\w+\s+(is|are|means|denotes|represents|indicates|implies)\s+"
            r"(a|an|the|every|any|all|when|that|used|called|\w+ing)\b", padded
        ):
            add(Label.NOTE, "n.copular_definition")
        if wc >= 6 and topics:
            add(Label.NOTE, "n.substantive_default")

        # ---------------- idea ----------------
        idea_hits = self._count(padded, IDEA_PHRASES)
        if idea_hits:
            add(Label.IDEA, "i.idea_phrase")
            add(Label.IDEA, "i.idea_phrase_extra", idea_hits - 1)
            if any(norm.startswith(normalize(p)) for p in IDEA_PHRASES):
                add(Label.IDEA, "i.leading_idea")
        if re.search(r"\b(i|we)\s+(should|might|may|could)\b", padded):
            add(Label.IDEA, "i.speculative_modal")

        # ---------------- progress ----------------
        prog_hits = self._count(padded, PROGRESS_VERBS)
        if prog_hits:
            add(Label.PROGRESS, "p.completion_verb")
            add(Label.PROGRESS, "p.completion_verb_extra", prog_hits - 1)

        quantities = quantity_mentions(body)
        if quantities:
            add(Label.PROGRESS, "p.quantity", note=f"{quantities[0][0]}{quantities[0][1]}")
        if FRACTION_RE.search(body) or PERCENT_RE.search(body):
            add(Label.PROGRESS, "p.fraction_or_percent")
        if any(m in raw for m in PROGRESS_MARKERS):
            add(Label.PROGRESS, "p.marker")
        if re.search(r"\b(today|finally|just now|just)\b", padded) and prog_hits:
            add(Label.PROGRESS, "p.today_frame")

        # ---------------- revision ----------------
        rev_hits = self._count(padded, REVISION_PHRASES)
        if rev_hits:
            add(Label.REVISION, "r.revision_phrase")
            add(Label.REVISION, "r.revision_phrase_extra", rev_hits - 1)
        if re.search(r"\b(again|once more|2nd time|second time|3rd time)\b", padded):
            add(Label.REVISION, "r.again_adverb")

        # ---------------- resource ----------------
        if urls:
            add(Label.RESOURCE, "s.url", note=f"{len(urls)}url")
            joined = " ".join(urls).lower()
            if any(d in joined for d in RESOURCE_DOMAINS):
                add(Label.RESOURCE, "s.known_domain")

        for att in message.attachments:
            fname = (att.filename or "").lower()
            ctype = (att.content_type or "").lower()
            if fname.endswith(DOC_EXTENSIONS) or "pdf" in ctype or "document" in ctype:
                add(Label.RESOURCE, "s.doc_attachment", note=fname[:24])
            elif fname.endswith(IMAGE_EXTENSIONS) or ctype.startswith("image/"):
                add(Label.RESOURCE, "s.image_attachment")

        res_hits = self._count(padded, RESOURCE_PHRASES)
        if res_hits:
            add(Label.RESOURCE, "s.resource_phrase")
            add(Label.RESOURCE, "s.resource_phrase_extra", res_hits - 1)

        # ---------------- random ----------------
        add(Label.RANDOM, "x.baseline")
        filler = sum(1 for t in tokens if t in FILLER_TOKENS)
        if filler and filler >= max(1, len(tokens) // 2):
            add(Label.RANDOM, "x.filler_token", note=f"{filler}/{len(tokens)}")
        if self._count(padded, FILLER_PHRASES):
            add(Label.RANDOM, "x.filler_phrase")
        if len(tokens) <= 3 and not urls and not message.attachments:
            add(Label.RANDOM, "x.very_short")

        # ---------------- topic influence ----------------
        if topics:
            for label in Label:
                if label is not Label.RANDOM:
                    scores[label] += WEIGHTS["x.topic_bonus_others"]
            scores[Label.RANDOM] += WEIGHTS["x.no_topic_penalty"]
            evidence.append(f"topics:{len(topics)}")

        return self._decide(scores, evidence)

    # ------------------------------------------------------------------
    @staticmethod
    def _count(padded_norm: str, phrases: List[str]) -> int:
        total = 0
        for p in phrases:
            needle = normalize(p)
            if needle and f" {needle} " in padded_norm:
                total += 1
            elif p.lower() in padded_norm:
                total += 1
        return total

    @staticmethod
    def _decide(scores: Dict[Label, float], evidence: List[str]) -> Classification:
        ranked: List[Tuple[Label, float]] = sorted(
            scores.items(), key=lambda kv: (-kv[1], LABEL_PRIORITY.index(kv[0]))
        )
        winner, top = ranked[0]
        runner, second = ranked[1] if len(ranked) > 1 else (None, 0.0)

        if top < MIN_DECISIVE_SCORE:
            winner, top = Label.RANDOM, max(top, WEIGHTS["x.baseline"])

        if top <= 0:
            confidence = 0.0
        else:
            margin = (top - max(second, 0.0)) / top
            confidence = round(min(0.99, 0.40 + 0.59 * margin), 3)

        return Classification(
            label=winner,
            secondary_label=runner if runner and second > 0 and runner is not winner else None,
            confidence=confidence,
            scores={k.value: round(v, 3) for k, v in scores.items()},
            evidence=evidence,
            classifier_name=RuleBasedClassifier.name,
            classifier_version=RuleBasedClassifier.version,
        )
