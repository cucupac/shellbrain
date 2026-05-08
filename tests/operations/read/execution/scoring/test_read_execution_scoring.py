"""Read execution contracts for read-policy scoring behavior."""

from collections.abc import Callable

import pytest

from app.core.contracts.requests import MemoryReadRequest
from app.core.policies.read_policy.expansion import expand_candidates
from app.core.policies.read_policy.fusion_rrf import fuse_with_rrf
from app.core.policies.read_policy.scoring import score_candidates
from app.core.use_cases.memory_retrieval.read_memory import execute_read_memory
from app.infrastructure.db.uow import PostgresUnitOfWork


def test_read_scoring_should_always_preserve_rrf_ordering_for_fused_direct_seeds() -> None:
    """read scoring should always preserve RRF ordering for fused direct seeds."""

    fused = [
        {"memory_id": "memory-b", "rrf_score": 0.20, "rank_semantic": 2, "rank_keyword": None},
        {"memory_id": "memory-a", "rrf_score": 0.30, "rank_semantic": 1, "rank_keyword": 3},
    ]

    scored = score_candidates({"direct": fused, "explicit": [], "implicit": []}, payload={})

    assert _candidate_ids(scored["direct"]) == ["memory-a", "memory-b"]


def test_read_scoring_should_always_rank_a_dual_lane_hit_above_single_lane_hits() -> None:
    """read scoring should always rank a dual-lane hit above single-lane hits."""

    fused = fuse_with_rrf(
        [
            {"memory_id": "dual-hit", "score": 1.0},
            {"memory_id": "semantic-only", "score": 0.9},
        ],
        [
            {"memory_id": "dual-hit", "score": 2.0},
            {"memory_id": "keyword-only", "score": 1.5},
        ],
    )

    scored = score_candidates({"direct": fused, "explicit": [], "implicit": []}, payload={})

    assert _candidate_ids(scored["direct"]) == ["dual-hit", "keyword-only", "semantic-only"]


def test_read_scoring_should_always_break_equal_rrf_scores_by_memory_identifier() -> None:
    """read scoring should always break equal RRF scores by shellbrain identifier."""

    fused = fuse_with_rrf(
        [{"memory_id": "memory-b", "score": 1.0}],
        [{"memory_id": "memory-a", "score": 1.0}],
    )

    scored = score_candidates({"direct": fused, "explicit": [], "implicit": []}, payload={})

    assert _candidate_ids(scored["direct"]) == ["memory-a", "memory-b"]


def test_read_scoring_should_always_rank_shallower_explicit_candidates_above_deeper_ones() -> None:
    """read scoring should always rank shallower explicit candidates above deeper ones."""

    scored = score_candidates(
        {
            "direct": [],
            "explicit": [
                {
                    "memory_id": "deep",
                    "anchor_memory_id": "anchor",
                    "anchor_score": 0.9,
                    "depth": 2,
                    "expansion_type": "problem_attempt",
                },
                {
                    "memory_id": "shallow",
                    "anchor_memory_id": "anchor",
                    "anchor_score": 0.9,
                    "depth": 1,
                    "expansion_type": "problem_attempt",
                },
            ],
            "implicit": [],
        },
        payload={},
    )

    assert _candidate_ids(scored["explicit"]) == ["shallow", "deep"]


def test_read_scoring_should_always_rank_stronger_association_edges_above_weaker_ones() -> None:
    """read scoring should always rank stronger association edges above weaker ones."""

    scored = score_candidates(
        {
            "direct": [],
            "explicit": [
                {
                    "memory_id": "weak",
                    "anchor_memory_id": "anchor",
                    "anchor_score": 0.9,
                    "depth": 1,
                    "expansion_type": "association",
                    "relation_strength": 0.2,
                },
                {
                    "memory_id": "strong",
                    "anchor_memory_id": "anchor",
                    "anchor_score": 0.9,
                    "depth": 1,
                    "expansion_type": "association",
                    "relation_strength": 0.8,
                },
            ],
            "implicit": [],
        },
        payload={},
    )

    assert _candidate_ids(scored["explicit"]) == ["strong", "weak"]


