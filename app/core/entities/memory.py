"""This module defines immutable shellbrain entities and core shellbrain enums."""

from dataclasses import dataclass
from enum import Enum
from typing import Final

from app.core.entities.ids import MemoryId, RepoId


class MemoryKind(str, Enum):
    """This enum defines ratified atomic shellbrain kinds."""

    PROBLEM = "problem"
    SOLUTION = "solution"
    FAILED_TACTIC = "failed_tactic"
    FACT = "fact"
    PREFERENCE = "preference"
    CHANGE = "change"
    FRONTIER = "frontier"


MATURE_MEMORY_KINDS: Final[tuple[MemoryKind, ...]] = (
    MemoryKind.PROBLEM,
    MemoryKind.SOLUTION,
    MemoryKind.FAILED_TACTIC,
    MemoryKind.FACT,
    MemoryKind.PREFERENCE,
    MemoryKind.CHANGE,
)
MATURE_MEMORY_KIND_VALUES: Final[tuple[str, ...]] = tuple(kind.value for kind in MATURE_MEMORY_KINDS)


def is_mature_memory_kind(kind: MemoryKind | str) -> bool:
    """Return whether one kind belongs to the mature durable-memory set."""

    normalized_kind = kind if isinstance(kind, MemoryKind) else MemoryKind(kind)
    return normalized_kind in MATURE_MEMORY_KINDS


class MemoryScope(str, Enum):
    """This enum defines shellbrain visibility scope."""

    REPO = "repo"
    GLOBAL = "global"


@dataclass(kw_only=True)
class Memory:
    """This dataclass models an immutable shellbrain record."""

    id: MemoryId
    repo_id: RepoId
    scope: MemoryScope
    kind: MemoryKind
    text: str
    archived: bool = False
