"""Read execution contracts for the production keyword retrieval seam."""

from collections.abc import Callable

from shellbrain.periphery.db.uow import PostgresUnitOfWork


def test_keyword_lane_prefers_high_coverage_partial_matches_over_generic_partial_matches(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_read_memory: Callable[..., None],
) -> None:
    """keyword retrieval should always admit high-coverage partial matches while rejecting low-coverage generic partial matches."""

    seed_read_memory(
        memory_id="full-match",
        repo_id="repo-a",
        scope="repo",
        kind="fact",
        text_value="Deployment issue root cause analysis.",
    )
    seed_read_memory(
        memory_id="issue-only",
        repo_id="repo-a",
        scope="repo",
        kind="fact",
        text_value="Issue triage notes without the first term.",
    )
    seed_read_memory(
        memory_id="deployment-only",
        repo_id="repo-a",
        scope="repo",
        kind="fact",
        text_value="Deployment rollout notes without the second term.",
    )
    seed_read_memory(
        memory_id="deployment-noise-1",
        repo_id="repo-a",
        scope="repo",
        kind="fact",
        text_value="Deployment checklist without problem context.",
    )
    seed_read_memory(
        memory_id="deployment-noise-2",
        repo_id="repo-a",
        scope="repo",
        kind="fact",
        text_value="Deployment status update without problem context.",
    )

    with uow_factory() as uow:
        candidates = uow.keyword_retrieval.query_keyword(
            repo_id="repo-a",
            mode="targeted",
            include_global=True,
            query_text="deployment issue",
            kinds=None,
            limit=10,
        )

    ids = _candidate_ids(candidates)
    assert "full-match" in ids
    assert "issue-only" in ids
    assert "deployment-only" not in ids


def test_keyword_lane_applies_stricter_coverage_gate_for_ambient_reads_than_targeted_reads(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_read_memory: Callable[..., None],
) -> None:
    """keyword retrieval should always be stricter for ambient reads than for targeted reads."""

    seed_read_memory(
        memory_id="targeted-only",
        repo_id="repo-a",
        scope="repo",
        kind="fact",
        text_value="Rollback deployment",
    )
    seed_read_memory(
        memory_id="auth-only",
        repo_id="repo-a",
        scope="repo",
        kind="fact",
        text_value="Auth",
    )

    with uow_factory() as uow:
        targeted = uow.keyword_retrieval.query_keyword(
            repo_id="repo-a",
            mode="targeted",
            include_global=True,
            query_text="rollback deployment auth",
            kinds=None,
            limit=10,
        )
        ambient = uow.keyword_retrieval.query_keyword(
            repo_id="repo-a",
            mode="ambient",
            include_global=True,
            query_text="rollback deployment auth",
            kinds=None,
            limit=10,
        )

    assert _candidate_ids(targeted) == ["targeted-only"]
    assert _candidate_ids(ambient) == []


def test_keyword_lane_uses_bm25_to_prefer_denser_shorter_matches(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_read_memory: Callable[..., None],
) -> None:
    """keyword retrieval should always rank denser shorter matches ahead of verbose matches."""

    seed_read_memory(
        memory_id="compact-hit",
        repo_id="repo-a",
        scope="repo",
        kind="fact",
        text_value="Rollback deployment",
    )
    seed_read_memory(
        memory_id="verbose-hit",
        repo_id="repo-a",
        scope="repo",
        kind="fact",
        text_value="Rollback deployment troubleshooting notes with extra unrelated detail and verbose context.",
    )

    with uow_factory() as uow:
        candidates = uow.keyword_retrieval.query_keyword(
            repo_id="repo-a",
            mode="targeted",
            include_global=True,
            query_text="rollback deployment",
            kinds=None,
            limit=10,
        )

    assert _candidate_ids(candidates) == ["compact-hit", "verbose-hit"]


def test_keyword_lane_applies_visibility_scope_kind_and_archived_filters_before_scoring(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_read_memory: Callable[..., None],
) -> None:
    """keyword retrieval should always gate the visible lexical corpus before scoring."""

    for memory_id, repo_id, scope, kind, archived in (
        ("repo-a-fact", "repo-a", "repo", "fact", False),
        ("repo-a-global-fact", "repo-a", "global", "fact", False),
        ("repo-b-fact", "repo-b", "repo", "fact", False),
        ("repo-a-problem", "repo-a", "repo", "problem", False),
        ("repo-a-archived-fact", "repo-a", "repo", "fact", True),
    ):
        seed_read_memory(
            memory_id=memory_id,
            repo_id=repo_id,
            scope=scope,
            kind=kind,
            text_value="Deployment issue lexical visibility probe.",
            archived=archived,
        )

    with uow_factory() as uow:
        without_global = uow.keyword_retrieval.query_keyword(
            repo_id="repo-a",
            mode="targeted",
            include_global=False,
            query_text="deployment issue",
            kinds=["fact"],
            limit=20,
        )
        with_global = uow.keyword_retrieval.query_keyword(
            repo_id="repo-a",
            mode="targeted",
            include_global=True,
            query_text="deployment issue",
            kinds=["fact"],
            limit=20,
        )

    assert _candidate_ids(without_global) == ["repo-a-fact"]
    assert _candidate_ids(with_global) == ["repo-a-fact", "repo-a-global-fact"]


def test_keyword_lane_keeps_tie_breaking_deterministic_by_memory_id(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_read_memory: Callable[..., None],
) -> None:
    """keyword retrieval should always break equal-score ties by shellbrain identifier."""

    seed_read_memory(
        memory_id="memory-a",
        repo_id="repo-a",
        scope="repo",
        kind="fact",
        text_value="Deployment issue",
    )
    seed_read_memory(
        memory_id="memory-b",
        repo_id="repo-a",
        scope="repo",
        kind="fact",
        text_value="Deployment issue",
    )

    with uow_factory() as uow:
        candidates = uow.keyword_retrieval.query_keyword(
            repo_id="repo-a",
            mode="targeted",
            include_global=True,
            query_text="deployment issue",
            kinds=None,
            limit=10,
        )

    assert _candidate_ids(candidates) == ["memory-a", "memory-b"]


def _candidate_ids(candidates) -> list[str]:
    """Extract ordered shellbrain identifiers from keyword candidate rows."""

    return [str(candidate["memory_id"]) for candidate in candidates]
