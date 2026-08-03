"""
Taxonomy loading.

The taxonomy is data, not code. Adding a semester means editing one JSON file —
no Python changes, no migrations. The loader flattens it into an alias index for
matching and a node/edge list for the knowledge graph.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ..models import NodeKind, Relation
from ..text_utils import canonical_tokens

log = logging.getLogger("learning.taxonomy")
DEFAULT_TAXONOMY_PATH = Path(__file__).parent / "data" / "taxonomy.json"


@dataclass
class TaxonomyNode:
    key: str
    name: str
    kind: NodeKind
    aliases: List[str] = field(default_factory=list)
    parent_key: Optional[str] = None
    subject_key: Optional[str] = None
    #: In scope for Mid Sem Exam 1. Subtopics inherit this from their parent.
    mse1: bool = False


@dataclass
class Taxonomy:
    version: str
    nodes: Dict[str, TaxonomyNode]
    edges: List[Tuple[str, str, Relation]]
    #: normalised alias -> node keys. Ambiguity is allowed, resolved by context.
    alias_index: Dict[str, List[str]]
    #: subject key -> the unit numbers MSE-1 covers, as printed on the syllabus
    mse1_units: Dict[str, str] = field(default_factory=dict)

    def mse1_keys(self) -> List[str]:
        return [k for k, n in self.nodes.items() if n.mse1]

    def node(self, key: str) -> Optional[TaxonomyNode]:
        return self.nodes.get(key)

    def subject_of(self, key: str) -> Optional[str]:
        n = self.nodes.get(key)
        return n.subject_key if n else None


def _norm(text: str) -> str:
    return " ".join(canonical_tokens(text))


def load_taxonomy(path: Path | str | None = None) -> Taxonomy:
    p = Path(path) if path else DEFAULT_TAXONOMY_PATH
    if not p.exists():
        log.warning("no taxonomy at %s", p)
        return Taxonomy("0", {}, [], {}, {})

    raw = json.loads(p.read_text(encoding="utf-8"))
    nodes: Dict[str, TaxonomyNode] = {}
    edges: List[Tuple[str, str, Relation]] = []
    alias_index: Dict[str, List[str]] = {}
    mse1_units: Dict[str, str] = {}

    def index(node: TaxonomyNode) -> None:
        for alias in [node.name] + node.aliases:
            key = _norm(alias)
            if not key:
                continue
            bucket = alias_index.setdefault(key, [])
            if node.key not in bucket:
                bucket.append(node.key)

    for subj in raw.get("subjects", []):
        s = TaxonomyNode(subj["key"], subj["name"], NodeKind.SUBJECT,
                         list(subj.get("aliases", [])), subject_key=subj["key"],
                         mse1=bool(subj.get("mse1_units")))
        nodes[s.key] = s
        index(s)
        if subj.get("mse1_units"):
            mse1_units[s.key] = subj["mse1_units"]

        for topic in subj.get("topics", []):
            t = TaxonomyNode(topic["key"], topic["name"], NodeKind.TOPIC,
                             list(topic.get("aliases", [])), s.key, s.key,
                             mse1=bool(topic.get("mse1")))
            nodes[t.key] = t
            index(t)
            edges.append((s.key, t.key, Relation.CONTAINS))

            for rel in topic.get("related", []):
                edges.append((t.key, rel, Relation.RELATED_TO))
            for pre in topic.get("prereq", []):
                edges.append((pre, t.key, Relation.PREREQ_OF))

            for sub in topic.get("subtopics", []):
                # A subtopic is examinable exactly when its parent topic is.
                st = TaxonomyNode(sub["key"], sub["name"], NodeKind.SUBTOPIC,
                                  list(sub.get("aliases", [])), t.key, s.key,
                                  mse1=t.mse1)
                nodes[st.key] = st
                index(st)
                edges.append((t.key, st.key, Relation.CONTAINS))

    # drop edges pointing at keys that don't exist — a typo shouldn't crash boot
    edges = [e for e in edges if e[0] in nodes and e[1] in nodes]

    in_scope = sum(1 for n in nodes.values() if n.mse1)
    log.info("taxonomy %s: %d nodes (%d in MSE-1), %d aliases",
             raw.get("version", "0"), len(nodes), in_scope, len(alias_index))
    return Taxonomy(str(raw.get("version", "0")), nodes, edges, alias_index, mse1_units)
