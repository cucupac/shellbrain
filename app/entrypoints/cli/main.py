"""Console-script shim for the Shellbrain CLI."""

from __future__ import annotations

import sys
from typing import Sequence

from app.entrypoints.cli.runner import main as runner_main
from app.startup.cli import build_cli_runtime


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI with startup-composed concrete dependencies."""

    return runner_main(argv, runtime_factory=build_cli_runtime)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
