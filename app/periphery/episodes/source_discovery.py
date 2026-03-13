"""Resolve local host transcript files for episodic ingestion."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from app.periphery.episodes.claude_code import (
    find_latest_claude_code_session_for_repo,
    resolve_claude_code_transcript_path,
)
from app.periphery.episodes.codex import find_latest_codex_session_for_repo, resolve_codex_transcript_path


def resolve_host_transcript_source(
    *,
    host_app: str,
    host_session_key: str,
    search_roots: Sequence[Path],
    last_known_path: Path | None = None,
) -> Path:
    """Resolve the transcript file for one supported host session."""

    search_roots = [Path(root) for root in search_roots]
    if host_app == "codex":
        return resolve_codex_transcript_path(
            host_session_key=host_session_key,
            search_roots=search_roots,
            last_known_path=last_known_path,
        )
    if host_app == "claude_code":
        return resolve_claude_code_transcript_path(
            host_session_key=host_session_key,
            search_roots=search_roots,
            last_known_path=last_known_path,
        )
    raise ValueError(f"Unsupported host app for episode sync: {host_app}")


def discover_active_host_session(
    *,
    host_app: str,
    repo_root: Path,
    search_roots: Sequence[Path],
) -> dict | None:
    """Discover the latest active session for one host and repo root."""

    search_roots = [Path(root) for root in search_roots]
    if host_app == "codex":
        return find_latest_codex_session_for_repo(repo_root=repo_root, search_roots=search_roots)
    if host_app == "claude_code":
        return find_latest_claude_code_session_for_repo(repo_root=repo_root, search_roots=search_roots)
    raise ValueError(f"Unsupported host app for episode sync: {host_app}")