def test_read_scoring_should_always_ignore_relation_strength_for_non_association_explicit_links() -> None:
    """read scoring should always ignore relation strength for non-association explicit links."""

    scored = score_candidates(
        {
            "direct": [],
            "explicit": [
                {
                    "memory_id": "memory-b",
                    "anchor_memory_id": "anchor",
                    "anchor_score": 0.9,
                    "depth": 1,
                    "expansion_type": "problem_attempt",
                    "relation_strength": 0.1,
                },
                {
                    "memory_id": "memory-a",
                    "anchor_memory_id": "anchor",
                    "anchor_score": 0.9,
                    "depth": 1,
                    "expansion_type": "problem_attempt",
                    "relation_strength": 0.9,
                },
            ],
            "implicit": [],
        },
        payload={},
    )

    assert _candidate_ids(scored["explicit"]) == ["memory-a", "memory-b"]


def test_read_scoring_should_always_rank_higher_similarity_implicit_candidates_above_lower_ones() -> None:
    """read scoring should always rank higher-similarity implicit candidates above lower ones."""

    scored = score_candidates(
        {
            "direct": [],
            "explicit": [],
            "implicit": [
                {
                    "memory_id": "low-similarity",
                    "anchor_memory_id": "anchor",
                    "anchor_score": 0.9,
                    "hop": 1,
                    "neighbor_similarity": 0.2,
                    "expansion_type": "semantic_neighbor",
                },
                {
                    "memory_id": "high-similarity",
                    "anchor_memory_id": "anchor",
                    "anchor_score": 0.9,
                    "hop": 1,
                    "neighbor_similarity": 0.8,
                    "expansion_type": "semantic_neighbor",
                },
            ],
        },
        payload={},
    )

    assert _candidate_ids(scored["implicit"]) == ["high-similarity", "low-similarity"]


def test_read_scoring_should_always_rank_lower_hop_implicit_candidates_above_higher_hop_ones() -> None:
    """read scoring should always rank lower-hop implicit candidates above higher-hop ones."""

    scored = score_candidates(
        {
            "direct": [],
            "explicit": [],
            "implicit": [
                {
                    "memory_id": "hop-two",
                    "anchor_memory_id": "anchor",
                    "anchor_score": 0.9,
                    "hop": 2,
                    "neighbor_similarity": 0.8,
                    "expansion_type": "semantic_neighbor",
                },
                {
                    "memory_id": "hop-one",
                    "anchor_memory_id": "anchor",
                    "anchor_score": 0.9,
                    "hop": 1,
                    "neighbor_similarity": 0.8,
                    "expansion_type": "semantic_neighbor",
                },
            ],
        },
        payload={},
    )

    assert _candidate_ids(scored["implicit"]) == ["hop-one", "hop-two"]


def test_read_scoring_should_always_return_raw_explicit_metadata_for_downstream_scoring(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_read_memory: Callable[..., None],
    seed_problem_attempt_link: Callable[..., None],
) -> None:
    """read scoring should always return raw explicit metadata for downstream scoring."""

    seed_read_memory(
        memory_id="problem-1",
        repo_id="repo-a",
        scope="repo",
        kind="problem",
        text_value="Problem anchor for explicit scoring metadata.",
    )
    seed_read_memory(
        memory_id="solution-1",
        repo_id="repo-a",
        scope="repo",
        kind="solution",
        text_value="Solution neighbor for explicit scoring metadata.",
    )
    seed_problem_attempt_link(problem_id="problem-1", attempt_id="solution-1", role="solution")

    with uow_factory() as uow:
        expanded = expand_candidates(
            [{"memory_id": "problem-1", "rrf_score": 0.75}],
            _make_read_payload(query="unused"),
            read_policy=uow.read_policy,
            semantic_retrieval=uow.semantic_retrieval,
        )

    assert expanded["explicit"] == [
        {
            "memory_id": "solution-1",
            "anchor_memory_id": "problem-1",
            "anchor_score": 0.75,
            "depth": 1,
            "expansion_type": "problem_attempt",
        }
    ]


