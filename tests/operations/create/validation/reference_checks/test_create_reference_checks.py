"""Create integrity contracts for edge validation."""

from collections.abc import Callable

from app.core.entities.memory import MemoryKind, MemoryScope
from app.periphery.cli.handlers import handle_create
from app.periphery.db.uow import PostgresUnitOfWork


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

    result = handle_create(
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

    result = handle_create(
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

    result = handle_create(
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

    result = handle_create(
        payload,
        uow_factory=uow_factory,
        embedding_provider_factory=lambda: None,
        embedding_model="stub-v1",
        inferred_repo_id="repo-a",
        defaults={"scope": "repo"},
    )

    assert result["status"] == "error"
    assert any(error["code"] == "integrity_error" for error in result["errors"])
