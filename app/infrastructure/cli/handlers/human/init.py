"""Human CLI endpoint for runtime initialization."""

from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path
from typing import Any

from app.infrastructure.cli.presenters.init import render_success_lines


def run(
    args: argparse.Namespace,
    *,
    resolve_admin_repo_root: Callable[[str | None], Path],
    should_register_repo: Callable[..., bool],
    run_init: Callable[..., Any],
    init_success_presenter_context: Callable[[], dict[str, Any]],
) -> int:
    """Run Shellbrain initialization and print the human-facing result."""

    repo_root = resolve_admin_repo_root(getattr(args, "repo_root", None))
    result = run_init(
        repo_root=repo_root,
        repo_id_override=getattr(args, "repo_id", None),
        register_repo_now=should_register_repo(
            repo_root=repo_root,
            repo_root_arg=getattr(args, "repo_root", None),
            repo_id_arg=getattr(args, "repo_id", None),
        ),
        skip_model_download=bool(getattr(args, "skip_model_download", False)),
        skip_host_assets=bool(getattr(args, "no_host_assets", False)),
        storage=getattr(args, "storage", None),
        admin_dsn=getattr(args, "admin_dsn", None),
        render_success_lines=lambda **kwargs: render_success_lines(
            **kwargs, **init_success_presenter_context()
        ),
    )
    print(f"Outcome: {result.outcome}")
    for line in result.lines:
        print(line)
    return result.exit_code
