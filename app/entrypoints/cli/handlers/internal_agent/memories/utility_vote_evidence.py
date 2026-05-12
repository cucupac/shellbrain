"""Memory command validation, evidence hydration, and guidance helpers."""

from __future__ import annotations

from app.core.errors import ErrorCode, ErrorDetail
from app.core.use_cases.memories.update.request import (
    MemoryBatchUpdateRequest,
    MemoryUpdateRequest,
)
from app.core.entities.identity import CallerIdentity
from app.core.use_cases.build_guidance import build_pending_utility_guidance


def hydrate_update_request_evidence_from_session_state(*, request, session_state):
    """Auto-fill missing utility evidence refs from session state when possible."""

    if session_state is None:
        if isinstance(request, MemoryBatchUpdateRequest):
            if any(item.update.evidence_refs for item in request.updates):
                return request, []
            return request, _missing_events_evidence_errors(request)
        if request.update.type != "utility_vote" or request.update.evidence_refs:
            return request, []
        return request, _missing_events_evidence_errors(request)

    if isinstance(request, MemoryBatchUpdateRequest):
        if any(item.update.evidence_refs for item in request.updates):
            return request, []
        if not session_state.last_events_event_ids:
            return request, _missing_events_evidence_errors(request)
        request_data = request.model_dump(mode="python")
        for item in request_data["updates"]:
            item["update"]["evidence_refs"] = list(session_state.last_events_event_ids)
        return MemoryBatchUpdateRequest.model_validate(request_data), []

    if request.update.type != "utility_vote" or request.update.evidence_refs:
        return request, []
    if not session_state.last_events_event_ids:
        return request, _missing_events_evidence_errors(request)
    request_data = request.model_dump(mode="python")
    request_data["update"]["evidence_refs"] = list(session_state.last_events_event_ids)
    return MemoryUpdateRequest.model_validate(request_data), []


def _missing_events_evidence_errors(request) -> list[ErrorDetail]:
    """Return the canonical semantic error when utility evidence cannot be auto-filled."""

    if isinstance(request, MemoryBatchUpdateRequest):
        return [
            ErrorDetail(
                code=ErrorCode.SEMANTIC_ERROR,
                message="Batch utility votes require recent episode evidence; run `events` first.",
                field="updates",
            )
        ]
    if getattr(request.update, "type", None) == "utility_vote":
        return [
            ErrorDetail(
                code=ErrorCode.SEMANTIC_ERROR,
                message="utility_vote requires recent episode evidence; run `events` first.",
                field="update.evidence_refs",
            )
        ]
    return []


def build_guidance_payloads(
    *,
    uow_factory,
    repo_id: str,
    caller_identity: CallerIdentity | None,
    session_state,
    now_iso: str,
    strong: bool,
) -> list[dict]:
    """Build public guidance payloads from telemetry and session state."""

    if session_state is None:
        return []
    with uow_factory() as guidance_uow:
        decisions = build_pending_utility_guidance(
            repo_id=repo_id,
            caller_identity=caller_identity,
            session_state=session_state,
            pending_utility_candidates=guidance_uow.guidance,
            now_iso=now_iso,
            strong=strong,
        )
    return [decision.to_payload() for decision in decisions]


def attach_guidance(result: dict, guidance_payloads: list[dict]) -> None:
    """Attach one or more guidance payloads to a successful result."""

    data = result.setdefault("data", {})
    if not isinstance(data, dict):
        return
    data["guidance"] = guidance_payloads
