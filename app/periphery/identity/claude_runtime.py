"""Compatibility shim for previously installed Claude hook command strings."""

from __future__ import annotations

import sys

from app.periphery.host_identity.claude_runtime import *  # noqa: F403
from app.periphery.host_identity.claude_runtime import main


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
