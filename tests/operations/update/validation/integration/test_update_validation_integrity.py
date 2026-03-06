"""Integrity contracts for update-path validation."""

from collections.abc import Callable

from app.core.contracts.requests import MemoryUpdateRequest
from app.core.entities.memory import MemoryKind, MemoryScope
from app.core.use_cases.update_memory import execute_update_memory
from app.periphery.db.uow import PostgresUnitOfWork


def test_update_requires_visible_target_memory(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_memory: Callable[..., object],
) -> None:
    """update requests should always require memory_id to reference a visible memory."""

    missing_request = _make_update_request(
        repo_id="repo-a",
        memory_id="missing-memory",
        update={"type": "archive_state", "archived": True},
    )

    with uow_factory() as uow:
        missing_result = execute_update_memory(missing_request, uow)

    assert missing_result.status == "error"
    assert any(error.code.value == "not_found" and error.field == "memory_id" for error in missing_result.errors)

    seed_memory(
        memory_id="hidden-memory",
        repo_id="repo-b",
        scope=MemoryScope.REPO,
        kind=MemoryKind.FACT,
        text_value="Hidden target memory.",
    )
    hidden_request = _make_update_request(
        repo_id="repo-a",
        memory_id="hidden-memory",
        update={"type": "archive_state", "archived": True},
    )

    with uow_factory() as uow:
        hidden_result = execute_update_memory(hidden_request, uow)

    assert hidden_result.status == "error"
    assert any(
        error.code.value == "integrity_error" and error.field == "memory_id" for error in hidden_result.errors
    )


def test_update_utility_vote_requires_visible_problem_memory(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_memory: Callable[..., object],
) -> None:
    """utility_vote updates should always require problem_id to reference a visible problem memory."""

    seed_memory(
        memory_id="target-memory",
        repo_id="repo-a",
        scope=MemoryScope.REPO,
        kind=MemoryKind.FACT,
        text_value="Target memory.",
    )

    missing_problem_request = _make_update_request(
        repo_id="repo-a",
        memory_id="target-memory",
        update={
            "type": "utility_vote",
            "problem_id": "problem-missing",
            "vote": 0.7,
        },
    )
    with uow_factory() as uow:
        missing_problem_result = execute_update_memory(missing_problem_request, uow)

    assert missing_problem_result.status == "error"
    assert any(
        error.code.value == "not_found" and error.field == "update.problem_id"
        for error in missing_problem_result.errors
    )

    seed_memory(
        memory_id="problem-hidden",
        repo_id="repo-b",
        scope=MemoryScope.REPO,
        kind=MemoryKind.PROBLEM,
        text_value="Hidden problem memory.",
    )
    hidden_problem_request = _make_update_request(
        repo_id="repo-a",
        memory_id="target-memory",
        update={
            "type": "utility_vote",
            "problem_id": "problem-hidden",
            "vote": 0.7,
        },
    )
    with uow_factory() as uow:
        hidden_problem_result = execute_update_memory(hidden_problem_request, uow)

    assert hidden_problem_result.status == "error"
    assert any(
        error.code.value == "integrity_error" and error.field == "update.problem_id"
        for error in hidden_problem_result.errors
    )

    seed_memory(
        memory_id="not-a-problem",
        repo_id="repo-a",
        scope=MemoryScope.REPO,
        kind=MemoryKind.FACT,
        text_value="Wrong kind.",
    )
    wrong_kind_request = _make_update_request(
        repo_id="repo-a",
        memory_id="target-memory",
        update={
            "type": "utility_vote",
            "problem_id": "not-a-problem",
            "vote": 0.7,
        },
    )
    with uow_factory() as uow:
        wrong_kind_result = execute_update_memory(wrong_kind_request, uow)

    assert wrong_kind_result.status == "error"
    assert any(
        error.code.value == "integrity_error" and error.field == "update.problem_id"
        for error in wrong_kind_result.errors
    )


