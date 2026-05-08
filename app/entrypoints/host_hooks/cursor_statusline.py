"""Cursor statusline hook entrypoint."""

from __future__ import annotations

# architecture-compat: direct-periphery - external hook entrypoint delegates to runtime adapter.
from app.periphery.host_identity.cursor_statusline import main


if __name__ == "__main__":
    raise SystemExit(main())
