"""Read execution contracts for semantic retrieval and implicit semantic expansion."""

from collections.abc import Callable

from app.core.contracts.requests import MemoryReadRequest
from app.core.interfaces.retrieval import IVectorSearch
from app.core.use_cases.read_memory import execute_read_memory
from app.periphery.db.uow import PostgresUnitOfWork
from tests.operations.read._execution_helpers import item_ids, make_read_request


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
        text_value="Alpha shellbrain text without query terms.",
    )
    seed_read_memory(
        memory_id="non-match",
        repo_id="repo-a",
        scope="repo",
        kind="fact",
        text_value="Distractor shellbrain text without query terms.",
    )
    seed_read_embedding(memory_id="semantic-hit", vector=[1.0, 0.0, 0.0, 0.0])

    request = make_read_request(
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

    assert item_ids(result) == ["semantic-hit"]


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
        make_read_request(
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
        make_read_request(
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

    without_global_ids = item_ids(without_global)
    with_global_ids = item_ids(with_global)
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

    request = make_read_request(
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

    ids = item_ids(result)
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
        text_value="Anchor shellbrain without shared query tokens.",
    )
    seed_read_memory(
        memory_id="neighbor-1",
        repo_id="repo-a",
        scope="repo",
        kind="fact",
        text_value="First linked shellbrain without shared query tokens.",
    )
    seed_read_memory(
        memory_id="neighbor-2",
        repo_id="repo-a",
        scope="repo",
        kind="fact",
        text_value="Second linked shellbrain without shared query tokens.",
    )
    seed_read_embedding(memory_id="anchor", vector=[1.0, 0.0, 0.0, 0.0])
    seed_read_embedding(memory_id="neighbor-1", vector=[0.6, 0.8, 0.0, 0.0])
    seed_read_embedding(memory_id="neighbor-2", vector=[0.0, 1.0, 0.0, 0.0])

    query_text = "latent vector probe"
    vector_search = stub_vector_search({query_text: [1.0, 0.0, 0.0, 0.0]})

    zero_hops = _execute_read_with_semantic_override(
        make_read_request(
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
        make_read_request(
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
        make_read_request(
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

    zero_hops_ids = item_ids(zero_hops)
    one_hop_ids = item_ids(one_hop)
    two_hops_ids = item_ids(two_hops)
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

    request = make_read_request(
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

    assert item_ids(first) == item_ids(second)


def test_read_excludes_archived_memories_from_direct_retrieval_and_all_expansion_paths(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_read_memory: Callable[..., None],
    seed_read_embedding: Callable[..., None],
    seed_problem_attempt_link: Callable[..., None],
    seed_fact_update_link: Callable[..., None],
    seed_association_edge: Callable[..., None],
    stub_vector_search: Callable[[dict[str, list[float]]], IVectorSearch],
    semantic_retrieval_override_factory: Callable[..., object],
) -> None:
    """read should always exclude archived memories from direct retrieval and all expansion paths."""

    seed_read_memory(
        memory_id="visible-problem",
        repo_id="repo-a",
        scope="repo",
        kind="problem",
        text_value="archived probe visible problem anchor",
    )
    seed_read_memory(
        memory_id="archived-direct",
        repo_id="repo-a",
        scope="repo",
        kind="fact",
        text_value="archived probe archived direct memory",
        archived=True,
    )
    seed_read_embedding(memory_id="archived-direct", vector=[1.0, 0.0, 0.0, 0.0])

    seed_read_memory(
        memory_id="visible-solution",
        repo_id="repo-a",
        scope="repo",
        kind="solution",
        text_value="visible solution without query overlap",
    )
    seed_read_memory(
        memory_id="archived-failed-tactic",
        repo_id="repo-a",
        scope="repo",
        kind="failed_tactic",
        text_value="archived failed tactic without query overlap",
        archived=True,
    )
    seed_problem_attempt_link(problem_id="visible-problem", attempt_id="visible-solution", role="solution")
    seed_problem_attempt_link(problem_id="visible-problem", attempt_id="archived-failed-tactic", role="failed_tactic")

    seed_read_memory(
        memory_id="visible-old-fact",
        repo_id="repo-a",
        scope="repo",
        kind="fact",
        text_value="archived probe visible fact anchor",
    )
    seed_read_memory(
        memory_id="visible-change",
        repo_id="repo-a",
        scope="repo",
        kind="change",
        text_value="visible change without query overlap",
    )
    seed_read_memory(
        memory_id="archived-new-fact",
        repo_id="repo-a",
        scope="repo",
        kind="fact",
        text_value="archived replacement fact without query overlap",
        archived=True,
    )
    seed_fact_update_link(
        link_id="fact-link-archived",
        old_fact_id="visible-old-fact",
        change_id="visible-change",
        new_fact_id="archived-new-fact",
    )

    seed_read_memory(
        memory_id="visible-assoc-anchor",
        repo_id="repo-a",
        scope="repo",
        kind="fact",
        text_value="archived probe visible association anchor",
    )
    seed_read_memory(
        memory_id="visible-assoc-neighbor",
        repo_id="repo-a",
        scope="repo",
        kind="fact",
        text_value="visible association neighbor without query overlap",
    )
    seed_read_memory(
        memory_id="archived-assoc-neighbor",
        repo_id="repo-a",
        scope="repo",
        kind="fact",
        text_value="archived association neighbor without query overlap",
        archived=True,
    )
    seed_association_edge(
        edge_id="edge-visible",
        repo_id="repo-a",
        from_memory_id="visible-assoc-anchor",
        to_memory_id="visible-assoc-neighbor",
        relation_type="associated_with",
        strength=0.9,
    )
    seed_association_edge(
        edge_id="edge-archived",
        repo_id="repo-a",
        from_memory_id="visible-assoc-anchor",
        to_memory_id="archived-assoc-neighbor",
        relation_type="associated_with",
        strength=0.9,
    )

    seed_read_memory(
        memory_id="visible-semantic-anchor",
        repo_id="repo-a",
        scope="repo",
        kind="fact",
        text_value="latent anchor without shared query tokens",
    )
    seed_read_memory(
        memory_id="visible-semantic-neighbor",
        repo_id="repo-a",
        scope="repo",
        kind="fact",
        text_value="visible latent neighbor without shared query tokens",
    )
    seed_read_memory(
        memory_id="archived-semantic-neighbor",
        repo_id="repo-a",
        scope="repo",
        kind="fact",
        text_value="archived latent neighbor without shared query tokens",
        archived=True,
    )
    seed_read_embedding(memory_id="visible-semantic-anchor", vector=[1.0, 0.0, 0.0, 0.0])
    seed_read_embedding(memory_id="visible-semantic-neighbor", vector=[0.6, 0.8, 0.0, 0.0])
    seed_read_embedding(memory_id="archived-semantic-neighbor", vector=[0.6, 0.8, 0.0, 0.0])

    request = make_read_request(
        repo_id="repo-a",
        query="archived probe",
        expand={"semantic_hops": 1},
    )
    result = _execute_read_with_semantic_override(
        request,
        uow_factory=uow_factory,
        vector_search=stub_vector_search({"archived probe": [1.0, 0.0, 0.0, 0.0]}),
        semantic_retrieval_override_factory=semantic_retrieval_override_factory,
    )

    ids = item_ids(result)
    assert "visible-problem" in ids
    assert "visible-solution" in ids
    assert "visible-old-fact" in ids
    assert "visible-change" in ids
    assert "visible-assoc-anchor" in ids
    assert "visible-assoc-neighbor" in ids
    assert "visible-semantic-anchor" in ids
    assert "visible-semantic-neighbor" in ids
    assert "archived-direct" not in ids
    assert "archived-failed-tactic" not in ids
    assert "archived-new-fact" not in ids
    assert "archived-assoc-neighbor" not in ids
    assert "archived-semantic-neighbor" not in ids


def _execute_read_with_semantic_override(
    request: MemoryReadRequest,
    *,
    uow_factory: Callable[[], PostgresUnitOfWork],
    vector_search: IVectorSearch,
    semantic_retrieval_override_factory: Callable[..., object],
):
    """Execute one read request with a deterministic semantic retrieval override."""

    with uow_factory() as uow:
        uow.vector_search = vector_search
        uow.semantic_retrieval = semantic_retrieval_override_factory(
            session=uow._session,
            vector_search=vector_search,
            active_query_text=request.query,
        )
        return execute_read_memory(request, uow)

