"""Read execution contracts for semantic retrieval and implicit semantic expansion."""

from collections.abc import Callable

from app.core.contracts.requests import MemoryReadRequest
from app.core.interfaces.retrieval import IVectorSearch
from app.core.use_cases.read_memory import execute_read_memory
from app.periphery.db.uow import PostgresUnitOfWork


def test_read_returns_semantic_seed_matches_when_lexical_misses(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_read_memory: Callable[..., None],
    seed_read_embedding: Callable[..., None],
    stub_vector_search: Callable[[dict[str, list[float]]], IVectorSearch],
    semantic_retrieval_override_factory: Callable[..., object],
) -> None:
    """read should always return semantic seed matches when lexical retrieval misses."""

    seed_read_memory(
        memory_id="semantic-hit",
        repo_id="repo-a",
        scope="repo",
        kind="fact",
        text_value="Alpha memory text without query terms.",
    )
    seed_read_memory(
        memory_id="non-match",
        repo_id="repo-a",
        scope="repo",
        kind="fact",
        text_value="Distractor memory text without query terms.",
    )
    seed_read_embedding(memory_id="semantic-hit", vector=[1.0, 0.0, 0.0, 0.0])

    request = _make_read_request(
        repo_id="repo-a",
        query="latent semantic regression",
        expand={"semantic_hops": 0},
    )
    result = _execute_read_with_semantic_override(
        request,
        uow_factory=uow_factory,
        vector_search=stub_vector_search({"latent semantic regression": [1.0, 0.0, 0.0, 0.0]}),
        semantic_retrieval_override_factory=semantic_retrieval_override_factory,
    )

    assert _item_ids(result) == ["semantic-hit"]


def test_read_applies_semantic_visibility_and_kind_filters_before_admission(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_read_memory: Callable[..., None],
    seed_read_embedding: Callable[..., None],
    stub_vector_search: Callable[[dict[str, list[float]]], IVectorSearch],
    semantic_retrieval_override_factory: Callable[..., object],
) -> None:
    """read should always apply repo visibility, include_global, and kinds filters before admitting semantic matches."""

    for memory_id, repo_id, scope, kind in (
        ("repo-a-fact", "repo-a", "repo", "fact"),
        ("repo-a-global-fact", "repo-a", "global", "fact"),
        ("repo-b-fact", "repo-b", "repo", "fact"),
        ("repo-a-problem", "repo-a", "repo", "problem"),
    ):
        seed_read_memory(
            memory_id=memory_id,
            repo_id=repo_id,
            scope=scope,
            kind=kind,
            text_value=f"{memory_id} without lexical overlap.",
        )
        seed_read_embedding(memory_id=memory_id, vector=[1.0, 0.0, 0.0, 0.0])

    query_text = "semantic only visibility probe"
    vector_search = stub_vector_search({query_text: [1.0, 0.0, 0.0, 0.0]})

    without_global = _execute_read_with_semantic_override(
        _make_read_request(
            repo_id="repo-a",
            query=query_text,
            include_global=False,
            kinds=["fact"],
            expand={"semantic_hops": 0},
        ),
        uow_factory=uow_factory,
        vector_search=vector_search,
        semantic_retrieval_override_factory=semantic_retrieval_override_factory,
    )
    with_global = _execute_read_with_semantic_override(
        _make_read_request(
            repo_id="repo-a",
            query=query_text,
            include_global=True,
            kinds=["fact"],
            expand={"semantic_hops": 0},
        ),
        uow_factory=uow_factory,
        vector_search=vector_search,
        semantic_retrieval_override_factory=semantic_retrieval_override_factory,
    )

    without_global_ids = _item_ids(without_global)
    with_global_ids = _item_ids(with_global)
    assert without_global_ids == ["repo-a-fact"]
    assert "repo-a-fact" in with_global_ids
    assert "repo-a-global-fact" in with_global_ids
    assert "repo-b-fact" not in with_global_ids
    assert "repo-a-problem" not in with_global_ids


def test_read_fuses_semantic_and_keyword_direct_hits_without_duplicates(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_read_memory: Callable[..., None],
    seed_read_embedding: Callable[..., None],
    stub_vector_search: Callable[[dict[str, list[float]]], IVectorSearch],
    semantic_retrieval_override_factory: Callable[..., object],
) -> None:
    """read should always fuse semantic and keyword direct hits without duplicating shared memories."""

    seed_read_memory(
        memory_id="dual-hit",
        repo_id="repo-a",
        scope="repo",
        kind="fact",
        text_value="rollback deployment",
    )
    seed_read_memory(
        memory_id="keyword-only",
        repo_id="repo-a",
        scope="repo",
        kind="fact",
        text_value="rollback deployment keyword only",
    )
    seed_read_embedding(memory_id="dual-hit", vector=[1.0, 0.0, 0.0, 0.0])

    request = _make_read_request(
        repo_id="repo-a",
        query="rollback deployment",
        expand={"semantic_hops": 0},
    )
    result = _execute_read_with_semantic_override(
        request,
        uow_factory=uow_factory,
        vector_search=stub_vector_search({"rollback deployment": [1.0, 0.0, 0.0, 0.0]}),
        semantic_retrieval_override_factory=semantic_retrieval_override_factory,
    )

    ids = _item_ids(result)
    assert ids.count("dual-hit") == 1
    assert "keyword-only" in ids
    assert ids[0] == "dual-hit"


