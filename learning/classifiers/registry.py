"""
Classifier registry.

Swapping the rule engine for a model is a config change, not a refactor:

    from learning.classifiers.registry import register
    register(MyModelClassifier)

then set LEARNING_CLASSIFIER=my-model. Old rows keep their original classifier
name, so the two can be compared over identical history.
"""

from __future__ import annotations

from typing import Dict, Type

from .base import BaseClassifier
from .rules import RuleBasedClassifier

_REGISTRY: Dict[str, Type[BaseClassifier]] = {}
_INSTANCES: Dict[str, BaseClassifier] = {}


def register(cls: Type[BaseClassifier]) -> Type[BaseClassifier]:
    _REGISTRY[cls.name] = cls
    return cls


def available() -> Dict[str, str]:
    return {name: cls.version for name, cls in _REGISTRY.items()}


def get_classifier(name: str = "rules") -> BaseClassifier:
    key = (name or "rules").strip().lower()
    if key not in _REGISTRY:
        key = "rules"
    if key not in _INSTANCES:
        inst = _REGISTRY[key]()
        inst.warmup()
        _INSTANCES[key] = inst
    return _INSTANCES[key]


register(RuleBasedClassifier)
