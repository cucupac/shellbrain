"""Read execution contracts for the production semantic retrieval seam."""

from collections.abc import Callable

from app.core.use_cases.retrieval.expansion import expand_candidates
from app.infrastructure.db.runtime.uow import PostgresUnitOfWork


def test_read_returns_visible_semantic_matches_through_real_semantic_lane_when_lexical_misses(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_read_memory: Callable[..., None],
    seed_read_embedding: Callable[..., None],
) -> None:
    """read should always return visible semantic matches through the real semantic lane when lexical retrieval misses."""

    seed_read_memory(
        memory_id="semantic-hit",
        repo_id="repo-a",
        scope="repo",
        kind="fact",
        text_value="Alpha shellbrain text without query words.",
    )
    seed_read_memory(
        memory_id="semantic-distractor",
        repo_id="repo-a",
        scope="repo",
        kind="fact",
        text_value="Distractor shellbrain text without query words.",
    )
    seed_read_embedding(memory_id="semantic-hit", vector=[1.0, 0.0, 0.0, 0.0])
    seed_read_embedding(memory_id="semantic-distractor", vector=[0.0, 1.0, 0.0, 0.0])

    with uow_factory() as uow:
        candidates = uow.semantic_retrieval.query_semantic(
            repo_id="repo-a",
            include_global=True,
            query_vector=[1.0, 0.0, 0.0, 0.0],
            kinds=None,
            limit=1,
        )

    assert _candidate_ids(candidates) == ["semantic-hit"]


def test_read_applies_real_semantic_lane_visibility_and_kind_filters_before_admission(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_read_memory: Callable[..., None],
    seed_read_embedding: Callable[..., None],
) -> None:
    """read should always apply archived, repo visibility, include_global, and kinds filters in the real semantic lane."""

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
            text_value=f"{memory_id} without lexical overlap.",
            archived=archived,
        )
        seed_read_embedding(memory_id=memory_id, vector=[1.0, 0.0, 0.0, 0.0])

    with uow_factory() as uow:
        without_global = uow.semantic_retrieval.query_semantic(
            repo_id="repo-a",
            include_global=False,
            query_vector=[1.0, 0.0, 0.0, 0.0],
            kinds=["fact"],
            limit=20,
        )
        with_global = uow.semantic_retrieval.query_semantic(
            repo_id="repo-a",
            include_global=True,
            query_vector=[1.0, 0.0, 0.0, 0.0],
            kinds=["fact"],
            limit=20,
        )

    without_global_ids = _candidate_ids(without_global)
    with_global_ids = _candidate_ids(with_global)
    assert without_global_ids == ["repo-a-fact"]
    assert "repo-a-fact" in with_global_ids
    assert "repo-a-global-fact" in with_global_ids
    assert "repo-b-fact" not in with_global_ids
    assert "repo-a-problem" not in with_global_ids
    assert "repo-a-archived-fact" not in with_global_ids
    assert len(with_global_ids) == 2


def test_read_expands_semantic_neighbors_through_the_real_semantic_lane_only_up_to_semantic_hops_depth(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_read_memory: Callable[..., None],
    seed_read_embedding: Callable[..., None],
) -> None:
    """read should always expand semantic neighbors through the real semantic lane only up to semantic_hops depth."""

    seed_read_memory(
        memory_id="anchor",
        repo_id="repo-a",
        scope="repo",
        kind="fact",
        text_value="Anchor shellbrain without query overlap.",
    )
    seed_read_memory(
        memory_id="neighbor-1",
        repo_id="repo-a",
        scope="repo",
        kind="fact",
        text_value="First semantic neighbor without query overlap.",
    )
    seed_read_memory(
        memory_id="neighbor-2",
        repo_id="repo-a",
        scope="repo",
        kind="fact",
        text_value="Second semantic neighbor without query overlap.",
    )
    seed_read_embedding(memory_id="anchor", vector=[1.0, 0.0, 0.0, 0.0])
    seed_read_embedding(memory_id="neighbor-1", vector=[0.6, 0.8, 0.0, 0.0])
    seed_read_embedding(memory_id="neighbor-2", vector=[0.0, 1.0, 0.0, 0.0])

    with uow_factory() as uow:
        zero_hops = expand_candidates(
            [{"memory_id": "anchor", "score": 1.0}],
            _make_expansion_payload(semantic_hops=0),
            read_policy=uow.read_policy,
            semantic_retrieval=uow.semantic_retrieval,
        )
        one_hop = expand_candidates(
            [{"memory_id": "anchor", "score": 1.0}],
            _make_expansion_payload(semantic_hops=1),
            read_policy=uow.read_policy,
            semantic_retrieval=uow.semantic_retrieval,
        )
        two_hops = expand_candidates(
            [{"memory_id": "anchor", "score": 1.0}],
            _make_expansion_payload(semantic_hops=2),
            read_policy=uow.read_policy,
            semantic_retrieval=uow.semantic_retrieval,
        )

    zero_hop_ids = _candidate_ids(zero_hops["implicit"])
    one_hop_ids = _candidate_ids(one_hop["implicit"])
    two_hop_ids = _candidate_ids(two_hops["implicit"])
    assert "neighbor-1" not in zero_hop_ids
    assert "neighbor-1" in one_hop_ids
    assert "neighbor-2" not in one_hop_ids
    assert "neighbor-2" in two_hop_ids


def _make_expansion_payload(*, semantic_hops: int) -> dict[str, object]:
    """Build the minimal payload shape needed by expansion-stage tests."""

    return {
        "repo_id": "repo-a",
        "include_global": True,
        "limit": 1,
        "expand": {
            "semantic_hops": semantic_hops,
            "include_problem_links": False,
            "include_fact_update_links": False,
            "include_association_links": False,
            "min_association_strength": 0.25,
        },
    }


def _candidate_ids(candidates) -> list[str]:
    """Extract ordered shellbrain identifiers from semantic candidate rows."""

    return [str(candidate["memory_id"]) for candidate in candidates]
