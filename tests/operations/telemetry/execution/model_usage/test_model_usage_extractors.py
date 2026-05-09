"""Extractor contracts for normalized model-usage telemetry."""

from __future__ import annotations

import json
from pathlib import Path

from app.infrastructure.host_transcripts.claude_code import (
    extract_claude_code_model_usage,
)
from app.infrastructure.host_transcripts.codex import extract_codex_model_usage
from app.infrastructure.host_transcripts.cursor import extract_cursor_model_usage
from app.infrastructure.host_transcripts.model_usage import (
    collect_model_usage_records_for_session,
)


def test_codex_extractor_should_read_last_token_usage_from_token_count_events(
    codex_transcript_fixture: dict[str, object],
) -> None:
    """Codex extraction should always use last_token_usage instead of cumulative totals."""

    rows = extract_codex_model_usage(
        host_session_key=str(codex_transcript_fixture["host_session_key"]),
        transcript_path=Path(str(codex_transcript_fixture["transcript_path"])),
    )

    assert len(rows) == 1
    assert rows[0]["source_kind"] == "codex_transcript"
    assert rows[0]["provider"] == "openai"
    assert rows[0]["input_tokens"] == 1200
    assert rows[0]["cached_input_tokens_total"] == 300
    assert rows[0]["output_tokens"] == 90
    assert rows[0]["reasoning_output_tokens"] == 25


def test_claude_extractor_should_dedupe_repeated_request_ids(tmp_path: Path) -> None:
    """Claude extraction should only emit one row per request id even if transcript duplicates usage."""

    transcript_path = tmp_path / "claude.jsonl"
    entries = [
        {
            "uuid": "assistant-1",
            "requestId": "req-1",
            "timestamp": "2026-03-12T02:01:15Z",
            "type": "assistant",
            "message": {
                "model": "claude-opus-4-6",
                "usage": {
                    "input_tokens": 80,
                    "cache_creation_input_tokens": 20,
                    "cache_read_input_tokens": 10,
                    "output_tokens": 12,
                },
            },
        },
        {
            "uuid": "assistant-2",
            "requestId": "req-1",
            "timestamp": "2026-03-12T02:01:16Z",
            "type": "assistant",
            "message": {
                "model": "claude-opus-4-6",
                "usage": {
                    "input_tokens": 80,
                    "cache_creation_input_tokens": 20,
                    "cache_read_input_tokens": 10,
                    "output_tokens": 12,
                },
            },
        },
    ]
    transcript_path.write_text(
        "".join(f"{json.dumps(entry)}\n" for entry in entries), encoding="utf-8"
    )

    rows = extract_claude_code_model_usage(
        host_session_key="claude-session-1",
        transcript_path=transcript_path,
    )

    assert len(rows) == 1
    assert rows[0]["host_usage_key"] == "req-1"
    assert rows[0]["cached_input_tokens_total"] == 30
    assert rows[0]["model_id"] == "claude-opus-4-6"


def test_cursor_extractor_should_read_per_bubble_token_counts_from_state_db(
    cursor_transcript_fixture: dict[str, object],
) -> None:
    """Cursor extraction should always read tokenCount values from cursorDiskKV bubbles."""

    rows = extract_cursor_model_usage(
        host_session_key=str(cursor_transcript_fixture["host_session_key"]),
        transcript_path=Path(str(cursor_transcript_fixture["transcript_path"])),
    )

    assert len(rows) == 2
    assert [row["host_usage_key"] for row in rows] == [
        "cursor-request-1",
        "cursor-request-2",
    ]
    assert rows[0]["source_kind"] == "cursor_state_vscdb"
    assert rows[0]["capture_quality"] == "exact"
    assert rows[0]["provider"] == "anthropic"
    assert rows[0]["model_id"] == "claude-3-7-sonnet"


def test_cursor_collection_should_include_estimated_statusline_sidecar_rows(
    cursor_transcript_fixture: dict[str, object],
    monkeypatch,
    tmp_path: Path,
) -> None:
    """Cursor collection should append managed statusline sidecar rows alongside DB-backed exact rows."""

    cursor_home = tmp_path / ".cursor"
    sidecar_path = (
        cursor_home
        / "shellbrain"
        / "model-usage"
        / f"{cursor_transcript_fixture['host_session_key']}.jsonl"
    )
    sidecar_path.parent.mkdir(parents=True, exist_ok=True)
    sidecar_path.write_text(
        json.dumps(
            {
                "session_id": str(cursor_transcript_fixture["host_session_key"]),
                "usage_key": "statusline-1",
                "occurred_at": "2026-03-12T02:02:00Z",
                "model_id": "claude-3-7-sonnet",
                "provider": "anthropic",
                "input_tokens": 15,
                "output_tokens": 5,
                "reasoning_output_tokens": 0,
                "cached_input_tokens_total": 0,
                "cache_read_input_tokens": 0,
                "cache_creation_input_tokens": 0,
                "capture_quality": "estimated",
                "raw_payload": {"kind": "sidecar"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CURSOR_HOME", str(cursor_home))

    records = collect_model_usage_records_for_session(
        repo_id="shellbrain",
        host_app="cursor",
        host_session_key=str(cursor_transcript_fixture["host_session_key"]),
        thread_id="cursor:thread-1",
        episode_id="episode-1",
        transcript_path=Path(str(cursor_transcript_fixture["transcript_path"])),
    )

    assert len(records) == 3
    assert {record.capture_quality for record in records} == {"exact", "estimated"}
    estimated = [record for record in records if record.capture_quality == "estimated"]
    assert len(estimated) == 1
    assert estimated[0].input_tokens == 15
