"""Telemetry-focused validation contracts for normalized episode event content."""

from __future__ import annotations

from pathlib import Path

from shellbrain.periphery.episodes.normalization import normalize_host_transcript


def test_episode_event_content_should_always_include_normalized_tool_telemetry_fields_when_present(
    codex_transcript_fixture: dict[str, object],
) -> None:
    """episode event content should always include normalized tool telemetry fields when present."""

    events = normalize_host_transcript(
        host_app="codex",
        host_session_key=str(codex_transcript_fixture["host_session_key"]),
        transcript_path=Path(str(codex_transcript_fixture["transcript_path"])),
    )

    tool_event = next(event for event in events if event["host_event_key"] == "codex-tool-important-1")

    assert tool_event["content_kind"] == "tool_result"
    assert tool_event["tool_name"] == "exec_command"
    assert tool_event["status"] == "error"
    assert tool_event["is_error"] is True


def test_episode_event_content_should_always_omit_tool_telemetry_fields_for_non_tool_events(
    codex_transcript_fixture: dict[str, object],
) -> None:
    """episode event content should always omit tool telemetry fields for non-tool events."""

    events = normalize_host_transcript(
        host_app="codex",
        host_session_key=str(codex_transcript_fixture["host_session_key"]),
        transcript_path=Path(str(codex_transcript_fixture["transcript_path"])),
    )

    user_event = next(event for event in events if event["host_event_key"] == "codex-user-1")

    assert "tool_name" not in user_event
    assert "status" not in user_event
    assert "is_error" not in user_event


def test_codex_and_claude_code_should_always_normalize_equivalent_tool_results_into_the_same_analytics_shape(
    codex_transcript_fixture: dict[str, object],
    claude_code_transcript_fixture: dict[str, object],
) -> None:
    """codex and claude code should always normalize equivalent tool results into the same analytics shape."""

    codex_events = normalize_host_transcript(
        host_app="codex",
        host_session_key=str(codex_transcript_fixture["host_session_key"]),
        transcript_path=Path(str(codex_transcript_fixture["transcript_path"])),
    )
    claude_events = normalize_host_transcript(
        host_app="claude_code",
        host_session_key=str(claude_code_transcript_fixture["host_session_key"]),
        transcript_path=Path(str(claude_code_transcript_fixture["transcript_path"])),
    )

    codex_tool = next(event for event in codex_events if event["host_event_key"] == "codex-tool-important-1")
    claude_tool = next(event for event in claude_events if event["host_event_key"] == "claude-tool-important-1")

    assert set(codex_tool) == set(claude_tool)
    assert codex_tool["content_kind"] == claude_tool["content_kind"] == "tool_result"
    assert codex_tool["source"] == claude_tool["source"] == "tool"
    assert codex_tool["status"] == claude_tool["status"] == "error"
    assert codex_tool["is_error"] is claude_tool["is_error"] is True
