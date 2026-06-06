"""SQLAlchemy Core table for generated wiki summary cache records."""

from sqlalchemy import CheckConstraint, Column, Index, String, Table, Text, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP

from app.infrastructure.db.runtime.models.metadata import metadata


_TARGET_TYPES = "'repo', 'concept'"
_GENERATION_STATUSES = "'pending', 'ok', 'failed'"


wiki_summaries = Table(
    "wiki_summaries",
    metadata,
    Column("repo_id", String, primary_key=True),
    Column("target_type", String, primary_key=True),
    Column("target_id", String, primary_key=True),
    Column("body", Text),
    Column("input_hash", String),
    Column("source_refs_json", JSONB, nullable=False, server_default=text("'[]'::jsonb")),
    Column("generated_at", TIMESTAMP(timezone=True)),
    Column("generation_status", String, nullable=False),
    Column("model", String),
    Column("prompt_version", String),
    Column("last_error_code", String),
    Column("last_error_message", Text),
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
        f"target_type IN ({_TARGET_TYPES})",
        name="ck_wiki_summaries_target_type",
    ),
    CheckConstraint(
        f"generation_status IN ({_GENERATION_STATUSES})",
        name="ck_wiki_summaries_generation_status",
    ),
    CheckConstraint(
        "generation_status <> 'ok' OR body IS NOT NULL",
        name="ck_wiki_summaries_ok_body",
    ),
    CheckConstraint(
        "generation_status <> 'ok' OR input_hash IS NOT NULL",
        name="ck_wiki_summaries_ok_input_hash",
    ),
)

Index(
    "idx_wiki_summaries_repo_status_updated",
    wiki_summaries.c.repo_id,
    wiki_summaries.c.generation_status,
    wiki_summaries.c.updated_at,
)
