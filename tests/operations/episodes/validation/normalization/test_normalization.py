"""Normalization contracts for episodic host transcripts."""

from __future__ import annotations

import json
from pathlib import Path

from app.periphery.episodes.normalization import normalize_host_transcript


EXPECTED_EVENT_KEYS = {
    "host_app",
    "host_session_key",
    "host_event_key",
    "source",
    "occurred_at",
    "content_kind",
    "content_text",
    "raw_ref",
}


def test_codex_parsing_normalizes_user_and_assistant_messages_into_common_event_shape(
    codex_transcript_fixture: dict[str, object],
) -> None:
    """codex parsing should always normalize user and assistant messages into the common event shape."""

    events = normalize_host_transcript(
        host_app="codex",
        host_session_key=str(codex_transcript_fixture["host_session_key"]),
        transcript_path=Path(str(codex_transcript_fixture["transcript_path"])),
    )

    _assert_normalized_event(
        events[0],
        host_app="codex",
        host_session_key=str(codex_transcript_fixture["host_session_key"]),
        host_event_key="codex-user-1",
        source="user",
        content_kind="message",
        content_text="Fix the smoke workflow.",
    )
    _assert_normalized_event(
        events[1],
        host_app="codex",
        host_session_key=str(codex_transcript_fixture["host_session_key"]),
        host_event_key="codex-assistant-1",
        source="assistant",
        content_kind="message",
        content_text="I will inspect the workflow.",
    )


def test_claude_code_parsing_normalizes_user_and_assistant_messages_into_common_event_shape(
    claude_code_transcript_fixture: dict[str, object],
) -> None:
    """claude code parsing should always normalize user and assistant messages into the common event shape."""

    events = normalize_host_transcript(
        host_app="claude_code",
        host_session_key=str(claude_code_transcript_fixture["host_session_key"]),
        transcript_path=Path(str(claude_code_transcript_fixture["transcript_path"])),
    )

    _assert_normalized_event(
        events[0],
        host_app="claude_code",
        host_session_key=str(claude_code_transcript_fixture["host_session_key"]),
        host_event_key="claude-user-1",
        source="user",
        content_kind="message",
        content_text="Fix the smoke workflow.",
    )
    _assert_normalized_event(
        events[1],
        host_app="claude_code",
        host_session_key=str(claude_code_transcript_fixture["host_session_key"]),
        host_event_key="claude-assistant-1",
        source="assistant",
        content_kind="message",
        content_text="I will inspect the workflow.",
    )


def test_episode_parsing_keeps_meaningful_tool_results_and_drops_noisy_tool_chatter(
    codex_transcript_fixture: dict[str, object],
) -> None:
    """episode parsing should always keep meaningful tool results and drop noisy tool chatter."""

    events = normalize_host_transcript(
        host_app="codex",
        host_session_key=str(codex_transcript_fixture["host_session_key"]),
        transcript_path=Path(str(codex_transcript_fixture["transcript_path"])),
    )

    host_event_keys = {event["host_event_key"] for event in events}
    assert "codex-tool-important-1" in host_event_keys
    assert "codex-tool-noise-1" not in host_event_keys


def test_episode_parsing_skips_unknown_transcript_lines_without_failing_normalization(
    codex_transcript_fixture: dict[str, object],
) -> None:
    """episode parsing should always skip unknown transcript lines without failing normalization."""

    transcript_path = Path(str(codex_transcript_fixture["transcript_path"]))
    with transcript_path.open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "event_id": "codex-unknown-1",
                    "timestamp": "2026-03-12T01:45:00Z",
                    "type": "metrics",
                    "payload": {"tokens": 123},
                }
            )
            + "\n"
        )

    events = normalize_host_transcript(
        host_app="codex",
        host_session_key=str(codex_transcript_fixture["host_session_key"]),
        transcript_path=transcript_path,
    )

    assert {event["host_event_key"] for event in events}.isdisjoint({"codex-unknown-1"})


def _assert_normalized_event(
    event: dict[str, object],
    *,
    host_app: str,
    host_session_key: str,
    host_event_key: str,
    source: str,
    content_kind: str,
    content_text: str,
) -> None:
    """Assert the common normalized event shape without overfitting raw host details."""

    assert set(event) == EXPECTED_EVENT_KEYS
    assert event["host_app"] == host_app
    assert event["host_session_key"] == host_session_key
    assert event["host_event_key"] == host_event_key
    assert event["source"] == source
    assert event["content_kind"] == content_kind
    assert event["content_text"] == content_text
    assert isinstance(event["occurred_at"], str)
    assert isinstance(event["raw_ref"], str)
    assert event["raw_ref"]
