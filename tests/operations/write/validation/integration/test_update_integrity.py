"""Update integrity contracts for write-path validation."""

from collections.abc import Callable

from app.core.contracts.requests import MemoryUpdateRequest
from app.core.entities.memory import MemoryKind, MemoryScope
from app.core.use_cases.update_memory import execute_update_memory
from app.periphery.db.uow import PostgresUnitOfWork


def test_utility_vote_requires_visible_problem(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_memory: Callable[..., object],
) -> None:
    """utility_vote updates should always require a visible problem reference."""

    seed_memory(
        memory_id="target-memory",
        repo_id="repo-a",
        scope=MemoryScope.REPO,
        kind=MemoryKind.FACT,
        text_value="Target memory.",
    )
    seed_memory(
        memory_id="problem-hidden",
        repo_id="repo-b",
        scope=MemoryScope.REPO,
        kind=MemoryKind.PROBLEM,
        text_value="Invisible problem.",
    )

    request = MemoryUpdateRequest.model_validate(
        {
            "op": "update",
            "repo_id": "repo-a",
            "memory_id": "target-memory",
            "mode": "commit",
            "update": {
                "type": "utility_vote",
                "problem_id": "problem-hidden",
                "vote": 0.8,
            },
        }
    )

    with uow_factory() as uow:
        result = execute_update_memory(request, uow)

    assert result.status == "error"
    assert any(error.code.value == "integrity_error" for error in result.errors)


def test_utility_vote_requires_problem_kind(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_memory: Callable[..., object],
) -> None:
    """utility_vote updates should always require problem_id to reference a problem memory."""

    seed_memory(
        memory_id="target-memory",
        repo_id="repo-a",
        scope=MemoryScope.REPO,
        kind=MemoryKind.FACT,
        text_value="Target memory.",
    )
    seed_memory(
        memory_id="not-problem",
        repo_id="repo-a",
        scope=MemoryScope.REPO,
        kind=MemoryKind.FACT,
        text_value="Wrong kind.",
    )

    request = MemoryUpdateRequest.model_validate(
        {
            "op": "update",
            "repo_id": "repo-a",
            "memory_id": "target-memory",
            "mode": "commit",
            "update": {
                "type": "utility_vote",
                "problem_id": "not-problem",
                "vote": 0.8,
            },
        }
    )

    with uow_factory() as uow:
        result = execute_update_memory(request, uow)

    assert result.status == "error"
    assert any(error.code.value == "integrity_error" for error in result.errors)


def test_fact_update_requires_fact_and_change_kinds(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_memory: Callable[..., object],
) -> None:
    """fact_update_link updates should always require fact endpoints and a change-memory target."""

    seed_memory(
        memory_id="target-not-change",
        repo_id="repo-a",
        scope=MemoryScope.REPO,
        kind=MemoryKind.PROBLEM,
        text_value="Wrong target kind.",
    )
    seed_memory(
        memory_id="old-not-fact",
        repo_id="repo-a",
        scope=MemoryScope.REPO,
        kind=MemoryKind.PROBLEM,
        text_value="Wrong old kind.",
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
            "memory_id": "target-not-change",
            "mode": "commit",
            "update": {
                "type": "fact_update_link",
                "old_fact_id": "old-not-fact",
                "new_fact_id": "new-fact",
            },
        }
    )

    with uow_factory() as uow:
        result = execute_update_memory(request, uow)

    assert result.status == "error"
    fields = {error.field for error in result.errors}
    assert "update.old_fact_id" in fields
    assert "memory_id" in fields


def test_association_update_rejects_invisible_target(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_memory: Callable[..., object],
) -> None:
    """association_link updates should always reject targets outside repo visibility."""

    seed_memory(
        memory_id="source-memory",
        repo_id="repo-a",
        scope=MemoryScope.REPO,
        kind=MemoryKind.FACT,
        text_value="Source memory.",
    )
    seed_memory(
        memory_id="target-hidden",
        repo_id="repo-b",
        scope=MemoryScope.REPO,
        kind=MemoryKind.FACT,
        text_value="Invisible target.",
    )

    request = MemoryUpdateRequest.model_validate(
        {
            "op": "update",
            "repo_id": "repo-a",
            "memory_id": "source-memory",
            "mode": "commit",
            "update": {
                "type": "association_link",
                "to_memory_id": "target-hidden",
                "relation_type": "depends_on",
                "evidence_refs": ["session://1"],
            },
        }
    )

    with uow_factory() as uow:
        result = execute_update_memory(request, uow)

    assert result.status == "error"
    assert any(error.code.value == "integrity_error" for error in result.errors)
