"""Backfill contracts for retroactive model-usage telemetry."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from sqlalchemy import text

from app.startup.model_usage_backfill import backfill_model_usage
from app.periphery.db.uow import PostgresUnitOfWork


def test_backfill_model_usage_should_import_rows_for_linked_historical_sessions(
    codex_transcript_fixture: dict[str, object],
    integration_engine,
    uow_factory: Callable[[], PostgresUnitOfWork],
    assert_relation_exists,
    fetch_relation_rows,
    monkeypatch,
) -> None:
    """backfill-token-usage should always import model_usage rows from linked host transcripts."""

    monkeypatch.setattr("app.startup.model_usage_backfill.get_uow_factory", lambda: uow_factory)
    with integration_engine.begin() as conn:
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
                    'sync-backfill-1',
                    'poller',
                    NULL,
                    'shellbrain',
                    'codex',
                    :host_session_key,
                    :thread_id,
                    'episode-backfill-1',
                    :transcript_path,
                    'ok',
                    NULL,
                    NULL,
                    10,
                    3,
                    3,
                    1,
                    1,
                    1,
                    0
                )
                """
            ),
            {
                "host_session_key": str(codex_transcript_fixture["host_session_key"]),
                "thread_id": str(codex_transcript_fixture["canonical_thread_id"]),
                "transcript_path": str(Path(str(codex_transcript_fixture["transcript_path"]))),
            },
        )

    summary = backfill_model_usage(engine=integration_engine)

    assert summary.sessions_examined == 1
    assert summary.sessions_with_records == 1
    assert summary.records_attempted == 1
    assert summary.host_counts == {"codex": 1}
    assert_relation_exists("model_usage")
    rows = fetch_relation_rows("model_usage", order_by="occurred_at ASC")
    assert len(rows) == 1
    assert rows[0]["host_app"] == "codex"
    assert rows[0]["input_tokens"] == 1200