def test_read_scoring_should_always_return_raw_implicit_metadata_for_downstream_scoring(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_read_memory: Callable[..., None],
    seed_read_embedding: Callable[..., None],
) -> None:
    """read scoring should always return raw implicit metadata for downstream scoring."""

    seed_read_memory(
        memory_id="anchor",
        repo_id="repo-a",
        scope="repo",
        kind="fact",
        text_value="Anchor shellbrain for implicit scoring metadata.",
    )
    seed_read_memory(
        memory_id="neighbor",
        repo_id="repo-a",
        scope="repo",
        kind="fact",
        text_value="Neighbor shellbrain for implicit scoring metadata.",
    )
    seed_read_embedding(memory_id="anchor", vector=[1.0, 0.0, 0.0, 0.0])
    seed_read_embedding(memory_id="neighbor", vector=[0.6, 0.8, 0.0, 0.0])

    with uow_factory() as uow:
        expanded = expand_candidates(
            [{"memory_id": "anchor", "rrf_score": 0.75}],
            _make_read_payload(query="unused", expand={"semantic_hops": 1}),
            read_policy=uow.read_policy,
            semantic_retrieval=uow.semantic_retrieval,
        )

    assert expanded["implicit"] == [
        {
            "memory_id": "neighbor",
            "anchor_memory_id": "anchor",
            "anchor_score": 0.75,
            "hop": 1,
            "expansion_type": "semantic_neighbor",
            "neighbor_similarity": pytest.approx(0.6),
        }
    ]


def test_read_scoring_should_always_order_competing_expanded_candidates_via_the_scoring_stage(
    uow_factory: Callable[[], PostgresUnitOfWork],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """read scoring should always order competing expanded candidates via the scoring stage."""

    monkeypatch.setattr(
        "app.core.policies.read_policy.pipeline.retrieve_seeds",
        lambda payload, **kwargs: {"semantic": [], "keyword": []},
    )
    monkeypatch.setattr(
        "app.core.policies.read_policy.pipeline.fuse_with_rrf",
        lambda semantic, keyword: [
            {
                "memory_id": "anchor",
                "rrf_score": 0.9,
                "rank_semantic": 1,
                "rank_keyword": 1,
                "kind": "problem",
                "text": "Anchor memory.",
                "why_included": "direct_match",
            }
        ],
    )
    monkeypatch.setattr(
        "app.core.policies.read_policy.pipeline.expand_candidates",
        lambda direct_candidates, payload, **kwargs: {
            "explicit": [
                {
                    "memory_id": "deep",
                    "anchor_memory_id": "anchor",
                    "anchor_score": 0.9,
                    "depth": 2,
                    "expansion_type": "problem_attempt",
                    "kind": "solution",
                    "text": "Deep memory.",
                },
                {
                    "memory_id": "shallow",
                    "anchor_memory_id": "anchor",
                    "anchor_score": 0.9,
                    "depth": 1,
                    "expansion_type": "problem_attempt",
                    "kind": "solution",
                    "text": "Shallow memory.",
                },
            ],
            "implicit": [],
        },
    )

    with uow_factory() as uow:
        result = execute_read_memory(
            MemoryReadRequest.model_validate(_make_read_payload(query="smoke scoring order")),
            uow,
        )

    assert _item_ids(result) == ["anchor", "shallow", "deep"]


def _make_read_payload(**overrides: object) -> dict[str, object]:
    """Build a read payload with deterministic defaults for scoring tests."""

    payload: dict[str, object] = {
        "op": "read",
        "repo_id": "repo-a",
        "mode": "targeted",
        "query": "deployment issue",
        "include_global": True,
        "limit": 20,
        "expand": {
            "semantic_hops": 0,
            "include_problem_links": True,
            "include_fact_update_links": True,
            "include_association_links": True,
            "max_association_depth": 2,
            "min_association_strength": 0.25,
        },
    }
    if "expand" in overrides:
        expanded = dict(payload["expand"])  # type: ignore[arg-type]
        expanded.update(overrides["expand"])  # type: ignore[arg-type]
        payload["expand"] = expanded
        overrides = {key: value for key, value in overrides.items() if key != "expand"}
    payload.update(overrides)
    return payload


def _candidate_ids(candidates: list[dict[str, object]]) -> list[str]:
    """Extract ordered candidate identifiers from a scored bucket."""

    return [str(candidate["memory_id"]) for candidate in candidates]


def _item_ids(result) -> list[str]:
    """Extract ordered shellbrain identifiers from a read operation result."""

    assert result.status == "ok"
    assert "pack" in result.data
    pack = result.data["pack"]
    return [
        *[item["memory_id"] for item in pack["direct"]],
        *[item["memory_id"] for item in pack["explicit_related"]],
        *[item["memory_id"] for item in pack["implicit_related"]],
    ]
