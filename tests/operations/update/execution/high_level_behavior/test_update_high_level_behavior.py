"""High-level behavior contracts for update execution."""

from collections.abc import Callable
from datetime import datetime, timezone

from app.core.entities.memories import MemoryKind, MemoryScope
from app.core.ports.system.clock import IClock
from app.core.use_cases.memories.update import execute_update_memory
from tests.operations._shared.id_generators import SequenceIdGenerator
from app.infrastructure.db.runtime.models.evidence import evidence_links
from app.infrastructure.db.runtime.models.memories import memories
from app.infrastructure.db.runtime.models.memories import memory_lifecycle_events
from app.infrastructure.db.runtime.uow import PostgresUnitOfWork
from tests.operations.update._execution_helpers import (
    make_update_request,
    snapshot_related_update_counts,
)


class _FixedClock(IClock):
    def now(self) -> datetime:
        return datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)


def test_update_lifecycle_archives_memory_and_records_auditable_event(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_memory: Callable[..., object],
    count_rows: Callable[[str], int],
    fetch_rows: Callable[..., list[dict[str, object]]],
) -> None:
    """lifecycle updates should mutate status and append event evidence."""

    seed_memory(
        memory_id="memory-1",
        repo_id="repo-a",
        scope=MemoryScope.REPO,
        kind=MemoryKind.FACT,
        text_value="Archive candidate.",
    )
    before_row = _fetch_memory_row(fetch_rows, "memory-1")
    before_counts = snapshot_related_update_counts(count_rows)
    request = make_update_request(
        repo_id="repo-a",
        memory_id="memory-1",
        update={
            "type": "update_lifecycle",
            "status": "archived",
            "rationale": "Retired duplicate.",
            "actor": "manual",
            "evidence": [{"kind": "manual", "note": "Verified."}],
        },
    )

    with uow_factory() as uow:
        execute_update_memory(
            request,
            uow,
            id_generator=SequenceIdGenerator(),
            clock=_FixedClock(),
        )

    after_row = _fetch_memory_row(fetch_rows, "memory-1")
    assert before_row["status"] == "active"
    assert after_row["status"] == "archived"
    assert after_row["updated_by"] == "manual"
    assert after_row["validated_at"] is None
    assert after_row["invalidated_at"] is None

    comparable_before = dict(before_row)
    comparable_after = dict(after_row)
    for field in ("status", "updated_by"):
        comparable_before.pop(field)
        comparable_after.pop(field)
    assert comparable_after == comparable_before
    assert snapshot_related_update_counts(count_rows) == {
        **before_counts,
        "evidence_refs": before_counts["evidence_refs"] + 1,
        "evidence_links": before_counts["evidence_links"] + 1,
        "memory_lifecycle_events": before_counts["memory_lifecycle_events"] + 1,
    }
    events = fetch_rows(memory_lifecycle_events)
    assert events[0]["memory_id"] == "memory-1"
    assert events[0]["from_status"] == "active"
    assert events[0]["to_status"] == "archived"
    assert events[0]["rationale"] == "Retired duplicate."
    assert fetch_rows(
        evidence_links,
        evidence_links.c.target_type == "memory_lifecycle_event",
        evidence_links.c.target_id == events[0]["id"],
    )


