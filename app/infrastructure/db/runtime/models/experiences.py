"""SQLAlchemy tables for curated memory-to-memory relations."""

from sqlalchemy import (
    CheckConstraint,
    Column,
    Float,
    ForeignKey,
    Index,
    String,
    Table,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP

from app.core.entities.memories import MemoryLifecycleActor, MemoryLifecycleStatus
from app.core.entities.structural_memory_relations import (
    STRUCTURAL_MEMORY_RELATION_PREDICATE_VALUES,
)
from app.infrastructure.db.runtime.models.metadata import metadata


def _quoted_values(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


_STRUCTURAL_RELATION_PREDICATES = _quoted_values(
    STRUCTURAL_MEMORY_RELATION_PREDICATE_VALUES
)
_MEMORY_LIFECYCLE_STATUSES = _quoted_values(
    tuple(status.value for status in MemoryLifecycleStatus)
)
_MEMORY_LIFECYCLE_ACTORS = _quoted_values(
    tuple(actor.value for actor in MemoryLifecycleActor)
)


structural_memory_relations = Table(
    "structural_memory_relations",
    metadata,
    Column("id", String, primary_key=True),
    Column("repo_id", String, nullable=False),
    Column(
        "subject_memory_id",
        String,
        ForeignKey("memories.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("predicate", String, nullable=False),
    Column(
        "object_memory_id",
        String,
        ForeignKey("memories.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "status",
        String,
        nullable=False,
        server_default=text("'active'"),
    ),
    Column("confidence", Float, nullable=True),
    Column("observed_at", TIMESTAMP(timezone=True), nullable=True),
    Column("validated_at", TIMESTAMP(timezone=True), nullable=True),
    Column("invalidated_at", TIMESTAMP(timezone=True), nullable=True),
    Column(
        "superseded_by_id",
        String,
        ForeignKey("structural_memory_relations.id", ondelete="SET NULL"),
        nullable=True,
    ),
    Column(
        "created_by",
        String,
        nullable=False,
        server_default=text("'worker'"),
    ),
    Column(
        "created_at",
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    ),
    Column(
        "updated_at",
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    ),
    CheckConstraint(
        f"predicate IN ({_STRUCTURAL_RELATION_PREDICATES})",
        name="ck_structural_memory_relations_predicate",
    ),
    CheckConstraint(
        f"status IN ({_MEMORY_LIFECYCLE_STATUSES})",
        name="ck_structural_memory_relations_status",
    ),
    CheckConstraint(
        "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
        name="ck_structural_memory_relations_confidence",
    ),
    CheckConstraint(
        "subject_memory_id <> object_memory_id",
        name="ck_structural_memory_relations_distinct_memories",
    ),
    CheckConstraint(
        f"created_by IN ({_MEMORY_LIFECYCLE_ACTORS})",
        name="ck_structural_memory_relations_created_by",
    ),
    UniqueConstraint(
        "repo_id",
        "subject_memory_id",
        "predicate",
        "object_memory_id",
        name="uq_structural_memory_relations_natural",
    ),
)

Index(
    "idx_structural_memory_relations_subject",
    structural_memory_relations.c.repo_id,
    structural_memory_relations.c.subject_memory_id,
    structural_memory_relations.c.predicate,
)
Index(
    "idx_structural_memory_relations_object",
    structural_memory_relations.c.repo_id,
    structural_memory_relations.c.object_memory_id,
    structural_memory_relations.c.predicate,
)
