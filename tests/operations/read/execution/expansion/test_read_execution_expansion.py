"""Read execution contracts for explicit expansion behavior."""

from collections.abc import Callable

from app.core.use_cases.retrieval.read import execute_read_memory
from app.infrastructure.db.runtime.uow import PostgresUnitOfWork
from tests.operations.read._execution_helpers import item_ids, make_read_request


def test_read_includes_structural_problem_links_when_enabled(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_read_memory: Callable[..., None],
    seed_structural_problem_link: Callable[..., None],
) -> None:
    """read should include solved_by relations when problem-link expansion is enabled."""

    seed_read_memory(
        memory_id="problem-1",
        repo_id="repo-a",
        scope="repo",
        kind="problem",
        text_value="Intermittent deployment failure root problem.",
    )
    seed_read_memory(
        memory_id="solution-1",
        repo_id="repo-a",
        scope="repo",
        kind="solution",
        text_value="Candidate rollback fix for deployment failure.",
    )
    seed_structural_problem_link(
        problem_id="problem-1", linked_memory_id="solution-1", link_kind="solution"
    )

    request = make_read_request(
        repo_id="repo-a",
        query="rollback fix",
        expand={
            "include_problem_links": True,
            "include_fact_update_links": False,
            "include_association_links": False,
        },
    )
    with uow_factory() as uow:
        result = execute_read_memory(request, uow)

    ids = item_ids(result)
    assert "solution-1" in ids
    assert "problem-1" in ids


def test_read_includes_structural_fact_change_relations_when_enabled(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_read_memory: Callable[..., None],
    seed_structural_fact_change_relations: Callable[..., None],
) -> None:
    """read should include supersession/change relations when fact-update expansion is enabled."""

    seed_read_memory(
        memory_id="old-fact-1",
        repo_id="repo-a",
        scope="repo",
        kind="fact",
        text_value="Previous deploy behavior fact.",
    )
    seed_read_memory(
        memory_id="change-1",
        repo_id="repo-a",
        scope="repo",
        kind="change",
        text_value="Deployment flow changed in latest release.",
    )
    seed_read_memory(
        memory_id="new-fact-1",
        repo_id="repo-a",
        scope="repo",
        kind="fact",
        text_value="New deploy behavior fact after release.",
    )
    seed_structural_fact_change_relations(
        relation_group_id="fact-link-1",
        old_fact_id="old-fact-1",
        change_id="change-1",
        new_fact_id="new-fact-1",
    )

    request = make_read_request(
        repo_id="repo-a",
        query="previous deploy behavior",
        expand={
            "include_problem_links": False,
            "include_fact_update_links": True,
            "include_association_links": False,
        },
    )
    with uow_factory() as uow:
        result = execute_read_memory(request, uow)

    ids = item_ids(result)
    assert "old-fact-1" in ids
    assert "new-fact-1" in ids


def test_read_includes_structural_problem_relations_with_stable_expansion_label(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_read_memory: Callable[..., None],
    seed_structural_memory_relation: Callable[..., None],
) -> None:
    """structural solved_by links should emit the stable problem_attempt category."""

    seed_read_memory(
        memory_id="problem-structural",
        repo_id="repo-a",
        scope="repo",
        kind="problem",
        text_value="Structural deployment problem.",
    )
    seed_read_memory(
        memory_id="solution-structural",
        repo_id="repo-a",
        scope="repo",
        kind="solution",
        text_value="Structural deployment solution.",
    )
    seed_structural_memory_relation(
        relation_id="relation-solved-by",
        repo_id="repo-a",
        subject_memory_id="problem-structural",
        predicate="solved_by",
        object_memory_id="solution-structural",
    )

    request = make_read_request(
        repo_id="repo-a",
        query="structural deployment problem",
        expand={
            "include_problem_links": True,
            "include_fact_update_links": False,
            "include_association_links": False,
        },
    )
    with uow_factory() as uow:
        result = execute_read_memory(request, uow)

    explicit_related = result.data["pack"]["explicit_related"]
    assert {
        (item["memory_id"], item["why_included"]) for item in explicit_related
    } == {("solution-structural", "problem_attempt")}


