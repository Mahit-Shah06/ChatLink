"""
The classifier contract — the seam that makes AI swappable later.

Anything that turns an IncomingMessage into a Classification is a valid
classifier: regexes, logistic regression over TF-IDF, a fine-tuned transformer,
an LLM call. The pipeline, the storage layer and the GUI never learn which one
you used, except as a name recorded on every row.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional

from ..models import Classification, IncomingMessage, Label, TopicMatch


class BaseClassifier(ABC):
    #: Recorded on every classification row. Bump the version when behaviour
    #: changes, so old rows stay attributable and two classifiers can be
    #: compared over the same corpus.
    name: str = "base"
    version: str = "0"

    @abstractmethod
    def classify(self, message: IncomingMessage,
                 topics: Optional[List[TopicMatch]] = None) -> Classification:
        """Return a Classification. Must never raise — fall back to RANDOM."""

    def warmup(self) -> None:
        """Optional. Load weights, open a model file. Called once at startup."""
        return None

    def _empty(self) -> Classification:
        return Classification(label=Label.RANDOM, confidence=0.0,
                              classifier_name=self.name, classifier_version=self.version)
