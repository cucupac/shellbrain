"""Update execution contracts for write-path side effects."""

from collections.abc import Callable

from app.core.contracts.requests import MemoryUpdateRequest
from app.core.entities.memory import MemoryKind, MemoryScope
from app.core.use_cases.update_memory import execute_update_memory
from app.periphery.db.models.associations import association_edge_evidence, association_edges, association_observations
from app.periphery.db.models.experiences import fact_updates
from app.periphery.db.models.memories import memories
from app.periphery.db.models.utility import utility_observations
from app.periphery.db.uow import PostgresUnitOfWork


def test_update_archive_state_commit_modifies_only_archived_state(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_memory: Callable[..., object],
    count_rows: Callable[[str], int],
    fetch_rows: Callable[..., list[dict[str, object]]],
) -> None:
    """update(archive_state) commit should always change archived state and preserve other memory fields."""

    seed_memory(
        memory_id="memory-1",
        repo_id="repo-a",
        scope=MemoryScope.REPO,
        kind=MemoryKind.FACT,
        text_value="Archive candidate.",
        confidence=0.33,
    )
    request = MemoryUpdateRequest.model_validate(
        {
            "op": "update",
            "repo_id": "repo-a",
            "memory_id": "memory-1",
            "mode": "commit",
            "update": {"type": "archive_state", "archived": True},
        }
    )

    with uow_factory() as uow:
        result = execute_update_memory(request, uow)

    assert result.status == "ok"
    rows = fetch_rows(memories, memories.c.id == "memory-1")
    assert len(rows) == 1
    assert rows[0]["archived"] is True
    assert rows[0]["text"] == "Archive candidate."
    assert float(rows[0]["create_confidence"]) == 0.33
    assert count_rows("utility_observations") == 0
    assert count_rows("fact_updates") == 0
    assert count_rows("association_edges") == 0
    assert count_rows("association_observations") == 0


def test_update_utility_vote_commit_appends_observation_with_exact_payload(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_memory: Callable[..., object],
    fetch_rows: Callable[..., list[dict[str, object]]],
) -> None:
    """update(utility_vote) commit should always append one utility_observation with the provided payload."""

    seed_memory(
        memory_id="target-memory",
        repo_id="repo-a",
        scope=MemoryScope.REPO,
        kind=MemoryKind.FACT,
        text_value="Target memory.",
    )
    seed_memory(
        memory_id="problem-1",
        repo_id="repo-a",
        scope=MemoryScope.REPO,
        kind=MemoryKind.PROBLEM,
        text_value="Problem memory.",
    )
    request = MemoryUpdateRequest.model_validate(
        {
            "op": "update",
            "repo_id": "repo-a",
            "memory_id": "target-memory",
            "mode": "commit",
            "update": {
                "type": "utility_vote",
                "problem_id": "problem-1",
                "vote": 0.7,
                "rationale": "Worked well for this problem.",
            },
        }
    )

    with uow_factory() as uow:
        result = execute_update_memory(request, uow)

    assert result.status == "ok"
    rows = fetch_rows(
        utility_observations,
        utility_observations.c.memory_id == "target-memory",
        utility_observations.c.problem_id == "problem-1",
    )
    assert len(rows) == 1
    assert float(rows[0]["vote"]) == 0.7
    assert rows[0]["rationale"] == "Worked well for this problem."


