"""Add explicit problem-run token metrics."""

from alembic import op

from app.periphery.db.models.views import (
    USAGE_PROBLEM_READ_ROI_LEGACY_SQL,
    USAGE_PROBLEM_RUN_TOKENS_SQL,
    USAGE_PROBLEM_TOKENS_LEGACY_SQL,
    USAGE_READ_BEFORE_SOLVE_ROI_LEGACY_SQL,
)

revision = "20260422_0015"
down_revision = "20260422_0014"
branch_labels = None
depends_on = None


def _unsuffixed_proxy_sql(sql: str) -> str:
    """Return the pre-legacy view name for downgrade compatibility."""

    return (
        sql.replace("usage_read_before_solve_roi_legacy", "usage_read_before_solve_roi")
        .replace("usage_problem_read_roi_legacy", "usage_problem_read_roi")
        .replace("usage_problem_tokens_legacy", "usage_problem_tokens")
    )


def upgrade() -> None:
    """Create problem-run windows and rename memory-derived token proxies."""

    op.execute(
        """
        DROP VIEW IF EXISTS usage_read_before_solve_roi;
        DROP VIEW IF EXISTS usage_problem_read_roi;
        DROP VIEW IF EXISTS usage_problem_tokens;

        CREATE TABLE problem_runs (
          id TEXT PRIMARY KEY,
          repo_id TEXT NOT NULL,
          thread_id TEXT,
          host_app TEXT,
          host_session_key TEXT,
          episode_id TEXT REFERENCES episodes(id) ON DELETE SET NULL,
          status TEXT NOT NULL,
          opened_at TIMESTAMPTZ NOT NULL,
          closed_at TIMESTAMPTZ,
          opened_by TEXT NOT NULL,
          closed_by TEXT,
          problem_memory_id TEXT REFERENCES memories(id) ON DELETE SET NULL,
          solution_memory_id TEXT REFERENCES memories(id) ON DELETE SET NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          CONSTRAINT ck_problem_runs_status CHECK (status IN ('open', 'closed', 'abandoned')),
          CONSTRAINT ck_problem_runs_opened_by CHECK (opened_by IN ('worker', 'librarian', 'manual', 'system')),
          CONSTRAINT ck_problem_runs_closed_by CHECK (closed_by IS NULL OR closed_by IN ('worker', 'librarian', 'manual', 'system')),
          CONSTRAINT ck_problem_runs_closed_after_opened CHECK (closed_at IS NULL OR closed_at >= opened_at),
          CONSTRAINT ck_problem_runs_status_closed_at CHECK (
            (
              status = 'open'
              AND closed_at IS NULL
            ) OR (
              status IN ('closed', 'abandoned')
              AND closed_at IS NOT NULL
            )
          )
        );

        CREATE INDEX idx_problem_runs_repo_thread_window
          ON problem_runs(repo_id, thread_id, opened_at, closed_at);
        CREATE INDEX idx_problem_runs_repo_host_session_window
          ON problem_runs(repo_id, host_app, host_session_key, opened_at, closed_at);
        CREATE INDEX idx_problem_runs_repo_status_opened_at
          ON problem_runs(repo_id, status, opened_at);
        CREATE INDEX idx_problem_runs_problem_memory
          ON problem_runs(problem_memory_id);
        CREATE INDEX idx_problem_runs_solution_memory
          ON problem_runs(solution_memory_id);
        """
    )
    op.execute(USAGE_PROBLEM_TOKENS_LEGACY_SQL)
    op.execute(USAGE_PROBLEM_READ_ROI_LEGACY_SQL)
    op.execute(USAGE_READ_BEFORE_SOLVE_ROI_LEGACY_SQL)
    op.execute(USAGE_PROBLEM_RUN_TOKENS_SQL)


def downgrade() -> None:
    """Drop problem-run metrics and restore the previous proxy view names."""

    op.execute(
        """
        DROP VIEW IF EXISTS usage_problem_run_tokens;
        DROP TABLE IF EXISTS problem_runs;

        DROP VIEW IF EXISTS usage_read_before_solve_roi_legacy;
        DROP VIEW IF EXISTS usage_problem_read_roi_legacy;
        DROP VIEW IF EXISTS usage_problem_tokens_legacy;
        """
    )
    op.execute(_unsuffixed_proxy_sql(USAGE_PROBLEM_TOKENS_LEGACY_SQL))
    op.execute(_unsuffixed_proxy_sql(USAGE_PROBLEM_READ_ROI_LEGACY_SQL))
    op.execute(_unsuffixed_proxy_sql(USAGE_READ_BEFORE_SOLVE_ROI_LEGACY_SQL))
