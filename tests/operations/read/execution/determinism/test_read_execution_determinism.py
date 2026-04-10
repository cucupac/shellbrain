"""Read execution contracts for dedupe and deterministic ordering."""

from collections.abc import Callable

from app.core.use_cases.read_memory import execute_read_memory
from app.periphery.db.uow import PostgresUnitOfWork
from tests.operations.read._execution_helpers import item_ids, make_read_request


def test_read_deduplicates_memories_reached_by_multiple_paths(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_read_memory: Callable[..., None],
    seed_association_edge: Callable[..., None],
) -> None:
    """read should always return each shellbrain at most once even if reached by multiple paths."""

    seed_read_memory(
        memory_id="anchor-1",
        repo_id="repo-a",
        scope="repo",
        kind="fact",
        text_value="Deployment anchor that matches query directly.",
    )
    seed_read_memory(
        memory_id="dup-target",
        repo_id="repo-a",
        scope="repo",
        kind="fact",
        text_value="Deployment target that also matches query directly.",
    )
    seed_association_edge(
        edge_id="edge-1",
        repo_id="repo-a",
        from_memory_id="anchor-1",
        to_memory_id="dup-target",
        relation_type="associated_with",
        strength=0.8,
    )

    request = make_read_request(
        repo_id="repo-a",
        query="deployment",
        expand={
            "include_problem_links": False,
            "include_fact_update_links": False,
            "include_association_links": True,
            "min_association_strength": 0.25,
        },
    )
    with uow_factory() as uow:
        result = execute_read_memory(request, uow)

    ids = item_ids(result)
    assert "dup-target" in ids
    assert len(ids) == len(set(ids))


def test_read_produces_deterministic_ordering_on_unchanged_snapshot(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_read_memory: Callable[..., None],
) -> None:
    """read should always produce deterministic ordering for the same input and snapshot."""

    seed_read_memory(
        memory_id="memory-a",
        repo_id="repo-a",
        scope="repo",
        kind="problem",
        text_value="Deployment issue shellbrain A.",
    )
    seed_read_memory(
        memory_id="memory-b",
        repo_id="repo-a",
        scope="repo",
        kind="problem",
        text_value="Deployment issue shellbrain B.",
    )
    seed_read_memory(
        memory_id="memory-c",
        repo_id="repo-a",
        scope="repo",
        kind="problem",
        text_value="Deployment issue shellbrain C.",
    )

    request = make_read_request(repo_id="repo-a", query="deployment issue", limit=3)

    with uow_factory() as uow:
        first = execute_read_memory(request, uow)
    with uow_factory() as uow:
        second = execute_read_memory(request, uow)

    first_ids = item_ids(first)
    second_ids = item_ids(second)
    assert len(first_ids) >= 2
    assert first_ids == second_ids