def test_read_expands_implicit_semantic_neighbors_only_up_to_semantic_hops_depth(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_read_memory: Callable[..., None],
    seed_read_embedding: Callable[..., None],
    stub_vector_search: Callable[[dict[str, list[float]]], IVectorSearch],
    semantic_retrieval_override_factory: Callable[..., object],
) -> None:
    """read should always expand implicit semantic neighbors only up to semantic_hops depth."""

    seed_read_memory(
        memory_id="anchor",
        repo_id="repo-a",
        scope="repo",
        kind="fact",
        text_value="Anchor memory without shared query tokens.",
    )
    seed_read_memory(
        memory_id="neighbor-1",
        repo_id="repo-a",
        scope="repo",
        kind="fact",
        text_value="First linked memory without shared query tokens.",
    )
    seed_read_memory(
        memory_id="neighbor-2",
        repo_id="repo-a",
        scope="repo",
        kind="fact",
        text_value="Second linked memory without shared query tokens.",
    )
    seed_read_embedding(memory_id="anchor", vector=[1.0, 0.0, 0.0, 0.0])
    seed_read_embedding(memory_id="neighbor-1", vector=[0.6, 0.8, 0.0, 0.0])
    seed_read_embedding(memory_id="neighbor-2", vector=[0.0, 1.0, 0.0, 0.0])

    query_text = "latent vector probe"
    vector_search = stub_vector_search({query_text: [1.0, 0.0, 0.0, 0.0]})

    zero_hops = _execute_read_with_semantic_override(
        _make_read_request(
            repo_id="repo-a",
            query=query_text,
            expand={
                "semantic_hops": 0,
                "include_problem_links": False,
                "include_fact_update_links": False,
                "include_association_links": False,
            },
        ),
        uow_factory=uow_factory,
        vector_search=vector_search,
        semantic_retrieval_override_factory=semantic_retrieval_override_factory,
    )
    one_hop = _execute_read_with_semantic_override(
        _make_read_request(
            repo_id="repo-a",
            query=query_text,
            expand={
                "semantic_hops": 1,
                "include_problem_links": False,
                "include_fact_update_links": False,
                "include_association_links": False,
            },
        ),
        uow_factory=uow_factory,
        vector_search=vector_search,
        semantic_retrieval_override_factory=semantic_retrieval_override_factory,
    )
    two_hops = _execute_read_with_semantic_override(
        _make_read_request(
            repo_id="repo-a",
            query=query_text,
            expand={
                "semantic_hops": 2,
                "include_problem_links": False,
                "include_fact_update_links": False,
                "include_association_links": False,
            },
        ),
        uow_factory=uow_factory,
        vector_search=vector_search,
        semantic_retrieval_override_factory=semantic_retrieval_override_factory,
    )

    zero_hops_ids = _item_ids(zero_hops)
    one_hop_ids = _item_ids(one_hop)
    two_hops_ids = _item_ids(two_hops)
    assert "neighbor-1" not in zero_hops_ids
    assert "neighbor-1" in one_hop_ids
    assert "neighbor-2" not in one_hop_ids
    assert "neighbor-2" in two_hops_ids


def test_read_keeps_semantic_ordering_deterministic_on_stable_snapshot(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_read_memory: Callable[..., None],
    seed_read_embedding: Callable[..., None],
    stub_vector_search: Callable[[dict[str, list[float]]], IVectorSearch],
    semantic_retrieval_override_factory: Callable[..., object],
) -> None:
    """read should always keep semantic ordering deterministic for the same input and snapshot."""

    seed_read_memory(
        memory_id="semantic-a",
        repo_id="repo-a",
        scope="repo",
        kind="fact",
        text_value="First semantic candidate without lexical overlap.",
    )
    seed_read_memory(
        memory_id="semantic-b",
        repo_id="repo-a",
        scope="repo",
        kind="fact",
        text_value="Second semantic candidate without lexical overlap.",
    )
    seed_read_embedding(memory_id="semantic-a", vector=[1.0, 0.0, 0.0, 0.0])
    seed_read_embedding(memory_id="semantic-b", vector=[1.0, 0.0, 0.0, 0.0])

    request = _make_read_request(
        repo_id="repo-a",
        query="deterministic semantic query",
        expand={"semantic_hops": 0},
    )
    vector_search = stub_vector_search({"deterministic semantic query": [1.0, 0.0, 0.0, 0.0]})

    first = _execute_read_with_semantic_override(
        request,
        uow_factory=uow_factory,
        vector_search=vector_search,
        semantic_retrieval_override_factory=semantic_retrieval_override_factory,
    )
    second = _execute_read_with_semantic_override(
        request,
        uow_factory=uow_factory,
        vector_search=vector_search,
        semantic_retrieval_override_factory=semantic_retrieval_override_factory,
    )

    assert _item_ids(first) == _item_ids(second)


def _execute_read_with_semantic_override(
    request: MemoryReadRequest,
    *,
    uow_factory: Callable[[], PostgresUnitOfWork],
    vector_search: IVectorSearch,
    semantic_retrieval_override_factory: Callable[..., object],
):
    """Execute one read request with a deterministic semantic retrieval override."""

    with uow_factory() as uow:
        uow.semantic_retrieval = semantic_retrieval_override_factory(
            session=uow._session,
            vector_search=vector_search,
            active_query_text=request.query,
        )
        return execute_read_memory(request, uow)


def _make_read_request(**overrides: object) -> MemoryReadRequest:
    """Build a read request with deterministic defaults and caller overrides."""

    payload: dict[str, object] = {
        "op": "read",
        "repo_id": "repo-a",
        "mode": "targeted",
        "query": "deployment issue",
        "include_global": True,
        "limit": 20,
        "expand": {
            "semantic_hops": 2,
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
    return MemoryReadRequest.model_validate(payload)


def _item_ids(result) -> list[str]:
    """Extract ordered memory IDs from a read operation result."""

    assert result.status == "ok"
    assert "items" in result.data
    return [item["memory_id"] for item in result.data["items"]]
