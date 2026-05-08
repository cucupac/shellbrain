"""Record-write contracts for update execution."""

from collections.abc import Callable

from app.core.entities.memory import MemoryKind, MemoryScope
from app.core.use_cases.memories.update_memory import execute_update_memory
from app.infrastructure.db.models.associations import association_edge_evidence, association_edges, association_observations
from app.infrastructure.db.models.experiences import fact_updates
from app.infrastructure.db.models.utility import utility_observations
from app.infrastructure.db.uow import PostgresUnitOfWork
from tests.operations.update._execution_helpers import make_update_request, snapshot_related_update_counts


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
    request = make_update_request(
        repo_id="repo-a",
        memory_id="target-memory",
        update={
            "type": "utility_vote",
            "problem_id": "problem-1",
            "vote": 0.7,
            "rationale": "Worked well for this problem.",
        },
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
    request = make_update_request(
        repo_id="repo-a",
        memory_id="change-1",
        update={
            "type": "fact_update_link",
            "old_fact_id": "old-fact",
            "new_fact_id": "new-fact",
        },
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
    request = make_update_request(
        repo_id="repo-a",
        memory_id="source-memory",
        update={
            "type": "association_link",
            "to_memory_id": "target-memory",
            "relation_type": "depends_on",
            "confidence": 0.9,
            "salience": 0.8,
            "evidence_refs": ["session://1", "session://2"],
        },
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


def test_update_matures_into_commit_persists_edge_observation_and_edge_evidence(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_memory: Callable[..., object],
    fetch_rows: Callable[..., list[dict[str, object]]],
) -> None:
    """update(matures_into) commit should always persist edge, observation, and edge evidence links."""

    seed_memory(
        memory_id="frontier-memory",
        repo_id="repo-a",
        scope=MemoryScope.REPO,
        kind=MemoryKind.FRONTIER,
        text_value="Half-formed theory.",
    )
    seed_memory(
        memory_id="mature-memory",
        repo_id="repo-a",
        scope=MemoryScope.REPO,
        kind=MemoryKind.FACT,
        text_value="Ratified fact.",
    )
    request = make_update_request(
        repo_id="repo-a",
        memory_id="frontier-memory",
        update={
            "type": "association_link",
            "to_memory_id": "mature-memory",
            "relation_type": "matures_into",
            "confidence": 0.9,
            "salience": 0.8,
            "evidence_refs": ["session://1", "session://2"],
        },
    )

    with uow_factory() as uow:
        result = execute_update_memory(request, uow)

    assert result.status == "ok"
    edges = fetch_rows(
        association_edges,
        association_edges.c.repo_id == "repo-a",
        association_edges.c.from_memory_id == "frontier-memory",
        association_edges.c.to_memory_id == "mature-memory",
        association_edges.c.relation_type == "matures_into",
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


def test_update_writes_only_its_own_related_record_family(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_memory: Callable[..., object],
    count_rows: Callable[[str], int],
) -> None:
    """each update type should always write only its own kind of related record."""

    cases = [
        (
            "utility-target-memory",
            {
                "type": "utility_vote",
                "problem_id": "utility-problem-1",
                "vote": 0.7,
            },
            lambda: (
                seed_memory(
                    memory_id="utility-target-memory",
                    repo_id="repo-a",
                    scope=MemoryScope.REPO,
                    kind=MemoryKind.FACT,
                    text_value="Utility target.",
                ),
                seed_memory(
                    memory_id="utility-problem-1",
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
            "change-1",
            {
                "type": "fact_update_link",
                "old_fact_id": "old-fact-1",
                "new_fact_id": "new-fact-1",
            },
            lambda: (
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
            "association-source-memory",
            {
                "type": "association_link",
                "to_memory_id": "association-target-memory",
                "relation_type": "depends_on",
                "confidence": 0.9,
                "salience": 0.8,
                "evidence_refs": ["session://1"],
            },
            lambda: (
                seed_memory(
                    memory_id="association-source-memory",
                    repo_id="repo-a",
                    scope=MemoryScope.REPO,
                    kind=MemoryKind.FACT,
                    text_value="Association source.",
                ),
                seed_memory(
                    memory_id="association-target-memory",
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
    ]

    for target_id, update_payload, seed_case, expected_deltas in cases:
        seed_case()
        before_counts = snapshot_related_update_counts(count_rows)
        request = make_update_request(repo_id="repo-a", memory_id=target_id, update=update_payload)

        with uow_factory() as uow:
            result = execute_update_memory(request, uow)

        after_counts = snapshot_related_update_counts(count_rows)
        assert result.status == "ok"
        assert _count_deltas(before_counts, after_counts) == expected_deltas


def _count_deltas(before: dict[str, int], after: dict[str, int]) -> dict[str, int]:
    """Compute per-table count deltas between two snapshots."""

    return {table_name: after[table_name] - before[table_name] for table_name in before}
