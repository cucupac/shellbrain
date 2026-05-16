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
                input_tokens=run.input_tokens,
                output_tokens=run.output_tokens,
                reasoning_output_tokens=run.reasoning_output_tokens,
                cached_input_tokens_total=run.cached_input_tokens_total,
                cache_read_input_tokens=run.cache_read_input_tokens,
                cache_creation_input_tokens=run.cache_creation_input_tokens,
                capture_quality=run.capture_quality,
                run_summary=run.run_summary,
                error_code=run.error_code,
                error_message=run.error_message,
                read_trace_json=run.read_trace,
                code_trace_json=run.code_trace,
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
        input_tokens: int | None,
        output_tokens: int | None,
        reasoning_output_tokens: int | None,
        cached_input_tokens_total: int | None,
        cache_read_input_tokens: int | None,
        cache_creation_input_tokens: int | None,
        capture_quality: str | None,
        run_summary: str | None,
        error_code: str | None,
        error_message: str | None,
        finished_at: datetime,
        read_trace: dict[str, object] | None = None,
        code_trace: dict[str, object] | None = None,
    ) -> None:
        """Finalize one previously-running build_knowledge run."""

        self._session.execute(
            update(knowledge_build_runs)
            .where(knowledge_build_runs.c.id == run_id)
            .values(
                status=status.value,
                write_count=write_count,
                skipped_item_count=skipped_item_count,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                reasoning_output_tokens=reasoning_output_tokens,
                cached_input_tokens_total=cached_input_tokens_total,
                cache_read_input_tokens=cache_read_input_tokens,
                cache_creation_input_tokens=cache_creation_input_tokens,
                capture_quality=capture_quality,
                run_summary=run_summary,
                error_code=error_code,
                error_message=error_message,
                read_trace_json=read_trace or {},
                code_trace_json=code_trace or {},
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
        input_tokens=row["input_tokens"],
        output_tokens=row["output_tokens"],
        reasoning_output_tokens=row["reasoning_output_tokens"],
        cached_input_tokens_total=row["cached_input_tokens_total"],
        cache_read_input_tokens=row["cache_read_input_tokens"],
        cache_creation_input_tokens=row["cache_creation_input_tokens"],
        capture_quality=row["capture_quality"],
        run_summary=row["run_summary"],
        error_code=row["error_code"],
        error_message=row["error_message"],
        read_trace=row["read_trace_json"] or {},
        code_trace=row["code_trace_json"] or {},
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        created_at=row["created_at"],
    )
