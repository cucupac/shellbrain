"""This module defines SQLAlchemy Core tables for utility observation records."""

from sqlalchemy import CheckConstraint, Column, Float, ForeignKey, String, Table
from sqlalchemy.dialects.postgresql import TIMESTAMP

from app.infrastructure.db.runtime.models.metadata import metadata


utility_observations = Table(
    "utility_observations",
    metadata,
    Column("id", String, primary_key=True),
    Column(
        "memory_id",
        String,
        ForeignKey("memories.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "problem_id",
        String,
        ForeignKey("memories.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("vote", Float, nullable=False),
    Column("rationale", String),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    CheckConstraint(
        "vote >= -1 AND vote <= 1", name="ck_utility_observations_vote_range"
    ),
)

utility_observation_evidence = Table(
    "utility_observation_evidence",
    metadata,
    Column(
        "observation_id",
        String,
        ForeignKey("utility_observations.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "evidence_id",
        String,
        ForeignKey("evidence_refs.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)