def test_read_excludes_retired_structural_problem_relations(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_read_memory: Callable[..., None],
    seed_structural_memory_relation: Callable[..., None],
) -> None:
    """retired canonical relations should not expand explicit neighbors."""

    seed_read_memory(
        memory_id="problem-retired-relation",
        repo_id="repo-a",
        scope="repo",
        kind="problem",
        text_value="Problem with retired structural relation.",
    )
    seed_read_memory(
        memory_id="solution-retired-relation",
        repo_id="repo-a",
        scope="repo",
        kind="solution",
        text_value="Solution hidden by retired structural relation.",
    )
    seed_structural_memory_relation(
        relation_id="relation-retired-solved-by",
        repo_id="repo-a",
        subject_memory_id="problem-retired-relation",
        predicate="solved_by",
        object_memory_id="solution-retired-relation",
        status="wrong",
    )

    request = make_read_request(
        repo_id="repo-a",
        query="retired structural relation problem",
        expand={
            "include_problem_links": True,
            "include_fact_update_links": False,
            "include_association_links": False,
        },
    )
    with uow_factory() as uow:
        result = execute_read_memory(request, uow)

    assert "problem-retired-relation" in item_ids(result)
    assert "solution-retired-relation" not in item_ids(result)


def test_read_includes_structural_fact_update_relations_with_stable_expansion_label(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_read_memory: Callable[..., None],
    seed_structural_memory_relation: Callable[..., None],
) -> None:
    """structural fact-change relations should emit the stable fact_update category."""

    seed_read_memory(
        memory_id="old-structural-fact",
        repo_id="repo-a",
        scope="repo",
        kind="fact",
        text_value="Old structural deploy fact.",
    )
    seed_read_memory(
        memory_id="change-structural",
        repo_id="repo-a",
        scope="repo",
        kind="change",
        text_value="Structural deploy change.",
    )
    seed_read_memory(
        memory_id="new-structural-fact",
        repo_id="repo-a",
        scope="repo",
        kind="fact",
        text_value="New structural deploy fact.",
    )
    seed_structural_memory_relation(
        relation_id="relation-superseded-by",
        repo_id="repo-a",
        subject_memory_id="old-structural-fact",
        predicate="superseded_by",
        object_memory_id="new-structural-fact",
    )
    seed_structural_memory_relation(
        relation_id="relation-old-change",
        repo_id="repo-a",
        subject_memory_id="old-structural-fact",
        predicate="explained_by_change",
        object_memory_id="change-structural",
    )

    request = make_read_request(
        repo_id="repo-a",
        query="old structural deploy",
        expand={
            "include_problem_links": False,
            "include_fact_update_links": True,
            "include_association_links": False,
        },
    )
    with uow_factory() as uow:
        result = execute_read_memory(request, uow)

    explicit_related = result.data["pack"]["explicit_related"]
    assert {
        (item["memory_id"], item["why_included"]) for item in explicit_related
    } == {
        ("change-structural", "fact_update"),
        ("new-structural-fact", "fact_update"),
    }


