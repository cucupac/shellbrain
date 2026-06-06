"""Relational persistence for generated wiki summary cache records."""

from __future__ import annotations

from datetime import datetime
from typing import Sequence

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert

from app.core.entities.wiki_summaries import (
    WikiSummaryGenerationStatus,
    WikiSummaryInputSnapshot,
    WikiSummaryRecord,
    WikiSummaryTarget,
    WikiSummaryTargetType,
)
from app.core.ports.db.wiki_summaries import IWikiSummaryRepo
from app.infrastructure.db.runtime.models.wiki_summaries import wiki_summaries


class WikiSummariesRepo(IWikiSummaryRepo):
    """Persist generated wiki summaries in PostgreSQL."""

    def __init__(self, session) -> None:
        """Store the active SQLAlchemy session."""

        self._session = session

    def get(self, target: WikiSummaryTarget) -> WikiSummaryRecord | None:
        """Return the cached summary for one target when present."""

        row = (
            self._session.execute(
                select(wiki_summaries).where(
                    wiki_summaries.c.repo_id == target.repo_id,
                    wiki_summaries.c.target_type == target.target_type.value,
                    wiki_summaries.c.target_id == target.target_id,
                )
            )
            .mappings()
            .first()
        )
        return None if row is None else _record_from_row(row)

    def acquire_refresh(
        self,
        *,
        snapshot: WikiSummaryInputSnapshot,
        model: str,
        prompt_version: str,
        now: datetime,
        stale_running_before: datetime,
    ) -> bool:
        """Mark one target pending when no fresh refresh is already running."""

        if not self._acquire_target_lock(snapshot.target):
            return False
        current = self.get(snapshot.target)
        if (
            current is not None
            and current.generation_status == WikiSummaryGenerationStatus.PENDING
            and current.updated_at > stale_running_before
        ):
            return False

        identity_values = {
            "repo_id": snapshot.target.repo_id,
            "target_type": snapshot.target.target_type.value,
            "target_id": snapshot.target.target_id,
        }
        update_values = {
            "input_hash": snapshot.input_hash,
            "source_refs_json": list(snapshot.source_refs),
            "generation_status": WikiSummaryGenerationStatus.PENDING.value,
            "model": model,
            "prompt_version": prompt_version,
            "last_error_code": None,
            "last_error_message": None,
            "updated_at": now,
        }
        self._session.execute(
            insert(wiki_summaries)
            .values(created_at=now, **identity_values, **update_values)
            .on_conflict_do_update(
                index_elements=[
                    wiki_summaries.c.repo_id,
                    wiki_summaries.c.target_type,
                    wiki_summaries.c.target_id,
                ],
                set_=update_values,
            )
        )
        return True

    def record_success(
        self,
        *,
        snapshot: WikiSummaryInputSnapshot,
        body: str,
        model: str,
        prompt_version: str,
        now: datetime,
    ) -> None:
        """Persist generated summary prose for one target."""

        identity_values = {
            "repo_id": snapshot.target.repo_id,
            "target_type": snapshot.target.target_type.value,
            "target_id": snapshot.target.target_id,
        }
        update_values = {
            "body": body,
            "input_hash": snapshot.input_hash,
            "source_refs_json": list(snapshot.source_refs),
            "generated_at": now,
            "generation_status": WikiSummaryGenerationStatus.OK.value,
            "model": model,
            "prompt_version": prompt_version,
            "last_error_code": None,
            "last_error_message": None,
            "updated_at": now,
        }
        self._session.execute(
            insert(wiki_summaries)
            .values(created_at=now, **identity_values, **update_values)
            .on_conflict_do_update(
                index_elements=[
                    wiki_summaries.c.repo_id,
                    wiki_summaries.c.target_type,
                    wiki_summaries.c.target_id,
                ],
                set_=update_values,
            )
        )

    def record_failure(
        self,
        *,
        snapshot: WikiSummaryInputSnapshot,
        model: str,
        prompt_version: str,
        error_code: str,
        error_message: str,
        now: datetime,
    ) -> None:
        """Persist a failed refresh attempt without deleting prior prose."""

        identity_values = {
            "repo_id": snapshot.target.repo_id,
            "target_type": snapshot.target.target_type.value,
            "target_id": snapshot.target.target_id,
        }
        update_values = {
            "input_hash": snapshot.input_hash,
            "source_refs_json": list(snapshot.source_refs),
            "generation_status": WikiSummaryGenerationStatus.FAILED.value,
            "model": model,
            "prompt_version": prompt_version,
            "last_error_code": error_code,
            "last_error_message": error_message,
            "updated_at": now,
        }
        self._session.execute(
            insert(wiki_summaries)
            .values(created_at=now, **identity_values, **update_values)
            .on_conflict_do_update(
                index_elements=[
                    wiki_summaries.c.repo_id,
                    wiki_summaries.c.target_type,
                    wiki_summaries.c.target_id,
                ],
                set_=update_values,
            )
        )

    def list_existing_targets(
        self, *, repo_ids: Sequence[str]
    ) -> Sequence[WikiSummaryTarget]:
        """Return summary targets that already have cache rows for these repos."""

        ids = tuple(dict.fromkeys(str(repo_id) for repo_id in repo_ids))
        if not ids:
            return ()
        rows = (
            self._session.execute(
                select(
                    wiki_summaries.c.repo_id,
                    wiki_summaries.c.target_type,
                    wiki_summaries.c.target_id,
                ).where(wiki_summaries.c.repo_id.in_(ids))
            )
            .mappings()
            .all()
        )
        return tuple(
            WikiSummaryTarget(
                repo_id=row["repo_id"],
                target_type=WikiSummaryTargetType(row["target_type"]),
                target_id=row["target_id"],
            )
            for row in rows
        )

    def _acquire_target_lock(self, target: WikiSummaryTarget) -> bool:
        key = f"{target.target_type.value}:{target.target_id}"
        return bool(
            self._session.execute(
                text(
                    "SELECT pg_try_advisory_xact_lock("
                    "hashtext(:repo_id), hashtext(:target_key)"
                    ")"
                ),
                {"repo_id": target.repo_id, "target_key": key},
            ).scalar()
        )


def _record_from_row(row) -> WikiSummaryRecord:
    """Map one relational row into a core summary record."""

    return WikiSummaryRecord(
        target=WikiSummaryTarget(
            repo_id=row["repo_id"],
            target_type=WikiSummaryTargetType(row["target_type"]),
            target_id=row["target_id"],
        ),
        body=row["body"],
        input_hash=row["input_hash"],
        source_refs=tuple(str(value) for value in (row["source_refs_json"] or [])),
        generation_status=WikiSummaryGenerationStatus(row["generation_status"]),
        generated_at=row["generated_at"],
        model=row["model"],
        prompt_version=row["prompt_version"],
        last_error_code=row["last_error_code"],
        last_error_message=row["last_error_message"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
