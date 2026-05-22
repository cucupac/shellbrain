"""This module defines SQLAlchemy Core tables for memories and shellbrain embeddings."""

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP

from app.infrastructure.db.runtime.models.metadata import metadata


_MEMORY_LIFECYCLE_STATUSES = (
    "'active', 'maybe_stale', 'stale', 'superseded', 'wrong', 'archived'"
)
_MEMORY_LIFECYCLE_ACTORS = "'worker', 'librarian', 'manual', 'import'"


memories = Table(
    "memories",
    metadata,
    Column("id", String, primary_key=True),
    Column("repo_id", String, nullable=False),
    Column("scope", String, nullable=False),
    Column("kind", String, nullable=False),
    Column("text", Text, nullable=False),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("status", String, nullable=False),
    Column("validated_at", TIMESTAMP(timezone=True)),
    Column("invalidated_at", TIMESTAMP(timezone=True)),
    Column("superseded_by_id", String, ForeignKey("memories.id", ondelete="SET NULL")),
    Column("updated_by", String),
    CheckConstraint(
        f"status IN ({_MEMORY_LIFECYCLE_STATUSES})",
        name="ck_memories_status",
    ),
    CheckConstraint(
        f"updated_by IS NULL OR updated_by IN ({_MEMORY_LIFECYCLE_ACTORS})",
        name="ck_memories_updated_by",
    ),
)

memory_lifecycle_events = Table(
    "memory_lifecycle_events",
    metadata,
    Column("id", String, primary_key=True),
    Column("repo_id", String, nullable=False),
    Column(
        "memory_id",
        String,
        ForeignKey("memories.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("from_status", String, nullable=False),
    Column("to_status", String, nullable=False),
    Column("rationale", Text, nullable=False),
    Column("actor", String, nullable=False),
    Column("superseded_by_id", String, ForeignKey("memories.id", ondelete="SET NULL")),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    CheckConstraint(
        f"from_status IN ({_MEMORY_LIFECYCLE_STATUSES})",
        name="ck_memory_lifecycle_events_from_status",
    ),
    CheckConstraint(
        f"to_status IN ({_MEMORY_LIFECYCLE_STATUSES})",
        name="ck_memory_lifecycle_events_to_status",
    ),
    CheckConstraint(
        f"actor IN ({_MEMORY_LIFECYCLE_ACTORS})",
        name="ck_memory_lifecycle_events_actor",
    ),
    CheckConstraint(
        "length(btrim(rationale)) > 0",
        name="ck_memory_lifecycle_events_rationale",
    ),
)

memory_embeddings = Table(
    "memory_embeddings",
    metadata,
    Column(
        "memory_id",
        String,
        ForeignKey("memories.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("model", String, nullable=False),
    Column("dim", Integer, nullable=False),
    Column("vector", Vector(), nullable=False),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    CheckConstraint("dim > 0", name="ck_memory_embeddings_dim_positive"),
)

memory_evidence = Table(
    "memory_evidence",
    metadata,
    Column(
        "memory_id",
        String,
        ForeignKey("memories.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "evidence_id",
        String,
        ForeignKey("evidence_refs.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    UniqueConstraint("memory_id", "evidence_id", name="uq_memory_evidence_pair"),
)

Index(
    "idx_memories_read_visibility",
    memories.c.repo_id,
    memories.c.status,
    memories.c.scope,
    memories.c.kind,
    memories.c.id,
)
Index(
    "idx_memory_lifecycle_events_memory",
    memory_lifecycle_events.c.repo_id,
    memory_lifecycle_events.c.memory_id,
    memory_lifecycle_events.c.created_at,
)
Index(
    "idx_memory_embeddings_model_dim_memory",
    memory_embeddings.c.model,
    memory_embeddings.c.dim,
    memory_embeddings.c.memory_id,
)
