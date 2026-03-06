"""Transaction contracts for update-path validation."""

from collections.abc import Callable

from app.core.contracts.requests import MemoryUpdateRequest
from app.core.entities.memory import MemoryKind, MemoryScope
from app.core.use_cases.update_memory import execute_update_memory
from app.periphery.db.uow import PostgresUnitOfWork


def test_rejected_update_requests_write_nothing(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_memory: Callable[..., object],
    count_rows: Callable[[str], int],
) -> None:
    """rejected update requests should always write nothing."""

    seed_memory(
        memory_id="source-memory",
        repo_id="repo-a",
        scope=MemoryScope.REPO,
        kind=MemoryKind.FACT,
        text_value="Source memory.",
    )
    seed_memory(
        memory_id="problem-hidden",
        repo_id="repo-b",
        scope=MemoryScope.REPO,
        kind=MemoryKind.PROBLEM,
        text_value="Hidden problem memory.",
    )

    before = _snapshot_update_tables(count_rows)

    semantic_failure_request = MemoryUpdateRequest.model_validate(
        {
            "op": "update",
            "repo_id": "repo-a",
            "memory_id": "source-memory",
            "mode": "commit",
            "update": {
                "type": "association_link",
                "to_memory_id": "source-memory",
                "relation_type": "depends_on",
                "evidence_refs": ["session://1"],
            },
        }
    )
    with uow_factory() as uow:
        semantic_failure_result = execute_update_memory(semantic_failure_request, uow)

    assert semantic_failure_result.status == "error"
    assert _snapshot_update_tables(count_rows) == before

    integrity_failure_request = MemoryUpdateRequest.model_validate(
        {
            "op": "update",
            "repo_id": "repo-a",
            "memory_id": "source-memory",
            "mode": "commit",
            "update": {
                "type": "utility_vote",
                "problem_id": "problem-hidden",
                "vote": 0.8,
            },
        }
    )
    with uow_factory() as uow:
        integrity_failure_result = execute_update_memory(integrity_failure_request, uow)

    assert integrity_failure_result.status == "error"
    assert _snapshot_update_tables(count_rows) == before


def _snapshot_update_tables(count_rows: Callable[[str], int]) -> dict[str, int]:
    """Capture row counts for tables that update operations are allowed to touch."""

    return {
        "memories": count_rows("memories"),
        "utility_observations": count_rows("utility_observations"),
        "fact_updates": count_rows("fact_updates"),
        "association_edges": count_rows("association_edges"),
        "association_observations": count_rows("association_observations"),
        "association_edge_evidence": count_rows("association_edge_evidence"),
        "evidence_refs": count_rows("evidence_refs"),
    }
