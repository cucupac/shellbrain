"""Shared telemetry fixtures and helpers for telemetry-first TDD coverage."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re

import psycopg
import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine


_SAFE_IDENTIFIER = re.compile(r"^[a-z_][a-z0-9_]*$")


def _relation_name(name: str) -> str:
    """Return one validated relation name for raw SQL helpers."""

    if not _SAFE_IDENTIFIER.fullmatch(name):
        raise ValueError(f"Unsafe relation name: {name}")
    return name


@pytest.fixture
def assert_relation_exists(integration_engine: Engine):
    """Provide helper for asserting that one telemetry table or view exists."""

    def _assert(relation_name: str) -> str:
        relation_name = _relation_name(relation_name)
        with integration_engine.connect() as conn:
            relation = conn.execute(
                text("SELECT to_regclass(:qualified_name);"),
                {"qualified_name": f"public.{relation_name}"},
            ).scalar_one()
        assert relation is not None
        return str(relation)

    return _assert


@pytest.fixture
def fetch_relation_rows(integration_engine: Engine):
    """Provide helper for reading rows from one future telemetry relation."""

    def _fetch(
        relation_name: str,
        *,
        where_sql: str = "TRUE",
        params: dict[str, object] | None = None,
        order_by: str | None = None,
    ) -> list[dict[str, object]]:
        relation_name = _relation_name(relation_name)
        order_clause = f" ORDER BY {order_by}" if order_by else ""
        statement = text(f"SELECT * FROM {relation_name} WHERE {where_sql}{order_clause};")
        with integration_engine.connect() as conn:
            return [dict(row) for row in conn.execute(statement, params or {}).mappings().all()]

    return _fetch


@pytest.fixture
def seed_usage_telemetry_dataset(integration_engine: Engine):
    """Provide helper for seeding one deterministic telemetry dataset."""

    def _seed() -> dict[str, str]:
        return seed_usage_telemetry_dataset_via_engine(integration_engine)

    return _seed


@pytest.fixture
def assert_usage_telemetry_dataset(integration_engine: Engine):
    """Provide helper for asserting a seeded telemetry dataset is still intact."""

    def _assert(expected: dict[str, str]) -> None:
        assert_usage_telemetry_dataset_via_engine(integration_engine, expected)

    return _assert


@pytest.fixture
def seed_competing_same_repo_codex_sessions(tmp_path: Path):
    """Provide helper for writing two repo-matching Codex sessions under one search root."""

    def _seed(*, repo_root: Path) -> dict[str, object]:
        thread_ids = [
            "019ce136-e14d-7b80-92bc-be07e4330536",
            "019ce136-e14d-7b80-92bc-be07e4330537",
        ]
        transcript_root = tmp_path / "codex-root" / ".codex" / "sessions" / "2026" / "03" / "18"
        transcript_root.mkdir(parents=True, exist_ok=True)

        transcript_paths: list[Path] = []
        for offset, thread_id in enumerate(thread_ids, start=1):
            transcript_path = transcript_root / f"telemetry-2026-03-18T10-0{offset}-00-{thread_id}.jsonl"
            payload = [
                {
                    "type": "session_meta",
                    "payload": {
                        "id": thread_id,
                        "cwd": str(repo_root.resolve()),
                    },
                },
                {
                    "event_id": f"codex-user-{offset}",
                    "timestamp": f"2026-03-18T10:0{offset}:00Z",
                    "type": "message",
                    "role": "user",
                    "text": f"Telemetry ambiguity {offset}.",
                },
            ]
            transcript_path.write_text("".join(f"{json.dumps(entry)}\n" for entry in payload), encoding="utf-8")
            transcript_paths.append(transcript_path)

        older_path, newer_path = transcript_paths
        os.utime(older_path, (1_742_294_400, 1_742_294_400))
        os.utime(newer_path, (1_742_294_460, 1_742_294_460))

        return {
            "search_roots": [tmp_path / "codex-root" / ".codex" / "sessions"],
            "older_session_key": thread_ids[0],
            "newer_session_key": thread_ids[1],
        }

    return _seed


def seed_usage_telemetry_dataset_via_engine(engine: Engine) -> dict[str, str]:
    """Insert one small but cross-cutting telemetry dataset through raw SQL."""

    expected = {
        "read_invocation_id": "inv-read-1",
        "events_invocation_id": "inv-events-1",
        "create_invocation_id": "inv-create-1",
        "sync_run_id": "sync-1",
        "repo_id": "telemetry-repo",
        "memory_id": "mem-1",
    }
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO operation_invocations (
                    id,
                    command,
                    repo_id,
                    repo_root,
                    no_sync,
                    selected_host_app,
                    selected_host_session_key,
                    selected_thread_id,
                    selected_episode_id,
                    matching_candidate_count,
                    selection_ambiguous,
                    outcome,
                    error_stage,
                    error_code,
                    error_message,
                    total_latency_ms,
                    poller_start_attempted,
                    poller_started,
                    created_at
                ) VALUES (
                    :id,
                    :command,
                    :repo_id,
                    :repo_root,
                    :no_sync,
                    :selected_host_app,
                    :selected_host_session_key,
                    :selected_thread_id,
                    :selected_episode_id,
                    :matching_candidate_count,
                    :selection_ambiguous,
                    :outcome,
                    :error_stage,
                    :error_code,
                    :error_message,
                    :total_latency_ms,
                    :poller_start_attempted,
                    :poller_started,
                    :created_at
                )
                """
            ),
            [
                {
                    "id": expected["read_invocation_id"],
                    "command": "read",
                    "repo_id": expected["repo_id"],
                    "repo_root": "/tmp/telemetry-repo",
                    "no_sync": False,
                    "selected_host_app": "codex",
                    "selected_host_session_key": "session-1",
                    "selected_thread_id": "codex:session-1",
                    "selected_episode_id": "episode-1",
                    "matching_candidate_count": 0,
                    "selection_ambiguous": False,
                    "outcome": "ok",
                    "error_stage": None,
                    "error_code": None,
                    "error_message": None,
                    "total_latency_ms": 12,
                    "poller_start_attempted": True,
                    "poller_started": True,
                    "created_at": "2026-03-18T10:00:00+00:00",
                },
                {
                    "id": expected["events_invocation_id"],
                    "command": "events",
                    "repo_id": expected["repo_id"],
                    "repo_root": "/tmp/telemetry-repo",
                    "no_sync": False,
                    "selected_host_app": "codex",
                    "selected_host_session_key": "session-1",
                    "selected_thread_id": "codex:session-1",
                    "selected_episode_id": "episode-1",
                    "matching_candidate_count": 2,
                    "selection_ambiguous": True,
                    "outcome": "ok",
                    "error_stage": None,
                    "error_code": None,
                    "error_message": None,
                    "total_latency_ms": 21,
                    "poller_start_attempted": False,
                    "poller_started": False,
                    "created_at": "2026-03-18T10:01:00+00:00",
                },
                {
                    "id": expected["create_invocation_id"],
                    "command": "create",
                    "repo_id": expected["repo_id"],
                    "repo_root": "/tmp/telemetry-repo",
                    "no_sync": False,
                    "selected_host_app": "codex",
                    "selected_host_session_key": "session-1",
                    "selected_thread_id": "codex:session-1",
                    "selected_episode_id": "episode-1",
                    "matching_candidate_count": 0,
                    "selection_ambiguous": False,
                    "outcome": "ok",
                    "error_stage": None,
                    "error_code": None,
                    "error_message": None,
                    "total_latency_ms": 33,
                    "poller_start_attempted": False,
                    "poller_started": False,
                    "created_at": "2026-03-18T10:02:00+00:00",
                },
            ],
        )
        conn.execute(
            text(
                """
                INSERT INTO read_invocation_summaries (
                    invocation_id,
                    query_text,
                    mode,
                    requested_limit,
                    effective_limit,
                    include_global,
                    kinds_filter,
                    direct_count,
                    explicit_related_count,
                    implicit_related_count,
                    total_returned,
                    zero_results
                ) VALUES (
                    :invocation_id,
                    :query_text,
                    :mode,
                    :requested_limit,
                    :effective_limit,
                    :include_global,
                    CAST(:kinds_filter AS JSONB),
                    :direct_count,
                    :explicit_related_count,
                    :implicit_related_count,
                    :total_returned,
                    :zero_results
                )
                """
            ),
            {
                "invocation_id": expected["read_invocation_id"],
                "query_text": "why did telemetry fail",
                "mode": "targeted",
                "requested_limit": 8,
                "effective_limit": 8,
                "include_global": True,
                "kinds_filter": json.dumps(["problem", "solution"]),
                "direct_count": 1,
                "explicit_related_count": 1,
                "implicit_related_count": 0,
                "total_returned": 2,
                "zero_results": False,
            },
        )
        conn.execute(
            text(
                """
                INSERT INTO read_result_items (
                    invocation_id,
                    ordinal,
                    memory_id,
                    kind,
                    section,
                    priority,
                    why_included,
                    anchor_memory_id,
                    relation_type
                ) VALUES (
                    :invocation_id,
                    :ordinal,
                    :memory_id,
                    :kind,
                    :section,
                    :priority,
                    :why_included,
                    :anchor_memory_id,
                    :relation_type
                )
                """
            ),
            [
                {
                    "invocation_id": expected["read_invocation_id"],
                    "ordinal": 1,
                    "memory_id": expected["memory_id"],
                    "kind": "problem",
                    "section": "direct",
                    "priority": 1,
                    "why_included": "direct_match",
                    "anchor_memory_id": None,
                    "relation_type": None,
                },
                {
                    "invocation_id": expected["read_invocation_id"],
                    "ordinal": 2,
                    "memory_id": "mem-2",
                    "kind": "solution",
                    "section": "explicit_related",
                    "priority": 2,
                    "why_included": "association_link",
                    "anchor_memory_id": expected["memory_id"],
                    "relation_type": "depends_on",
                },
            ],
        )
        conn.execute(
            text(
                """
                INSERT INTO write_invocation_summaries (
                    invocation_id,
                    operation_command,
                    target_memory_id,
                    target_kind,
                    update_type,
                    scope,
                    evidence_ref_count,
                    planned_effect_count,
                    created_memory_count,
                    archived_memory_count,
                    utility_observation_count,
                    association_effect_count,
                    fact_update_count
                ) VALUES (
                    :invocation_id,
                    :operation_command,
                    :target_memory_id,
                    :target_kind,
                    :update_type,
                    :scope,
                    :evidence_ref_count,
                    :planned_effect_count,
                    :created_memory_count,
                    :archived_memory_count,
                    :utility_observation_count,
                    :association_effect_count,
                    :fact_update_count
                )
                """
            ),
            {
                "invocation_id": expected["create_invocation_id"],
                "operation_command": "create",
                "target_memory_id": expected["memory_id"],
                "target_kind": "problem",
                "update_type": None,
                "scope": "repo",
                "evidence_ref_count": 1,
                "planned_effect_count": 3,
                "created_memory_count": 1,
                "archived_memory_count": 0,
                "utility_observation_count": 0,
                "association_effect_count": 1,
                "fact_update_count": 0,
            },
        )
        conn.execute(
            text(
                """
                INSERT INTO write_effect_items (
                    invocation_id,
                    ordinal,
                    effect_type,
                    repo_id,
                    primary_memory_id,
                    secondary_memory_id,
                    params_json
                ) VALUES (
                    :invocation_id,
                    :ordinal,
                    :effect_type,
                    :repo_id,
                    :primary_memory_id,
                    :secondary_memory_id,
                    CAST(:params_json AS JSONB)
                )
                """
            ),
            [
                {
                    "invocation_id": expected["create_invocation_id"],
                    "ordinal": 1,
                    "effect_type": "memory_created",
                    "repo_id": expected["repo_id"],
                    "primary_memory_id": expected["memory_id"],
                    "secondary_memory_id": None,
                    "params_json": json.dumps({"kind": "problem"}),
                },
                {
                    "invocation_id": expected["create_invocation_id"],
                    "ordinal": 2,
                    "effect_type": "association_edge_created",
                    "repo_id": expected["repo_id"],
                    "primary_memory_id": expected["memory_id"],
                    "secondary_memory_id": "mem-2",
                    "params_json": json.dumps({"relation_type": "depends_on"}),
                },
            ],
        )
        conn.execute(
            text(
                """
                INSERT INTO episode_sync_runs (
                    id,
                    source,
                    invocation_id,
                    repo_id,
                    host_app,
                    host_session_key,
                    thread_id,
                    episode_id,
                    transcript_path,
                    outcome,
                    error_stage,
                    error_message,
                    duration_ms,
                    imported_event_count,
                    total_event_count,
                    user_event_count,
                    assistant_event_count,
                    tool_event_count,
                    system_event_count
                ) VALUES (
                    :id,
                    :source,
                    :invocation_id,
                    :repo_id,
                    :host_app,
                    :host_session_key,
                    :thread_id,
                    :episode_id,
                    :transcript_path,
                    :outcome,
                    :error_stage,
                    :error_message,
                    :duration_ms,
                    :imported_event_count,
                    :total_event_count,
                    :user_event_count,
                    :assistant_event_count,
                    :tool_event_count,
                    :system_event_count
                )
                """
            ),
            {
                "id": expected["sync_run_id"],
                "source": "events_inline",
                "invocation_id": expected["events_invocation_id"],
                "repo_id": expected["repo_id"],
                "host_app": "codex",
                "host_session_key": "session-1",
                "thread_id": "codex:session-1",
                "episode_id": "episode-1",
                "transcript_path": "/tmp/telemetry-repo/.codex/session-1.jsonl",
                "outcome": "ok",
                "error_stage": None,
                "error_message": None,
                "duration_ms": 9,
                "imported_event_count": 3,
                "total_event_count": 3,
                "user_event_count": 1,
                "assistant_event_count": 1,
                "tool_event_count": 1,
                "system_event_count": 0,
            },
        )
        conn.execute(
            text(
                """
                INSERT INTO episode_sync_tool_types (
                    sync_run_id,
                    tool_type,
                    event_count
                ) VALUES (
                    :sync_run_id,
                    :tool_type,
                    :event_count
                )
                """
            ),
            {
                "sync_run_id": expected["sync_run_id"],
                "tool_type": "exec_command",
                "event_count": 1,
            },
        )
    return expected


