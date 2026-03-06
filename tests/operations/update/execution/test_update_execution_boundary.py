"""Execution contracts for the top-level update operation."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from app.core.contracts.requests import MemoryUpdateRequest
from app.core.entities.memory import MemoryKind, MemoryScope
from app.core.use_cases.update_memory import execute_update_memory
from app.periphery.db.models.associations import association_edge_evidence, association_edges, association_observations
from app.periphery.db.models.evidence import evidence_refs
from app.periphery.db.models.experiences import fact_updates
from app.periphery.db.models.memories import memories, memory_embeddings
from app.periphery.db.models.utility import utility_observations
from app.periphery.db.uow import PostgresUnitOfWork


def test_update_preview_only_describes_writes_and_makes_no_writes(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_memory: Callable[..., object],
    count_rows: Callable[[str], int],
) -> None:
    """preview-only updates should always describe the writes they would make and then make no writes."""

    seed_memory(
        memory_id="memory-1",
        repo_id="repo-a",
        scope=MemoryScope.REPO,
        kind=MemoryKind.FACT,
        text_value="Preview-only target memory.",
    )
    before = _snapshot_update_counts(count_rows)
    request = _make_update_request(
        repo_id="repo-a",
        memory_id="memory-1",
        mode="dry_run",
        update={"type": "archive_state", "archived": True},
    )

    with uow_factory() as uow:
        result = execute_update_memory(request, uow)

    assert result.status == "ok"
    assert result.data["accepted"] is True
    assert len(result.data["planned_side_effects"]) == 1
    assert result.data["planned_side_effects"][0]["effect_type"] == "memory.archive_state"
    assert _snapshot_update_counts(count_rows) == before


def test_update_archiving_changes_only_archived_flag(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_memory: Callable[..., object],
    count_rows: Callable[[str], int],
    fetch_rows: Callable[..., list[dict[str, object]]],
) -> None:
    """archiving a memory should always change only its archived flag."""

    seed_memory(
        memory_id="memory-1",
        repo_id="repo-a",
        scope=MemoryScope.REPO,
        kind=MemoryKind.FACT,
        text_value="Archive candidate.",
        confidence=0.33,
    )
    before_row = _fetch_memory_row(fetch_rows, "memory-1")
    before_counts = _snapshot_related_update_counts(count_rows)
    request = _make_update_request(
        repo_id="repo-a",
        memory_id="memory-1",
        update={"type": "archive_state", "archived": True},
    )

    with uow_factory() as uow:
        result = execute_update_memory(request, uow)

    after_row = _fetch_memory_row(fetch_rows, "memory-1")
    assert result.status == "ok"
    assert before_row["archived"] is False
    assert after_row["archived"] is True

    comparable_before = dict(before_row)
    comparable_after = dict(after_row)
    comparable_before.pop("archived")
    comparable_after.pop("archived")
    assert comparable_after == comparable_before
    assert _snapshot_related_update_counts(count_rows) == before_counts


@pytest.mark.parametrize(
    ("case_name", "target_kind", "target_id", "update_payload", "extra_seed"),
    [
        (
            "utility_vote",
            MemoryKind.FACT,
            "target-memory",
            {
                "type": "utility_vote",
                "problem_id": "problem-1",
                "vote": 0.7,
                "rationale": "Useful in this problem.",
            },
            lambda seed_memory: seed_memory(
                memory_id="problem-1",
                repo_id="repo-a",
                scope=MemoryScope.REPO,
                kind=MemoryKind.PROBLEM,
                text_value="Problem context.",
            ),
        ),
        (
            "fact_update_link",
            MemoryKind.CHANGE,
            "change-1",
            {
                "type": "fact_update_link",
                "old_fact_id": "old-fact-1",
                "new_fact_id": "new-fact-1",
            },
            lambda seed_memory: (
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
            "association_link",
            MemoryKind.FACT,
            "source-memory",
            {
                "type": "association_link",
                "to_memory_id": "target-memory",
                "relation_type": "depends_on",
                "confidence": 0.9,
                "salience": 0.8,
                "evidence_refs": ["session://1"],
            },
            lambda seed_memory: seed_memory(
                memory_id="target-memory",
                repo_id="repo-a",
                scope=MemoryScope.REPO,
                kind=MemoryKind.FACT,
                text_value="Association target.",
            ),
        ),
    ],
    ids=["utility_vote", "fact_update_link", "association_link"],
)
def test_update_non_archiving_preserves_original_memory_row(
    case_name: str,
    target_kind: MemoryKind,
    target_id: str,
    update_payload: dict[str, object],
    extra_seed: Callable[[Callable[..., object]], object],
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_memory: Callable[..., object],
    count_rows: Callable[[str], int],
    fetch_rows: Callable[..., list[dict[str, object]]],
) -> None:
    """non-archiving updates should always leave the original memory row unchanged."""

    _ = case_name
    seed_memory(
        memory_id=target_id,
        repo_id="repo-a",
        scope=MemoryScope.REPO,
        kind=target_kind,
        text_value="Unchanged target memory.",
        confidence=0.42,
    )
    extra_seed(seed_memory)
    before_row = _fetch_memory_row(fetch_rows, target_id)
    before_memory_count = count_rows("memories")
    before_embedding_count = count_rows("memory_embeddings")
    request = _make_update_request(repo_id="repo-a", memory_id=target_id, update=update_payload)

    with uow_factory() as uow:
        result = execute_update_memory(request, uow)

    after_row = _fetch_memory_row(fetch_rows, target_id)
    assert result.status == "ok"
    assert after_row == before_row
    assert count_rows("memories") == before_memory_count
    assert count_rows("memory_embeddings") == before_embedding_count


@pytest.mark.parametrize(
    ("case_name", "target_id", "update_payload", "extra_seed", "expected_deltas"),
    [
        (
            "utility_vote",
            "target-memory",
            {
                "type": "utility_vote",
                "problem_id": "problem-1",
                "vote": 0.7,
            },
            lambda seed_memory: (
                seed_memory(
                    memory_id="target-memory",
                    repo_id="repo-a",
                    scope=MemoryScope.REPO,
                    kind=MemoryKind.FACT,
                    text_value="Utility target.",
                ),
                seed_memory(
                    memory_id="problem-1",
                    repo_id="repo-a",
                    scope=MemoryScope.REPO,
                    kind=MemoryKind.PROBLEM,
                    text_value="Problem context.",
                ),
            ),
            {
                "utility_observations": 1,
                "fact_updates": 0,
                "association_edges": 0,
                "association_observations": 0,
                "association_edge_evidence": 0,
                "evidence_refs": 0,
            },
        ),
        (
            "fact_update_link",
            "change-1",
            {
                "type": "fact_update_link",
                "old_fact_id": "old-fact-1",
                "new_fact_id": "new-fact-1",
            },
            lambda seed_memory: (
                seed_memory(
                    memory_id="change-1",
                    repo_id="repo-a",
                    scope=MemoryScope.REPO,
                    kind=MemoryKind.CHANGE,
                    text_value="Change memory.",
                ),
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
            {
                "utility_observations": 0,
                "fact_updates": 1,
                "association_edges": 0,
                "association_observations": 0,
                "association_edge_evidence": 0,
                "evidence_refs": 0,
            },
        ),
        (
            "association_link",
            "source-memory",
            {
                "type": "association_link",
                "to_memory_id": "target-memory",
                "relation_type": "depends_on",
                "confidence": 0.9,
                "salience": 0.8,
                "evidence_refs": ["session://1"],
            },
            lambda seed_memory: (
                seed_memory(
                    memory_id="source-memory",
                    repo_id="repo-a",
                    scope=MemoryScope.REPO,
                    kind=MemoryKind.FACT,
                    text_value="Association source.",
                ),
                seed_memory(
                    memory_id="target-memory",
                    repo_id="repo-a",
                    scope=MemoryScope.REPO,
                    kind=MemoryKind.FACT,
                    text_value="Association target.",
                ),
            ),
            {
                "utility_observations": 0,
                "fact_updates": 0,
                "association_edges": 1,
                "association_observations": 1,
                "association_edge_evidence": 1,
                "evidence_refs": 1,
            },
        ),
    ],
    ids=["utility_vote", "fact_update_link", "association_link"],
)
def test_update_writes_only_its_own_related_record_family(
    case_name: str,
    target_id: str,
    update_payload: dict[str, object],
    extra_seed: Callable[[Callable[..., object]], object],
    expected_deltas: dict[str, int],
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_memory: Callable[..., object],
    count_rows: Callable[[str], int],
) -> None:
    """each update type should always write only its own kind of related record."""

    _ = case_name
    extra_seed(seed_memory)
    before_counts = _snapshot_related_update_counts(count_rows)
    request = _make_update_request(repo_id="repo-a", memory_id=target_id, update=update_payload)

    with uow_factory() as uow:
        result = execute_update_memory(request, uow)

    after_counts = _snapshot_related_update_counts(count_rows)
    assert result.status == "ok"
    assert _count_deltas(before_counts, after_counts) == expected_deltas


def test_update_failure_rolls_back_every_partial_write(
    monkeypatch: pytest.MonkeyPatch,
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_memory: Callable[..., object],
    count_rows: Callable[[str], int],
) -> None:
    """failed update execution should always roll back every partial write."""

    seed_memory(
        memory_id="source-memory",
        repo_id="repo-a",
        scope=MemoryScope.REPO,
        kind=MemoryKind.FACT,
        text_value="Association source.",
    )
    seed_memory(
        memory_id="target-memory",
        repo_id="repo-a",
        scope=MemoryScope.REPO,
        kind=MemoryKind.FACT,
        text_value="Association target.",
    )
    before_counts = _snapshot_related_update_counts(count_rows)
    request = _make_update_request(
        repo_id="repo-a",
        memory_id="source-memory",
        update={
            "type": "association_link",
            "to_memory_id": "target-memory",
            "relation_type": "depends_on",
            "confidence": 0.9,
            "salience": 0.8,
            "evidence_refs": ["session://1"],
        },
    )

    with pytest.raises(RuntimeError, match="edge evidence persistence failed"):
        with uow_factory() as uow:
            monkeypatch.setattr(
                uow.evidence,
                "link_association_edge_evidence",
                _raise_edge_evidence_failure,
            )
            execute_update_memory(request, uow)

    after_counts = _snapshot_related_update_counts(count_rows)
    assert after_counts == before_counts


def _make_update_request(
    *,
    repo_id: str,
    memory_id: str,
    update: dict[str, object],
    mode: str = "commit",
) -> MemoryUpdateRequest:
    """Build a valid update request with caller-provided payload."""

    return MemoryUpdateRequest.model_validate(
        {
            "op": "update",
            "repo_id": repo_id,
            "memory_id": memory_id,
            "mode": mode,
            "update": update,
        }
    )


def _fetch_memory_row(
    fetch_rows: Callable[..., list[dict[str, object]]],
    memory_id: str,
) -> dict[str, object]:
    """Return one memory row as a plain dictionary."""

    rows = fetch_rows(memories, memories.c.id == memory_id)
    assert len(rows) == 1
    return rows[0]


def _snapshot_update_counts(count_rows: Callable[[str], int]) -> dict[str, int]:
    """Capture counts for all tables update execution may touch."""

    return {
        "memories": count_rows("memories"),
        "memory_embeddings": count_rows("memory_embeddings"),
        "utility_observations": count_rows("utility_observations"),
        "fact_updates": count_rows("fact_updates"),
        "association_edges": count_rows("association_edges"),
        "association_observations": count_rows("association_observations"),
        "association_edge_evidence": count_rows("association_edge_evidence"),
        "evidence_refs": count_rows("evidence_refs"),
    }


def _snapshot_related_update_counts(count_rows: Callable[[str], int]) -> dict[str, int]:
    """Capture counts for the related-record tables written by non-archive updates."""

    return {
        "utility_observations": count_rows("utility_observations"),
        "fact_updates": count_rows("fact_updates"),
        "association_edges": count_rows("association_edges"),
        "association_observations": count_rows("association_observations"),
        "association_edge_evidence": count_rows("association_edge_evidence"),
        "evidence_refs": count_rows("evidence_refs"),
    }


def _count_deltas(before: dict[str, int], after: dict[str, int]) -> dict[str, int]:
    """Compute per-table count deltas between two snapshots."""

    return {table_name: after[table_name] - before[table_name] for table_name in before}


def _raise_edge_evidence_failure(edge_id: str, evidence_id: str) -> None:
    """Raise a deterministic failure while linking association edge evidence."""

    _ = (edge_id, evidence_id)
    raise RuntimeError("edge evidence persistence failed")
