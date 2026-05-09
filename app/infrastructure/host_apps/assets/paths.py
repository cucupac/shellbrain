"""Default host paths for Shellbrain-managed assets."""

from __future__ import annotations

import os
from pathlib import Path


def default_codex_home() -> Path:
    """Return the default Codex home path for host assets."""

    raw = os.getenv("CODEX_HOME")
    if raw:
        return Path(raw).expanduser().resolve()
    return (Path.home() / ".codex").resolve()


def default_claude_root() -> Path:
    """Return the default Claude home path for host assets."""

    return (Path.home() / ".claude").resolve()


def default_cursor_home() -> Path:
    """Return the default Cursor home path for host assets."""

    raw = os.getenv("CURSOR_HOME")
    if raw:
        return Path(raw).expanduser().resolve()
    return (Path.home() / ".cursor").resolve()
