"""Wiki command implementation."""

from __future__ import annotations

import argparse
from collections.abc import Callable
import sys
from typing import Any


def run_wiki_command(
    args: argparse.Namespace,
    *,
    resolve_repo_context: Callable[..., Any],
    warn_or_fail_on_unsafe_app_role: Callable[[], None],
    run_wiki: Callable[..., int],
) -> int:
    """Open the read-only Shellbrain Wiki for the current repo."""

    try:
        if bool(
            getattr(args, "repo_id", None)
            or getattr(args, "repo_root", None)
            or getattr(args, "no_sync", False)
            or getattr(args, "wiki_extra_args", ())
            or getattr(args, "wiki_port", None) is not None
            or getattr(args, "wiki_no_open", False)
            or getattr(args, "wiki_repo_id", None) is not None
            or getattr(args, "wiki_repo_root", None) is not None
            or getattr(args, "wiki_no_sync", False)
        ):
            raise ValueError(
                "`shellbrain wiki` does not accept options. Run `shellbrain wiki`."
            )
        repo_context = resolve_repo_context(repo_root_arg=None, repo_id_arg=None)
        return run_wiki(
            repo_id=repo_context.repo_id,
            warn_or_fail_on_unsafe_app_role=warn_or_fail_on_unsafe_app_role,
        )
    except (RuntimeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
