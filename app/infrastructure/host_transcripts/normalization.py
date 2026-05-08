"""Normalize host transcript files into compact episode events."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.infrastructure.host_transcripts.claude_code import normalize_claude_code_transcript
from app.infrastructure.host_transcripts.codex import normalize_codex_transcript
from app.infrastructure.host_transcripts.cursor import normalize_cursor_transcript


def normalize_host_transcript(
    *,
    host_app: str,
    host_session_key: str,
    transcript_path: Path,
) -> list[dict[str, Any]]:
    """Normalize one host transcript file into common episode-event dictionaries."""

    transcript_path = Path(transcript_path)
    if host_app == "codex":
        return normalize_codex_transcript(
            host_session_key=host_session_key,
            transcript_path=transcript_path,
        )
    if host_app == "claude_code":
        return normalize_claude_code_transcript(
            host_session_key=host_session_key,
            transcript_path=transcript_path,
        )
    if host_app == "cursor":
        return normalize_cursor_transcript(
            host_session_key=host_session_key,
            transcript_path=transcript_path,
        )
    raise ValueError(f"Unsupported host app for episode sync: {host_app}")