def test_update_lifecycle_supersedes_memory_with_replacement(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_memory: Callable[..., object],
    fetch_rows: Callable[..., list[dict[str, object]]],
) -> None:
    """superseded lifecycle updates should persist replacement and invalidation time."""

    seed_memory(
        memory_id="old-fact",
        repo_id="repo-a",
        scope=MemoryScope.REPO,
        kind=MemoryKind.FACT,
        text_value="Old fact.",
    )
    seed_memory(
        memory_id="new-fact",
        repo_id="repo-a",
        scope=MemoryScope.REPO,
        kind=MemoryKind.FACT,
        text_value="New fact.",
    )
    request = make_update_request(
        repo_id="repo-a",
        memory_id="old-fact",
        update={
            "type": "update_lifecycle",
            "status": "superseded",
            "superseded_by_id": "new-fact",
            "rationale": "Replaced by newer fact.",
            "actor": "manual",
            "evidence": [{"kind": "manual", "note": "Verified replacement."}],
        },
    )

    with uow_factory() as uow:
        execute_update_memory(
            request,
            uow,
            id_generator=SequenceIdGenerator(),
            clock=_FixedClock(),
        )

    old_fact = _fetch_memory_row(fetch_rows, "old-fact")
    assert old_fact["status"] == "superseded"
    assert old_fact["superseded_by_id"] == "new-fact"
    assert old_fact["invalidated_at"] == _FixedClock().now()


def test_update_non_archiving_preserves_original_memory_row(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_memory: Callable[..., object],
    count_rows: Callable[[str], int],
    fetch_rows: Callable[..., list[dict[str, object]]],
) -> None:
    """non-archiving updates should always leave the original shellbrain row unchanged."""

    cases = [
        (
            MemoryKind.FACT,
            "utility-target-memory",
            {
                "type": "utility_vote",
                "problem_id": "utility-problem-1",
                "vote": 0.7,
                "rationale": "Useful in this problem.",
            },
            lambda: seed_memory(
                memory_id="utility-problem-1",
                repo_id="repo-a",
                scope=MemoryScope.REPO,
                kind=MemoryKind.PROBLEM,
                text_value="Problem context.",
            ),
        ),
        (
            MemoryKind.CHANGE,
            "change-1",
            {
                "type": "fact_update_link",
                "old_fact_id": "old-fact-1",
                "new_fact_id": "new-fact-1",
            },
            lambda: (
                seed_memory(
                    memory_id="old-fact-1",
                    repo_id="repo-a",
                    scope=MemoryScope.REPO,
                    kind=MemoryKind.FACT,
                    text_value="Old fact.",
                ),
                seed_memory(
                    memory_id="new-fact-1",
                    repo_id="repo-a",
                    scope=MemoryScope.REPO,
                    kind=MemoryKind.FACT,
                    text_value="New fact.",
                ),
            ),
        ),
        (
            MemoryKind.FACT,
            "association-source-memory",
            {
                "type": "association_link",
                "to_memory_id": "association-target-memory",
                "relation_type": "depends_on",
                "confidence": 0.9,
                "salience": 0.8,
                "evidence_refs": ["session://1"],
            },
            lambda: seed_memory(
                memory_id="association-target-memory",
                repo_id="repo-a",
                scope=MemoryScope.REPO,
                kind=MemoryKind.FACT,
                text_value="Association target.",
            ),
        ),
    ]

    for target_kind, target_id, update_payload, extra_seed in cases:
        seed_memory(
            memory_id=target_id,
            repo_id="repo-a",
            scope=MemoryScope.REPO,
            kind=target_kind,
            text_value="Unchanged target memory.",
        )
        extra_seed()
        before_row = _fetch_memory_row(fetch_rows, target_id)
        before_memory_count = count_rows("memories")
        before_embedding_count = count_rows("memory_embeddings")
        request = make_update_request(
            repo_id="repo-a", memory_id=target_id, update=update_payload
        )

        with uow_factory() as uow:
            execute_update_memory(request, uow, id_generator=SequenceIdGenerator())

        after_row = _fetch_memory_row(fetch_rows, target_id)
        assert after_row == before_row
        assert count_rows("memories") == before_memory_count
        assert count_rows("memory_embeddings") == before_embedding_count


def _fetch_memory_row(
    fetch_rows: Callable[..., list[dict[str, object]]],
    memory_id: str,
) -> dict[str, object]:
    """Return one shellbrain row as a plain dictionary."""

    rows = fetch_rows(memories, memories.c.id == memory_id)
    assert len(rows) == 1
    return rows[0]
