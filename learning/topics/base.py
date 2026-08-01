"""
Topic extraction contract.

Deliberately separate from classification: "what kind of message is this" and
"what is it about" are different problems that will be solved by different
models at different times. Keeping them apart means either can be upgraded
without touching the other.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Tuple

from ..models import IncomingMessage, TopicMatch


class BaseTopicExtractor(ABC):
    name: str = "base"
    version: str = "0"

    @abstractmethod
    def extract(self, message: IncomingMessage) -> Tuple[List[TopicMatch], List[str]]:
        """Return (matches, unrecognised_terms). Must never raise."""

    def warmup(self) -> None:
        return None
