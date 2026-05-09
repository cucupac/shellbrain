"""Argparse dispatch for the Shellbrain CLI adapter."""

from __future__ import annotations

import argparse
from collections.abc import Callable
from dataclasses import dataclass
import json
from pathlib import Path
import sys
from typing import Any, Sequence

from app.entrypoints.cli.handlers.human.admin import (
    AdminCommandDependencies,
    run_admin_command,
)
from app.entrypoints.cli.handlers.human.init import run as run_init_command
from app.entrypoints.cli.handlers.human.metrics import run_metrics_command
from app.entrypoints.cli.handlers.human.upgrade import run as run_upgrade_command
from app.entrypoints.cli.parser import build_parser
from app.entrypoints.cli.presenters.json import render


@dataclass(frozen=True)
class CliRuntime:
    """Startup-provided concrete dependencies for the CLI runner."""

    resolve_repo_context: Callable[..., Any]
    run_operation_command: Callable[..., dict[str, Any]]
    get_create_hydration_defaults: Callable[[], dict[str, Any]]
    get_read_hydration_defaults: Callable[[], dict[str, Any]]
    get_uow_factory: Callable[[], Any]
    get_embedding_provider_factory: Callable[[], Any]
    get_embedding_model: Callable[[], str]
    get_operation_telemetry_context: Callable[[], Any]
    handle_memory_add: Callable[..., dict[str, Any]]
    handle_update: Callable[..., dict[str, Any]]
    handle_read: Callable[..., dict[str, Any]]
    handle_recall: Callable[..., dict[str, Any]]
    handle_events: Callable[..., dict[str, Any]]
    handle_concept_add: Callable[..., dict[str, Any]]
    handle_concept_update: Callable[..., dict[str, Any]]
    should_register_repo_during_init: Callable[..., bool]
    run_init: Callable[..., Any]
    init_success_presenter_context: Callable[[], dict[str, Any]]
    run_upgrade_command: Callable[[], int]
    warn_or_fail_on_unsafe_app_role: Callable[[], None]
    run_metrics_dashboard: Callable[..., object]
    admin_dependencies: AdminCommandDependencies


