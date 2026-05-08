"""Compatibility shim for previously installed Cursor statusline command strings."""

from __future__ import annotations

from app.periphery.host_identity.cursor_statusline import *  # noqa: F403
from app.periphery.host_identity.cursor_statusline import main


if __name__ == "__main__":
    raise SystemExit(main())
