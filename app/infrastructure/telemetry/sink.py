"""Telemetry sink helpers for handler workflows."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from app.core.entities.identity import IdentityTrustLevel
from app.core.entities.runtime_context import (
    RuntimeContext,
    SessionSelectionSummary,
)
from app.core.ports.system.clock import IClock
from app.infrastructure.telemetry.operation_invocations import (
    build_operation_invocation_record,
)
from app.infrastructure.telemetry.inner_agent_records import (
    build_inner_agent_invocation_records,
)
from app.infrastructure.telemetry.read_records import build_read_summary_records
from app.infrastructure.telemetry.recall_records import build_recall_summary_records
from app.infrastructure.telemetry.recorder import (
    record_episode_sync_telemetry,
    record_model_usage_telemetry,
    record_operation_telemetry,
)
from app.infrastructure.telemetry.sync_records import build_episode_sync_records
from app.infrastructure.telemetry.write_records import build_write_summary_records


@dataclass(frozen=True)
class TelemetrySink:
    """Best-effort command telemetry sink wired by startup."""

    clock: IClock
    summarize_runtime_selection: Callable[..., SessionSelectionSummary]

    def record(
        self,
        *,
        command: str,
        uow_factory,
        repo_id: str,
        telemetry_context: RuntimeContext,
        result: dict,
        error_stage: str | None,
        request=None,
        requested_limit: int | None = None,
        selection_summary: SessionSelectionSummary | None = None,
        sync_run_payload: dict[str, Any] | None = None,
        model_usage_records: Iterable[object] = (),
        planned_side_effects: Iterable[object] = (),
        recall_telemetry: dict | None = None,
        total_latency_ms: int | None = None,
    ) -> None:
        """Persist invocation telemetry in a second best-effort transaction."""

        try:
            created_at = self.clock.now()
            with uow_factory() as telemetry_uow:
                resolved_selection = selection_summary
                if resolved_selection is None:
                    resolved_selection = self._selection_summary_from_runtime_context(
                        runtime_context=telemetry_context,
                        repo_id=repo_id,
                        uow=telemetry_uow,
                    )
                invocation = build_operation_invocation_record(
                    command=command,
                    repo_id=repo_id,
                    runtime_context=telemetry_context,
                    selection_summary=resolved_selection,
                    result=result,
                    error_stage=error_stage,
                    total_latency_ms=total_latency_ms
                    if total_latency_ms is not None
                    else 0,
                    created_at=created_at,
                )

                read_summary = None
                read_items = ()
                recall_summary = None
                recall_items = ()
                inner_agent_invocations = ()
                write_summary = None
                write_items = ()

                if (
                    result.get("status") == "ok"
                    and command == "read"
                    and request is not None
                ):
                    pack = result.get("data", {}).get("pack", {})
                    if isinstance(pack, dict):
                        read_summary, read_items = build_read_summary_records(
                            invocation_id=telemetry_context.invocation_id,
                            requested_limit=requested_limit,
                            request=request,
                            pack=pack,
                            created_at=created_at,
                        )

                if (
                    result.get("status") == "ok"
                    and command == "recall"
                    and request is not None
                ):
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
                                fallback_reason=str(fallback_reason)
                                if isinstance(fallback_reason, str)
                                else None,
                                created_at=created_at,
                            )
                            inner_agent_invocations = (
                                build_inner_agent_invocation_records(
                                    invocation_id=telemetry_context.invocation_id,
                                    recall_telemetry=recall_telemetry,
                                    created_at=created_at,
                                )
                            )

                if (
                    result.get("status") == "ok"
                    and command in {"create", "update"}
                    and request is not None
                ):
                    effect_plan = list(planned_side_effects)
                    if effect_plan:
                        write_summary, write_items = build_write_summary_records(
                            invocation_id=telemetry_context.invocation_id,
                            command=command,
                            request=request,
                            planned_side_effects=effect_plan,
                            created_at=created_at,
                        )

                record_operation_telemetry(
                    uow=telemetry_uow,
                    invocation=invocation,
                    read_summary=read_summary,
                    read_items=read_items,
                    recall_summary=recall_summary,
                    recall_items=recall_items,
                    inner_agent_invocations=inner_agent_invocations,
                    write_summary=write_summary,
                    write_items=write_items,
                )
                if sync_run_payload is not None:
                    sync_run, sync_tool_types = build_episode_sync_records(
                        **sync_run_payload
                    )
                    record_episode_sync_telemetry(
                        uow=telemetry_uow,
                        run=sync_run,
                        tool_types=sync_tool_types,
                    )
                model_usage_tuple = tuple(model_usage_records)
                if model_usage_tuple:
                    record_model_usage_telemetry(
                        uow=telemetry_uow,
                        records=model_usage_tuple,
                    )
        except Exception:
            return

    def _selection_summary_from_runtime_context(
        self,
        *,
        runtime_context: RuntimeContext,
        repo_id: str,
        uow,
    ) -> SessionSelectionSummary:
        caller_identity = runtime_context.caller_identity
        if (
            caller_identity is None
            or caller_identity.trust_level != IdentityTrustLevel.TRUSTED
        ):
            return self.summarize_runtime_selection(
                repo_root=Path(runtime_context.repo_root),
                repo_id=repo_id,
                uow=uow,
            )
        selected_episode_id = None
        episode = uow.episodes.get_episode_by_thread(
            repo_id=repo_id, thread_id=caller_identity.canonical_id or ""
        )
        if episode is not None:
            selected_episode_id = episode.id
        return replace(
            SessionSelectionSummary(
                selected_host_app=caller_identity.host_app,
                selected_host_session_key=caller_identity.host_session_key,
                selected_thread_id=caller_identity.canonical_id,
                matching_candidate_count=1,
                selection_ambiguous=False,
            ),
            selected_episode_id=selected_episode_id,
        )
