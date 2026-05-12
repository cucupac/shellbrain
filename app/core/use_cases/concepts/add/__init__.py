"""Concept add use case."""

from app.core.use_cases.concepts.add.request import (
    AddConceptAction,
    ConceptAddAction,
    ConceptAddRequest,
)
from app.core.use_cases.concepts.add.result import ConceptAddResult

__all__ = [
    "AddConceptAction",
    "ConceptAddAction",
    "ConceptAddRequest",
    "ConceptAddResult",
    "add_concepts",
]


def __getattr__(name: str):
    if name == "add_concepts":
        from app.core.use_cases.concepts.add.execute import add_concepts

        return add_concepts
    raise AttributeError(name)
