"""Working-agent operation for shadow snapshot capture."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

from app.core.entities.runtime_context import OperationDispatchTelemetryContext
from app.core.entities.snapshots import ShadowSnapshotReason
from app.core.errors import ErrorCode, ErrorDetail
from app.core.use_cases.episodes.sync_episode import SyncEpisodeRequest, sync_episode
from app.core.use_cases.snapshots.capture_snapshot import (
    CaptureSnapshotRequest,
    execute_capture_snapshot,
)
from app.entrypoints.cli.handlers.dependencies import (
    OperationDependencies,
    ensure_telemetry_context,
)
from app.entrypoints.cli.handlers.internal_agent.episodes.selection import (
    resolve_events_source,
    selection_summary_from_events_source,
)
from app.entrypoints.cli.handlers.result_envelopes import error_response, ok_envelope


@dataclass(frozen=True)
class _EpisodeLink:
    """Optional transcript linkage for one snapshot capture."""

    episode_id: str | None
    captured_after_event_seq: int | None
    status: str
    reason: str | None = None

    def to_response_data(self) -> dict[str, object]:
        return {
            "status": self.status,
            "episode_id": self.episode_id,
            "captured_after_event_seq": self.captured_after_event_seq,
            "reason": self.reason,
        }


def run_snapshot_operation(
    *,
    dependencies: OperationDependencies,
    uow_factory,
    inferred_repo_id: str,
    telemetry_context: OperationDispatchTelemetryContext | None = None,
    repo_root: Path | None = None,
):
    """Capture current repo state into repo-local shadow Git."""

    started_at = perf_counter()
    resolved_repo_root = (repo_root or Path.cwd()).resolve()
    resolved_telemetry_context = ensure_telemetry_context(
        dependencies=dependencies,
        telemetry_context=telemetry_context,
        repo_root=resolved_repo_root,
    )
    error_stage: str | None = None
    try:
        episode_link = _sync_active_episode(
            dependencies=dependencies,
            uow_factory=uow_factory,
            repo_id=inferred_repo_id,
            repo_root=resolved_repo_root,
            telemetry_context=resolved_telemetry_context,
        )
        with uow_factory() as uow:
            capture_result = execute_capture_snapshot(
                CaptureSnapshotRequest(
                    repo_id=inferred_repo_id,
                    repo_root=str(resolved_repo_root),
                    reason=ShadowSnapshotReason.CLOSEOUT,
                    episode_id=episode_link.episode_id,
                    captured_after_event_seq=episode_link.captured_after_event_seq,
                    operation_invocation_id=resolved_telemetry_context.invocation_id,
                ),
                uow,
                shadow_git_store=dependencies.shadow_git_store,
                id_generator=dependencies.id_generator,
                clock=dependencies.clock,
            )
        data = capture_result.to_response_data()
        data["episode_link"] = episode_link.to_response_data()
        result = ok_envelope(data)
    except Exception as exc:
        error_stage = "snapshot_capture"
        result = error_response(
            [ErrorDetail(code=ErrorCode.INTERNAL_ERROR, message=str(exc))]
        )

    dependencies.telemetry_sink.record(
        command="snapshot",
        uow_factory=uow_factory,
        repo_id=inferred_repo_id,
        telemetry_context=resolved_telemetry_context,
        result=result,
        error_stage=error_stage,
        total_latency_ms=int((perf_counter() - started_at) * 1000),
    )
    return result


def _sync_active_episode(
    *,
    dependencies: OperationDependencies,
    uow_factory,
    repo_id: str,
    repo_root: Path,
    telemetry_context: OperationDispatchTelemetryContext,
) -> _EpisodeLink:
    """Best-effort active transcript sync used only for snapshot linkage."""

    try:
        source = resolve_events_source(
            dependencies=dependencies,
            repo_root=repo_root,
            search_roots_by_host=None,
            runtime_context=telemetry_context,
        )
        normalized_events = dependencies.normalize_host_transcript(
            host_app=str(source.host_app),
            host_session_key=str(source.host_session_key),
            transcript_path=Path(str(source.transcript_path)),
        )
        with uow_factory() as uow:
            sync_result = sync_episode(
                SyncEpisodeRequest.from_raw_events(
                    repo_id=repo_id,
                    host_app=str(source.host_app),
                    host_session_key=str(source.host_session_key),
                    thread_id=str(source.canonical_thread_id),
                    transcript_path=str(source.transcript_path),
                    normalized_events=normalized_events,
                ),
                uow=uow,
                clock=dependencies.clock,
                id_generator=dependencies.id_generator,
            )
            event_watermark = uow.episodes.event_watermark(
                repo_id=repo_id, episode_id=sync_result.episode_id
            )
        selection_summary = selection_summary_from_events_source(source)
        if selection_summary.selection_ambiguous:
            return _EpisodeLink(
                episode_id=sync_result.episode_id,
                captured_after_event_seq=event_watermark,
                status="linked_ambiguous",
                reason="multiple host sessions matched; selected runtime source was used",
            )
        return _EpisodeLink(
            episode_id=sync_result.episode_id,
            captured_after_event_seq=event_watermark,
            status="linked",
        )
    except Exception as exc:
        return _EpisodeLink(
            episode_id=None,
            captured_after_event_seq=None,
            status="unavailable",
            reason=str(exc),
        )
