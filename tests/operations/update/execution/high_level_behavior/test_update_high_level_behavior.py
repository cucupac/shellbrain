"""High-level behavior contracts for update execution."""

from collections.abc import Callable

from app.core.entities.memories import MemoryKind, MemoryScope
from app.core.use_cases.memories.update import execute_update_memory
from tests.operations._shared.id_generators import SequenceIdGenerator
from app.infrastructure.db.runtime.models.memories import memories
from app.infrastructure.db.runtime.uow import PostgresUnitOfWork
from tests.operations.update._execution_helpers import (
    make_update_request,
    snapshot_related_update_counts,
)


def test_update_archiving_changes_only_archived_flag(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_memory: Callable[..., object],
    count_rows: Callable[[str], int],
    fetch_rows: Callable[..., list[dict[str, object]]],
) -> None:
    """archiving a shellbrain should always change only its archived flag."""

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
        update={"type": "archive_state", "archived": True},
    )

    with uow_factory() as uow:
        execute_update_memory(request, uow, id_generator=SequenceIdGenerator())

    after_row = _fetch_memory_row(fetch_rows, "memory-1")
    assert before_row["archived"] is False
    assert after_row["archived"] is True

    comparable_before = dict(before_row)
    comparable_after = dict(after_row)
    comparable_before.pop("archived")
    comparable_after.pop("archived")
    assert comparable_after == comparable_before
    assert snapshot_related_update_counts(count_rows) == before_counts


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
