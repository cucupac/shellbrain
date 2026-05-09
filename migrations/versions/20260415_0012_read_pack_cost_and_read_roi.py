"""Add read-pack cost telemetry and read-before-solve ROI views."""

from alembic import op

from app.infrastructure.db.runtime.models.views import (
    USAGE_PROBLEM_READ_ROI_SQL,
    USAGE_READ_BEFORE_SOLVE_ROI_SQL,
)

revision = "20260415_0012"
down_revision = "20260414_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add read-pack estimate columns, a read-focused partial index, and ROI views."""

    op.execute(
        """
        ALTER TABLE read_invocation_summaries
          ADD COLUMN pack_char_count INTEGER,
          ADD COLUMN pack_token_estimate INTEGER,
          ADD COLUMN pack_token_estimate_method TEXT,
          ADD COLUMN direct_token_estimate INTEGER,
          ADD COLUMN explicit_related_token_estimate INTEGER,
          ADD COLUMN implicit_related_token_estimate INTEGER;

        CREATE INDEX idx_operation_invocations_successful_read_thread_created_at
          ON operation_invocations(repo_id, selected_thread_id, created_at)
          WHERE command = 'read'
            AND outcome = 'ok'
            AND selected_thread_id IS NOT NULL;
        """
    )
    op.execute(USAGE_PROBLEM_READ_ROI_SQL)
    op.execute(USAGE_READ_BEFORE_SOLVE_ROI_SQL)


def downgrade() -> None:
    """Drop read ROI views, partial index, and read-pack estimate columns."""

    op.execute(
        """
        DROP VIEW IF EXISTS usage_read_before_solve_roi;
        DROP VIEW IF EXISTS usage_problem_read_roi;

        DROP INDEX IF EXISTS idx_operation_invocations_successful_read_thread_created_at;

        ALTER TABLE read_invocation_summaries
          DROP COLUMN IF EXISTS implicit_related_token_estimate,
          DROP COLUMN IF EXISTS explicit_related_token_estimate,
          DROP COLUMN IF EXISTS direct_token_estimate,
          DROP COLUMN IF EXISTS pack_token_estimate_method,
          DROP COLUMN IF EXISTS pack_token_estimate,
          DROP COLUMN IF EXISTS pack_char_count;
        """
    )
