"""This module defines SQLAlchemy Core tables for episodes, events, and session transfers."""

from sqlalchemy import CheckConstraint, Column, ForeignKey, Integer, String, Table, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import TIMESTAMP

from app.periphery.db.models.metadata import metadata


episodes = Table(
    "episodes",
    metadata,
    Column("id", String, primary_key=True),
    Column("repo_id", String, nullable=False),
    Column("host_app", String, nullable=False),
    Column("thread_id", String),
    Column("title", String),
    Column("objective", String),
    Column("status", String, nullable=False),
    Column("started_at", TIMESTAMP(timezone=True), nullable=False),
    Column("ended_at", TIMESTAMP(timezone=True)),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    UniqueConstraint("repo_id", "thread_id", name="uq_episodes_repo_thread"),
    CheckConstraint("ended_at IS NULL OR ended_at >= started_at", name="ck_episodes_ended_after_started"),
)

episode_events = Table(
    "episode_events",
    metadata,
    Column("id", String, primary_key=True),
    Column("episode_id", String, ForeignKey("episodes.id", ondelete="CASCADE"), nullable=False),
    Column("seq", Integer, nullable=False),
    Column("host_event_key", String, nullable=False),
    Column("source", String, nullable=False),
    Column("content", Text, nullable=False),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    CheckConstraint("seq > 0", name="ck_episode_events_seq_positive"),
    UniqueConstraint("episode_id", "seq", name="uq_episode_events_seq"),
    UniqueConstraint("episode_id", "host_event_key", name="uq_episode_events_host_event_key"),
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
    CheckConstraint("from_episode_id <> to_episode_id", name="ck_session_transfers_distinct_episodes"),
    UniqueConstraint("from_episode_id", "to_episode_id", "event_id", "transfer_kind", name="uq_session_transfers_transfer"),
)
