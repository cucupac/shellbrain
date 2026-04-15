"""Record-write contracts for read-summary telemetry."""

from __future__ import annotations

from collections.abc import Callable
import json

import pytest

from app.periphery.cli.handlers import handle_read
from app.periphery.db.uow import PostgresUnitOfWork

pytestmark = pytest.mark.usefixtures("telemetry_db_reset")


def test_read_should_always_append_one_read_summary_row_with_effective_request_metadata(
    uow_factory: Callable[[], PostgresUnitOfWork],
    monkeypatch: pytest.MonkeyPatch,
    assert_relation_exists,
    fetch_relation_rows,
) -> None:
    """read should always append one read summary row with effective request metadata."""

    _stub_read_pipeline(monkeypatch, zero_results=False)

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
    rows = fetch_relation_rows("read_invocation_summaries", order_by="created_at DESC, invocation_id DESC")

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


def test_read_should_always_append_one_read_result_item_row_per_returned_memory_in_display_order(
    uow_factory: Callable[[], PostgresUnitOfWork],
    monkeypatch: pytest.MonkeyPatch,
    assert_relation_exists,
    fetch_relation_rows,
) -> None:
    """read should always append one read result item row per returned memory in display order."""

    _stub_read_pipeline(monkeypatch, zero_results=False)

    result = handle_read(
        {"query": "display order telemetry", "mode": "targeted"},
        uow_factory=uow_factory,
        inferred_repo_id="repo-a",
    )

    assert result["status"] == "ok"
    assert_relation_exists("read_result_items")
    rows = fetch_relation_rows("read_result_items", order_by="invocation_id ASC, ordinal ASC")

    assert len(rows) == 3
    assert [row["ordinal"] for row in rows] == [1, 2, 3]
    assert [row["memory_id"] for row in rows] == ["direct-1", "explicit-1", "implicit-1"]


def test_read_should_always_record_kind_section_priority_why_included_and_anchor_metadata_for_each_returned_item(
    uow_factory: Callable[[], PostgresUnitOfWork],
    monkeypatch: pytest.MonkeyPatch,
    assert_relation_exists,
    fetch_relation_rows,
) -> None:
    """read should always record kind, section, priority, why-included, and anchor metadata for each returned item."""

    _stub_read_pipeline(monkeypatch, zero_results=False)

    result = handle_read(
        {"query": "item metadata telemetry", "mode": "targeted"},
        uow_factory=uow_factory,
        inferred_repo_id="repo-a",
    )

    assert result["status"] == "ok"
    assert_relation_exists("read_result_items")
    rows = fetch_relation_rows("read_result_items", order_by="invocation_id ASC, ordinal ASC")

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

    _stub_read_pipeline(monkeypatch, zero_results=True)

    result = handle_read(
        {"query": "zero results telemetry", "mode": "targeted"},
        uow_factory=uow_factory,
        inferred_repo_id="repo-a",
    )

    assert result["status"] == "ok"
    assert_relation_exists("read_invocation_summaries")
    rows = fetch_relation_rows("read_invocation_summaries", order_by="created_at DESC, invocation_id DESC")

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


def _stub_read_pipeline(monkeypatch: pytest.MonkeyPatch, *, zero_results: bool) -> None:
    """Patch the read pipeline to return deterministic summary rows."""

    monkeypatch.setattr(
        "app.core.policies.read_policy.pipeline.retrieve_seeds",
        lambda payload, **kwargs: {"semantic": [], "keyword": []},
    )
    monkeypatch.setattr(
        "app.core.policies.read_policy.pipeline.fuse_with_rrf",
        lambda semantic, keyword: []
        if zero_results
        else [
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
        "app.core.policies.read_policy.pipeline.expand_candidates",
        lambda direct_candidates, payload, **kwargs: {"explicit": [], "implicit": []}
        if zero_results
        else {
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
        "app.core.policies.read_policy.pipeline.score_candidates",
        lambda bucketed_candidates, payload: bucketed_candidates,
    )


def _normalize_jsonish(value: object) -> object:
    """Return Python objects for JSON-like DB values."""

    if isinstance(value, str):
        return json.loads(value)
    return value
