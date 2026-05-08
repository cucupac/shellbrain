"""Human CLI endpoint for package upgrades."""

from __future__ import annotations

from app.startup.cli import run_upgrade_command


def run() -> int:
    """Run the hosted upgrade path."""

    return run_upgrade_command()
