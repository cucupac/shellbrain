"""This module defines immutable shellbrain entities and core shellbrain enums."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Final, Literal

from app.core.entities.ids import MemoryId, RepoId


MemoryKindValue = Literal[
    "problem", "solution", "failed_tactic", "fact", "preference", "change"
]
AssociationRelationValue = Literal["depends_on", "associated_with"]
MemoryLifecycleStatusValue = Literal[
    "active", "maybe_stale", "stale", "superseded", "wrong", "archived"
]
MemoryLifecycleActorValue = Literal["worker", "librarian", "manual", "import"]


class MemoryKind(str, Enum):
    """This enum defines ratified atomic shellbrain kinds."""

    PROBLEM = "problem"
    SOLUTION = "solution"
    FAILED_TACTIC = "failed_tactic"
    FACT = "fact"
    PREFERENCE = "preference"
    CHANGE = "change"

    @property
    def requires_problem_link(self) -> bool:
        """Return whether memories of this kind must link to a problem."""

        return self in {MemoryKind.SOLUTION, MemoryKind.FAILED_TACTIC}

    @property
    def is_mature(self) -> bool:
        """Return whether this kind belongs to the durable mature-memory set."""

        return self in MATURE_MEMORY_KINDS


MATURE_MEMORY_KINDS: Final[tuple[MemoryKind, ...]] = (
    MemoryKind.PROBLEM,
    MemoryKind.SOLUTION,
    MemoryKind.FAILED_TACTIC,
    MemoryKind.FACT,
    MemoryKind.PREFERENCE,
    MemoryKind.CHANGE,
)
MATURE_MEMORY_KIND_VALUES: Final[tuple[str, ...]] = tuple(
    kind.value for kind in MATURE_MEMORY_KINDS
)


def is_mature_memory_kind(kind: MemoryKind | str) -> bool:
    """Return whether one kind belongs to the mature durable-memory set."""

    normalized_kind = kind if isinstance(kind, MemoryKind) else MemoryKind(kind)
    return normalized_kind.is_mature


class MemoryScope(str, Enum):
    """This enum defines shellbrain visibility scope."""

    REPO = "repo"
    GLOBAL = "global"


class MemoryLifecycleStatus(str, Enum):
    """Lifecycle state for concrete durable memories."""

    ACTIVE = "active"
    MAYBE_STALE = "maybe_stale"
    STALE = "stale"
    SUPERSEDED = "superseded"
    WRONG = "wrong"
    ARCHIVED = "archived"

    @property
    def has_positive_retrieval_signal(self) -> bool:
        """Return whether normal read/recall may retrieve this memory."""

        return self in DEFAULT_RETRIEVABLE_MEMORY_STATUSES

    @property
    def retrieval_multiplier(self) -> float:
        """Return the default retrieval strength multiplier for this lifecycle state."""

        return {
            MemoryLifecycleStatus.ACTIVE: 1.0,
            MemoryLifecycleStatus.MAYBE_STALE: 0.65,
            MemoryLifecycleStatus.STALE: 0.25,
            MemoryLifecycleStatus.SUPERSEDED: 0.0,
            MemoryLifecycleStatus.WRONG: 0.0,
            MemoryLifecycleStatus.ARCHIVED: 0.0,
        }[self]


class MemoryLifecycleActor(str, Enum):
    """Actor classes allowed to mutate concrete memory lifecycle state."""

    WORKER = "worker"
    LIBRARIAN = "librarian"
    MANUAL = "manual"
    IMPORT = "import"


DEFAULT_RETRIEVABLE_MEMORY_STATUSES: Final[tuple[MemoryLifecycleStatus, ...]] = (
    MemoryLifecycleStatus.ACTIVE,
    MemoryLifecycleStatus.MAYBE_STALE,
    MemoryLifecycleStatus.STALE,
)
DEFAULT_RETRIEVABLE_MEMORY_STATUS_VALUES: Final[tuple[str, ...]] = tuple(
    status.value for status in DEFAULT_RETRIEVABLE_MEMORY_STATUSES
)


@dataclass(frozen=True)
class EvidenceRefs:
    """Validated immutable episode-event evidence references."""

    values: tuple[str, ...]

    def __post_init__(self) -> None:
        if any(not ref.strip() for ref in self.values):
            raise ValueError("evidence_refs must be non-empty strings")
        if len(self.values) != len(set(self.values)):
            raise ValueError("evidence_refs must be unique")

    @classmethod
    def required(cls, refs: list[str] | tuple[str, ...]) -> "EvidenceRefs":
        """Build evidence refs for operations that require at least one ref."""

        values = tuple(refs)
        if not values:
            raise ValueError("evidence_refs must not be empty")
        return cls(values)

    @classmethod
    def optional(cls, refs: list[str] | tuple[str, ...]) -> "EvidenceRefs":
        """Build evidence refs for operations where evidence is optional."""

        return cls(tuple(refs))


def _validate_range(value: float, *, name: str, minimum: float, maximum: float) -> None:
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum:g} and {maximum:g}")


@dataclass(frozen=True)
class ConfidenceValue:
    """Validated association confidence value."""

    value: float

    def __post_init__(self) -> None:
        _validate_range(self.value, name="confidence", minimum=0.0, maximum=1.0)


@dataclass(frozen=True)
class SalienceValue:
    """Validated association salience value."""

    value: float

    def __post_init__(self) -> None:
        _validate_range(self.value, name="salience", minimum=0.0, maximum=1.0)


@dataclass(frozen=True)
class UtilityVoteValue:
    """Validated utility vote value."""

    value: float

    def __post_init__(self) -> None:
        _validate_range(self.value, name="utility vote", minimum=-1.0, maximum=1.0)


@dataclass(kw_only=True)
class Memory:
    """This dataclass models an immutable shellbrain record."""

    id: MemoryId
    repo_id: RepoId
    scope: MemoryScope
    kind: MemoryKind
    text: str
    created_at: datetime | None = None
    status: MemoryLifecycleStatus = MemoryLifecycleStatus.ACTIVE
    validated_at: datetime | None = None
    invalidated_at: datetime | None = None
    superseded_by_id: MemoryId | None = None
    updated_by: MemoryLifecycleActor | None = None

    def is_visible_in(self, repo_id: RepoId | str) -> bool:
        """Return whether this memory is visible inside a repo operation context."""

        return self.repo_id == repo_id or self.scope == MemoryScope.GLOBAL

    def has_positive_retrieval_signal(self) -> bool:
        """Return whether normal read/recall should retrieve this memory."""

        return self.status.has_positive_retrieval_signal


@dataclass(kw_only=True)
class MemoryLifecycleEvent:
    """Append-only audit event for concrete memory lifecycle transitions."""

    id: str
    repo_id: RepoId
    memory_id: MemoryId
    from_status: MemoryLifecycleStatus
    to_status: MemoryLifecycleStatus
    rationale: str
    actor: MemoryLifecycleActor
    superseded_by_id: MemoryId | None = None
    created_at: datetime | None = None
