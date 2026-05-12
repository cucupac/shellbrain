"""Record-write contracts for recall telemetry."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from sqlalchemy import text

from app.core.use_cases.retrieval.read.result import ReadMemoryResult
from tests.operations._shared.handler_calls import handle_recall
from app.infrastructure.db.runtime.uow import PostgresUnitOfWork

pytestmark = pytest.mark.usefixtures("telemetry_db_reset")


def test_recall_schema_should_create_summary_and_source_tables_with_source_item_primary_key(
    assert_relation_exists,
    integration_engine,
) -> None:
    """recall telemetry tables should exist with source items keyed by invocation and ordinal."""

    assert_relation_exists("recall_invocation_summaries")
    assert_relation_exists("recall_source_items")
    assert_relation_exists("inner_agent_invocations")

    with integration_engine.connect() as conn:
        primary_key_columns = conn.execute(
            text(
                """
                SELECT array_agg(att.attname ORDER BY keyed.ordinality)
                  FROM pg_constraint con
                  JOIN pg_class rel ON rel.oid = con.conrelid
                  JOIN unnest(con.conkey) WITH ORDINALITY AS keyed(attnum, ordinality) ON TRUE
                  JOIN pg_attribute att ON att.attrelid = rel.oid AND att.attnum = keyed.attnum
                 WHERE rel.relname = 'recall_source_items'
                   AND con.contype = 'p';
                """
            )
        ).scalar_one()
        recall_summary_fk_count = conn.execute(
            text(
                """
                SELECT count(*)
                  FROM pg_constraint con
                  JOIN pg_class rel ON rel.oid = con.conrelid
                 WHERE rel.relname = 'recall_invocation_summaries'
                   AND con.contype = 'f';
                """
            )
        ).scalar_one()

    assert primary_key_columns == ["invocation_id", "ordinal"]
    assert recall_summary_fk_count == 1


def test_recall_command_telemetry_can_be_inserted_after_migration(
    integration_engine,
) -> None:
    """operation invocation command constraints should allow recall rows."""

    with integration_engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO operation_invocations (
                    id,
                    command,
                    repo_id,
                    repo_root,
                    no_sync,
                    outcome,
                    total_latency_ms,
                    poller_start_attempted,
                    poller_started
                ) VALUES (
                    'inv-recall-direct',
                    'recall',
                    'repo-a',
                    '/tmp/repo-a',
                    FALSE,
                    'ok',
                    1,
                    FALSE,
                    FALSE
                );
                """
            )
        )


def test_successful_recall_should_write_recall_summary_source_items_and_no_read_telemetry(
    uow_factory: Callable[[], PostgresUnitOfWork],
    monkeypatch: pytest.MonkeyPatch,
    fetch_relation_rows,
) -> None:
    """successful recall should persist recall-specific telemetry without normal read rows."""

    captured = _stub_internal_read(monkeypatch, pack=_candidate_pack())

    result = handle_recall(
        {
            "query": "recall telemetry",
            "limit": 2,
            "current_problem": _current_problem(),
        },
        uow_factory=uow_factory,
        inferred_repo_id="repo-a",
    )

    assert result["status"] == "ok"
    assert "_telemetry" not in result["data"]
    assert result["data"]["fallback_reason"] is None
    assert len(result["data"]["brief"]["sources"]) == 3
    read_request = captured["request"]
    assert read_request.op == "read"
    assert read_request.mode == "targeted"
    assert read_request.query == "recall telemetry"
    assert read_request.limit == 2

    operation_rows = fetch_relation_rows(
        "operation_invocations", order_by="created_at DESC, id DESC"
    )
    assert len(operation_rows) == 1
    assert operation_rows[0]["command"] == "recall"
    assert operation_rows[0]["outcome"] == "ok"

    summary_rows = fetch_relation_rows("recall_invocation_summaries")
    assert len(summary_rows) == 1
    assert summary_rows[0]["query_text"] == "recall telemetry"
    assert (
        summary_rows[0]["candidate_token_estimate"]
        > summary_rows[0]["brief_token_estimate"]
        > 0
    )
    assert summary_rows[0]["fallback_reason"] is None
    assert summary_rows[0]["provider"] == "codex"
    assert summary_rows[0]["model"] == "gpt-5.4-mini"
    assert summary_rows[0]["reasoning"] == "low"
    assert summary_rows[0]["private_read_count"] == 0
    assert summary_rows[0]["concept_expansion_count"] == 0

    source_rows = fetch_relation_rows("recall_source_items", order_by="ordinal ASC")
    assert [row["ordinal"] for row in source_rows] == [1, 2, 3]
    source_tuples = [
        (
            row["source_kind"],
            row["source_id"],
            row["input_section"],
            row["output_section"],
        )
        for row in source_rows
    ]
    assert source_tuples == [
        ("memory", "direct-1", "direct", "sources"),
        ("memory", "explicit-1", "explicit_related", "sources"),
        ("concept", "concept-1", "concept_orientation", "sources"),
    ]

    assert fetch_relation_rows("read_invocation_summaries") == []
    assert fetch_relation_rows("read_result_items") == []
    inner_agent_rows = fetch_relation_rows("inner_agent_invocations")
    assert len(inner_agent_rows) == 1
    assert inner_agent_rows[0]["agent_name"] == "build_context"
    assert inner_agent_rows[0]["provider"] == "codex"
    assert inner_agent_rows[0]["status"] == "provider_unavailable"
    assert inner_agent_rows[0]["fallback_used"] is True


