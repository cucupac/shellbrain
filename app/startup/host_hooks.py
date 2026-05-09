"""Composition helpers for host hook entrypoints."""

from __future__ import annotations

CLAUDE_SESSION_START_ENTRYPOINT_MODULE = (
    "app.entrypoints.host_hooks.claude_session_start"
)
CURSOR_STATUSLINE_ENTRYPOINT_MODULE = "app.entrypoints.host_hooks.cursor_statusline"


def run_claude_session_start(argv: list[str] | None = None) -> int:
    """Run the Claude SessionStart hook adapter."""

    from app.infrastructure.host_identity.claude_runtime import main

    return main(argv)


def run_cursor_statusline() -> int:
    """Run the Cursor statusline adapter."""

    from app.infrastructure.host_identity.cursor_statusline import main

    return main()
