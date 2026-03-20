"""This module defines immutable shellbrain entities and core shellbrain enums."""

from dataclasses import dataclass
from enum import Enum


class MemoryKind(str, Enum):
    """This enum defines ratified atomic shellbrain kinds."""

    PROBLEM = "problem"
    SOLUTION = "solution"
    FAILED_TACTIC = "failed_tactic"
    FACT = "fact"
    PREFERENCE = "preference"
    CHANGE = "change"


class MemoryScope(str, Enum):
    """This enum defines shellbrain visibility scope."""

    REPO = "repo"
    GLOBAL = "global"


@dataclass(kw_only=True)
class Memory:
    """This dataclass models an immutable shellbrain record."""

    id: str
    repo_id: str
    scope: MemoryScope
    kind: MemoryKind
    text: str
    archived: bool = False
