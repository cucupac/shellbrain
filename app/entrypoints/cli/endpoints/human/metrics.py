"""Metrics command implementation."""

from __future__ import annotations

import argparse
import sys
from typing import Callable


def run_metrics_command(args: argparse.Namespace, *, warn_or_fail_on_unsafe_app_role: Callable[[], None]) -> int:
    """Generate metrics snapshots and artifacts for one or many repos."""

    try:
        from app.startup.metrics import run_metrics_dashboard

        if bool(getattr(args, "repo_id", None) or getattr(args, "repo_root", None) or getattr(args, "no_sync", False)):
            raise ValueError("`shellbrain metrics` does not accept options. Run `shellbrain metrics`.")

        for line in run_metrics_dashboard(warn_or_fail_on_unsafe_app_role=warn_or_fail_on_unsafe_app_role):
            print(line)
        return 0
    except (RuntimeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
