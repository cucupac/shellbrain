"""Failure-handling contracts for update execution."""

from collections.abc import Callable

import pytest

from app.core.entities.memories import MemoryKind, MemoryScope
from app.core.use_cases.memories.update import execute_update_memory
from tests.operations._shared.id_generators import SequenceIdGenerator
from app.infrastructure.db.uow import PostgresUnitOfWork
from tests.operations.update._execution_helpers import (
    make_update_request,
    snapshot_related_update_counts,
)


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
    before_counts = snapshot_related_update_counts(count_rows)
    request = make_update_request(
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
            execute_update_memory(request, uow, id_generator=SequenceIdGenerator())

    after_counts = snapshot_related_update_counts(count_rows)
    assert after_counts == before_counts


def _raise_edge_evidence_failure(edge_id: str, evidence_id: str) -> None:
    """Raise a deterministic failure while linking association edge evidence."""

    _ = (edge_id, evidence_id)
    raise RuntimeError("edge evidence persistence failed")
