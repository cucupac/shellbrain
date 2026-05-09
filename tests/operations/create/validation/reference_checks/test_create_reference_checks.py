"""Create integrity contracts for edge validation."""

from collections.abc import Callable

from app.core.entities.memories import MemoryKind, MemoryScope
from tests.operations._shared.handler_calls import handle_memory_add
from app.infrastructure.db.runtime.uow import PostgresUnitOfWork


def test_create_rejects_missing_problem_reference(
    uow_factory: Callable[[], PostgresUnitOfWork],
) -> None:
    """create should always reject problem references that do not exist."""

    payload = {
        "memory": {
            "text": "Candidate solution.",
            "scope": "repo",
            "kind": "solution",
            "links": {"problem_id": "problem-missing"},
            "evidence_refs": ["session://1"],
        },
    }

    result = handle_memory_add(
        payload,
        uow_factory=uow_factory,
        embedding_provider_factory=lambda: None,
        embedding_model="stub-v1",
        inferred_repo_id="repo-a",
        defaults={"scope": "repo"},
    )

    assert result["status"] == "error"
    assert any(error["code"] == "not_found" for error in result["errors"])


def test_create_rejects_invisible_problem_reference(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_memory: Callable[..., object],
) -> None:
    """create should always reject problem references outside repo visibility."""

    seed_memory(
        memory_id="problem-hidden",
        repo_id="repo-b",
        scope=MemoryScope.REPO,
        kind=MemoryKind.PROBLEM,
        text_value="Repo B problem.",
    )

    payload = {
        "memory": {
            "text": "Candidate solution.",
            "scope": "repo",
            "kind": "solution",
            "links": {"problem_id": "problem-hidden"},
            "evidence_refs": ["session://1"],
        },
    }

    result = handle_memory_add(
        payload,
        uow_factory=uow_factory,
        embedding_provider_factory=lambda: None,
        embedding_model="stub-v1",
        inferred_repo_id="repo-a",
        defaults={"scope": "repo"},
    )

    assert result["status"] == "error"
    assert any(error["code"] == "integrity_error" for error in result["errors"])


def test_create_rejects_non_problem_reference(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_memory: Callable[..., object],
) -> None:
    """create should always require links.problem_id to reference a problem memory."""

    seed_memory(
        memory_id="fact-1",
        repo_id="repo-a",
        scope=MemoryScope.REPO,
        kind=MemoryKind.FACT,
        text_value="This is a fact, not a problem.",
    )

    payload = {
        "memory": {
            "text": "Candidate solution.",
            "scope": "repo",
            "kind": "solution",
            "links": {"problem_id": "fact-1"},
            "evidence_refs": ["session://1"],
        },
    }

    result = handle_memory_add(
        payload,
        uow_factory=uow_factory,
        embedding_provider_factory=lambda: None,
        embedding_model="stub-v1",
        inferred_repo_id="repo-a",
        defaults={"scope": "repo"},
    )

    assert result["status"] == "error"
    assert any(error["code"] == "integrity_error" for error in result["errors"])


def test_create_rejects_invisible_association_target(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_memory: Callable[..., object],
) -> None:
    """create should always reject association targets outside repo visibility."""

    seed_memory(
        memory_id="target-hidden",
        repo_id="repo-b",
        scope=MemoryScope.REPO,
        kind=MemoryKind.FACT,
        text_value="Invisible target.",
    )

    payload = {
        "memory": {
            "text": "Problem with hidden association target.",
            "scope": "repo",
            "kind": "problem",
            "links": {
                "associations": [
                    {
                        "to_memory_id": "target-hidden",
                        "relation_type": "depends_on",
                    }
                ]
            },
            "evidence_refs": ["session://1"],
        },
    }

    result = handle_memory_add(
        payload,
        uow_factory=uow_factory,
        embedding_provider_factory=lambda: None,
        embedding_model="stub-v1",
        inferred_repo_id="repo-a",
        defaults={"scope": "repo"},
    )

    assert result["status"] == "error"
    assert any(error["code"] == "integrity_error" for error in result["errors"])


