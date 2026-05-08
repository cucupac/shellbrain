"""Claude SessionStart hook entrypoint."""

from __future__ import annotations

import sys

# architecture-compat: direct-periphery - external hook entrypoint delegates to runtime adapter.
from app.periphery.host_identity.claude_runtime import main


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
