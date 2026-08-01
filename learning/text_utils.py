"""
Text helpers. Standard library only — no spaCy, no NLTK, no model downloads.

Everything here is deterministic and fast enough to run inline on a Discord
message event.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import List, Set, Tuple

URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
CODE_BLOCK_RE = re.compile(r"```.*?```", re.DOTALL)
INLINE_CODE_RE = re.compile(r"`[^`]+`")
MENTION_RE = re.compile(r"<[@#!&:][^>]+>")
EMOJI_RE = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF]", flags=re.UNICODE
)
BULLET_RE = re.compile(r"^\s*([-*•▪]|\d+[.)])\s+", re.MULTILINE)
FRACTION_RE = re.compile(r"\b\d+\s*/\s*\d+\b")
PERCENT_RE = re.compile(r"\b\d{1,3}\s*%")
NUM_QTY_RE = re.compile(
    r"\b(\d+)\s*(?:\+)?\s*"
    r"(questions?|qs|ques|pyqs?|problems?|sums?|mcqs?|numericals?|lectures?|videos?|"
    r"pages?|chapters?|units?|chaps?|modules?|topics?|hours?|hrs?|mins?|minutes?|"
    r"papers?|sets?|tests?|slides?|labs?|assignments?)\b",
    re.IGNORECASE,
)

STOPWORDS: Set[str] = {
    "a", "about", "after", "again", "all", "also", "am", "an", "and", "any", "are", "as", "at",
    "be", "because", "been", "before", "being", "but", "by", "can", "cant", "could", "did", "do",
    "does", "doing", "done", "dont", "each", "for", "from", "get", "got", "had", "has", "have",
    "he", "her", "here", "him", "his", "how", "i", "if", "im", "in", "into", "is", "it", "its",
    "just", "know", "like", "ll", "me", "more", "most", "my", "no", "not", "now", "of", "on",
    "one", "only", "or", "other", "our", "out", "over", "re", "really", "s", "same", "she",
    "should", "so", "some", "such", "t", "than", "that", "the", "their", "them", "then", "there",
    "these", "they", "this", "those", "to", "too", "u", "up", "us", "ve", "very", "was", "we",
    "were", "what", "when", "where", "which", "while", "who", "why", "will", "with", "would",
    "you", "your", "yes", "ok", "okay",
}


def strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def extract_urls(text: str) -> List[str]:
    return URL_RE.findall(text or "")


def strip_noise(text: str) -> str:
    """Remove URLs, code blocks, mentions and emoji before matching."""
    text = CODE_BLOCK_RE.sub(" ", text or "")
    text = INLINE_CODE_RE.sub(" ", text)
    text = URL_RE.sub(" ", text)
    text = MENTION_RE.sub(" ", text)
    return EMOJI_RE.sub(" ", text)


def normalize(text: str) -> str:
    text = strip_accents(text or "").lower()
    text = re.sub(r"[^a-z0-9+#/&\s-]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def tokenize(text: str) -> List[str]:
    return [t for t in normalize(text).split(" ") if t]


def singularize(token: str) -> str:
    """Crude but predictable. Enough for alias matching."""
    if len(token) > 4 and token.endswith("ies"):
        return token[:-3] + "y"
    if len(token) > 3 and token.endswith("sses"):
        return token[:-2]
    if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def canonical_tokens(text: str) -> List[str]:
    return [singularize(t) for t in tokenize(text)]


def bullet_line_count(text: str) -> int:
    return len(BULLET_RE.findall(text or ""))


def word_count(text: str) -> int:
    return len(tokenize(text))


def has_code_block(text: str) -> bool:
    return "```" in (text or "")


def quantity_mentions(text: str) -> List[Tuple[int, str]]:
    return [(int(m.group(1)), m.group(2).lower()) for m in NUM_QTY_RE.finditer(text or "")]


def content_hash(text: str) -> str:
    return hashlib.sha1(normalize(text).encode("utf-8")).hexdigest()


CAPITALISED_RE = re.compile(r"\b([A-Z][a-zA-Z]{2,}(?:\s+[A-Z][a-zA-Z]{2,}){0,3})\b")
ACRONYM_RE = re.compile(r"\b([A-Z]{2,6})\b")


def candidate_phrases(raw_text: str) -> List[str]:
    """Proper-noun-ish phrases the taxonomy might be missing."""
    cleaned = strip_noise(raw_text or "")
    found = [m.group(1).strip() for m in CAPITALISED_RE.finditer(cleaned)]
    found += [m.group(1) for m in ACRONYM_RE.finditer(cleaned)]
    seen, out = set(), []
    for f in found:
        key = normalize(f)
        if key and key not in seen and key not in STOPWORDS and len(key) > 1:
            seen.add(key)
            out.append(f)
    return out
