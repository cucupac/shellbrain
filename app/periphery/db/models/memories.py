"""This module defines SQLAlchemy Core tables for memories and shellbrain embeddings."""

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, CheckConstraint, Column, ForeignKey, Integer, String, Table, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import TIMESTAMP

from app.periphery.db.models.metadata import metadata


memories = Table(
    "memories",
    metadata,
    Column("id", String, primary_key=True),
    Column("repo_id", String, nullable=False),
    Column("scope", String, nullable=False),
    Column("kind", String, nullable=False),
    Column("text", Text, nullable=False),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("archived", Boolean, nullable=False, default=False),
)

memory_embeddings = Table(
    "memory_embeddings",
    metadata,
    Column("memory_id", String, ForeignKey("memories.id", ondelete="CASCADE"), primary_key=True),
    Column("model", String, nullable=False),
    Column("dim", Integer, nullable=False),
    Column("vector", Vector(), nullable=False),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    CheckConstraint("dim > 0", name="ck_memory_embeddings_dim_positive"),
)

memory_evidence = Table(
    "memory_evidence",
    metadata,
    Column("memory_id", String, ForeignKey("memories.id", ondelete="CASCADE"), primary_key=True),
    Column("evidence_id", String, ForeignKey("evidence_refs.id", ondelete="CASCADE"), primary_key=True),
    UniqueConstraint("memory_id", "evidence_id", name="uq_memory_evidence_pair"),
)
