"""
Taxonomy-driven topic extraction. Dictionary matching, no model.

  1. Tokenise and singularise.
  2. Scan n-grams longest-first, suppressing overlaps so "binary search tree"
     matches Trees rather than Searching + Trees.
  3. Resolve ambiguous aliases using the channel's subject prior and whatever
     else matched in the same message.
  4. Prune single-word matches from distant subjects when one subject clearly
     dominates — "normalization" means different things in Data Mining and
     Web Dev, and context should decide.
  5. Roll subtopics up to parents so the graph stays connected.
  6. Report unmatched proper nouns as taxonomy growth candidates.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from ..models import IncomingMessage, NodeKind, TopicMatch
from ..text_utils import STOPWORDS, candidate_phrases, canonical_tokens, strip_noise
from .base import BaseTopicExtractor
from .taxonomy import Taxonomy, load_taxonomy

CONF_MULTIWORD = 0.95
CONF_SINGLE_WORD = 0.85
CONF_SHORT_ALIAS = 0.60
CONF_CHANNEL_PRIOR = 0.40
CONF_ROLLUP_PARENT = 0.55
CONF_ROLLUP_SUBJECT = 0.50

SHORT_ALIAS_LEN = 3


class TaxonomyTopicExtractor(BaseTopicExtractor):
    name = "taxonomy-matcher"
    version = "1.0"

    def __init__(self, taxonomy: Optional[Taxonomy] = None, path: Path | str | None = None):
        self.taxonomy = taxonomy or load_taxonomy(path)
        self.version = f"1.0+tax{self.taxonomy.version}"

    # ------------------------------------------------------------------
    def extract(self, message: IncomingMessage) -> Tuple[List[TopicMatch], List[str]]:
        try:
            return self._extract(message)
        except Exception:
            return [], []

    def _extract(self, message: IncomingMessage) -> Tuple[List[TopicMatch], List[str]]:
        body = strip_noise(message.content or "")
        tokens = canonical_tokens(body)
        if not tokens:
            return self._channel_only(message), []

        prior = self._prior_subject(message)
        hits: Dict[str, TopicMatch] = {}
        consumed: Set[int] = set()

        for n in range(min(4, len(tokens)), 0, -1):
            for i in range(len(tokens) - n + 1):
                span = range(i, i + n)
                if any(idx in consumed for idx in span):
                    continue
                phrase = " ".join(tokens[i:i + n])
                node_keys = self.taxonomy.alias_index.get(phrase)
                if not node_keys:
                    continue

                is_short = n == 1 and len(phrase) <= SHORT_ALIAS_LEN
                if is_short and not self._short_ok(node_keys, prior, hits):
                    continue

                key = self._disambiguate(node_keys, prior, hits)
                node = self.taxonomy.node(key)
                if not node:
                    continue

                conf = CONF_SHORT_ALIAS if is_short else (
                    CONF_MULTIWORD if n > 1 else CONF_SINGLE_WORD)

                self._put(hits, TopicMatch(
                    node_key=node.key, node_kind=node.kind, name=node.name,
                    confidence=conf, matched_text=phrase,
                    subject_key=node.subject_key, parent_key=node.parent_key,
                ))
                consumed.update(span)

        self._prune_cross_subject(hits)

        for match in list(hits.values()):
            self._rollup(hits, match)

        if not hits:
            for m in self._channel_only(message):
                self._put(hits, m)

        candidates = self._candidates(message, hits)
        ordered = sorted(hits.values(), key=lambda m: (-m.confidence, m.node_key))
        return ordered, candidates

    # ------------------------------------------------------------------
    @staticmethod
    def _put(hits: Dict[str, TopicMatch], match: TopicMatch) -> None:
        existing = hits.get(match.node_key)
        if existing is None or match.confidence > existing.confidence:
            hits[match.node_key] = match

    def _prior_subject(self, message: IncomingMessage) -> Optional[str]:
        ch = message.channel
        if ch and ch.subject_key and ch.subject_key in self.taxonomy.nodes:
            return ch.subject_key
        return None

    def _channel_only(self, message: IncomingMessage) -> List[TopicMatch]:
        subject = self._prior_subject(message)
        node = self.taxonomy.node(subject) if subject else None
        if not node:
            return []
        return [TopicMatch(
            node_key=node.key, node_kind=node.kind, name=node.name,
            confidence=CONF_CHANNEL_PRIOR, matched_text="(channel context)",
            subject_key=node.subject_key,
        )]

    def _short_ok(self, node_keys: List[str], prior: Optional[str],
                  hits: Dict[str, TopicMatch]) -> bool:
        """Two-letter aliases are landmines. Require corroboration."""
        if prior:
            for key in node_keys:
                if key == prior or self.taxonomy.subject_of(key) == prior:
                    return True
        in_play = {m.subject_key for m in hits.values() if m.subject_key}
        if any(self.taxonomy.subject_of(k) in in_play for k in node_keys):
            return True
        return len(node_keys) == 1 and not hits

    def _disambiguate(self, node_keys: List[str], prior: Optional[str],
                      hits: Dict[str, TopicMatch]) -> str:
        if len(node_keys) == 1:
            return node_keys[0]

        pool = node_keys
        if prior:
            scoped = [k for k in pool if self.taxonomy.subject_of(k) == prior]
            if scoped:
                pool = scoped
        else:
            in_play = {m.subject_key for m in hits.values() if m.subject_key}
            scoped = [k for k in pool if self.taxonomy.subject_of(k) in in_play]
            if scoped:
                pool = scoped

        depth = {NodeKind.SUBTOPIC: 0, NodeKind.TOPIC: 1, NodeKind.SUBJECT: 2, NodeKind.TAG: 3}
        return sorted(pool, key=lambda k: depth.get(self.taxonomy.nodes[k].kind, 9))[0]

    @staticmethod
    def _prune_cross_subject(hits: Dict[str, TopicMatch]) -> None:
        """Drop stray single-word hits from unrelated subjects.

        Multi-word matches are never pruned, so a genuine cross-subject message
        ("used pandas to preprocess the mining dataset") keeps both.
        """
        if len(hits) < 2:
            return

        weights: Dict[str, float] = {}
        only_single: Dict[str, bool] = {}
        for m in hits.values():
            if not m.subject_key or m.matched_text.startswith("("):
                continue
            multi = " " in m.matched_text
            weights[m.subject_key] = weights.get(m.subject_key, 0.0) + (2.0 if multi else 1.0)
            if multi:
                only_single[m.subject_key] = False
            else:
                only_single.setdefault(m.subject_key, True)

        if len(weights) < 2:
            return

        top = max(weights, key=lambda k: weights[k])
        for subject, weight in weights.items():
            if subject == top:
                continue
            if only_single.get(subject, False) and weights[top] >= 2 * weight:
                for key in [k for k, m in hits.items() if m.subject_key == subject]:
                    hits.pop(key, None)

    def _rollup(self, hits: Dict[str, TopicMatch], match: TopicMatch) -> None:
        node = self.taxonomy.node(match.node_key)
        if not node:
            return
        if node.parent_key:
            parent = self.taxonomy.node(node.parent_key)
            if parent:
                self._put(hits, TopicMatch(
                    node_key=parent.key, node_kind=parent.kind, name=parent.name,
                    confidence=round(match.confidence * CONF_ROLLUP_PARENT, 3),
                    matched_text=f"(via {node.name})",
                    subject_key=parent.subject_key, parent_key=parent.parent_key,
                ))
        if node.subject_key and node.subject_key != node.key:
            subject = self.taxonomy.node(node.subject_key)
            if subject:
                self._put(hits, TopicMatch(
                    node_key=subject.key, node_kind=subject.kind, name=subject.name,
                    confidence=round(match.confidence * CONF_ROLLUP_SUBJECT, 3),
                    matched_text=f"(via {node.name})", subject_key=subject.key,
                ))

    def _candidates(self, message: IncomingMessage, hits: Dict[str, TopicMatch]) -> List[str]:
        matched = {m.matched_text for m in hits.values()}
        out: List[str] = []
        for phrase in candidate_phrases(message.content or ""):
            norm = " ".join(canonical_tokens(phrase))
            if not norm or norm in STOPWORDS or len(norm) < 3:
                continue
            if norm in self.taxonomy.alias_index or norm in matched:
                continue
            out.append(phrase)
        return out[:8]
