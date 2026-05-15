"""Argparse dispatch for the Shellbrain CLI adapter."""

from __future__ import annotations

import argparse
from collections.abc import Callable
import json
import os
from pathlib import Path
import sys
from typing import Any, Sequence

from app.entrypoints.cli.parser import build_parser
from app.entrypoints.cli.presenters.json import render
from app.startup.cli_runtime import CliRuntime


_INNER_AGENT_READ_ONLY_ENV = "SHELLBRAIN_INNER_AGENT_READ_ONLY"
_INNER_AGENT_MODE_ENV = "SHELLBRAIN_INNER_AGENT_MODE"
_INNER_AGENT_READ_ONLY_ALLOWED_COMMANDS = {"read", "events", "concept:show"}
_INNER_AGENT_ALLOWED_COMMANDS_BY_MODE = {
    "build_context": _INNER_AGENT_READ_ONLY_ALLOWED_COMMANDS,
    "build_knowledge": {
        "read",
        "events",
        "concept:show",
        "memory:add",
        "memory:update",
        "concept:add",
        "concept:update",
        "scenario:record",
    },
}


def run_operation_command(**kwargs):
    """Lazy operation-command wrapper so CLI help stays dependency-light."""

    from app.entrypoints.cli.operation_command import run_operation_command as run

    return run(**kwargs)


