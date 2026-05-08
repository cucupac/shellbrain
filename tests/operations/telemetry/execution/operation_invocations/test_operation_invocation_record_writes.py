"""Record-write contracts for operation-level telemetry invocations."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from app.core.entities.memory import MemoryKind, MemoryScope
import app.entrypoints.cli.main as cli_main
from app.startup.agent_operations import handle_create, handle_events, handle_read, handle_update
from app.infrastructure.db.uow import PostgresUnitOfWork

pytestmark = pytest.mark.usefixtures("telemetry_db_reset")


def test_read_should_always_append_one_operation_invocation_row_with_command_repo_id_outcome_and_latency_fields(
    uow_factory: Callable[[], PostgresUnitOfWork],
    monkeypatch: pytest.MonkeyPatch,
    assert_relation_exists,
    fetch_relation_rows,
) -> None:
    """read should always append one operation invocation row with command, repo_id, outcome, and latency fields."""

    _stub_read_pipeline(monkeypatch, zero_results=False)

    result = handle_read(
        {"query": "telemetry read invocation", "mode": "targeted", "limit": 8, "include_global": True},
        uow_factory=uow_factory,
        inferred_repo_id="repo-a",
    )

    assert result["status"] == "ok"
    assert_relation_exists("operation_invocations")
    rows = fetch_relation_rows(
        "operation_invocations",
        where_sql="command = :command",
        params={"command": "read"},
        order_by="created_at DESC, id DESC",
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["command"] == "read"
    assert row["repo_id"] == "repo-a"
    assert row["outcome"] == "ok"
    assert row["total_latency_ms"] is not None


def test_create_should_always_append_one_operation_invocation_row_with_command_repo_id_outcome_and_latency_fields(
    uow_factory: Callable[[], PostgresUnitOfWork],
    stub_embedding_provider,
    seed_default_evidence_events,
    assert_relation_exists,
    fetch_relation_rows,
) -> None:
    """create should always append one operation invocation row with command, repo_id, outcome, and latency fields."""

    seed_default_evidence_events(repo_id="repo-a")

    result = handle_create(
        {
            "memory": {
                "text": "Telemetry create invocation.",
                "kind": "problem",
                "evidence_refs": ["session://1"],
            }
        },
        uow_factory=uow_factory,
        embedding_provider_factory=lambda: stub_embedding_provider,
        embedding_model="stub-v1",
        inferred_repo_id="repo-a",
        defaults={"scope": "repo"},
    )

    assert result["status"] == "ok"
    assert_relation_exists("operation_invocations")
    rows = fetch_relation_rows(
        "operation_invocations",
        where_sql="command = :command",
        params={"command": "create"},
        order_by="created_at DESC, id DESC",
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["command"] == "create"
    assert row["repo_id"] == "repo-a"
    assert row["outcome"] == "ok"
    assert row["total_latency_ms"] is not None


def test_update_should_always_append_one_operation_invocation_row_with_command_repo_id_outcome_and_latency_fields(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_memory,
    assert_relation_exists,
    fetch_relation_rows,
) -> None:
    """update should always append one operation invocation row with command, repo_id, outcome, and latency fields."""

    seed_memory(
        memory_id="memory-1",
        repo_id="repo-a",
        scope=MemoryScope.REPO,
        kind=MemoryKind.FACT,
        text_value="Telemetry update target.",
    )

    result = handle_update(
        {
            "memory_id": "memory-1",
            "update": {
                "type": "archive_state",
                "archived": True,
            },
        },
        uow_factory=uow_factory,
        inferred_repo_id="repo-a",
    )

    assert result["status"] == "ok"
    assert_relation_exists("operation_invocations")
    rows = fetch_relation_rows(
        "operation_invocations",
        where_sql="command = :command",
        params={"command": "update"},
        order_by="created_at DESC, id DESC",
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["command"] == "update"
    assert row["repo_id"] == "repo-a"
    assert row["outcome"] == "ok"
    assert row["total_latency_ms"] is not None


def test_events_should_always_append_one_operation_invocation_row_with_the_resolved_host_session_thread_and_episode_ids(
    codex_transcript_fixture: dict[str, object],
    uow_factory: Callable[[], PostgresUnitOfWork],
    assert_relation_exists,
    fetch_relation_rows,
) -> None:
    """events should always append one operation invocation row with the resolved host, session, thread, and episode ids."""

    result = handle_events(
        {},
        uow_factory=uow_factory,
        inferred_repo_id="shellbrain",
        repo_root=Path.cwd().resolve(),
        search_roots_by_host={
            "codex": list(codex_transcript_fixture["search_roots"]),
            "claude_code": [],
        },
    )

    assert result["status"] == "ok"
    assert_relation_exists("operation_invocations")
    rows = fetch_relation_rows(
        "operation_invocations",
        where_sql="command = :command",
        params={"command": "events"},
        order_by="created_at DESC, id DESC",
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["selected_host_app"] == "codex"
    assert row["selected_host_session_key"] == codex_transcript_fixture["host_session_key"]
    assert row["selected_thread_id"] == codex_transcript_fixture["canonical_thread_id"]
    assert row["selected_episode_id"] == result["data"]["episode_id"]


def test_operational_invocations_should_always_record_whether_no_sync_was_used(
    tmp_path: Path,
    uow_factory: Callable[[], PostgresUnitOfWork],
    monkeypatch: pytest.MonkeyPatch,
    assert_relation_exists,
    fetch_relation_rows,
) -> None:
    """operational invocations should always record whether no-sync was used."""

    repo_root = tmp_path / "telemetry-no-sync-repo"
    repo_root.mkdir()
    _stub_read_pipeline(monkeypatch, zero_results=False)
    monkeypatch.setattr("app.startup.use_cases.get_uow_factory", lambda: uow_factory)
    monkeypatch.setattr(cli_main, "_print_operation_result", lambda result: None)
    monkeypatch.setattr(cli_main, "_maybe_start_sync", lambda repo_context: None)

    exit_code = cli_main.main(
        [
            "--repo-root",
            str(repo_root),
            "--repo-id",
            "repo-a",
            "read",
            "--no-sync",
            "--json",
            '{"query":"telemetry no-sync","mode":"targeted"}',
        ]
    )

    assert exit_code == 0
    assert_relation_exists("operation_invocations")
    rows = fetch_relation_rows(
        "operation_invocations",
        where_sql="command = :command",
        params={"command": "read"},
        order_by="created_at DESC, id DESC",
    )

    assert len(rows) == 1
    assert rows[0]["no_sync"] is True


def test_repo_matching_multi_session_discovery_should_always_record_candidate_count_and_selection_ambiguous_when_more_than_one_session_matches(
    tmp_path: Path,
    seed_competing_same_repo_codex_sessions,
    uow_factory: Callable[[], PostgresUnitOfWork],
    assert_relation_exists,
    fetch_relation_rows,
) -> None:
    """repo-matching multi-session discovery should always record candidate count and selection_ambiguous when more than one session matches."""

    repo_root = tmp_path / "telemetry-ambiguity-repo"
    repo_root.mkdir()
    competing = seed_competing_same_repo_codex_sessions(repo_root=repo_root)

    result = handle_events(
        {},
        uow_factory=uow_factory,
        inferred_repo_id="telemetry-ambiguity-repo",
        repo_root=repo_root,
        search_roots_by_host={
            "codex": list(competing["search_roots"]),
            "claude_code": [],
        },
    )

    assert result["status"] == "ok"
    assert_relation_exists("operation_invocations")
    rows = fetch_relation_rows(
        "operation_invocations",
        where_sql="command = :command",
        params={"command": "events"},
        order_by="created_at DESC, id DESC",
    )

    assert len(rows) == 1
    assert rows[0]["matching_candidate_count"] == 2
    assert rows[0]["selection_ambiguous"] is True


def _stub_read_pipeline(monkeypatch: pytest.MonkeyPatch, *, zero_results: bool) -> None:
    """Patch the read pipeline to return deterministic candidate sets."""

    monkeypatch.setattr(
        "app.core.use_cases.memory_retrieval.context_pack_pipeline.retrieve_seeds",
        lambda payload, **kwargs: {"semantic": [], "keyword": []},
    )
    monkeypatch.setattr(
        "app.core.use_cases.memory_retrieval.context_pack_pipeline.fuse_with_rrf",
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
        "app.core.use_cases.memory_retrieval.context_pack_pipeline.expand_candidates",
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
            "implicit": [],
        },
    )
    monkeypatch.setattr(
        "app.core.use_cases.memory_retrieval.context_pack_pipeline.score_candidates",
        lambda bucketed_candidates, payload: bucketed_candidates,
    )
