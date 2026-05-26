"""SQLAlchemy Core tables for shadow snapshots and solution deltas."""

from sqlalchemy import (
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP

from app.infrastructure.db.runtime.models.metadata import metadata


shadow_snapshots = Table(
    "shadow_snapshots",
    metadata,
    Column("id", String, primary_key=True),
    Column("repo_id", String, nullable=False),
    Column("repo_root", Text, nullable=False),
    Column("episode_id", String, ForeignKey("episodes.id", ondelete="SET NULL")),
    Column("captured_after_event_seq", Integer),
    Column("operation_invocation_id", String),
    Column("shadow_commit_sha", String, nullable=False),
    Column("parent_shadow_commit_sha", String),
    Column(
        "changed_paths_json",
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    ),
    Column("reason", String, nullable=False),
    Column(
        "created_at",
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    ),
    CheckConstraint(
        "reason IN ('baseline', 'closeout', 'baseline_only')",
        name="ck_shadow_snapshots_reason",
    ),
    CheckConstraint(
        "captured_after_event_seq IS NULL OR captured_after_event_seq >= 0",
        name="ck_shadow_snapshots_event_seq_nonnegative",
    ),
    UniqueConstraint(
        "repo_id",
        "repo_root",
        "shadow_commit_sha",
        name="uq_shadow_snapshots_repo_commit",
    ),
)

Index(
    "idx_shadow_snapshots_repo_created",
    shadow_snapshots.c.repo_id,
    shadow_snapshots.c.repo_root,
    shadow_snapshots.c.created_at,
)
Index(
    "idx_shadow_snapshots_repo_episode_seq",
    shadow_snapshots.c.repo_id,
    shadow_snapshots.c.repo_root,
    shadow_snapshots.c.episode_id,
    shadow_snapshots.c.captured_after_event_seq,
)
Index("idx_shadow_snapshots_commit", shadow_snapshots.c.shadow_commit_sha)


solution_deltas = Table(
    "solution_deltas",
    metadata,
    Column("id", String, primary_key=True),
    Column(
        "problem_run_id",
        String,
        ForeignKey("problem_runs.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("repo_id", String, nullable=False),
    Column("repo_root", Text, nullable=False),
    Column("episode_id", String, ForeignKey("episodes.id", ondelete="SET NULL")),
    Column("base_snapshot_id", String, ForeignKey("shadow_snapshots.id"), nullable=False),
    Column("final_snapshot_id", String, ForeignKey("shadow_snapshots.id"), nullable=False),
    Column("patch_sha", String, nullable=False),
    Column(
        "changed_paths_json",
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    ),
    Column(
        "created_at",
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    ),
    CheckConstraint(
        "base_snapshot_id <> final_snapshot_id",
        name="ck_solution_deltas_distinct_snapshots",
    ),
    UniqueConstraint("problem_run_id", name="uq_solution_deltas_problem_run"),
)

Index("idx_solution_deltas_repo", solution_deltas.c.repo_id, solution_deltas.c.repo_root)
Index("idx_solution_deltas_problem_run", solution_deltas.c.problem_run_id)
Index("idx_solution_deltas_base_snapshot", solution_deltas.c.base_snapshot_id)
Index("idx_solution_deltas_final_snapshot", solution_deltas.c.final_snapshot_id)
