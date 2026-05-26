"""Add shadow snapshots and solution deltas."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260526_0036"
down_revision = "20260522_0035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create code-evidence tables."""

    op.create_table(
        "shadow_snapshots",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("repo_id", sa.String(), nullable=False),
        sa.Column("repo_root", sa.Text(), nullable=False),
        sa.Column(
            "episode_id",
            sa.String(),
            sa.ForeignKey("episodes.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("captured_after_event_seq", sa.Integer(), nullable=True),
        sa.Column("operation_invocation_id", sa.String(), nullable=True),
        sa.Column("shadow_commit_sha", sa.String(), nullable=False),
        sa.Column("parent_shadow_commit_sha", sa.String(), nullable=True),
        sa.Column(
            "changed_paths_json",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.CheckConstraint(
            "reason IN ('baseline', 'closeout', 'baseline_only')",
            name="ck_shadow_snapshots_reason",
        ),
        sa.CheckConstraint(
            "captured_after_event_seq IS NULL OR captured_after_event_seq >= 0",
            name="ck_shadow_snapshots_event_seq_nonnegative",
        ),
        sa.UniqueConstraint(
            "repo_id",
            "repo_root",
            "shadow_commit_sha",
            name="uq_shadow_snapshots_repo_commit",
        ),
    )
    op.create_index(
        "idx_shadow_snapshots_repo_created",
        "shadow_snapshots",
        ["repo_id", "repo_root", "created_at"],
    )
    op.create_index(
        "idx_shadow_snapshots_repo_episode_seq",
        "shadow_snapshots",
        ["repo_id", "repo_root", "episode_id", "captured_after_event_seq"],
    )
    op.create_index(
        "idx_shadow_snapshots_commit",
        "shadow_snapshots",
        ["shadow_commit_sha"],
    )

    op.create_table(
        "solution_deltas",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "problem_run_id",
            sa.String(),
            sa.ForeignKey("problem_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("repo_id", sa.String(), nullable=False),
        sa.Column("repo_root", sa.Text(), nullable=False),
        sa.Column(
            "episode_id",
            sa.String(),
            sa.ForeignKey("episodes.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "base_snapshot_id",
            sa.String(),
            sa.ForeignKey("shadow_snapshots.id"),
            nullable=False,
        ),
        sa.Column(
            "final_snapshot_id",
            sa.String(),
            sa.ForeignKey("shadow_snapshots.id"),
            nullable=False,
        ),
        sa.Column("patch_sha", sa.String(), nullable=False),
        sa.Column(
            "changed_paths_json",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.CheckConstraint(
            "base_snapshot_id <> final_snapshot_id",
            name="ck_solution_deltas_distinct_snapshots",
        ),
        sa.UniqueConstraint("problem_run_id", name="uq_solution_deltas_problem_run"),
    )
    op.create_index(
        "idx_solution_deltas_repo",
        "solution_deltas",
        ["repo_id", "repo_root"],
    )
    op.create_index(
        "idx_solution_deltas_problem_run",
        "solution_deltas",
        ["problem_run_id"],
    )
    op.create_index(
        "idx_solution_deltas_base_snapshot",
        "solution_deltas",
        ["base_snapshot_id"],
    )
    op.create_index(
        "idx_solution_deltas_final_snapshot",
        "solution_deltas",
        ["final_snapshot_id"],
    )


def downgrade() -> None:
    """Drop code-evidence tables."""

    op.drop_index("idx_solution_deltas_final_snapshot", table_name="solution_deltas")
    op.drop_index("idx_solution_deltas_base_snapshot", table_name="solution_deltas")
    op.drop_index("idx_solution_deltas_problem_run", table_name="solution_deltas")
    op.drop_index("idx_solution_deltas_repo", table_name="solution_deltas")
    op.drop_table("solution_deltas")
    op.drop_index("idx_shadow_snapshots_commit", table_name="shadow_snapshots")
    op.drop_index("idx_shadow_snapshots_repo_episode_seq", table_name="shadow_snapshots")
    op.drop_index("idx_shadow_snapshots_repo_created", table_name="shadow_snapshots")
    op.drop_table("shadow_snapshots")
