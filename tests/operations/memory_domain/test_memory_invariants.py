"""Memory-domain invariant tests."""

import pytest

from app.core.entities.ids import MemoryId, RepoId
from app.core.entities.memories import (
    ConfidenceValue,
    EvidenceRefs,
    Memory,
    MemoryKind,
    MemoryScope,
    SalienceValue,
    UtilityVoteValue,
)


def test_memory_kind_declares_problem_link_requirement() -> None:
    assert MemoryKind.SOLUTION.requires_problem_link
    assert MemoryKind.FAILED_TACTIC.requires_problem_link
    assert not MemoryKind.PROBLEM.requires_problem_link
    assert not MemoryKind.FACT.requires_problem_link


def test_memory_visibility_allows_same_repo_or_global_scope() -> None:
    repo_memory = Memory(
        id=MemoryId("repo-memory"),
        repo_id=RepoId("repo-a"),
        scope=MemoryScope.REPO,
        kind=MemoryKind.FACT,
        text="Repo fact.",
    )
    global_memory = Memory(
        id=MemoryId("global-memory"),
        repo_id=RepoId("repo-b"),
        scope=MemoryScope.GLOBAL,
        kind=MemoryKind.FACT,
        text="Global fact.",
    )

    assert repo_memory.is_visible_in("repo-a")
    assert not repo_memory.is_visible_in("repo-b")
    assert global_memory.is_visible_in("repo-a")


def test_evidence_refs_require_non_empty_unique_values() -> None:
    assert EvidenceRefs.required(["event-1"]).values == ("event-1",)
    assert EvidenceRefs.optional([]).values == ()

    with pytest.raises(ValueError, match="unique"):
        EvidenceRefs.required(["event-1", "event-1"])
    with pytest.raises(ValueError, match="non-empty"):
        EvidenceRefs.required([""])


def test_bounded_memory_values_validate_ranges_and_defaults() -> None:
    assert ConfidenceValue.from_optional(None).value == 0.5
    assert SalienceValue.from_optional(None).value == 0.5
    assert UtilityVoteValue(1.0).value == 1.0

    with pytest.raises(ValueError, match="confidence"):
        ConfidenceValue(1.1)
    with pytest.raises(ValueError, match="salience"):
        SalienceValue(-0.1)
    with pytest.raises(ValueError, match="utility vote"):
        UtilityVoteValue(-1.1)
