"""Unit coverage for parsing visible SB checkpoints from transcript events."""

from __future__ import annotations

from datetime import datetime, timezone

from app.core.use_cases.metrics.analyze_agent_behavior import _parse_checkpoint_lines


def test_parse_checkpoint_lines_should_detect_embedded_sb_checkpoints() -> None:
    """Checkpoint parsing should work when SB lines share a message with other prose."""

    created_at = datetime(2026, 4, 8, 12, 0, tzinfo=timezone.utc)

    checkpoints = _parse_checkpoint_lines(
        repo_id="github.com/example/repo",
        host_app="codex",
        thread_id="codex:thread-1",
        source="assistant",
        content=(
            "I should reconsider memory here. SB: read | fix auth callback | api | oauth callback loop | new hypothesis\n"
            "SB: skip | same signature | no new evidence\n\n"
            "Continuing with the current plan."
        ),
        created_at=created_at,
    )

    assert checkpoints == [
        {
            "repo_id": "github.com/example/repo",
            "host_app": "codex",
            "thread_id": "codex:thread-1",
            "source": "assistant",
            "action": "read",
            "signature": "fix auth callback | api | oauth callback loop | new hypothesis",
            "reason": None,
            "raw_line": "SB: read | fix auth callback | api | oauth callback loop | new hypothesis",
            "created_at": created_at,
        },
        {
            "repo_id": "github.com/example/repo",
            "host_app": "codex",
            "thread_id": "codex:thread-1",
            "source": "assistant",
            "action": "skip",
            "signature": None,
            "reason": "same signature | no new evidence",
            "raw_line": "SB: skip | same signature | no new evidence",
            "created_at": created_at,
        },
    ]