def test_create_matures_into_requires_frontier_source_and_mature_target(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_memory: Callable[..., object],
) -> None:
    """create should always restrict matures_into edges to frontier -> mature pairs."""

    seed_memory(
        memory_id="target-fact",
        repo_id="repo-a",
        scope=MemoryScope.REPO,
        kind=MemoryKind.FACT,
        text_value="Mature fact target.",
    )
    seed_memory(
        memory_id="target-frontier",
        repo_id="repo-a",
        scope=MemoryScope.REPO,
        kind=MemoryKind.FRONTIER,
        text_value="Frontier target.",
    )

    non_frontier_payload = {
        "memory": {
            "text": "Problem with invalid promotion edge.",
            "scope": "repo",
            "kind": "problem",
            "links": {
                "associations": [
                    {
                        "to_memory_id": "target-fact",
                        "relation_type": "matures_into",
                    }
                ]
            },
            "evidence_refs": ["session://1"],
        },
    }
    non_mature_target_payload = {
        "memory": {
            "text": "Half-formed idea that points at another frontier.",
            "scope": "repo",
            "kind": "frontier",
            "links": {
                "associations": [
                    {
                        "to_memory_id": "target-frontier",
                        "relation_type": "matures_into",
                    }
                ]
            },
            "evidence_refs": ["session://1"],
        },
    }

    non_frontier_result = handle_memory_add(
        non_frontier_payload,
        uow_factory=uow_factory,
        embedding_provider_factory=lambda: None,
        embedding_model="stub-v1",
        inferred_repo_id="repo-a",
        defaults={"scope": "repo"},
    )
    non_mature_target_result = handle_memory_add(
        non_mature_target_payload,
        uow_factory=uow_factory,
        embedding_provider_factory=lambda: None,
        embedding_model="stub-v1",
        inferred_repo_id="repo-a",
        defaults={"scope": "repo"},
    )

    assert non_frontier_result["status"] == "error"
    assert any(
        error["field"] == "memory.links.associations.0.relation_type"
        for error in non_frontier_result["errors"]
    )

    assert non_mature_target_result["status"] == "error"
    assert any(
        error["field"] == "memory.links.associations.0.relation_type"
        for error in non_mature_target_result["errors"]
    )


def test_create_rejects_missing_episode_event_evidence(
    uow_factory: Callable[[], PostgresUnitOfWork],
) -> None:
    """create should always reject evidence refs that do not resolve to stored episode events."""

    payload = {
        "memory": {
            "text": "Problem with missing evidence.",
            "scope": "repo",
            "kind": "problem",
            "evidence_refs": ["missing-event-id"],
        },
    }

    result = handle_memory_add(
        payload,
        uow_factory=uow_factory,
        embedding_provider_factory=lambda: None,
        embedding_model="stub-v1",
        inferred_repo_id="repo-a",
        defaults={"scope": "repo"},
    )

    assert result["status"] == "error"
    assert any(
        error["code"] == "not_found" and error["field"] == "memory.evidence_refs.0"
        for error in result["errors"]
    )


def test_create_rejects_episode_event_evidence_from_another_repo(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_episode: Callable[..., object],
    seed_episode_event: Callable[..., object],
) -> None:
    """create should always reject evidence refs that belong to another repo's episode."""

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

    payload = {
        "memory": {
            "text": "Problem with hidden evidence.",
            "scope": "repo",
            "kind": "problem",
            "evidence_refs": ["repo-b-event-1"],
        },
    }

    result = handle_memory_add(
        payload,
        uow_factory=uow_factory,
        embedding_provider_factory=lambda: None,
        embedding_model="stub-v1",
        inferred_repo_id="repo-a",
        defaults={"scope": "repo"},
    )

    assert result["status"] == "error"
    assert any(
        error["code"] == "integrity_error"
        and error["field"] == "memory.evidence_refs.0"
        for error in result["errors"]
    )
