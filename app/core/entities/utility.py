"""This module defines utility-observation entities used for contextual feedback."""

from dataclasses import dataclass


@dataclass(kw_only=True)
class UtilityObservation:
    """This dataclass models a utility vote linked to memory and problem context."""

    id: str
    memory_id: str
    problem_id: str
    vote: float
    rationale: str | None = None
