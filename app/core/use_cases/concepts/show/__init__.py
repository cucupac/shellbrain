"""Concept show use case."""

from app.core.use_cases.concepts.show.request import ConceptShowRequest
from app.core.use_cases.concepts.show.result import ConceptShowResult

__all__ = ["ConceptShowRequest", "ConceptShowResult", "show_concept"]


def __getattr__(name: str):
    if name == "show_concept":
        from app.core.use_cases.concepts.show.execute import show_concept

        return show_concept
    raise AttributeError(name)
