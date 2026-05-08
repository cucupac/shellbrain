"""Operation telemetry persistence for agent operation workflows."""

from __future__ import annotations

from pathlib import Path

from app.core.entities.telemetry import OperationDispatchTelemetryContext, SessionSelectionSummary
from app.core.observability.telemetry.operation_records import (
    build_operation_invocation_record,
    build_recall_summary_records,
    build_read_summary_records,
    build_write_summary_records,
)
from app.core.use_cases.agent_operations.dependencies import OperationDependencies
from app.core.use_cases.agent_operations.events_selection import selection_summary_from_runtime_context
from app.core.use_cases.record_episode_sync_telemetry import record_episode_sync_telemetry
from app.core.use_cases.record_model_usage_telemetry import record_model_usage_telemetry
from app.core.use_cases.record_operation_telemetry import record_operation_telemetry


def ensure_telemetry_context(
    *,
    dependencies: OperationDependencies,
    telemetry_context: OperationDispatchTelemetryContext | None,
    repo_root: Path | None,
) -> OperationDispatchTelemetryContext:
    """Return the active handler telemetry context or synthesize one for direct calls."""

    if telemetry_context is not None:
        return telemetry_context
    inherited = dependencies.get_operation_telemetry_context()
    if inherited is not None:
        return inherited
    caller_identity_resolution = dependencies.resolve_caller_identity()
    return OperationDispatchTelemetryContext(
        invocation_id=dependencies.id_generator.new_id(),
        repo_root=str((repo_root or Path.cwd()).resolve()),
        no_sync=False,
        caller_identity=caller_identity_resolution.caller_identity,
        caller_identity_error=caller_identity_resolution.error,
    )


def persist_operation_telemetry_best_effort(
    *,
    dependencies: OperationDependencies,
    command: str,
    uow_factory,
    repo_id: str,
    telemetry_context: OperationDispatchTelemetryContext,
    result: dict,
    error_stage: str | None,
    request=None,
    requested_limit: int | None = None,
    selection_summary: SessionSelectionSummary | None = None,
    sync_run=None,
    sync_tool_types=(),
    model_usage_records=(),
    recall_telemetry: dict | None = None,
    total_latency_ms: int | None = None,
) -> None:
    """Persist invocation telemetry in a second best-effort transaction."""

    try:
        created_at = dependencies.clock.now()
        with uow_factory() as telemetry_uow:
            resolved_selection = selection_summary
            if resolved_selection is None:
                resolved_selection = selection_summary_from_runtime_context(
                    dependencies=dependencies,
                    caller_identity=telemetry_context.caller_identity,
                    repo_id=repo_id,
                    repo_root=Path(telemetry_context.repo_root),
                    uow=telemetry_uow,
                )
            invocation = build_operation_invocation_record(
                command=command,
                repo_id=repo_id,
                runtime_context=telemetry_context,
                selection_summary=resolved_selection,
                result=result,
                error_stage=error_stage,
                total_latency_ms=total_latency_ms if total_latency_ms is not None else 0,
                created_at=created_at,
            )

            read_summary = None
            read_items = ()
            recall_summary = None
            recall_items = ()
            write_summary = None
            write_items = ()

            if result.get("status") == "ok" and command == "read" and request is not None:
                pack = result.get("data", {}).get("pack", {})
                if isinstance(pack, dict):
                    read_summary, read_items = build_read_summary_records(
                        invocation_id=telemetry_context.invocation_id,
                        requested_limit=requested_limit,
                        request=request,
                        pack=pack,
                        created_at=created_at,
                    )

            if result.get("status") == "ok" and command == "recall" and request is not None:
                data = result.get("data", {})
                if isinstance(data, dict) and isinstance(recall_telemetry, dict):
                    brief = data.get("brief", {})
                    if isinstance(brief, dict):
                        fallback_reason = data.get("fallback_reason")
                        recall_summary, recall_items = build_recall_summary_records(
                            invocation_id=telemetry_context.invocation_id,
                            request=request,
                            recall_telemetry=recall_telemetry,
                            brief=brief,
                            fallback_reason=str(fallback_reason) if isinstance(fallback_reason, str) else None,
                            created_at=created_at,
                        )

            if result.get("status") == "ok" and command in {"create", "update"} and request is not None:
                planned_side_effects = result.get("data", {}).get("planned_side_effects", [])
                if isinstance(planned_side_effects, list):
                    write_summary, write_items = build_write_summary_records(
                        invocation_id=telemetry_context.invocation_id,
                        command=command,
                        request=request,
                        planned_side_effects=planned_side_effects,
                        created_at=created_at,
                    )

            record_operation_telemetry(
                uow=telemetry_uow,
                invocation=invocation,
                read_summary=read_summary,
                read_items=read_items,
                recall_summary=recall_summary,
                recall_items=recall_items,
                write_summary=write_summary,
                write_items=write_items,
            )
            if sync_run is not None:
                record_episode_sync_telemetry(
                    uow=telemetry_uow,
                    run=sync_run,
                    tool_types=sync_tool_types,
                )
            if model_usage_records:
                record_model_usage_telemetry(
                    uow=telemetry_uow,
                    records=tuple(model_usage_records),
                )
    except Exception:
        return
