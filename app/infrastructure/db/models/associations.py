"""This module defines SQLAlchemy Core tables for association edges and observations."""

from sqlalchemy import CheckConstraint, Column, Float, ForeignKey, Integer, String, Table, UniqueConstraint
from sqlalchemy.dialects.postgresql import TIMESTAMP

from app.infrastructure.db.models.metadata import metadata


association_edges = Table(
    "association_edges",
    metadata,
    Column("id", String, primary_key=True),
    Column("repo_id", String, nullable=False),
    Column("from_memory_id", String, ForeignKey("memories.id", ondelete="CASCADE"), nullable=False),
    Column("to_memory_id", String, ForeignKey("memories.id", ondelete="CASCADE"), nullable=False),
    Column("relation_type", String, nullable=False),
    Column("source_mode", String, nullable=False),
    Column("state", String, nullable=False),
    Column("strength", Float, nullable=False, default=0.0),
    Column("obs_count", Integer, nullable=False, default=0),
    Column("positive_obs", Integer, nullable=False, default=0),
    Column("negative_obs", Integer, nullable=False, default=0),
    Column("salience_sum", Float, nullable=False, default=0.0),
    Column("last_reinforced_at", TIMESTAMP(timezone=True)),
    Column("last_used_at", TIMESTAMP(timezone=True)),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False),
    CheckConstraint("from_memory_id <> to_memory_id", name="ck_association_edges_no_self_loop"),
    UniqueConstraint("repo_id", "from_memory_id", "to_memory_id", "relation_type", name="uq_association_edges_pair"),
)

association_observations = Table(
    "association_observations",
    metadata,
    Column("id", String, primary_key=True),
    Column("repo_id", String, nullable=False),
    Column("edge_id", String, ForeignKey("association_edges.id", ondelete="CASCADE")),
    Column("from_memory_id", String, ForeignKey("memories.id", ondelete="CASCADE"), nullable=False),
    Column("to_memory_id", String, ForeignKey("memories.id", ondelete="CASCADE"), nullable=False),
    Column("relation_type", String, nullable=False),
    Column("source", String, nullable=False),
    Column("problem_id", String, ForeignKey("memories.id", ondelete="SET NULL")),
    Column("episode_id", String, ForeignKey("episodes.id", ondelete="SET NULL")),
    Column("valence", Float, nullable=False),
    Column("salience", Float, nullable=False, default=0.5),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    CheckConstraint("from_memory_id <> to_memory_id", name="ck_association_observations_no_self_loop"),
)

association_edge_evidence = Table(
    "association_edge_evidence",
    metadata,
    Column("edge_id", String, ForeignKey("association_edges.id", ondelete="CASCADE"), primary_key=True),
    Column("evidence_id", String, ForeignKey("evidence_refs.id", ondelete="CASCADE"), primary_key=True),
)
