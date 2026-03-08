"""Read execution contracts for semantic seed wiring on the live read path."""

from collections.abc import Callable
from typing import Any

import pytest

from app.core.contracts.errors import ErrorCode
from app.core.contracts.requests import MemoryReadRequest
from app.core.use_cases.read_memory import execute_read_memory
from app.periphery.cli.handlers import handle_read
from app.periphery.db.repos.semantic.semantic_retrieval_repo import SemanticRetrievalRepo
from app.periphery.db.uow import PostgresUnitOfWork


def test_read_returns_semantic_direct_matches_through_live_query_embedding_seam_when_lexical_misses(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_read_memory: Callable[..., None],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """read should always return semantic direct matches through the live query-embedding seam when lexical retrieval misses."""

    seed_read_memory(
        memory_id="semantic-hit",
        repo_id="repo-a",
        scope="repo",
        kind="fact",
        text_value="Alpha memory text without keyword overlap.",
    )
    captured: dict[str, list[float]] = {}

    def _query_semantic_spy(
        self,
        *,
        repo_id: str,
        include_global: bool,
        query_vector,
        kinds,
        limit: int,
    ) -> list[dict[str, object]]:
        _ = (self, repo_id, include_global, kinds, limit)
        captured["query_vector"] = list(query_vector)
        if not query_vector:
            return []
        return [{"memory_id": "semantic-hit", "score": 1.0}]

    monkeypatch.setattr(SemanticRetrievalRepo, "query_semantic", _query_semantic_spy)

    request = _make_read_request(
        repo_id="repo-a",
        query="latent semantic regression",
        expand={"semantic_hops": 0},
    )
    with uow_factory() as uow:
        result = execute_read_memory(request, uow)

    assert captured["query_vector"] != []
    assert _item_ids(result) == ["semantic-hit"]


def test_read_fuses_live_semantic_seeds_with_keyword_direct_hits_without_duplicates(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_read_memory: Callable[..., None],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """read should always fuse live semantic seeds with keyword direct hits without duplicates."""

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
    seed_read_memory(
        memory_id="semantic-only",
        repo_id="repo-a",
        scope="repo",
        kind="fact",
        text_value="Alpha memory text without keyword overlap.",
    )
    captured: dict[str, list[float]] = {}

    def _query_semantic_spy(
        self,
        *,
        repo_id: str,
        include_global: bool,
        query_vector,
        kinds,
        limit: int,
    ) -> list[dict[str, object]]:
        _ = (self, repo_id, include_global, kinds, limit)
        captured["query_vector"] = list(query_vector)
        if not query_vector:
            return []
        return [
            {"memory_id": "dual-hit", "score": 1.0},
            {"memory_id": "semantic-only", "score": 0.9},
        ]

    monkeypatch.setattr(SemanticRetrievalRepo, "query_semantic", _query_semantic_spy)

    request = _make_read_request(
        repo_id="repo-a",
        query="rollback deployment",
        expand={"semantic_hops": 0},
    )
    with uow_factory() as uow:
        result = execute_read_memory(request, uow)

    ids = _item_ids(result)
    assert captured["query_vector"] != []
    assert ids.count("dual-hit") == 1
    assert "keyword-only" in ids
    assert "semantic-only" in ids


def test_handle_read_surfaces_query_embedding_failure_as_a_structured_read_error(
    uow_factory: Callable[[], PostgresUnitOfWork],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """read should always surface query-embedding failure as a structured read error rather than silently dropping the semantic lane."""

    def _build_context_pack_raising(*args: Any, **kwargs: Any) -> dict[str, Any]:
        _ = (args, kwargs)
        raise RuntimeError("query embedding failed")

    monkeypatch.setattr("app.core.use_cases.read_memory.build_context_pack", _build_context_pack_raising)

    result = handle_read(_make_read_payload(query="latent semantic regression"), uow_factory=uow_factory)

    assert result["status"] == "error"
    assert result["errors"] == [
        {
            "code": ErrorCode.INTERNAL_ERROR.value,
            "message": "query embedding failed",
            "field": None,
        }
    ]


def _make_read_request(**overrides: object) -> MemoryReadRequest:
    """Build a read request with deterministic defaults and caller overrides."""

    return MemoryReadRequest.model_validate(_make_read_payload(**overrides))


def _make_read_payload(**overrides: object) -> dict[str, object]:
    """Build a read payload with deterministic defaults and caller overrides."""

    payload: dict[str, object] = {
        "op": "read",
        "repo_id": "repo-a",
        "mode": "targeted",
        "query": "deployment issue",
        "include_global": True,
        "limit": 20,
        "expand": {
            "semantic_hops": 2,
            "include_problem_links": False,
            "include_fact_update_links": False,
            "include_association_links": False,
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


def _item_ids(result) -> list[str]:
    """Extract ordered memory IDs from a read operation result."""

    assert result.status == "ok"
    assert "items" in result.data
    return [item["memory_id"] for item in result.data["items"]]
