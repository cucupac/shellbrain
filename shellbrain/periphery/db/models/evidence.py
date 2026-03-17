"""This module defines SQLAlchemy Core tables for evidence reference records."""

from sqlalchemy import Column, ForeignKey, String, Table, UniqueConstraint
from sqlalchemy.dialects.postgresql import TIMESTAMP

from shellbrain.periphery.db.models.metadata import metadata


evidence_refs = Table(
    "evidence_refs",
    metadata,
    Column("id", String, primary_key=True),
    Column("repo_id", String, nullable=False),
    Column("ref", String, nullable=False),
    Column("episode_event_id", String, ForeignKey("episode_events.id"), nullable=True),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    UniqueConstraint("repo_id", "ref", name="uq_evidence_repo_ref"),
    UniqueConstraint("repo_id", "episode_event_id", name="uq_evidence_repo_episode_event"),
)