def test_no_candidate_recall_should_write_no_candidates_fallback(
    uow_factory: Callable[[], PostgresUnitOfWork],
    monkeypatch: pytest.MonkeyPatch,
    fetch_relation_rows,
) -> None:
    """recall should write one fallback summary when no memory or concept candidates exist."""

    _stub_internal_read(monkeypatch, pack=_empty_pack())

    result = handle_recall(
        {"query": "nothing matches", "current_problem": _current_problem()},
        uow_factory=uow_factory,
        inferred_repo_id="repo-a",
    )

    assert result["status"] == "ok"
    assert result["data"]["fallback_reason"] == "no_candidates"
    assert result["data"]["brief"]["sources"] == []
    assert result["data"]["brief"]["gaps"]

    summary_rows = fetch_relation_rows("recall_invocation_summaries")
    assert len(summary_rows) == 1
    assert summary_rows[0]["query_text"] == "nothing matches"
    assert summary_rows[0]["fallback_reason"] == "no_candidates"
    assert summary_rows[0]["candidate_token_estimate"] > 0
    assert summary_rows[0]["brief_token_estimate"] > 0
    assert fetch_relation_rows("recall_source_items") == []


def test_recall_should_not_mutate_knowledge_state(
    uow_factory: Callable[[], PostgresUnitOfWork],
    monkeypatch: pytest.MonkeyPatch,
    fetch_relation_rows,
) -> None:
    """recall should not write memories, concepts, utility observations, or problem runs."""

    _stub_internal_read(monkeypatch, pack=_candidate_pack())
    before = _knowledge_counts(fetch_relation_rows)

    result = handle_recall(
        {"query": "read-only recall", "current_problem": _current_problem()},
        uow_factory=uow_factory,
        inferred_repo_id="repo-a",
    )

    assert result["status"] == "ok"
    assert _knowledge_counts(fetch_relation_rows) == before


def test_recall_token_estimates_should_be_deterministic(
    uow_factory: Callable[[], PostgresUnitOfWork],
    monkeypatch: pytest.MonkeyPatch,
    fetch_relation_rows,
) -> None:
    """candidate and brief token estimates should be stable for identical recall output."""

    _stub_internal_read(monkeypatch, pack=_candidate_pack())

    for _ in range(2):
        result = handle_recall(
            {
                "query": "deterministic estimates",
                "current_problem": _current_problem(),
            },
            uow_factory=uow_factory,
            inferred_repo_id="repo-a",
        )
        assert result["status"] == "ok"

    rows = fetch_relation_rows(
        "recall_invocation_summaries", order_by="created_at ASC, invocation_id ASC"
    )
    estimates = {
        (row["candidate_token_estimate"], row["brief_token_estimate"]) for row in rows
    }
    assert len(rows) == 2
    assert len(estimates) == 1


def _stub_internal_read(
    monkeypatch: pytest.MonkeyPatch, *, pack: dict
) -> dict[str, object]:
    """Patch recall's internal read dependency and capture the forwarded request."""

    captured: dict[str, object] = {}
    monkeypatch.setattr(
        "app.startup.operation_dependencies.get_build_context_inner_agent_runner",
        lambda: None,
    )

    def _fake_execute_read_memory(request, uow, **kwargs) -> ReadMemoryResult:
        del kwargs
        captured["request"] = request
        return ReadMemoryResult(pack=pack)

    monkeypatch.setattr(
        "app.core.use_cases.retrieval.build_context.execute.execute_read_memory",
        _fake_execute_read_memory,
    )
    return captured


def _candidate_pack() -> dict:
    """Return one deterministic read pack with memory and concept candidates."""

    return {
        "meta": {
            "mode": "targeted",
            "limit": 2,
            "counts": {"direct": 1, "explicit_related": 1, "implicit_related": 0},
        },
        "direct": [
            {
                "memory_id": "direct-1",
                "kind": "problem",
                "text": "Primary recall memory with enough private context to exceed the brief size.",
                "why_included": "direct_match",
            }
        ],
        "explicit_related": [
            {
                "memory_id": "explicit-1",
                "kind": "solution",
                "text": "Related solution memory with detailed private context.",
                "why_included": "association_link",
            }
        ],
        "implicit_related": [],
        "concepts": {
            "mode": "auto",
            "items": [
                {
                    "id": "concept-1",
                    "ref": "recall-telemetry",
                    "name": "Recall Telemetry",
                    "kind": "workflow",
                    "orientation": "Recall transforms private candidate context into a compact worker brief.",
                }
            ],
            "missing_refs": [],
            "guidance": "Use the compact brief.",
        },
    }


def _current_problem() -> dict[str, str]:
    """Return mandatory recall problem context for telemetry handler tests."""

    return {
        "goal": "verify recall telemetry",
        "surface": "telemetry",
        "obstacle": "ensure summaries are written",
        "hypothesis": "fallback recall path still emits telemetry",
    }


def _empty_pack() -> dict:
    """Return one deterministic read pack with no memory or concept candidates."""

    return {
        "meta": {
            "mode": "targeted",
            "limit": 8,
            "counts": {"direct": 0, "explicit_related": 0, "implicit_related": 0},
        },
        "direct": [],
        "explicit_related": [],
        "implicit_related": [],
        "concepts": {
            "mode": "auto",
            "items": [],
            "missing_refs": [],
            "guidance": "No concepts matched.",
        },
    }


def _knowledge_counts(fetch_relation_rows) -> dict[str, int]:
    """Return row counts for state tables recall must not mutate."""

    return {
        name: len(fetch_relation_rows(name))
        for name in ("memories", "concepts", "utility_observations", "problem_runs")
    }
