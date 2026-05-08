"""Composition helpers for host hook entrypoints."""

from __future__ import annotations


def run_claude_session_start(argv: list[str] | None = None) -> int:
    """Run the Claude SessionStart hook adapter."""

    from app.infrastructure.host_identity.claude_runtime import main

    return main(argv)


def run_cursor_statusline() -> int:
    """Run the Cursor statusline adapter."""

    from app.infrastructure.host_identity.cursor_statusline import main

    return main()
