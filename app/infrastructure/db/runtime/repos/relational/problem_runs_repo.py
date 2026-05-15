"""Relational persistence for explicit problem-run scenario windows."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from app.core.entities.scenarios import ProblemRun, ProblemRunStatus
from app.core.ports.db.problem_runs import IProblemRunsRepo
from app.infrastructure.db.runtime.models.problem_runs import problem_runs


class ProblemRunsRepo(IProblemRunsRepo):
    """Persist bounded problem-solving scenarios in PostgreSQL."""

    def __init__(self, session) -> None:
        """Store the active SQLAlchemy session."""

        self._session = session

    def get_by_scenario_key(
        self,
        *,
        repo_id: str,
        episode_id: str,
        problem_memory_id: str,
        opened_event_id: str,
    ) -> ProblemRun | None:
        """Return an existing scenario row by its natural idempotency key."""

        row = (
            self._session.execute(
                select(problem_runs).where(
                    problem_runs.c.repo_id == repo_id,
                    problem_runs.c.episode_id == episode_id,
                    problem_runs.c.problem_memory_id == problem_memory_id,
                    problem_runs.c.opened_event_id == opened_event_id,
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            return None
        return _problem_run_from_row(row)

    def add(self, run: ProblemRun) -> None:
        """Append one explicit problem-run window."""

        now = datetime.now(timezone.utc)
        self._session.execute(
            problem_runs.insert().values(
                id=run.id,
                repo_id=run.repo_id,
                thread_id=run.thread_id,
                host_app=run.host_app,
                host_session_key=run.host_session_key,
                episode_id=run.episode_id,
                status=run.status.value,
                opened_at=run.opened_at,
                closed_at=run.closed_at,
                opened_by=run.opened_by,
                closed_by=run.closed_by,
                opened_event_id=run.opened_event_id,
                closed_event_id=run.closed_event_id,
                problem_memory_id=run.problem_memory_id,
                solution_memory_id=run.solution_memory_id,
                created_at=run.created_at or now,
                updated_at=run.updated_at or now,
            )
        )


def _problem_run_from_row(row) -> ProblemRun:
    """Map one relational row to the core scenario entity."""

    return ProblemRun(
        id=row["id"],
        repo_id=row["repo_id"],
        thread_id=row["thread_id"],
        host_app=row["host_app"],
        host_session_key=row["host_session_key"],
        episode_id=row["episode_id"],
        opened_event_id=row["opened_event_id"],
        status=ProblemRunStatus(row["status"]),
        opened_at=row["opened_at"],
        closed_at=row["closed_at"],
        opened_by=row["opened_by"],
        closed_by=row["closed_by"],
        closed_event_id=row["closed_event_id"],
        problem_memory_id=row["problem_memory_id"],
        solution_memory_id=row["solution_memory_id"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
