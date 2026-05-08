"""This module defines SQLAlchemy Core tables for problem attempts and fact updates."""

from sqlalchemy import CheckConstraint, Column, ForeignKey, String, Table, UniqueConstraint
from sqlalchemy.dialects.postgresql import TIMESTAMP

from app.infrastructure.db.models.metadata import metadata


problem_attempts = Table(
    "problem_attempts",
    metadata,
    Column("problem_id", String, ForeignKey("memories.id", ondelete="CASCADE"), primary_key=True),
    Column("attempt_id", String, ForeignKey("memories.id", ondelete="CASCADE"), primary_key=True),
    Column("role", String, nullable=False),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    CheckConstraint("problem_id <> attempt_id", name="ck_problem_attempts_distinct_memories"),
)

fact_updates = Table(
    "fact_updates",
    metadata,
    Column("id", String, primary_key=True),
    Column("old_fact_id", String, ForeignKey("memories.id", ondelete="CASCADE"), nullable=False),
    Column("change_id", String, ForeignKey("memories.id", ondelete="CASCADE"), nullable=False),
    Column("new_fact_id", String, ForeignKey("memories.id", ondelete="CASCADE"), nullable=False),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    CheckConstraint("old_fact_id <> new_fact_id", name="ck_fact_updates_distinct_fact_endpoints"),
    CheckConstraint(
        "change_id <> old_fact_id AND change_id <> new_fact_id",
        name="ck_fact_updates_change_id_distinct",
    ),
    UniqueConstraint("old_fact_id", "change_id", "new_fact_id", name="uq_fact_updates_chain"),
)
