"""Read execution contracts for grouped context-pack JSON output."""

from collections.abc import Callable

import pytest

from app.core.contracts.requests import MemoryReadRequest
from app.core.use_cases.memory_retrieval.read_memory import execute_read_memory
from app.infrastructure.db.uow import PostgresUnitOfWork


def test_read_context_pack_should_always_return_grouped_sections_under_data_pack(
    uow_factory: Callable[[], PostgresUnitOfWork],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """read context pack should always return grouped sections under data.pack."""

    result = _execute_stubbed_read(uow_factory=uow_factory, monkeypatch=monkeypatch)

    assert "pack" in result.data


def test_read_context_pack_should_always_order_sections_as_meta_direct_explicit_related_implicit_then_concepts(
    uow_factory: Callable[[], PostgresUnitOfWork],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """read context pack should always order sections as meta, memory sections, then concepts."""

    result = _execute_stubbed_read(uow_factory=uow_factory, monkeypatch=monkeypatch)

    assert list(result.data["pack"].keys()) == ["meta", "direct", "explicit_related", "implicit_related", "concepts"]


def test_read_context_pack_should_always_include_stable_concepts_section(
    uow_factory: Callable[[], PostgresUnitOfWork],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """read context pack should always include a stable concepts section."""

    result = _execute_stubbed_read(uow_factory=uow_factory, monkeypatch=monkeypatch)

    assert result.data["pack"]["concepts"] == {
        "mode": "auto",
        "items": [],
        "missing_refs": [],
        "guidance": "No strong concept match found.",
    }


def test_read_context_pack_should_never_echo_the_request_query_in_meta(
    uow_factory: Callable[[], PostgresUnitOfWork],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """read context pack should never echo the request query in meta."""

    result = _execute_stubbed_read(uow_factory=uow_factory, monkeypatch=monkeypatch)

    assert "query" not in result.data["pack"]["meta"]


def test_read_context_pack_should_always_assign_global_priority_values_in_displayed_order(
    uow_factory: Callable[[], PostgresUnitOfWork],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """read context pack should always assign global priority values in displayed order."""

    result = _execute_stubbed_read(uow_factory=uow_factory, monkeypatch=monkeypatch)

    priorities = [
        item["priority"]
        for section in ("direct", "explicit_related", "implicit_related")
        for item in result.data["pack"][section]
    ]
    assert priorities == [1, 2, 3]


def test_read_context_pack_should_always_include_kind_and_text_for_each_returned_memory(
    uow_factory: Callable[[], PostgresUnitOfWork],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """read context pack should always include kind and text for each returned memory."""

    result = _execute_stubbed_read(uow_factory=uow_factory, monkeypatch=monkeypatch)

    for section in ("direct", "explicit_related", "implicit_related"):
        for item in result.data["pack"][section]:
            assert "kind" in item
            assert "text" in item


def test_read_context_pack_should_always_include_why_included_for_every_item(
    uow_factory: Callable[[], PostgresUnitOfWork],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """read context pack should always include why_included for every item."""

    result = _execute_stubbed_read(uow_factory=uow_factory, monkeypatch=monkeypatch)

    for section in ("direct", "explicit_related", "implicit_related"):
        for item in result.data["pack"][section]:
            assert "why_included" in item


def test_read_context_pack_should_always_include_anchor_memory_id_only_for_non_direct_items(
    uow_factory: Callable[[], PostgresUnitOfWork],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """read context pack should always include anchor_memory_id only for non-direct items."""

    result = _execute_stubbed_read(uow_factory=uow_factory, monkeypatch=monkeypatch)

    assert "anchor_memory_id" not in result.data["pack"]["direct"][0]
    assert result.data["pack"]["explicit_related"][0]["anchor_memory_id"] == "direct-1"
    assert result.data["pack"]["implicit_related"][0]["anchor_memory_id"] == "direct-1"


def test_read_context_pack_should_always_include_relation_type_only_for_association_link_items(
    uow_factory: Callable[[], PostgresUnitOfWork],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """read context pack should always include relation_type only for association-link items."""

    result = _execute_stubbed_read(uow_factory=uow_factory, monkeypatch=monkeypatch)

    assert result.data["pack"]["explicit_related"][0]["relation_type"] == "depends_on"
    assert "relation_type" not in result.data["pack"]["direct"][0]
    assert "relation_type" not in result.data["pack"]["implicit_related"][0]


def test_read_context_pack_should_always_omit_scenarios_in_this_slice(
    uow_factory: Callable[[], PostgresUnitOfWork],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """read context pack should always omit scenarios in this slice."""

    result = _execute_stubbed_read(uow_factory=uow_factory, monkeypatch=monkeypatch)

    assert "scenarios" not in result.data["pack"]


def _execute_stubbed_read(
    *,
    uow_factory: Callable[[], PostgresUnitOfWork],
    monkeypatch: pytest.MonkeyPatch,
):
    """Execute one read call with deterministic scored candidates for JSON-shape tests."""

    monkeypatch.setattr(
        "app.core.use_cases.memory_retrieval.context_pack_pipeline.retrieve_seeds",
        lambda payload, **kwargs: {"semantic": [], "keyword": []},
    )
    monkeypatch.setattr(
        "app.core.use_cases.memory_retrieval.context_pack_pipeline.fuse_with_rrf",
        lambda semantic, keyword: [
            {
                "memory_id": "direct-1",
                "rrf_score": 0.99,
                "score": 0.99,
                "kind": "problem",
                "text": "Primary direct memory.",
                "why_included": "direct_match",
            }
        ],
    )
    monkeypatch.setattr(
        "app.core.use_cases.memory_retrieval.context_pack_pipeline.expand_candidates",
        lambda direct_candidates, payload, **kwargs: {
            "explicit": [
                {
                    "memory_id": "explicit-1",
                    "score": 0.88,
                    "kind": "solution",
                    "text": "Linked association memory.",
                    "why_included": "association_link",
                    "anchor_memory_id": "direct-1",
                    "relation_type": "depends_on",
                }
            ],
            "implicit": [
                {
                    "memory_id": "implicit-1",
                    "score": 0.77,
                    "kind": "fact",
                    "text": "Nearby semantic memory.",
                    "why_included": "semantic_neighbor",
                    "anchor_memory_id": "direct-1",
                }
            ],
        },
    )
    monkeypatch.setattr(
        "app.core.use_cases.memory_retrieval.context_pack_pipeline.score_candidates",
        lambda bucketed_candidates, payload: bucketed_candidates,
    )

    with uow_factory() as uow:
        return execute_read_memory(
            MemoryReadRequest.model_validate(
                {
                    "op": "read",
                    "repo_id": "repo-a",
                    "mode": "targeted",
                    "query": "rollback deployment issue",
                    "include_global": True,
                    "limit": 8,
                    "expand": {
                        "semantic_hops": 0,
                        "include_problem_links": True,
                        "include_fact_update_links": True,
                        "include_association_links": True,
                        "max_association_depth": 2,
                        "min_association_strength": 0.25,
                    },
                }
            ),
            uow,
        )