def assert_usage_telemetry_dataset_via_engine(engine: Engine, expected: dict[str, str]) -> None:
    """Assert that the sentinel telemetry dataset exists after a durability operation."""

    with engine.connect() as conn:
        operation_rows = conn.execute(text("SELECT * FROM operation_invocations ORDER BY id;")).mappings().all()
        read_rows = conn.execute(text("SELECT * FROM read_invocation_summaries ORDER BY invocation_id;")).mappings().all()
        read_item_rows = conn.execute(text("SELECT * FROM read_result_items ORDER BY invocation_id, ordinal;")).mappings().all()
        write_rows = conn.execute(text("SELECT * FROM write_invocation_summaries ORDER BY invocation_id;")).mappings().all()
        write_effect_rows = conn.execute(text("SELECT * FROM write_effect_items ORDER BY invocation_id, ordinal;")).mappings().all()
        sync_rows = conn.execute(text("SELECT * FROM episode_sync_runs ORDER BY id;")).mappings().all()
        sync_tool_rows = conn.execute(text("SELECT * FROM episode_sync_tool_types ORDER BY sync_run_id, tool_type;")).mappings().all()

    assert {row["id"] for row in operation_rows} == {
        expected["create_invocation_id"],
        expected["events_invocation_id"],
        expected["read_invocation_id"],
    }
    assert [row["invocation_id"] for row in read_rows] == [expected["read_invocation_id"]]
    assert [row["invocation_id"] for row in write_rows] == [expected["create_invocation_id"]]
    assert {row["memory_id"] for row in read_item_rows} >= {expected["memory_id"]}
    assert {row["primary_memory_id"] for row in write_effect_rows} >= {expected["memory_id"]}
    assert [row["id"] for row in sync_rows] == [expected["sync_run_id"]]
    assert [row["tool_type"] for row in sync_tool_rows] == ["exec_command"]


def seed_usage_telemetry_dataset_via_dsn(dsn: str) -> dict[str, str]:
    """Insert the sentinel telemetry dataset into one explicit SQLAlchemy DSN."""

    from shellbrain.periphery.db.engine import get_engine

    engine = get_engine(dsn)
    try:
        return seed_usage_telemetry_dataset_via_engine(engine)
    finally:
        engine.dispose()


def assert_usage_telemetry_dataset_via_dsn(dsn: str, expected: dict[str, str]) -> None:
    """Assert the sentinel telemetry dataset against one explicit SQLAlchemy DSN."""

    from shellbrain.periphery.db.engine import get_engine

    engine = get_engine(dsn)
    try:
        assert_usage_telemetry_dataset_via_engine(engine, expected)
    finally:
        engine.dispose()


def relation_exists_via_dsn(dsn: str, relation_name: str) -> bool:
    """Return whether one table or view exists in the target database."""

    relation_name = _relation_name(relation_name)
    raw_dsn = dsn.replace("+psycopg", "")
    with psycopg.connect(raw_dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass(%s);", (f"public.{relation_name}",))
            return cur.fetchone()[0] is not None
