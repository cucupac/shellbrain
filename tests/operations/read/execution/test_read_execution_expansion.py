"""Read execution contracts for explicit expansion behavior."""

from collections.abc import Callable

from app.core.contracts.requests import MemoryReadRequest
from app.core.use_cases.read_memory import execute_read_memory
from app.periphery.db.uow import PostgresUnitOfWork


def test_read_includes_problem_attempt_links_when_enabled(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_read_memory: Callable[..., None],
    seed_problem_attempt_link: Callable[..., None],
) -> None:
    """read should always include linked problem attempts when problem-link expansion is enabled."""

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
    seed_problem_attempt_link(problem_id="problem-1", attempt_id="solution-1", role="solution")

    request = _make_read_request(
        repo_id="repo-a",
        query="rollback fix",
        expand={"include_problem_links": True, "include_fact_update_links": False, "include_association_links": False},
    )
    with uow_factory() as uow:
        result = execute_read_memory(request, uow)

    ids = _item_ids(result)
    assert "solution-1" in ids
    assert "problem-1" in ids


def test_read_includes_fact_update_links_when_enabled(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_read_memory: Callable[..., None],
    seed_fact_update_link: Callable[..., None],
) -> None:
    """read should always include linked fact updates when fact-update expansion is enabled."""

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
    seed_fact_update_link(
        link_id="fact-link-1",
        old_fact_id="old-fact-1",
        change_id="change-1",
        new_fact_id="new-fact-1",
    )

    request = _make_read_request(
        repo_id="repo-a",
        query="previous deploy behavior",
        expand={"include_problem_links": False, "include_fact_update_links": True, "include_association_links": False},
    )
    with uow_factory() as uow:
        result = execute_read_memory(request, uow)

    ids = _item_ids(result)
    assert "old-fact-1" in ids
    assert "new-fact-1" in ids


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
        text_value="Deployment anchor memory for association expansion.",
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

    request_enabled = _make_read_request(
        repo_id="repo-a",
        query="deployment anchor",
        expand={
            "include_problem_links": False,
            "include_fact_update_links": False,
            "include_association_links": True,
            "min_association_strength": 0.25,
        },
    )
    request_disabled = _make_read_request(
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

    enabled_ids = _item_ids(enabled)
    disabled_ids = _item_ids(disabled)
    assert "neighbor-strong" in enabled_ids
    assert "neighbor-weak" not in enabled_ids
    assert "neighbor-strong" not in disabled_ids


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

