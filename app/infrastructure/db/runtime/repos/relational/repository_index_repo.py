"""Relational repository index queries."""

from __future__ import annotations

from sqlalchemy import func, select, union_all

from app.core.entities.repositories import RepositorySummary
from app.core.ports.db.repository_index import IRepositoryIndexRepo
from app.infrastructure.db.runtime.models.concepts import concepts
from app.infrastructure.db.runtime.models.evidence import evidence_refs
from app.infrastructure.db.runtime.models.memories import memories
from app.infrastructure.db.runtime.models.telemetry import operation_invocations


class RepositoryIndexRepo(IRepositoryIndexRepo):
    """Read known repository ids and compact counts from existing tables."""

    def __init__(self, session) -> None:
        """Store the active SQLAlchemy session."""

        self._session = session

    def list_repositories(self) -> list[RepositorySummary]:
        """Return repositories ordered by recent activity and repo id."""

        repo_ids = union_all(
            select(concepts.c.repo_id.label("repo_id")),
            select(memories.c.repo_id.label("repo_id")),
            select(evidence_refs.c.repo_id.label("repo_id")),
        ).subquery()
        distinct_repos = (
            select(repo_ids.c.repo_id).distinct().subquery()
        )
        concept_counts = (
            select(
                concepts.c.repo_id.label("repo_id"),
                func.count().label("concept_count"),
            )
            .group_by(concepts.c.repo_id)
            .subquery()
        )
        memory_counts = (
            select(
                memories.c.repo_id.label("repo_id"),
                func.count().label("memory_count"),
            )
            .group_by(memories.c.repo_id)
            .subquery()
        )
        evidence_counts = (
            select(
                evidence_refs.c.repo_id.label("repo_id"),
                func.count().label("evidence_count"),
            )
            .group_by(evidence_refs.c.repo_id)
            .subquery()
        )
        repo_activity = (
            select(
                operation_invocations.c.repo_id.label("repo_id"),
                func.max(operation_invocations.c.created_at).label("last_seen_at"),
            )
            .group_by(operation_invocations.c.repo_id)
            .subquery()
        )
        root_counts = (
            select(
                operation_invocations.c.repo_id.label("repo_id"),
                operation_invocations.c.repo_root.label("repo_root"),
                func.count().label("root_count"),
                func.max(operation_invocations.c.created_at).label("root_last_seen_at"),
            )
            .where(operation_invocations.c.repo_root.is_not(None))
            .group_by(operation_invocations.c.repo_id, operation_invocations.c.repo_root)
            .subquery()
        )
        ranked_roots = (
            select(
                root_counts.c.repo_id,
                root_counts.c.repo_root,
                func.row_number()
                .over(
                    partition_by=root_counts.c.repo_id,
                    order_by=(
                        root_counts.c.root_count.desc(),
                        root_counts.c.root_last_seen_at.desc(),
                        root_counts.c.repo_root.asc(),
                    ),
                )
                .label("root_rank"),
            )
            .subquery()
        )
        primary_roots = (
            select(ranked_roots.c.repo_id, ranked_roots.c.repo_root)
            .where(ranked_roots.c.root_rank == 1)
            .subquery()
        )
        rows = (
            self._session.execute(
                select(
                    distinct_repos.c.repo_id,
                    primary_roots.c.repo_root,
                    func.coalesce(concept_counts.c.concept_count, 0).label(
                        "concept_count"
                    ),
                    func.coalesce(memory_counts.c.memory_count, 0).label(
                        "memory_count"
                    ),
                    func.coalesce(evidence_counts.c.evidence_count, 0).label(
                        "evidence_count"
                    ),
                    repo_activity.c.last_seen_at,
                )
                .select_from(
                    distinct_repos.outerjoin(
                        concept_counts,
                        concept_counts.c.repo_id == distinct_repos.c.repo_id,
                    )
                    .outerjoin(
                        memory_counts,
                        memory_counts.c.repo_id == distinct_repos.c.repo_id,
                    )
                    .outerjoin(
                        evidence_counts,
                        evidence_counts.c.repo_id == distinct_repos.c.repo_id,
                    )
                    .outerjoin(
                        repo_activity,
                        repo_activity.c.repo_id == distinct_repos.c.repo_id,
                    )
                    .outerjoin(
                        primary_roots,
                        primary_roots.c.repo_id == distinct_repos.c.repo_id,
                    )
                )
                .order_by(
                    repo_activity.c.last_seen_at.desc().nullslast(),
                    distinct_repos.c.repo_id.asc(),
                )
            )
            .mappings()
            .all()
        )
        return [
            RepositorySummary(
                repo_id=str(row["repo_id"]),
                repo_root=str(row["repo_root"]) if row["repo_root"] is not None else None,
                concept_count=int(row["concept_count"] or 0),
                memory_count=int(row["memory_count"] or 0),
                evidence_count=int(row["evidence_count"] or 0),
                last_seen_at=(
                    row["last_seen_at"].isoformat()
                    if row["last_seen_at"] is not None
                    else None
                ),
            )
            for row in rows
        ]
