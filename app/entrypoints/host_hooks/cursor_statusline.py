"""Cursor statusline hook entrypoint."""

from __future__ import annotations

from app.startup.host_hooks import run_cursor_statusline


if __name__ == "__main__":
    raise SystemExit(run_cursor_statusline())
