"""This module defines SQLAlchemy Core tables for evidence reference records."""

from sqlalchemy import Column, String, Table, UniqueConstraint
from sqlalchemy.dialects.postgresql import TIMESTAMP

from app.periphery.db.models.metadata import metadata


evidence_refs = Table(
    "evidence_refs",
    metadata,
    Column("id", String, primary_key=True),
    Column("repo_id", String, nullable=False),
    Column("ref", String, nullable=False),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    UniqueConstraint("repo_id", "ref", name="uq_evidence_repo_ref"),
)
