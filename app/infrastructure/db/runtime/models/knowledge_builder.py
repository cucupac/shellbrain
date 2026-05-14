"""SQLAlchemy Core tables for knowledge-builder lifecycle records."""

from sqlalchemy import (
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP

from app.infrastructure.db.runtime.models.metadata import metadata


_TRIGGERS = "'session_replaced', 'idle_stable'"
_STATUSES = (
    "'running', 'ok', 'skipped', 'provider_unavailable', "
    "'timeout', 'invalid_output', 'error'"
)


knowledge_build_runs = Table(
    "knowledge_build_runs",
    metadata,
    Column("id", String, primary_key=True),
    Column("repo_id", String, nullable=False),
    Column(
        "episode_id",
        String,
        ForeignKey("episodes.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("trigger", String, nullable=False),
    Column("status", String, nullable=False),
    Column("event_watermark", Integer, nullable=False),
    Column("previous_event_watermark", Integer),
    Column("provider", String, nullable=False),
    Column("model", String, nullable=False),
    Column("reasoning", String, nullable=False),
    Column("write_count", Integer, nullable=False, server_default=text("0")),
    Column("skipped_item_count", Integer, nullable=False, server_default=text("0")),
    Column("run_summary", Text),
    Column("error_code", String),
    Column("error_message", Text),
    Column("started_at", TIMESTAMP(timezone=True), nullable=False),
    Column("finished_at", TIMESTAMP(timezone=True)),
    Column(
        "created_at",
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    ),
    CheckConstraint(
        f"trigger IN ({_TRIGGERS})",
        name="ck_knowledge_build_runs_trigger",
    ),
    CheckConstraint(
        f"status IN ({_STATUSES})",
        name="ck_knowledge_build_runs_status",
    ),
    CheckConstraint(
        "event_watermark >= 0",
        name="ck_knowledge_build_runs_watermark_nonnegative",
    ),
    CheckConstraint(
        "previous_event_watermark IS NULL OR previous_event_watermark >= 0",
        name="ck_knowledge_build_runs_previous_watermark_nonnegative",
    ),
    CheckConstraint(
        "write_count >= 0",
        name="ck_knowledge_build_runs_write_count_nonnegative",
    ),
    CheckConstraint(
        "skipped_item_count >= 0",
        name="ck_knowledge_build_runs_skipped_count_nonnegative",
    ),
)

Index(
    "idx_knowledge_build_runs_episode_status_created_at",
    knowledge_build_runs.c.repo_id,
    knowledge_build_runs.c.episode_id,
    knowledge_build_runs.c.status,
    knowledge_build_runs.c.created_at,
)
