"""Claude SessionStart hook entrypoint."""

from __future__ import annotations

import sys

from app.startup.host_hooks import run_claude_session_start


if __name__ == "__main__":
    raise SystemExit(run_claude_session_start(sys.argv[1:]))
