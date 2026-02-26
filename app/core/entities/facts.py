"""This module defines fact-chain and problem-attempt linkage entities."""

from dataclasses import dataclass
from enum import Enum


class ProblemAttemptRole(str, Enum):
    """This enum defines the role of an attempt linked to a problem."""

    SOLUTION = "solution"
    FAILED_TACTIC = "failed_tactic"


@dataclass(kw_only=True)
class ProblemAttempt:
    """This dataclass models a direct problem-to-attempt link."""

    problem_id: str
    attempt_id: str
    role: ProblemAttemptRole


@dataclass(kw_only=True)
class FactUpdate:
    """This dataclass models an immutable fact-update chain record."""

    id: str
    old_fact_id: str
    change_id: str
    new_fact_id: str
