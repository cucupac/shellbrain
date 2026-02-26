"""This module defines SQLAlchemy Core tables for episodes, events, and session transfers."""

from sqlalchemy import CheckConstraint, Column, ForeignKey, Integer, String, Table, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import TIMESTAMP

from app.periphery.db.models.metadata import metadata


episodes = Table(
    "episodes",
    metadata,
    Column("id", String, primary_key=True),
    Column("repo_id", String, nullable=False),
    Column("thread_id", String),
    Column("title", String),
    Column("objective", String),
    Column("status", String, nullable=False),
    Column("started_at", TIMESTAMP(timezone=True), nullable=False),
    Column("ended_at", TIMESTAMP(timezone=True)),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
)

episode_events = Table(
    "episode_events",
    metadata,
    Column("id", String, primary_key=True),
    Column("episode_id", String, ForeignKey("episodes.id", ondelete="CASCADE"), nullable=False),
    Column("seq", Integer, nullable=False),
    Column("source", String, nullable=False),
    Column("content", Text, nullable=False),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    CheckConstraint("seq > 0", name="ck_episode_events_seq_positive"),
    UniqueConstraint("episode_id", "seq", name="uq_episode_events_seq"),
)

session_transfers = Table(
    "session_transfers",
    metadata,
    Column("id", String, primary_key=True),
    Column("repo_id", String, nullable=False),
    Column("from_episode_id", String, ForeignKey("episodes.id", ondelete="CASCADE"), nullable=False),
    Column("to_episode_id", String, ForeignKey("episodes.id", ondelete="CASCADE"), nullable=False),
    Column("event_id", String, ForeignKey("episode_events.id", ondelete="CASCADE"), nullable=False),
    Column("transfer_kind", String, nullable=False),
    Column("rationale", Text),
    Column("transferred_by", String),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
)
