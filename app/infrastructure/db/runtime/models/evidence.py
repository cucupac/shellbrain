"""This module defines SQLAlchemy Core tables for unified evidence storage."""

from sqlalchemy import (
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    String,
    Table,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP

from app.infrastructure.db.runtime.models.metadata import metadata


_EVIDENCE_SOURCE_KINDS = (
    "'episode_event', 'anchor', 'memory', 'commit', 'transcript', 'test', 'manual'"
)
_EVIDENCE_TARGET_TYPES = (
    "'memory', 'fact_update', 'association_edge', 'utility_observation', "
    "'concept_claim', 'concept_relation', 'concept_grounding', "
    "'concept_memory_link', 'concept_lifecycle_event'"
)
_EVIDENCE_ROLES = (
    "'supports', 'contradicts', 'observed_in', 'created_from', "
    "'validated_by', 'invalidated_by', 'explains'"
)


evidence_refs = Table(
    "evidence_refs",
    metadata,
    Column("id", String, primary_key=True),
    Column("repo_id", String, nullable=False),
    Column("kind", String, nullable=False),
    Column("ref", String, nullable=False),
    Column("canonical_hash", String, nullable=False),
    Column("episode_event_id", String, ForeignKey("episode_events.id"), nullable=True),
    Column("anchor_id", String, ForeignKey("anchors.id", ondelete="SET NULL")),
    Column("memory_id", String, ForeignKey("memories.id", ondelete="SET NULL")),
    Column("commit_ref", String),
    Column("transcript_ref", String),
    Column("note", String),
    Column(
        "created_at",
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    ),
    CheckConstraint(
        f"kind IN ({_EVIDENCE_SOURCE_KINDS})",
        name="ck_evidence_refs_kind",
    ),
    UniqueConstraint(
        "repo_id", "episode_event_id", name="uq_evidence_repo_episode_event"
    ),
    UniqueConstraint(
        "repo_id",
        "canonical_hash",
        name="uq_evidence_repo_canonical_hash",
    ),
)

evidence_links = Table(
    "evidence_links",
    metadata,
    Column("id", String, primary_key=True),
    Column("repo_id", String, nullable=False),
    Column("target_type", String, nullable=False),
    Column("target_id", String, nullable=False),
    Column(
        "evidence_id",
        String,
        ForeignKey("evidence_refs.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("evidence_role", String, nullable=False),
    Column(
        "created_at",
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    ),
    CheckConstraint(
        f"target_type IN ({_EVIDENCE_TARGET_TYPES})",
        name="ck_evidence_links_target_type",
    ),
    CheckConstraint(
        f"evidence_role IN ({_EVIDENCE_ROLES})",
        name="ck_evidence_links_role",
    ),
    UniqueConstraint(
        "repo_id",
        "target_type",
        "target_id",
        "evidence_id",
        "evidence_role",
        name="uq_evidence_links_target_evidence_role",
    ),
)

Index(
    "idx_evidence_links_target",
    evidence_links.c.repo_id,
    evidence_links.c.target_type,
    evidence_links.c.target_id,
)
Index(
    "idx_evidence_links_evidence",
    evidence_links.c.evidence_id,
)