def test_update_fact_update_link_commit_appends_fact_update_with_change_id(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_memory: Callable[..., object],
    fetch_rows: Callable[..., list[dict[str, object]]],
) -> None:
    """update(fact_update_link) commit should always append one fact_update with change_id equal to memory_id."""

    seed_memory(
        memory_id="change-1",
        repo_id="repo-a",
        scope=MemoryScope.REPO,
        kind=MemoryKind.CHANGE,
        text_value="Change memory.",
    )
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
    request = MemoryUpdateRequest.model_validate(
        {
            "op": "update",
            "repo_id": "repo-a",
            "memory_id": "change-1",
            "mode": "commit",
            "update": {
                "type": "fact_update_link",
                "old_fact_id": "old-fact",
                "new_fact_id": "new-fact",
            },
        }
    )

    with uow_factory() as uow:
        result = execute_update_memory(request, uow)

    assert result.status == "ok"
    rows = fetch_rows(fact_updates, fact_updates.c.change_id == "change-1")
    assert len(rows) == 1
    assert rows[0]["old_fact_id"] == "old-fact"
    assert rows[0]["new_fact_id"] == "new-fact"
    assert rows[0]["change_id"] == "change-1"


def test_update_association_link_commit_persists_edge_observation_and_edge_evidence(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_memory: Callable[..., object],
    fetch_rows: Callable[..., list[dict[str, object]]],
) -> None:
    """update(association_link) commit should always persist edge, observation, and edge evidence links."""

    seed_memory(
        memory_id="source-memory",
        repo_id="repo-a",
        scope=MemoryScope.REPO,
        kind=MemoryKind.FACT,
        text_value="Source memory.",
    )
    seed_memory(
        memory_id="target-memory",
        repo_id="repo-a",
        scope=MemoryScope.REPO,
        kind=MemoryKind.FACT,
        text_value="Target memory.",
    )
    request = MemoryUpdateRequest.model_validate(
        {
            "op": "update",
            "repo_id": "repo-a",
            "memory_id": "source-memory",
            "mode": "commit",
            "update": {
                "type": "association_link",
                "to_memory_id": "target-memory",
                "relation_type": "depends_on",
                "confidence": 0.9,
                "salience": 0.8,
                "evidence_refs": ["session://1", "session://2"],
            },
        }
    )

    with uow_factory() as uow:
        result = execute_update_memory(request, uow)

    assert result.status == "ok"
    edges = fetch_rows(
        association_edges,
        association_edges.c.repo_id == "repo-a",
        association_edges.c.from_memory_id == "source-memory",
        association_edges.c.to_memory_id == "target-memory",
        association_edges.c.relation_type == "depends_on",
    )
    assert len(edges) == 1

    edge_id = edges[0]["id"]
    observations = fetch_rows(
        association_observations,
        association_observations.c.edge_id == edge_id,
    )
    assert len(observations) == 1

    edge_evidence_rows = fetch_rows(
        association_edge_evidence,
        association_edge_evidence.c.edge_id == edge_id,
    )
    assert len(edge_evidence_rows) == 2


def test_update_dry_run_returns_plan_and_writes_nothing(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_memory: Callable[..., object],
    count_rows: Callable[[str], int],
    fetch_rows: Callable[..., list[dict[str, object]]],
) -> None:
    """update(dry_run) should always return planned_side_effects and write nothing."""

    seed_memory(
        memory_id="memory-1",
        repo_id="repo-a",
        scope=MemoryScope.REPO,
        kind=MemoryKind.FACT,
        text_value="Dry run target.",
    )
    request = MemoryUpdateRequest.model_validate(
        {
            "op": "update",
            "repo_id": "repo-a",
            "memory_id": "memory-1",
            "mode": "dry_run",
            "update": {"type": "archive_state", "archived": True},
        }
    )

    with uow_factory() as uow:
        result = execute_update_memory(request, uow)

    assert result.status == "ok"
    assert result.data["accepted"] is True
    assert len(result.data["planned_side_effects"]) == 1
    assert result.data["planned_side_effects"][0]["effect_type"] == "memory.archive_state"

    memory_rows = fetch_rows(memories, memories.c.id == "memory-1")
    assert len(memory_rows) == 1
    assert memory_rows[0]["archived"] is False
    assert count_rows("utility_observations") == 0
    assert count_rows("fact_updates") == 0
    assert count_rows("association_edges") == 0
    assert count_rows("association_observations") == 0
