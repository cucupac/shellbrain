"""This module defines relational repository operations for shellbrain aggregates."""

from datetime import datetime, timezone
from typing import Sequence

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert

from app.core.entities.memories import (
    Memory,
    MemoryKind,
    MemoryLifecycleActor,
    MemoryLifecycleEvent,
    MemoryLifecycleStatus,
    MemoryScope,
)
from app.core.ports.db.memory_repositories import IMemoriesRepo
from app.infrastructure.db.runtime.models.memories import (
    memories,
    memory_embeddings,
    memory_lifecycle_events,
)


class MemoriesRepo(IMemoriesRepo):
    """This class provides relational persistence operations for memories."""

    def __init__(self, session) -> None:
        """This method stores the active DB session for repository operations."""

        self._session = session

    def create(self, memory: Memory) -> None:
        """This method persists a shellbrain record into relational storage."""

        self._session.execute(
            memories.insert().values(
                id=memory.id,
                repo_id=memory.repo_id,
                scope=memory.scope.value,
                kind=memory.kind.value,
                text=memory.text,
                created_at=memory.created_at or datetime.now(timezone.utc),
                status=memory.status.value,
                validated_at=memory.validated_at,
                invalidated_at=memory.invalidated_at,
                superseded_by_id=memory.superseded_by_id,
                updated_by=memory.updated_by.value if memory.updated_by else None,
            )
        )

    def get(self, memory_id: str) -> Memory | None:
        """This method loads a shellbrain record by identifier."""

        row = (
            self._session.execute(select(memories).where(memories.c.id == memory_id))
            .mappings()
            .first()
        )
        if row is None:
            return None
        return self._to_memory(row)

    def list_by_ids(self, ids: Sequence[str]) -> Sequence[Memory]:
        """This method loads visible shellbrain records in the caller's identifier order."""

        unique_ids = list(dict.fromkeys(str(memory_id) for memory_id in ids))
        if not unique_ids:
            return []
        rows = (
            self._session.execute(select(memories).where(memories.c.id.in_(unique_ids)))
            .mappings()
            .all()
        )
        memories_by_id = {str(row["id"]): self._to_memory(row) for row in rows}
        return [
            memories_by_id[memory_id]
            for memory_id in unique_ids
            if memory_id in memories_by_id
        ]

    def list_recent(
        self, *, repo_id: str, statuses: Sequence[str], limit: int
    ) -> Sequence[Memory]:
        """Load recent memories for one repository in newest-first order."""

        if limit <= 0:
            return []
        status_values = tuple(str(status) for status in statuses)
        if not status_values:
            return []
        rows = (
            self._session.execute(
                select(memories)
                .where(memories.c.repo_id == repo_id)
                .where(memories.c.status.in_(status_values))
                .order_by(memories.c.created_at.desc(), memories.c.id.asc())
                .limit(limit)
            )
            .mappings()
            .all()
        )
        return [self._to_memory(row) for row in rows]

    def _to_memory(self, row) -> Memory:
        """Convert one relational row into the canonical shellbrain entity."""

        return Memory(
            id=row["id"],
            repo_id=row["repo_id"],
            scope=MemoryScope(row["scope"]),
            kind=MemoryKind(row["kind"]),
            text=row["text"],
            created_at=row["created_at"],
            status=MemoryLifecycleStatus(row["status"]),
            validated_at=row["validated_at"],
            invalidated_at=row["invalidated_at"],
            superseded_by_id=row["superseded_by_id"],
            updated_by=MemoryLifecycleActor(row["updated_by"])
            if row["updated_by"] is not None
            else None,
        )

    def update_lifecycle(self, memory: Memory) -> bool:
        """Update lifecycle fields for one concrete memory."""

        result = self._session.execute(
            update(memories)
            .where(memories.c.id == memory.id)
            .values(
                status=memory.status.value,
                validated_at=memory.validated_at,
                invalidated_at=memory.invalidated_at,
                superseded_by_id=memory.superseded_by_id,
                updated_by=memory.updated_by.value if memory.updated_by else None,
            )
        )
        return bool(result.rowcount)

    def add_lifecycle_event(
        self, event: MemoryLifecycleEvent
    ) -> MemoryLifecycleEvent:
        """Append one auditable concrete memory lifecycle transition."""

        self._session.execute(
            memory_lifecycle_events.insert().values(
                id=event.id,
                repo_id=event.repo_id,
                memory_id=event.memory_id,
                from_status=event.from_status.value,
                to_status=event.to_status.value,
                rationale=event.rationale,
                actor=event.actor.value,
                superseded_by_id=event.superseded_by_id,
                created_at=event.created_at or datetime.now(timezone.utc),
            )
        )
        return event

    def upsert_embedding(
        self, *, memory_id: str, model: str, vector: Sequence[float]
    ) -> None:
        """This method inserts or updates the embedding vector for the target memory."""

        self._session.execute(
            insert(memory_embeddings)
            .values(
                memory_id=memory_id,
                model=model,
                dim=len(vector),
                vector=list(vector),
                created_at=datetime.now(timezone.utc),
            )
            .on_conflict_do_update(
                index_elements=["memory_id"],
                set_={
                    "model": model,
                    "dim": len(vector),
                    "vector": list(vector),
                    "created_at": datetime.now(timezone.utc),
                },
            )
        )