def main(
    argv: Sequence[str] | None,
    *,
    runtime: CliRuntime | None = None,
    runtime_factory: Callable[[], CliRuntime] | None = None,
) -> int:
    """Parse CLI arguments and dispatch to operation or human commands."""

    parser = build_parser()
    args = parser.parse_args(argv)
    runtime = _require_runtime(runtime=runtime, runtime_factory=runtime_factory)

    if args.command == "init":
        try:
            return run_init_command(
                args,
                resolve_admin_repo_root=_resolve_admin_repo_root,
                should_register_repo=runtime.should_register_repo_during_init,
                run_init=runtime.run_init,
                init_success_presenter_context=runtime.init_success_presenter_context,
            )
        except ValueError as exc:
            parser.error(str(exc))
            return 2

    if args.command == "upgrade":
        return run_upgrade_command(run_upgrade_command=runtime.run_upgrade_command)

    if args.command == "metrics":
        return run_metrics_command(
            args,
            warn_or_fail_on_unsafe_app_role=runtime.warn_or_fail_on_unsafe_app_role,
            run_metrics_dashboard=runtime.run_metrics_dashboard,
        )

    if args.command == "admin":
        return run_admin_command(
            args,
            resolve_admin_repo_root=_resolve_admin_repo_root,
            dependencies=runtime.admin_dependencies,
        )

    try:
        repo_context = runtime.resolve_repo_context(
            repo_root_arg=getattr(args, "repo_root", None),
            repo_id_arg=getattr(args, "repo_id", None),
        )
        payload = _load_payload(
            getattr(args, "json_text", None), getattr(args, "json_file", None)
        )
    except ValueError as exc:
        parser.error(str(exc))
        return 2

    try:
        result = runtime.run_operation_command(
            command=_operation_route_command(args),
            payload=payload,
            repo_context=repo_context,
            repo_id_override=getattr(args, "repo_id", None),
            no_sync=bool(getattr(args, "no_sync", False)),
            dispatch_operation=lambda command, payload, context: (
                _dispatch_operation_command(command, payload, context, runtime=runtime)
            ),
        )
        print(render(result))
        return 0
    except (RuntimeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


def _load_payload(json_text: str | None, json_file: str | None) -> dict[str, Any]:
    """Load one JSON payload from inline text or a file path."""

    if json_text:
        return json.loads(json_text)
    if json_file:
        content = Path(json_file).read_text(encoding="utf-8")
        return json.loads(content)
    raise ValueError("Either --json or --json-file is required")


def _require_runtime(
    *,
    runtime: CliRuntime | None,
    runtime_factory: Callable[[], CliRuntime] | None,
) -> CliRuntime:
    """Resolve the startup-provided runtime after argparse has handled exits."""

    if runtime is not None:
        return runtime
    if runtime_factory is not None:
        return runtime_factory()
    raise ValueError("CLI runtime is required")


def _operation_route_command(args: argparse.Namespace) -> str:
    """Map parsed CLI syntax to one operation route key."""

    if args.command == "memory":
        return f"memory:{args.memory_command}"
    if args.command == "concept" and getattr(args, "concept_command", None):
        return f"concept:{args.concept_command}"
    return str(args.command)


def _dispatch_operation_command(
    command: str, payload: dict[str, Any], repo_context: Any, *, runtime: CliRuntime
) -> dict[str, Any]:
    """Prepare raw CLI payloads and call startup-wired CLI operation handlers."""

    repo_id = repo_context.repo_id
    repo_root = repo_context.repo_root
    if command == "recall":
        from app.entrypoints.cli.protocol.retrieval import prepare_recall_request

        prepared = prepare_recall_request(payload, inferred_repo_id=repo_id)
        return runtime.handle_recall(
            prepared.request,
            uow_factory=runtime.get_uow_factory(),
            inferred_repo_id=repo_id,
            validation_errors=prepared.errors,
            validation_error_stage=prepared.error_stage,
            telemetry_context=runtime.get_operation_telemetry_context(),
            repo_root=repo_root,
        )
    if command == "read":
        from app.entrypoints.cli.protocol.retrieval import prepare_read_request

        prepared = prepare_read_request(
            payload,
            inferred_repo_id=repo_id,
            defaults=runtime.get_read_hydration_defaults(),
        )
        return runtime.handle_read(
            prepared.request,
            uow_factory=runtime.get_uow_factory(),
            inferred_repo_id=repo_id,
            validation_errors=prepared.errors,
            validation_error_stage=prepared.error_stage,
            requested_limit=prepared.requested_limit,
            telemetry_context=runtime.get_operation_telemetry_context(),
            repo_root=repo_root,
        )
    if command == "events":
        from app.entrypoints.cli.protocol.episodes import prepare_events_request

        prepared = prepare_events_request(payload, inferred_repo_id=repo_id)
        return runtime.handle_events(
            prepared.request,
            uow_factory=runtime.get_uow_factory(),
            inferred_repo_id=repo_id,
            validation_errors=prepared.errors,
            validation_error_stage=prepared.error_stage,
            repo_root=repo_root,
            telemetry_context=runtime.get_operation_telemetry_context(),
        )
    if command == "memory:add":
        from app.entrypoints.cli.protocol.memories import prepare_memory_add_request

        prepared = prepare_memory_add_request(
            payload,
            inferred_repo_id=repo_id,
            defaults=runtime.get_create_hydration_defaults(),
        )
        return runtime.handle_memory_add(
            prepared.request,
            uow_factory=runtime.get_uow_factory(),
            embedding_provider_factory=runtime.get_embedding_provider_factory(),
            embedding_model=runtime.get_embedding_model(),
            inferred_repo_id=repo_id,
            validation_errors=prepared.errors,
            validation_error_stage=prepared.error_stage,
            telemetry_context=runtime.get_operation_telemetry_context(),
            repo_root=repo_root,
        )
    if command == "memory:update":
        from app.entrypoints.cli.protocol.memories import prepare_update_request

        prepared = prepare_update_request(payload, inferred_repo_id=repo_id)
        return runtime.handle_update(
            prepared.request,
            uow_factory=runtime.get_uow_factory(),
            inferred_repo_id=repo_id,
            validation_errors=prepared.errors,
            validation_error_stage=prepared.error_stage,
            telemetry_context=runtime.get_operation_telemetry_context(),
            repo_root=repo_root,
        )
    if command == "concept:add":
        from app.entrypoints.cli.protocol.concepts import prepare_concept_add_request

        prepared = prepare_concept_add_request(payload, inferred_repo_id=repo_id)
        return runtime.handle_concept_add(
            prepared.request,
            uow_factory=runtime.get_uow_factory(),
            inferred_repo_id=repo_id,
            validation_errors=prepared.errors,
            validation_error_stage=prepared.error_stage,
            telemetry_context=runtime.get_operation_telemetry_context(),
            repo_root=repo_root,
        )
    if command == "concept:update":
        from app.entrypoints.cli.protocol.concepts import (
            prepare_concept_update_request,
        )

        prepared = prepare_concept_update_request(payload, inferred_repo_id=repo_id)
        return runtime.handle_concept_update(
            prepared.request,
            uow_factory=runtime.get_uow_factory(),
            inferred_repo_id=repo_id,
            validation_errors=prepared.errors,
            validation_error_stage=prepared.error_stage,
            telemetry_context=runtime.get_operation_telemetry_context(),
            repo_root=repo_root,
        )
    raise ValueError(f"Unsupported command: {command}")


def _resolve_admin_repo_root(repo_root_arg: str | None) -> Path:
    """Resolve one admin repo root without inferring repo_id."""

    repo_root = (
        Path(repo_root_arg).expanduser().resolve()
        if repo_root_arg
        else Path.cwd().resolve()
    )
    if not repo_root.exists():
        raise ValueError(f"repo_root does not exist: {repo_root}")
    if not repo_root.is_dir():
        raise ValueError(f"repo_root must be a directory: {repo_root}")
    return repo_root
