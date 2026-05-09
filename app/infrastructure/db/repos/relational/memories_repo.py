"""This module defines relational repository operations for shellbrain aggregates."""

from datetime import datetime, timezone
from typing import Sequence

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert

from app.core.entities.memories import Memory, MemoryKind, MemoryScope
from app.core.ports.memory_repositories import IMemoriesRepo
from app.infrastructure.db.models.memories import memories, memory_embeddings


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
                created_at=datetime.now(timezone.utc),
                archived=memory.archived,
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

    def _to_memory(self, row) -> Memory:
        """Convert one relational row into the canonical shellbrain entity."""

        return Memory(
            id=row["id"],
            repo_id=row["repo_id"],
            scope=MemoryScope(row["scope"]),
            kind=MemoryKind(row["kind"]),
            text=row["text"],
            archived=row["archived"],
        )

    def set_archived(self, *, memory_id: str, archived: bool) -> bool:
        """This method updates the archived state for a shellbrain and returns whether a row changed."""

        result = self._session.execute(
            update(memories).where(memories.c.id == memory_id).values(archived=archived)
        )
        return bool(result.rowcount)

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