def main(
    argv: Sequence[str] | None,
    *,
    runtime: CliRuntime | None = None,
    runtime_factory: Callable[[], CliRuntime] | None = None,
) -> int:
    """Parse CLI arguments and dispatch to operation or human commands."""

    parser = build_parser()
    args = parser.parse_args(argv)
    command = _operation_route_command(args)
    try:
        _enforce_inner_agent_mode(command)
    except ValueError as exc:
        parser.error(str(exc))
        return 2
    runtime = _require_runtime(runtime=runtime, runtime_factory=runtime_factory)

    if args.command == "init":
        from app.entrypoints.cli.handlers.human.init import run as run_init_command

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
        from app.entrypoints.cli.handlers.human.upgrade import (
            run as run_upgrade_command,
        )

        return run_upgrade_command(run_upgrade_command=runtime.run_upgrade_command)

    if args.command == "metrics":
        from app.entrypoints.cli.handlers.human.metrics import run_metrics_command

        return run_metrics_command(
            args,
            warn_or_fail_on_unsafe_app_role=runtime.warn_or_fail_on_unsafe_app_role,
            run_metrics_dashboard=runtime.run_metrics_dashboard,
        )

    if args.command == "admin":
        from app.entrypoints.cli.handlers.human.admin import run_admin_command

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
        result = run_operation_command(
            command=command,
            payload=payload,
            repo_context=repo_context,
            repo_id_override=getattr(args, "repo_id", None),
            no_sync=bool(getattr(args, "no_sync", False)),
            runtime=runtime,
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
    if args.command == "scenario":
        return f"scenario:{args.scenario_command}"
    return str(args.command)


def _enforce_inner_agent_mode(command: str) -> None:
    """Reject routes outside the current inner-agent allowlist."""

    mode = _inner_agent_mode()
    if mode is None:
        return
    allowed_commands = _INNER_AGENT_ALLOWED_COMMANDS_BY_MODE.get(mode)
    if allowed_commands is None:
        valid = ", ".join(sorted(_INNER_AGENT_ALLOWED_COMMANDS_BY_MODE))
        raise ValueError(f"{_INNER_AGENT_MODE_ENV} must be one of: {valid}")
    if command in allowed_commands:
        return
    allowed = ", ".join(sorted(allowed_commands))
    raise ValueError(
        f"{_INNER_AGENT_MODE_ENV}={mode} allows only these routes: {allowed}"
    )


def _inner_agent_mode() -> str | None:
    """Return the active inner-agent mode, including legacy read-only support."""

    value = os.environ.get(_INNER_AGENT_MODE_ENV, "").strip()
    if value:
        return value
    if _inner_agent_read_only_enabled():
        return "build_context"
    return None


def _inner_agent_read_only_enabled() -> bool:
    """Return whether the inner-agent read-only CLI mode is active."""

    value = os.environ.get(_INNER_AGENT_READ_ONLY_ENV, "")
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _dispatch_operation_command(
    command: str, payload: dict[str, Any], repo_context: Any, *, runtime: CliRuntime
) -> dict[str, Any]:
    """Prepare raw CLI payloads and call startup-wired CLI operation handlers."""

    repo_id = repo_context.repo_id
    repo_root = repo_context.repo_root
    dependencies = runtime.build_operation_dependencies()
    if command == "recall":
        from app.entrypoints.cli.handlers.working_agent.recall import (
            run_recall_memory_operation,
        )
        from app.entrypoints.cli.request_parsing.retrieval import prepare_recall_request

        prepared = prepare_recall_request(payload, inferred_repo_id=repo_id)
        return run_recall_memory_operation(
            prepared.request,
            dependencies=dependencies,
            uow_factory=runtime.get_uow_factory(),
            inferred_repo_id=repo_id,
            validation_errors=prepared.errors,
            validation_error_stage=prepared.error_stage,
            telemetry_context=runtime.get_operation_telemetry_context(),
            repo_root=repo_root,
        )
    if command == "read":
        from app.entrypoints.cli.handlers.internal_agent.retrieval.read import (
            run_read_memory_operation,
        )
        from app.entrypoints.cli.request_parsing.retrieval import prepare_read_request

        prepared = prepare_read_request(
            payload,
            inferred_repo_id=repo_id,
            defaults=runtime.get_read_hydration_defaults(),
        )
        return run_read_memory_operation(
            prepared.request,
            dependencies=dependencies,
            uow_factory=runtime.get_uow_factory(),
            inferred_repo_id=repo_id,
            validation_errors=prepared.errors,
            validation_error_stage=prepared.error_stage,
            requested_limit=prepared.requested_limit,
            telemetry_context=runtime.get_operation_telemetry_context(),
            repo_root=repo_root,
        )
    if command == "events":
        from app.entrypoints.cli.handlers.internal_agent.episodes.events import (
            run_read_events_operation,
        )
        from app.entrypoints.cli.request_parsing.episodes import prepare_events_request

        prepared = prepare_events_request(payload, inferred_repo_id=repo_id)
        return run_read_events_operation(
            prepared.request,
            dependencies=dependencies,
            uow_factory=runtime.get_uow_factory(),
            inferred_repo_id=repo_id,
            validation_errors=prepared.errors,
            validation_error_stage=prepared.error_stage,
            repo_root=repo_root,
            telemetry_context=runtime.get_operation_telemetry_context(),
        )
    if command == "memory:add":
        from app.entrypoints.cli.handlers.internal_agent.memories.add import (
            run_create_memory_operation,
        )
        from app.entrypoints.cli.request_parsing.memories import prepare_memory_add_request

        prepared = prepare_memory_add_request(
            payload,
            inferred_repo_id=repo_id,
            defaults=runtime.get_create_hydration_defaults(),
        )
        return run_create_memory_operation(
            prepared.request,
            dependencies=dependencies,
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
        from app.entrypoints.cli.handlers.internal_agent.memories.update import (
            run_update_memory_operation,
        )
        from app.entrypoints.cli.request_parsing.memories import prepare_update_request

        prepared = prepare_update_request(payload, inferred_repo_id=repo_id)
        return run_update_memory_operation(
            prepared.request,
            dependencies=dependencies,
            uow_factory=runtime.get_uow_factory(),
            inferred_repo_id=repo_id,
            validation_errors=prepared.errors,
            validation_error_stage=prepared.error_stage,
            telemetry_context=runtime.get_operation_telemetry_context(),
            repo_root=repo_root,
        )
    if command == "concept:add":
        from app.entrypoints.cli.handlers.internal_agent.concepts.add import (
            run_concept_add_operation,
        )
        from app.entrypoints.cli.request_parsing.concepts import prepare_concept_add_request

        prepared = prepare_concept_add_request(payload, inferred_repo_id=repo_id)
        return run_concept_add_operation(
            prepared.request,
            dependencies=dependencies,
            uow_factory=runtime.get_uow_factory(),
            inferred_repo_id=repo_id,
            validation_errors=prepared.errors,
            validation_error_stage=prepared.error_stage,
            telemetry_context=runtime.get_operation_telemetry_context(),
            repo_root=repo_root,
        )
    if command == "concept:show":
        from app.entrypoints.cli.handlers.internal_agent.concepts.show import (
            run_concept_show_operation,
        )
        from app.entrypoints.cli.request_parsing.concepts import (
            prepare_concept_show_request,
        )

        prepared = prepare_concept_show_request(payload, inferred_repo_id=repo_id)
        return run_concept_show_operation(
            prepared.request,
            dependencies=dependencies,
            uow_factory=runtime.get_uow_factory(),
            inferred_repo_id=repo_id,
            validation_errors=prepared.errors,
            validation_error_stage=prepared.error_stage,
            telemetry_context=runtime.get_operation_telemetry_context(),
            repo_root=repo_root,
        )
    if command == "concept:update":
        from app.entrypoints.cli.handlers.internal_agent.concepts.update import (
            run_concept_update_operation,
        )
        from app.entrypoints.cli.request_parsing.concepts import (
            prepare_concept_update_request,
        )

        prepared = prepare_concept_update_request(payload, inferred_repo_id=repo_id)
        return run_concept_update_operation(
            prepared.request,
            dependencies=dependencies,
            uow_factory=runtime.get_uow_factory(),
            inferred_repo_id=repo_id,
            validation_errors=prepared.errors,
            validation_error_stage=prepared.error_stage,
            telemetry_context=runtime.get_operation_telemetry_context(),
            repo_root=repo_root,
        )
    if command == "scenario:record":
        from app.entrypoints.cli.handlers.internal_agent.scenarios.record import (
            run_scenario_record_operation,
        )
        from app.entrypoints.cli.request_parsing.scenarios import (
            prepare_scenario_record_request,
        )

        prepared = prepare_scenario_record_request(payload, inferred_repo_id=repo_id)
        return run_scenario_record_operation(
            prepared.request,
            dependencies=dependencies,
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
