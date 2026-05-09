"""Human CLI endpoint for package upgrades."""

from __future__ import annotations

from collections.abc import Callable


def run(*, run_upgrade_command: Callable[[], int]) -> int:
    """Run the hosted upgrade path."""

    return run_upgrade_command()
