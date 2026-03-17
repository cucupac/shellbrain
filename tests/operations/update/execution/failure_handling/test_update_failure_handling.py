"""Failure-handling contracts for update execution."""

from collections.abc import Callable

import pytest

from shellbrain.core.contracts.requests import MemoryUpdateRequest
from shellbrain.core.entities.memory import MemoryKind, MemoryScope
from shellbrain.core.use_cases.update_memory import execute_update_memory
from shellbrain.periphery.db.uow import PostgresUnitOfWork


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
) -> MemoryUpdateRequest:
    """Build a valid update request with caller-provided payload."""

    return MemoryUpdateRequest.model_validate(
        {
            "op": "update",
            "repo_id": repo_id,
            "memory_id": memory_id,
            "update": update,
        }
    )


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


def _raise_edge_evidence_failure(edge_id: str, evidence_id: str) -> None:
    """Raise a deterministic failure while linking association edge evidence."""

    _ = (edge_id, evidence_id)
    raise RuntimeError("edge evidence persistence failed")