def test_update_fact_update_requires_visible_fact_endpoints_and_visible_change_memory(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_memory: Callable[..., object],
) -> None:
    """fact_update_link updates should always require visible fact endpoints and memory_id to reference a visible change memory."""

    seed_memory(
        memory_id="change-1",
        repo_id="repo-a",
        scope=MemoryScope.REPO,
        kind=MemoryKind.CHANGE,
        text_value="Visible change memory.",
    )
    seed_memory(
        memory_id="old-fact-1",
        repo_id="repo-a",
        scope=MemoryScope.REPO,
        kind=MemoryKind.FACT,
        text_value="Visible old fact.",
    )
    seed_memory(
        memory_id="new-fact-1",
        repo_id="repo-a",
        scope=MemoryScope.REPO,
        kind=MemoryKind.FACT,
        text_value="Visible new fact.",
    )

    missing_old_fact_request = _make_update_request(
        repo_id="repo-a",
        memory_id="change-1",
        update={
            "type": "fact_update_link",
            "old_fact_id": "old-fact-missing",
            "new_fact_id": "new-fact-1",
        },
    )
    with uow_factory() as uow:
        missing_old_fact_result = execute_update_memory(missing_old_fact_request, uow)

    assert missing_old_fact_result.status == "error"
    assert any(
        error.code.value == "not_found" and error.field == "update.old_fact_id"
        for error in missing_old_fact_result.errors
    )

    seed_memory(
        memory_id="old-fact-hidden",
        repo_id="repo-b",
        scope=MemoryScope.REPO,
        kind=MemoryKind.FACT,
        text_value="Hidden old fact.",
    )
    hidden_old_fact_request = _make_update_request(
        repo_id="repo-a",
        memory_id="change-1",
        update={
            "type": "fact_update_link",
            "old_fact_id": "old-fact-hidden",
            "new_fact_id": "new-fact-1",
        },
    )
    with uow_factory() as uow:
        hidden_old_fact_result = execute_update_memory(hidden_old_fact_request, uow)

    assert hidden_old_fact_result.status == "error"
    assert any(
        error.code.value == "integrity_error" and error.field == "update.old_fact_id"
        for error in hidden_old_fact_result.errors
    )

    missing_new_fact_request = _make_update_request(
        repo_id="repo-a",
        memory_id="change-1",
        update={
            "type": "fact_update_link",
            "old_fact_id": "old-fact-1",
            "new_fact_id": "new-fact-missing",
        },
    )
    with uow_factory() as uow:
        missing_new_fact_result = execute_update_memory(missing_new_fact_request, uow)

    assert missing_new_fact_result.status == "error"
    assert any(
        error.code.value == "not_found" and error.field == "update.new_fact_id"
        for error in missing_new_fact_result.errors
    )

    seed_memory(
        memory_id="new-fact-hidden",
        repo_id="repo-b",
        scope=MemoryScope.REPO,
        kind=MemoryKind.FACT,
        text_value="Hidden new fact.",
    )
    hidden_new_fact_request = _make_update_request(
        repo_id="repo-a",
        memory_id="change-1",
        update={
            "type": "fact_update_link",
            "old_fact_id": "old-fact-1",
            "new_fact_id": "new-fact-hidden",
        },
    )
    with uow_factory() as uow:
        hidden_new_fact_result = execute_update_memory(hidden_new_fact_request, uow)

    assert hidden_new_fact_result.status == "error"
    assert any(
        error.code.value == "integrity_error" and error.field == "update.new_fact_id"
        for error in hidden_new_fact_result.errors
    )

    seed_memory(
        memory_id="not-a-change",
        repo_id="repo-a",
        scope=MemoryScope.REPO,
        kind=MemoryKind.PROBLEM,
        text_value="Wrong target kind.",
    )
    wrong_target_kind_request = _make_update_request(
        repo_id="repo-a",
        memory_id="not-a-change",
        update={
            "type": "fact_update_link",
            "old_fact_id": "old-fact-1",
            "new_fact_id": "new-fact-1",
        },
    )
    with uow_factory() as uow:
        wrong_target_kind_result = execute_update_memory(wrong_target_kind_request, uow)

    assert wrong_target_kind_result.status == "error"
    assert any(
        error.code.value == "integrity_error" and error.field == "memory_id"
        for error in wrong_target_kind_result.errors
    )


def test_update_association_link_requires_visible_target_memory(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_memory: Callable[..., object],
) -> None:
    """association_link updates should always require to_memory_id to reference a visible memory."""

    seed_memory(
        memory_id="source-memory",
        repo_id="repo-a",
        scope=MemoryScope.REPO,
        kind=MemoryKind.FACT,
        text_value="Source memory.",
    )

    missing_target_request = _make_update_request(
        repo_id="repo-a",
        memory_id="source-memory",
        update={
            "type": "association_link",
            "to_memory_id": "target-missing",
            "relation_type": "depends_on",
            "evidence_refs": ["session://1"],
        },
    )
    with uow_factory() as uow:
        missing_target_result = execute_update_memory(missing_target_request, uow)

    assert missing_target_result.status == "error"
    assert any(
        error.code.value == "not_found" and error.field == "update.to_memory_id"
        for error in missing_target_result.errors
    )

    seed_memory(
        memory_id="target-hidden",
        repo_id="repo-b",
        scope=MemoryScope.REPO,
        kind=MemoryKind.FACT,
        text_value="Hidden target memory.",
    )
    hidden_target_request = _make_update_request(
        repo_id="repo-a",
        memory_id="source-memory",
        update={
            "type": "association_link",
            "to_memory_id": "target-hidden",
            "relation_type": "depends_on",
            "evidence_refs": ["session://1"],
        },
    )
    with uow_factory() as uow:
        hidden_target_result = execute_update_memory(hidden_target_request, uow)

    assert hidden_target_result.status == "error"
    assert any(
        error.code.value == "integrity_error" and error.field == "update.to_memory_id"
        for error in hidden_target_result.errors
    )


def _make_update_request(*, repo_id: str, memory_id: str, update: dict[str, object]) -> MemoryUpdateRequest:
    """Build a valid update request with caller-provided target and update payload."""

    return MemoryUpdateRequest.model_validate(
        {
            "op": "update",
            "repo_id": repo_id,
            "memory_id": memory_id,
            "mode": "commit",
            "update": update,
        }
    )