def test_read_applies_association_expansion_flag_and_strength_threshold(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_read_memory: Callable[..., None],
    seed_association_edge: Callable[..., None],
) -> None:
    """read should always include linked association neighbors only when enabled and edge strength passes threshold."""

    seed_read_memory(
        memory_id="anchor-1",
        repo_id="repo-a",
        scope="repo",
        kind="fact",
        text_value="Deployment anchor shellbrain for association expansion.",
    )
    seed_read_memory(
        memory_id="neighbor-strong",
        repo_id="repo-a",
        scope="repo",
        kind="fact",
        text_value="Strong association neighbor.",
    )
    seed_read_memory(
        memory_id="neighbor-weak",
        repo_id="repo-a",
        scope="repo",
        kind="fact",
        text_value="Weak association neighbor.",
    )
    seed_association_edge(
        edge_id="edge-strong",
        repo_id="repo-a",
        from_memory_id="anchor-1",
        to_memory_id="neighbor-strong",
        relation_type="associated_with",
        strength=0.9,
    )
    seed_association_edge(
        edge_id="edge-weak",
        repo_id="repo-a",
        from_memory_id="anchor-1",
        to_memory_id="neighbor-weak",
        relation_type="associated_with",
        strength=0.1,
    )

    request_enabled = make_read_request(
        repo_id="repo-a",
        query="deployment anchor",
        expand={
            "include_problem_links": False,
            "include_fact_update_links": False,
            "include_association_links": True,
            "min_association_strength": 0.25,
        },
    )
    request_disabled = make_read_request(
        repo_id="repo-a",
        query="deployment anchor",
        expand={
            "include_problem_links": False,
            "include_fact_update_links": False,
            "include_association_links": False,
            "min_association_strength": 0.25,
        },
    )

    with uow_factory() as uow:
        enabled = execute_read_memory(request_enabled, uow)
    with uow_factory() as uow:
        disabled = execute_read_memory(request_disabled, uow)

    enabled_ids = item_ids(enabled)
    disabled_ids = item_ids(disabled)
    assert "neighbor-strong" in enabled_ids
    assert "neighbor-weak" not in enabled_ids
    assert "neighbor-strong" not in disabled_ids


def test_read_expands_association_neighbors_only_up_to_max_association_depth(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_read_memory: Callable[..., None],
    seed_association_edge: Callable[..., None],
) -> None:
    """read should always expand association neighbors only up to max_association_depth."""

    seed_read_memory(
        memory_id="anchor-depth",
        repo_id="repo-a",
        scope="repo",
        kind="fact",
        text_value="Depth anchor shellbrain for association traversal.",
    )
    seed_read_memory(
        memory_id="association-hop-1",
        repo_id="repo-a",
        scope="repo",
        kind="fact",
        text_value="First association hop.",
    )
    seed_read_memory(
        memory_id="association-hop-2",
        repo_id="repo-a",
        scope="repo",
        kind="fact",
        text_value="Second association hop.",
    )
    seed_association_edge(
        edge_id="edge-hop-1",
        repo_id="repo-a",
        from_memory_id="anchor-depth",
        to_memory_id="association-hop-1",
        relation_type="depends_on",
        strength=0.9,
    )
    seed_association_edge(
        edge_id="edge-hop-2",
        repo_id="repo-a",
        from_memory_id="association-hop-1",
        to_memory_id="association-hop-2",
        relation_type="depends_on",
        strength=0.8,
    )

    one_hop = make_read_request(
        repo_id="repo-a",
        query="depth anchor",
        expand={
            "semantic_hops": 0,
            "include_problem_links": False,
            "include_fact_update_links": False,
            "include_association_links": True,
            "max_association_depth": 1,
            "min_association_strength": 0.25,
        },
    )
    two_hops = make_read_request(
        repo_id="repo-a",
        query="depth anchor",
        expand={
            "semantic_hops": 0,
            "include_problem_links": False,
            "include_fact_update_links": False,
            "include_association_links": True,
            "max_association_depth": 2,
            "min_association_strength": 0.25,
        },
    )

    with uow_factory() as uow:
        one_hop_result = execute_read_memory(one_hop, uow)
    with uow_factory() as uow:
        two_hop_result = execute_read_memory(two_hops, uow)

    one_hop_ids = item_ids(one_hop_result)
    two_hop_ids = item_ids(two_hop_result)
    assert "association-hop-1" in one_hop_ids
    assert "association-hop-2" not in one_hop_ids
    assert "association-hop-2" in two_hop_ids
