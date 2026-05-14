"""Relational persistence for build_knowledge run records."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import desc, select, text, update

from app.core.entities.knowledge_builder import (
    KnowledgeBuildRun,
    KnowledgeBuildRunStatus,
    KnowledgeBuildTrigger,
)
from app.core.ports.db.knowledge_builder import IKnowledgeBuildRunsRepo
from app.infrastructure.db.runtime.models.knowledge_builder import knowledge_build_runs


class KnowledgeBuildRunsRepo(IKnowledgeBuildRunsRepo):
    """Persist build_knowledge lifecycle rows in PostgreSQL."""

    def __init__(self, session) -> None:
        """Store the active SQLAlchemy session."""

        self._session = session

    def acquire_episode_lock(self, *, repo_id: str, episode_id: str) -> bool:
        """Try to acquire a transaction-scoped lock for one repo episode."""

        value = self._session.execute(
            text(
                """
                SELECT pg_try_advisory_xact_lock(
                  hashtext(:repo_id),
                  hashtext(:episode_id)
                )
                """
            ),
            {"repo_id": repo_id, "episode_id": episode_id},
        ).scalar_one()
        return bool(value)

    def latest_successful_watermark(
        self, *, repo_id: str, episode_id: str
    ) -> int | None:
        """Return the latest successful processed event watermark."""

        row = (
            self._session.execute(
                select(knowledge_build_runs.c.event_watermark)
                .where(
                    knowledge_build_runs.c.repo_id == repo_id,
                    knowledge_build_runs.c.episode_id == episode_id,
                    knowledge_build_runs.c.status.in_(
                        (
                            KnowledgeBuildRunStatus.OK.value,
                            KnowledgeBuildRunStatus.SKIPPED.value,
                        )
                    ),
                )
                .order_by(desc(knowledge_build_runs.c.event_watermark))
                .limit(1)
            )
            .scalars()
            .first()
        )
        return None if row is None else int(row)

    def list_running_runs(
        self, *, repo_id: str, episode_id: str
    ) -> tuple[KnowledgeBuildRun, ...]:
        """Return running rows for this episode ordered by start time."""

        rows = (
            self._session.execute(
                select(knowledge_build_runs)
                .where(
                    knowledge_build_runs.c.repo_id == repo_id,
                    knowledge_build_runs.c.episode_id == episode_id,
                    knowledge_build_runs.c.status
                    == KnowledgeBuildRunStatus.RUNNING.value,
                )
                .order_by(knowledge_build_runs.c.started_at.asc())
            )
            .mappings()
            .all()
        )
        return tuple(_run_from_row(row) for row in rows)

    def add(self, run: KnowledgeBuildRun) -> None:
        """Append one build_knowledge run row."""

        now = datetime.now(timezone.utc)
        self._session.execute(
            knowledge_build_runs.insert().values(
                id=run.id,
                repo_id=run.repo_id,
                episode_id=run.episode_id,
                trigger=run.trigger.value,
                status=run.status.value,
                event_watermark=run.event_watermark,
                previous_event_watermark=run.previous_event_watermark,
                provider=run.provider,
                model=run.model,
                reasoning=run.reasoning,
                write_count=run.write_count,
                skipped_item_count=run.skipped_item_count,
                run_summary=run.run_summary,
                error_code=run.error_code,
                error_message=run.error_message,
                started_at=run.started_at or now,
                finished_at=run.finished_at,
                created_at=run.created_at or now,
            )
        )

    def complete(
        self,
        *,
        run_id: str,
        status: KnowledgeBuildRunStatus,
        write_count: int,
        skipped_item_count: int,
        run_summary: str | None,
        error_code: str | None,
        error_message: str | None,
        finished_at: datetime,
    ) -> None:
        """Finalize one previously-running build_knowledge run."""

        self._session.execute(
            update(knowledge_build_runs)
            .where(knowledge_build_runs.c.id == run_id)
            .values(
                status=status.value,
                write_count=write_count,
                skipped_item_count=skipped_item_count,
                run_summary=run_summary,
                error_code=error_code,
                error_message=error_message,
                finished_at=finished_at,
            )
        )


def _run_from_row(row) -> KnowledgeBuildRun:
    """Map a relational row into a core run entity."""

    return KnowledgeBuildRun(
        id=row["id"],
        repo_id=row["repo_id"],
        episode_id=row["episode_id"],
        trigger=KnowledgeBuildTrigger(row["trigger"]),
        status=KnowledgeBuildRunStatus(row["status"]),
        event_watermark=row["event_watermark"],
        previous_event_watermark=row["previous_event_watermark"],
        provider=row["provider"],
        model=row["model"],
        reasoning=row["reasoning"],
        write_count=row["write_count"],
        skipped_item_count=row["skipped_item_count"],
        run_summary=row["run_summary"],
        error_code=row["error_code"],
        error_message=row["error_message"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        created_at=row["created_at"],
    )
