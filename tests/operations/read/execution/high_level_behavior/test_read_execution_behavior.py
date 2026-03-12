"""Core read execution contracts for retrieval behavior."""

from collections.abc import Callable

from app.core.contracts.requests import MemoryReadRequest
from app.core.use_cases.read_memory import execute_read_memory
from app.periphery.db.uow import PostgresUnitOfWork


def test_read_never_mutates_database_state(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_read_memory: Callable[..., None],
    snapshot_row_counts: Callable[[], dict[str, int]],
) -> None:
    """read should always be retrieval-only and never mutate database state."""

    seed_read_memory(
        memory_id="repo-a-problem",
        repo_id="repo-a",
        scope="repo",
        kind="problem",
        text_value="Deployment issue after release.",
    )
    before = snapshot_row_counts()
    request = _make_read_request(repo_id="repo-a", query="deployment issue")

    with uow_factory() as uow:
        result = execute_read_memory(request, uow)

    after = snapshot_row_counts()
    assert result.status == "ok"
    assert before == after


def test_read_enforces_repo_visibility_and_include_global_scope(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_read_memory: Callable[..., None],
) -> None:
    """read should always enforce repo visibility and include_global scope rules."""

    seed_read_memory(
        memory_id="repo-a-problem",
        repo_id="repo-a",
        scope="repo",
        kind="problem",
        text_value="Deployment issue in repo A.",
    )
    seed_read_memory(
        memory_id="repo-a-global",
        repo_id="repo-a",
        scope="global",
        kind="preference",
        text_value="Global preference for deployment issue rollback.",
    )
    seed_read_memory(
        memory_id="repo-b-problem",
        repo_id="repo-b",
        scope="repo",
        kind="problem",
        text_value="Deployment issue in repo B.",
    )

    request_without_global = _make_read_request(
        repo_id="repo-a",
        query="deployment issue",
        include_global=False,
    )
    request_with_global = _make_read_request(
        repo_id="repo-a",
        query="deployment issue",
        include_global=True,
    )

    with uow_factory() as uow:
        without_global = execute_read_memory(request_without_global, uow)
    with uow_factory() as uow:
        with_global = execute_read_memory(request_with_global, uow)

    without_global_ids = _item_ids(without_global)
    with_global_ids = _item_ids(with_global)
    assert "repo-a-problem" in without_global_ids
    assert "repo-a-global" not in without_global_ids
    assert "repo-a-global" in with_global_ids
    assert "repo-b-problem" not in with_global_ids


def test_read_applies_kinds_filter_as_include_only(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_read_memory: Callable[..., None],
) -> None:
    """read should always apply kinds as include-only filters."""

    seed_read_memory(
        memory_id="problem-1",
        repo_id="repo-a",
        scope="repo",
        kind="problem",
        text_value="Deployment issue memory.",
    )
    seed_read_memory(
        memory_id="fact-1",
        repo_id="repo-a",
        scope="repo",
        kind="fact",
        text_value="Deployment issue factual detail.",
    )

    request = _make_read_request(
        repo_id="repo-a",
        query="deployment issue",
        kinds=["problem"],
    )
    with uow_factory() as uow:
        result = execute_read_memory(request, uow)

    ids = _item_ids(result)
    assert "problem-1" in ids
    assert "fact-1" not in ids


def test_read_enforces_hard_output_cap_equal_to_limit(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_read_memory: Callable[..., None],
) -> None:
    """read should always enforce a hard output cap equal to limit."""

    seed_read_memory(
        memory_id="problem-1",
        repo_id="repo-a",
        scope="repo",
        kind="problem",
        text_value="Deployment issue one.",
    )
    seed_read_memory(
        memory_id="problem-2",
        repo_id="repo-a",
        scope="repo",
        kind="problem",
        text_value="Deployment issue two.",
    )
    seed_read_memory(
        memory_id="problem-3",
        repo_id="repo-a",
        scope="repo",
        kind="problem",
        text_value="Deployment issue three.",
    )

    request = _make_read_request(repo_id="repo-a", query="deployment issue", limit=2)
    with uow_factory() as uow:
        result = execute_read_memory(request, uow)

    ids = _item_ids(result)
    assert len(ids) == 2


def test_read_returns_empty_pack_when_no_candidates_pass(
    uow_factory: Callable[[], PostgresUnitOfWork],
) -> None:
    """read should always return an empty pack when nothing passes retrieval gates."""

    request = _make_read_request(repo_id="repo-a", query="nothing in this database")
    with uow_factory() as uow:
        result = execute_read_memory(request, uow)

    assert _item_ids(result) == []


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
    assert "pack" in result.data
    pack = result.data["pack"]
    return [
        *[item["memory_id"] for item in pack["direct"]],
        *[item["memory_id"] for item in pack["explicit_related"]],
        *[item["memory_id"] for item in pack["implicit_related"]],
    ]
