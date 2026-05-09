"""Metrics command implementation."""

from __future__ import annotations

import argparse
from collections.abc import Callable
import sys

from app.entrypoints.cli.presenters.metrics import render_metrics_dashboard_lines


def run_metrics_command(
    args: argparse.Namespace,
    *,
    warn_or_fail_on_unsafe_app_role: Callable[[], None],
    run_metrics_dashboard: Callable[..., object],
) -> int:
    """Generate metrics snapshots and artifacts for one or many repos."""

    try:
        if bool(
            getattr(args, "repo_id", None)
            or getattr(args, "repo_root", None)
            or getattr(args, "no_sync", False)
        ):
            raise ValueError(
                "`shellbrain metrics` does not accept options. Run `shellbrain metrics`."
            )

        result = run_metrics_dashboard(
            warn_or_fail_on_unsafe_app_role=warn_or_fail_on_unsafe_app_role
        )
        for line in render_metrics_dashboard_lines(result):
            print(line)
        return 0
    except (RuntimeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
