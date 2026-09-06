"""Record-write contracts for read-summary telemetry."""

from __future__ import annotations

from collections.abc import Callable
import json

import pytest

from app.core.use_cases.retrieval.read.result import ReadMemoryResult
from tests.operations._shared.handler_calls import handle_read
from tests.operations._shared.read_pipeline_stubs import stub_read_pipeline
from app.infrastructure.db.runtime.uow import PostgresUnitOfWork

pytestmark = pytest.mark.usefixtures("telemetry_db_reset")


def test_read_should_always_append_one_read_summary_row_with_effective_request_metadata(
    uow_factory: Callable[[], PostgresUnitOfWork],
    monkeypatch: pytest.MonkeyPatch,
    assert_relation_exists,
    fetch_relation_rows,
) -> None:
    """read should always append one read summary row with effective request metadata."""

    stub_read_pipeline(monkeypatch, zero_results=False)

    result = handle_read(
        {
            "query": "read summary telemetry",
            "mode": "targeted",
            "kinds": ["problem", "solution", "fact"],
            "limit": 8,
            "include_global": True,
        },
        uow_factory=uow_factory,
        inferred_repo_id="repo-a",
    )

    assert result["status"] == "ok"
    assert_relation_exists("read_invocation_summaries")
    rows = fetch_relation_rows(
        "read_invocation_summaries", order_by="created_at DESC, invocation_id DESC"
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["query_text"] == "read summary telemetry"
    assert row["mode"] == "targeted"
    assert row["requested_limit"] == 8
    assert row["effective_limit"] == 8
    assert row["include_global"] is True
    assert _normalize_jsonish(row["kinds_filter"]) == ["problem", "solution", "fact"]
    assert row["direct_count"] == 1
    assert row["explicit_related_count"] == 1
    assert row["implicit_related_count"] == 1
    assert row["total_returned"] == 3
    assert row["pack_char_count"] > 0
    assert row["pack_token_estimate"] > 0
    assert row["pack_token_estimate_method"] == "json_compact_chars_div4_v1"
    assert row["direct_token_estimate"] > 0
    assert row["explicit_related_token_estimate"] > 0
    assert row["implicit_related_token_estimate"] > 0
    assert row["concept_count"] == 0
    assert row["concept_token_estimate"] > 0
    assert _normalize_jsonish(row["concept_refs_returned"]) == []
    assert _normalize_jsonish(row["concept_facets_returned"]) == []


def test_read_should_always_append_one_read_result_item_row_per_returned_memory_in_display_order(
    uow_factory: Callable[[], PostgresUnitOfWork],
    monkeypatch: pytest.MonkeyPatch,
    assert_relation_exists,
    fetch_relation_rows,
) -> None:
    """read should always append one read result item row per returned memory in display order."""

    stub_read_pipeline(monkeypatch, zero_results=False)

    result = handle_read(
        {"query": "display order telemetry", "mode": "targeted"},
        uow_factory=uow_factory,
        inferred_repo_id="repo-a",
    )

    assert result["status"] == "ok"
    assert_relation_exists("read_result_items")
    rows = fetch_relation_rows(
        "read_result_items", order_by="invocation_id ASC, ordinal ASC"
    )

    assert len(rows) == 3
    assert [row["ordinal"] for row in rows] == [1, 2, 3]
    assert [row["memory_id"] for row in rows] == [
        "direct-1",
        "explicit-1",
        "implicit-1",
    ]


def test_read_should_always_record_kind_section_priority_why_included_and_anchor_metadata_for_each_returned_item(
    uow_factory: Callable[[], PostgresUnitOfWork],
    monkeypatch: pytest.MonkeyPatch,
    assert_relation_exists,
    fetch_relation_rows,
) -> None:
    """read should always record kind, section, priority, why-included, and anchor metadata for each returned item."""

    stub_read_pipeline(monkeypatch, zero_results=False)

    result = handle_read(
        {"query": "item metadata telemetry", "mode": "targeted"},
        uow_factory=uow_factory,
        inferred_repo_id="repo-a",
    )

    assert result["status"] == "ok"
    assert_relation_exists("read_result_items")
    rows = fetch_relation_rows(
        "read_result_items", order_by="invocation_id ASC, ordinal ASC"
    )

    assert len(rows) == 3
    assert rows[0]["kind"] == "problem"
    assert rows[0]["section"] == "direct"
    assert rows[0]["priority"] == 1
    assert rows[0]["why_included"] == "direct_match"
    assert rows[0]["anchor_memory_id"] is None
    assert rows[1]["kind"] == "solution"
    assert rows[1]["section"] == "explicit_related"
    assert rows[1]["priority"] == 2
    assert rows[1]["why_included"] == "association_link"
    assert rows[1]["anchor_memory_id"] == "direct-1"
    assert rows[1]["relation_type"] == "depends_on"
    assert rows[2]["kind"] == "fact"
    assert rows[2]["section"] == "implicit_related"
    assert rows[2]["priority"] == 3
    assert rows[2]["why_included"] == "semantic_neighbor"
    assert rows[2]["anchor_memory_id"] == "direct-1"


def test_read_should_always_record_zero_results_true_when_the_context_pack_is_empty(
    uow_factory: Callable[[], PostgresUnitOfWork],
    monkeypatch: pytest.MonkeyPatch,
    assert_relation_exists,
    fetch_relation_rows,
) -> None:
    """read should always record zero-results true when the context pack is empty."""

    stub_read_pipeline(monkeypatch, zero_results=True)

    result = handle_read(
        {"query": "zero results telemetry", "mode": "targeted"},
        uow_factory=uow_factory,
        inferred_repo_id="repo-a",
    )

    assert result["status"] == "ok"
    assert_relation_exists("read_invocation_summaries")
    rows = fetch_relation_rows(
        "read_invocation_summaries", order_by="created_at DESC, invocation_id DESC"
    )

    assert len(rows) == 1
    assert rows[0]["zero_results"] is True
    assert rows[0]["total_returned"] == 0
    assert rows[0]["direct_count"] == 0
    assert rows[0]["explicit_related_count"] == 0
    assert rows[0]["implicit_related_count"] == 0
    assert rows[0]["pack_char_count"] > 0
    assert rows[0]["pack_token_estimate"] > 0
    assert rows[0]["pack_token_estimate_method"] == "json_compact_chars_div4_v1"
    assert rows[0]["direct_token_estimate"] == 0
    assert rows[0]["explicit_related_token_estimate"] == 0
    assert rows[0]["implicit_related_token_estimate"] == 0
    assert rows[0]["concept_count"] == 0
    assert rows[0]["concept_token_estimate"] > 0


def test_read_summary_should_record_concept_context_telemetry(
    uow_factory: Callable[[], PostgresUnitOfWork],
    monkeypatch: pytest.MonkeyPatch,
    fetch_relation_rows,
) -> None:
    """read summary telemetry should capture concept-context cost fields."""

    monkeypatch.setattr(
        "app.entrypoints.cli.handlers.internal_agent.retrieval.execution.execute_read_memory",
        lambda request, uow, **kwargs: ReadMemoryResult(
            pack={
                "meta": {
                    "mode": "targeted",
                    "limit": 8,
                    "counts": {
                        "direct": 0,
                        "explicit_related": 0,
                        "implicit_related": 0,
                    },
                },
                "direct": [],
                "explicit_related": [],
                "implicit_related": [],
                "concepts": {
                    "mode": "auto",
                    "items": [
                        {
                            "ref": "deposit-addresses",
                            "name": "Deposit Addresses",
                            "kind": "domain",
                            "orientation": "Deposit address orientation.",
                            "key_claims": [
                                {
                                    "type": "definition",
                                    "text": "Deposit address orientation.",
                                }
                            ],
                        }
                    ],
                    "guidance": "Use concept show for details.",
                },
            },
        ),
    )

    result = handle_read(
        {"query": "concept telemetry", "mode": "targeted"},
        uow_factory=uow_factory,
        inferred_repo_id="repo-a",
    )

    assert result["status"] == "ok"
    rows = fetch_relation_rows(
        "read_invocation_summaries", order_by="created_at DESC, invocation_id DESC"
    )
    assert rows[0]["concept_count"] == 1
    assert rows[0]["concept_token_estimate"] > 0
    assert _normalize_jsonish(rows[0]["concept_refs_returned"]) == ["deposit-addresses"]
    assert _normalize_jsonish(rows[0]["concept_facets_returned"]) == []


def _normalize_jsonish(value: object) -> object:
    """Return Python objects for JSON-like DB values."""

    if isinstance(value, str):
        return json.loads(value)
    return value
