"""SQLAlchemy Core table for explicit problem-run telemetry windows."""

from sqlalchemy import CheckConstraint, Column, ForeignKey, Index, String, Table, text
from sqlalchemy.dialects.postgresql import TIMESTAMP

from app.periphery.db.models.metadata import metadata


_PROBLEM_RUN_STATUSES = "'open', 'closed', 'abandoned'"
_PROBLEM_RUN_ACTORS = "'worker', 'librarian', 'manual', 'system'"


problem_runs = Table(
    "problem_runs",
    metadata,
    Column("id", String, primary_key=True),
    Column("repo_id", String, nullable=False),
    Column("thread_id", String),
    Column("host_app", String),
    Column("host_session_key", String),
    Column("episode_id", String, ForeignKey("episodes.id", ondelete="SET NULL")),
    Column("status", String, nullable=False),
    Column("opened_at", TIMESTAMP(timezone=True), nullable=False),
    Column("closed_at", TIMESTAMP(timezone=True)),
    Column("opened_by", String, nullable=False),
    Column("closed_by", String),
    Column("problem_memory_id", String, ForeignKey("memories.id", ondelete="SET NULL")),
    Column("solution_memory_id", String, ForeignKey("memories.id", ondelete="SET NULL")),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()")),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()")),
    CheckConstraint(f"status IN ({_PROBLEM_RUN_STATUSES})", name="ck_problem_runs_status"),
    CheckConstraint(f"opened_by IN ({_PROBLEM_RUN_ACTORS})", name="ck_problem_runs_opened_by"),
    CheckConstraint(f"closed_by IS NULL OR closed_by IN ({_PROBLEM_RUN_ACTORS})", name="ck_problem_runs_closed_by"),
    CheckConstraint("closed_at IS NULL OR closed_at >= opened_at", name="ck_problem_runs_closed_after_opened"),
    CheckConstraint(
        """
        (
          status = 'open'
          AND closed_at IS NULL
        ) OR (
          status IN ('closed', 'abandoned')
          AND closed_at IS NOT NULL
        )
        """,
        name="ck_problem_runs_status_closed_at",
    ),
)

Index("idx_problem_runs_repo_thread_window", problem_runs.c.repo_id, problem_runs.c.thread_id, problem_runs.c.opened_at, problem_runs.c.closed_at)
Index(
    "idx_problem_runs_repo_host_session_window",
    problem_runs.c.repo_id,
    problem_runs.c.host_app,
    problem_runs.c.host_session_key,
    problem_runs.c.opened_at,
    problem_runs.c.closed_at,
)
Index("idx_problem_runs_repo_status_opened_at", problem_runs.c.repo_id, problem_runs.c.status, problem_runs.c.opened_at)
Index("idx_problem_runs_problem_memory", problem_runs.c.problem_memory_id)
Index("idx_problem_runs_solution_memory", problem_runs.c.solution_memory_id)
