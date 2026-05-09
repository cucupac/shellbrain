"""Console-script shim for the Shellbrain CLI."""

from __future__ import annotations

import sys
from typing import Sequence

from app.startup.cli import main as startup_main


def main(argv: Sequence[str] | None = None) -> int:
    """Delegate CLI startup to the composition root."""

    return startup_main(argv)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
