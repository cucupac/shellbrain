"""This module defines the CLI entry point for shellbrain operations and admin commands."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import TYPE_CHECKING, Any, Sequence
from uuid import uuid4

from app.entrypoints.cli.parser import build_parser
from app.startup.repo_context import resolve_repo_context

if TYPE_CHECKING:
    from app.startup.repo_context import RepoContext

def _load_payload(json_text: str | None, json_file: str | None) -> dict[str, Any]:
    """This function loads a payload from either inline JSON text or a JSON file."""

    if json_text:
        return json.loads(json_text)
    if json_file:
        content = Path(json_file).read_text(encoding="utf-8")
        return json.loads(content)
    raise ValueError("Either --json or --json-file is required")


def main(argv: Sequence[str] | None = None) -> int:
    """Parse CLI arguments and dispatch to the requested operational or admin path."""

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "init":
        try:
            from app.startup.admin_init import run_init

            repo_root = _resolve_admin_repo_root(getattr(args, "repo_root", None))
        except ValueError as exc:
            parser.error(str(exc))
            return 2
        result = run_init(
            repo_root=repo_root,
            repo_id_override=getattr(args, "repo_id", None),
            register_repo_now=_should_register_repo_during_init(
                repo_root=repo_root,
                repo_root_arg=getattr(args, "repo_root", None),
                repo_id_arg=getattr(args, "repo_id", None),
            ),
            skip_model_download=bool(getattr(args, "skip_model_download", False)),
            skip_host_assets=bool(getattr(args, "no_host_assets", False)),
            storage=getattr(args, "storage", None),
            admin_dsn=getattr(args, "admin_dsn", None),
        )
        print(f"Outcome: {result.outcome}")
        for line in result.lines:
            print(line)
        return result.exit_code

    if args.command == "upgrade":
        # architecture-compat: direct-periphery - upgrade remains an externally visible CLI adapter.
        from app.periphery.runtime.upgrade import run_upgrade

        return run_upgrade()

    if args.command == "metrics":
        return _run_metrics_command(args)

    if args.command == "admin":
        return _run_admin_command(args)

    try:
        from app.core.entities.runtime_context import RuntimeContext
        # architecture-compat: direct-periphery - CLI seeds telemetry context from host identity adapters.
        from app.periphery.host_identity.resolver import resolve_caller_identity
        from app.startup.runtime_context import reset_operation_telemetry_context, set_operation_telemetry_context

        repo_context = resolve_repo_context(
            repo_root_arg=getattr(args, "repo_root", None),
            repo_id_arg=getattr(args, "repo_id", None),
        )
        payload = _load_payload(getattr(args, "json_text", None), getattr(args, "json_file", None))
    except ValueError as exc:
        parser.error(str(exc))
        return 2

    caller_identity_resolution = resolve_caller_identity()
    operation_context = RuntimeContext(
        invocation_id=str(uuid4()),
        repo_root=str(repo_context.repo_root),
        no_sync=bool(getattr(args, "no_sync", False)),
        caller_identity=caller_identity_resolution.caller_identity,
        caller_identity_error=caller_identity_resolution.error,
    )
    token = set_operation_telemetry_context(operation_context)
    try:
        try:
            _warn_or_fail_on_unsafe_app_role()
            _ensure_repo_registration_for_operation(
                repo_context=repo_context,
                repo_id_override=getattr(args, "repo_id", None),
            )
            result = _dispatch_operation_command(args.command, payload, repo_context)
            _print_operation_result(result)
            if result.get("status") == "ok":
                if getattr(args, "no_sync", False):
                    _update_operation_polling_status(
                        invocation_id=operation_context.invocation_id,
                        attempted=False,
                        started=False,
                    )
                else:
                    started = bool(_maybe_start_sync(repo_context))
                    _update_operation_polling_status(
                        invocation_id=operation_context.invocation_id,
                        attempted=True,
                        started=started,
                    )
            return 0
        except (RuntimeError, ValueError) as exc:
            print(str(exc), file=sys.stderr)
            return 1
    finally:
        reset_operation_telemetry_context(token)


def _dispatch_operation_command(command: str, payload: dict[str, Any], repo_context: RepoContext) -> dict[str, Any]:
    """Resolve runtime dependencies lazily and execute one operational command."""

    from app.entrypoints.cli.commands.memory import dispatch_operation_command

    return dispatch_operation_command(
        command,
        payload,
        repo_id=repo_context.repo_id,
        repo_root=repo_context.repo_root,
    )


def _run_admin_command(args: argparse.Namespace) -> int:
    """Execute one admin command."""

    from app.entrypoints.cli.commands.admin import run_admin_command

    return run_admin_command(
        args,
        resolve_admin_repo_root=_resolve_admin_repo_root,
        managed_backup_kwargs=_managed_backup_kwargs,
        managed_restore_kwargs=_managed_restore_kwargs,
    )


def _run_metrics_command(args: argparse.Namespace) -> int:
    """Generate metrics snapshots and artifacts for one or many repos."""

    from app.entrypoints.cli.commands.metrics import run_metrics_command

    return run_metrics_command(args, warn_or_fail_on_unsafe_app_role=_warn_or_fail_on_unsafe_app_role)


def _print_operation_result(result: dict[str, Any]) -> None:
    """Render one operation result as JSON for agent consumption."""

    from app.entrypoints.cli.presenter_json import render

    print(render(result))


def _maybe_start_sync(repo_context: RepoContext) -> bool:
    """Best-effort startup for repo-local episode sync after a successful command."""

    try:
        from app.startup.episode_sync_launcher import ensure_episode_sync_started

        return bool(ensure_episode_sync_started(repo_id=repo_context.repo_id, repo_root=repo_context.repo_root))
    except Exception:
        return False


def _update_operation_polling_status(*, invocation_id: str, attempted: bool, started: bool) -> None:
    """Patch poller-start telemetry flags without affecting the visible command result."""

    try:
        from app.startup.use_cases import get_uow_factory

        with get_uow_factory()() as uow:
            uow.telemetry.update_operation_polling(
                invocation_id,
                attempted=attempted,
                started=started,
            )
    except Exception:
        return


def _resolve_admin_repo_root(repo_root_arg: str | None) -> Path:
    """Resolve one admin repo root without inferring repo_id."""

    repo_root = Path(repo_root_arg).expanduser().resolve() if repo_root_arg else Path.cwd().resolve()
    if not repo_root.exists():
        raise ValueError(f"repo_root does not exist: {repo_root}")
    if not repo_root.is_dir():
        raise ValueError(f"repo_root must be a directory: {repo_root}")
    return repo_root


def _should_register_repo_during_init(*, repo_root: Path, repo_root_arg: str | None, repo_id_arg: str | None) -> bool:
    """Return whether init should register one repo immediately."""

    # architecture-compat: direct-periphery - init registration probes local repo state.
    from app.periphery.local_state.repo_registration_store import load_repo_registration_for_target, resolve_git_root

    if repo_root_arg is not None or repo_id_arg is not None:
        return True
    if resolve_git_root(repo_root) is not None:
        return True
    return load_repo_registration_for_target(repo_root) is not None


def _ensure_repo_registration_for_operation(*, repo_context: RepoContext, repo_id_override: str | None) -> None:
    """Best-effort auto-registration of one repo before a real Shellbrain operation."""

    if repo_context.registration_root is None:
        return
    try:
        # architecture-compat: direct-periphery - operation startup registers local repo state.
        from app.periphery.local_state.machine_config_store import try_load_machine_config
        from app.periphery.local_state.repo_registration_store import register_repo_for_target

        machine_config, machine_error = try_load_machine_config()
        if machine_error is not None or machine_config is None:
            return
        register_repo_for_target(
            repo_root=repo_context.registration_root,
            machine_instance_id=machine_config.machine_instance_id,
            explicit_repo_id=repo_id_override,
        )
    except Exception:
        return


def _managed_backup_kwargs(machine_config, machine_error: str | None) -> dict[str, Any]:
    """Return managed-container backup kwargs when machine config is active and readable."""

    if (
        machine_error is not None
        or machine_config is None
        or machine_config.runtime_mode != "managed_local"
        or machine_config.managed is None
    ):
        return {}
    return {
        "container_name": machine_config.managed.container_name,
        "container_db_name": machine_config.managed.db_name,
        "container_admin_user": machine_config.managed.admin_user,
        "container_admin_password": machine_config.managed.admin_password,
    }


def _managed_restore_kwargs(managed_backup_kwargs: dict[str, Any]) -> dict[str, Any]:
    """Trim backup kwargs down to the subset restore understands."""

    return {
        key: value
        for key, value in managed_backup_kwargs.items()
        if key in {"container_name", "container_admin_user", "container_admin_password"}
    }


def _warn_or_fail_on_unsafe_app_role() -> None:
    """Emit one warning, or fail in strict mode, when the app DSN is overprivileged."""

    from app.startup.admin_db import should_fail_on_unsafe_app_role
    from app.startup.db import get_db_dsn
    # architecture-compat: direct-periphery - safety check reads concrete instance metadata.
    from app.periphery.postgres_admin.instance_guard import SCRATCH, TEST, fetch_instance_metadata, inspect_role_safety

    dsn = get_db_dsn()
    warnings = inspect_role_safety(dsn)
    if not warnings:
        return
    message = "Unsafe Shellbrain app-role configuration:\n- " + "\n- ".join(warnings)
    metadata = fetch_instance_metadata(dsn)
    if metadata is not None and metadata.instance_mode in {TEST, SCRATCH}:
        print(message, file=sys.stderr)
        return
    if should_fail_on_unsafe_app_role():
        raise ValueError(message)
    print(message, file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
