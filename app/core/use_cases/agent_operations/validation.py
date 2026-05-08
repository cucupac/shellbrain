"""Validation and session-state hydration for agent operation workflows."""

from __future__ import annotations

from app.core.contracts.errors import ErrorCode, ErrorDetail
from app.core.contracts.requests import MemoryBatchUpdateRequest, MemoryCreateRequest, MemoryUpdateRequest
from app.core.validation.memory_integrity import validate_create_integrity, validate_update_integrity
from app.core.validation.memory_semantic import validate_create_semantics, validate_update_semantics


def validate_create_request(request: MemoryCreateRequest, *, uow, gates: list[str]) -> list[ErrorDetail]:
    """Run non-schema create validations before invoking core execution."""

    if "semantic" in gates:
        semantic_errors = validate_create_semantics(request)
        if semantic_errors:
            return semantic_errors
    if "integrity" in gates:
        return validate_create_integrity(request, uow)
    return []


def validate_update_request(
    request: MemoryUpdateRequest | MemoryBatchUpdateRequest,
    *,
    uow,
    gates: list[str],
) -> list[ErrorDetail]:
    """Run non-schema update validations before invoking core execution."""

    if "semantic" in gates:
        semantic_errors = validate_update_semantics(request)
        if semantic_errors:
            return semantic_errors
    if "integrity" in gates:
        return validate_update_integrity(request, uow)
    return []


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
