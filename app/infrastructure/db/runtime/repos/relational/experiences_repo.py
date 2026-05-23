"""This module defines relational repository operations for structural memory links."""

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.core.entities.memories import (
    MemoryKind,
    MemoryLifecycleActor,
    MemoryLifecycleStatus,
)
from app.core.entities.structural_memory_relations import (
    StructuralMemoryRelation,
    validate_structural_memory_relation_kinds,
)
from app.core.ports.db.memory_repositories import IExperiencesRepo
from app.infrastructure.db.runtime.models.experiences import (
    structural_memory_relations,
)
from app.infrastructure.db.runtime.models.memories import memories


class ExperiencesRepo(IExperiencesRepo):
    """Persistence operations for canonical structural memory relations."""

    def __init__(self, session) -> None:
        """This method stores the active DB session for repository operations."""

        self._session = session

    def upsert_structural_memory_relation(
        self, relation: StructuralMemoryRelation
    ) -> StructuralMemoryRelation:
        """Insert or return one canonical structural memory relation."""

        self._validate_structural_relation_shape(relation)
        now = datetime.now(timezone.utc)
        self._session.execute(
            insert(structural_memory_relations)
            .values(
                id=relation.id,
                repo_id=relation.repo_id,
                subject_memory_id=relation.subject_memory_id,
                predicate=relation.predicate.value,
                object_memory_id=relation.object_memory_id,
                status=relation.status.value,
                confidence=relation.confidence,
                observed_at=relation.observed_at,
                validated_at=relation.validated_at,
                invalidated_at=relation.invalidated_at,
                superseded_by_id=relation.superseded_by_id,
                created_by=relation.created_by.value,
                created_at=relation.created_at or now,
                updated_at=relation.updated_at or now,
            )
            .on_conflict_do_nothing(
                index_elements=[
                    "repo_id",
                    "subject_memory_id",
                    "predicate",
                    "object_memory_id",
                ]
            )
        )
        row = (
            self._session.execute(
                select(structural_memory_relations).where(
                    structural_memory_relations.c.repo_id == relation.repo_id,
                    structural_memory_relations.c.subject_memory_id
                    == relation.subject_memory_id,
                    structural_memory_relations.c.predicate == relation.predicate.value,
                    structural_memory_relations.c.object_memory_id
                    == relation.object_memory_id,
                )
            )
            .mappings()
            .one()
        )
        return _structural_relation_from_row(row)

    def _validated_relation_endpoints(
        self, relation: StructuralMemoryRelation
    ) -> "_RelationEndpoints":
        subject = self._load_memory_endpoint(relation.subject_memory_id)
        if subject is None:
            raise LookupError(
                f"structural relation subject not found: {relation.subject_memory_id}"
            )
        obj = self._load_memory_endpoint(relation.object_memory_id)
        if obj is None:
            raise LookupError(
                f"structural relation object not found: {relation.object_memory_id}"
            )
        if subject.repo_id != relation.repo_id or obj.repo_id != relation.repo_id:
            raise ValueError("structural relation memories must belong to repo_id")
        return _RelationEndpoints(
            subject_kind=subject.kind,
            object_kind=obj.kind,
        )

    def _validate_structural_relation_shape(
        self, relation: StructuralMemoryRelation
    ) -> None:
        endpoints = self._validated_relation_endpoints(relation)
        validate_structural_memory_relation_kinds(
            predicate=relation.predicate,
            subject_kind=endpoints.subject_kind,
            object_kind=endpoints.object_kind,
        )

    def _load_memory_endpoint(self, memory_id: str) -> "_MemoryEndpoint | None":
        row = (
            self._session.execute(
                select(memories.c.repo_id, memories.c.kind).where(
                    memories.c.id == memory_id
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            return None
        return _MemoryEndpoint(
            repo_id=str(row["repo_id"]),
            kind=MemoryKind(str(row["kind"])),
        )


@dataclass(frozen=True)
class _MemoryEndpoint:
    repo_id: str
    kind: MemoryKind


@dataclass(frozen=True)
class _RelationEndpoints:
    subject_kind: MemoryKind
    object_kind: MemoryKind


def _structural_relation_from_row(row) -> StructuralMemoryRelation:
    return StructuralMemoryRelation(
        id=row["id"],
        repo_id=row["repo_id"],
        subject_memory_id=row["subject_memory_id"],
        predicate=row["predicate"],
        object_memory_id=row["object_memory_id"],
        status=MemoryLifecycleStatus(row["status"]),
        confidence=row["confidence"],
        observed_at=row["observed_at"],
        validated_at=row["validated_at"],
        invalidated_at=row["invalidated_at"],
        superseded_by_id=row["superseded_by_id"],
        created_by=MemoryLifecycleActor(row["created_by"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
