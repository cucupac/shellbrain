"""Integrity contracts for update-path validation."""

from collections.abc import Callable

from app.core.use_cases.memories.update.request import MemoryUpdateRequest
from app.core.entities.memories import MemoryKind, MemoryScope
from app.infrastructure.db.runtime.uow import PostgresUnitOfWork
from app.core.use_cases.memories.reference_checks import validate_update_integrity


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
        missing_errors = validate_update_integrity(missing_request, uow)

    assert any(
        error.code.value == "not_found" and error.field == "memory_id"
        for error in missing_errors
    )

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
        hidden_errors = validate_update_integrity(hidden_request, uow)

    assert any(
        error.code.value == "integrity_error" and error.field == "memory_id"
        for error in hidden_errors
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
        missing_problem_errors = validate_update_integrity(missing_problem_request, uow)

    assert any(
        error.code.value == "not_found" and error.field == "update.problem_id"
        for error in missing_problem_errors
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
        hidden_problem_errors = validate_update_integrity(hidden_problem_request, uow)

    assert any(
        error.code.value == "integrity_error" and error.field == "update.problem_id"
        for error in hidden_problem_errors
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
        wrong_kind_errors = validate_update_integrity(wrong_kind_request, uow)

    assert any(
        error.code.value == "integrity_error" and error.field == "update.problem_id"
        for error in wrong_kind_errors
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
        missing_old_fact_errors = validate_update_integrity(
            missing_old_fact_request, uow
        )

    assert any(
        error.code.value == "not_found" and error.field == "update.old_fact_id"
        for error in missing_old_fact_errors
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
        hidden_old_fact_errors = validate_update_integrity(hidden_old_fact_request, uow)

    assert any(
        error.code.value == "integrity_error" and error.field == "update.old_fact_id"
        for error in hidden_old_fact_errors
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
        missing_new_fact_errors = validate_update_integrity(
            missing_new_fact_request, uow
        )

    assert any(
        error.code.value == "not_found" and error.field == "update.new_fact_id"
        for error in missing_new_fact_errors
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
        hidden_new_fact_errors = validate_update_integrity(hidden_new_fact_request, uow)

    assert any(
        error.code.value == "integrity_error" and error.field == "update.new_fact_id"
        for error in hidden_new_fact_errors
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
        wrong_target_kind_errors = validate_update_integrity(
            wrong_target_kind_request, uow
        )

    assert any(
        error.code.value == "integrity_error" and error.field == "memory_id"
        for error in wrong_target_kind_errors
    )


def test_update_fact_update_requires_fact_endpoints_and_change_memory_target(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_memory: Callable[..., object],
) -> None:
    """fact_update_link updates should always require fact endpoints and a change-shellbrain target."""

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
        memory_id="new-not-fact",
        repo_id="repo-a",
        scope=MemoryScope.REPO,
        kind=MemoryKind.CHANGE,
        text_value="Wrong new kind.",
    )

    request = _make_update_request(
        repo_id="repo-a",
        memory_id="target-not-change",
        update={
            "type": "fact_update_link",
            "old_fact_id": "old-not-fact",
            "new_fact_id": "new-not-fact",
        },
    )

    with uow_factory() as uow:
        errors = validate_update_integrity(request, uow)

    fields = {error.field for error in errors}
    assert "memory_id" in fields
    assert "update.old_fact_id" in fields
    assert "update.new_fact_id" in fields


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
        missing_target_errors = validate_update_integrity(missing_target_request, uow)

    assert any(
        error.code.value == "not_found" and error.field == "update.to_memory_id"
        for error in missing_target_errors
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
        hidden_target_errors = validate_update_integrity(hidden_target_request, uow)

    assert any(
        error.code.value == "integrity_error" and error.field == "update.to_memory_id"
        for error in hidden_target_errors
    )


def test_update_association_link_rejects_episode_event_evidence_from_another_repo(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_memory: Callable[..., object],
    seed_episode: Callable[..., object],
    seed_episode_event: Callable[..., object],
) -> None:
    """association_link updates should always reject evidence refs from another repo's episode."""

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
    episode = seed_episode(
        episode_id="repo-b-evidence-episode",
        repo_id="repo-b",
        host_app="codex",
        thread_id="codex:repo-b-evidence",
    )
    seed_episode_event(
        event_id="repo-b-event-1",
        episode_id=episode.id,
        seq=1,
        content='{"content_text":"repo-b event"}',
    )

    request = _make_update_request(
        repo_id="repo-a",
        memory_id="source-memory",
        update={
            "type": "association_link",
            "to_memory_id": "target-memory",
            "relation_type": "depends_on",
            "evidence_refs": ["repo-b-event-1"],
        },
    )

    with uow_factory() as uow:
        errors = validate_update_integrity(request, uow)

    assert any(
        error.code.value == "integrity_error"
        and error.field == "update.evidence_refs.0"
        for error in errors
    )


def test_update_matures_into_requires_frontier_source_and_mature_target(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_memory: Callable[..., object],
) -> None:
    """association_link updates should always restrict matures_into edges to frontier -> mature pairs."""

    seed_memory(
        memory_id="source-frontier",
        repo_id="repo-a",
        scope=MemoryScope.REPO,
        kind=MemoryKind.FRONTIER,
        text_value="Frontier source.",
    )
    seed_memory(
        memory_id="source-fact",
        repo_id="repo-a",
        scope=MemoryScope.REPO,
        kind=MemoryKind.FACT,
        text_value="Non-frontier source.",
    )
    seed_memory(
        memory_id="target-fact",
        repo_id="repo-a",
        scope=MemoryScope.REPO,
        kind=MemoryKind.FACT,
        text_value="Mature target.",
    )
    seed_memory(
        memory_id="target-frontier",
        repo_id="repo-a",
        scope=MemoryScope.REPO,
        kind=MemoryKind.FRONTIER,
        text_value="Frontier target.",
    )

    non_frontier_source_request = _make_update_request(
        repo_id="repo-a",
        memory_id="source-fact",
        update={
            "type": "association_link",
            "to_memory_id": "target-fact",
            "relation_type": "matures_into",
            "evidence_refs": ["session://1"],
        },
    )
    non_mature_target_request = _make_update_request(
        repo_id="repo-a",
        memory_id="source-frontier",
        update={
            "type": "association_link",
            "to_memory_id": "target-frontier",
            "relation_type": "matures_into",
            "evidence_refs": ["session://1"],
        },
    )

    with uow_factory() as uow:
        non_frontier_source_errors = validate_update_integrity(
            non_frontier_source_request, uow
        )
    with uow_factory() as uow:
        non_mature_target_errors = validate_update_integrity(
            non_mature_target_request, uow
        )

    assert any(
        error.code.value == "integrity_error" and error.field == "update.relation_type"
        for error in non_frontier_source_errors
    )
    assert any(
        error.code.value == "integrity_error" and error.field == "update.relation_type"
        for error in non_mature_target_errors
    )


def test_update_optional_evidence_must_resolve_to_stored_episode_events_when_present(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_memory: Callable[..., object],
) -> None:
    """optional update evidence should always resolve to stored episode events when supplied."""

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

    request = _make_update_request(
        repo_id="repo-a",
        memory_id="target-memory",
        update={
            "type": "utility_vote",
            "problem_id": "problem-1",
            "vote": 0.6,
            "evidence_refs": ["missing-event-id"],
        },
    )

    with uow_factory() as uow:
        errors = validate_update_integrity(request, uow)

    assert any(
        error.code.value == "not_found" and error.field == "update.evidence_refs.0"
        for error in errors
    )


def _make_update_request(
    *, repo_id: str, memory_id: str, update: dict[str, object]
) -> MemoryUpdateRequest:
    """Build a valid update request with caller-provided target and update payload."""

    return MemoryUpdateRequest.model_validate(
        {
            "op": "update",
            "repo_id": repo_id,
            "memory_id": memory_id,
            "update": update,
        }
    )
