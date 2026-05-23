"""Record-write contracts for update execution."""

from collections.abc import Callable
from datetime import datetime, timezone

from app.core.entities.memories import MemoryKind, MemoryScope
from app.core.ports.system.clock import IClock
from app.core.use_cases.memories.update import execute_update_memory
from tests.operations._shared.id_generators import SequenceIdGenerator
from app.infrastructure.db.runtime.models.associations import (
    association_edges,
    association_observations,
)
from app.infrastructure.db.runtime.models.evidence import evidence_links
from app.infrastructure.db.runtime.models.experiences import structural_memory_relations
from app.infrastructure.db.runtime.models.utility import utility_observations
from app.infrastructure.db.runtime.uow import PostgresUnitOfWork
from tests.operations.update._execution_helpers import (
    make_update_request,
    snapshot_related_update_counts,
)


class _FixedClock(IClock):
    def now(self) -> datetime:
        return datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)


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
        execute_update_memory(request, uow, id_generator=SequenceIdGenerator())
    rows = fetch_rows(
        utility_observations,
        utility_observations.c.memory_id == "target-memory",
        utility_observations.c.problem_id == "problem-1",
    )
    assert len(rows) == 1
    assert float(rows[0]["vote"]) == 0.7
    assert rows[0]["rationale"] == "Worked well for this problem."


def test_update_fact_update_link_commit_appends_structural_relations(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_memory: Callable[..., object],
    fetch_rows: Callable[..., list[dict[str, object]]],
) -> None:
    """update(fact_update_link) should append canonical structural relations."""

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
            "evidence_refs": ["session://1"],
        },
    )

    with uow_factory() as uow:
        execute_update_memory(request, uow, id_generator=SequenceIdGenerator())
    relation_rows = fetch_rows(
        structural_memory_relations,
        structural_memory_relations.c.repo_id == "repo-a",
    )
    relation_shapes = {
        (
            str(row["subject_memory_id"]),
            str(row["predicate"]),
            str(row["object_memory_id"]),
        )
        for row in relation_rows
    }
    assert relation_shapes == {
        ("old-fact", "superseded_by", "new-fact"),
        ("old-fact", "explained_by_change", "change-1"),
        ("new-fact", "explained_by_change", "change-1"),
    }
    assert len(
        fetch_rows(
            evidence_links,
            evidence_links.c.target_type == "structural_memory_relation",
        )
    ) == 3


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
        execute_update_memory(request, uow, id_generator=SequenceIdGenerator())
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
        evidence_links,
        evidence_links.c.target_type == "association_edge",
        evidence_links.c.target_id == edge_id,
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
                "association_edges": 0,
                "association_observations": 0,
                "evidence_links": 0,
                "evidence_refs": 0,
                "memory_lifecycle_events": 0,
                "structural_memory_relations": 0,
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
                "association_edges": 0,
                "association_observations": 0,
                "evidence_links": 0,
                "evidence_refs": 0,
                "memory_lifecycle_events": 0,
                "structural_memory_relations": 3,
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
                "association_edges": 1,
                "association_observations": 1,
                "evidence_links": 1,
                "evidence_refs": 1,
                "memory_lifecycle_events": 0,
                "structural_memory_relations": 0,
            },
        ),
        (
            "lifecycle-memory",
            {
                "type": "update_lifecycle",
                "status": "wrong",
                "rationale": "Contradicted by later implementation.",
                "actor": "manual",
                "evidence": [{"kind": "manual", "note": "Verified."}],
            },
            lambda: seed_memory(
                memory_id="lifecycle-memory",
                repo_id="repo-a",
                scope=MemoryScope.REPO,
                kind=MemoryKind.FACT,
                text_value="Lifecycle target.",
            ),
            {
                "utility_observations": 0,
                "association_edges": 0,
                "association_observations": 0,
                "evidence_links": 1,
                "evidence_refs": 1,
                "memory_lifecycle_events": 1,
                "structural_memory_relations": 0,
            },
        ),
    ]

    for target_id, update_payload, seed_case, expected_deltas in cases:
        seed_case()
        before_counts = snapshot_related_update_counts(count_rows)
        request = make_update_request(
            repo_id="repo-a", memory_id=target_id, update=update_payload
        )

        with uow_factory() as uow:
            execute_update_memory(
                request,
                uow,
                id_generator=SequenceIdGenerator(),
                clock=_FixedClock(),
            )

        after_counts = snapshot_related_update_counts(count_rows)
        assert _count_deltas(before_counts, after_counts) == expected_deltas


def _count_deltas(before: dict[str, int], after: dict[str, int]) -> dict[str, int]:
    """Compute per-table count deltas between two snapshots."""

    return {table_name: after[table_name] - before[table_name] for table_name in before}
