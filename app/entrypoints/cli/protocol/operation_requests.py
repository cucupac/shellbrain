"""Prepare raw CLI operation payloads for typed core use cases."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

from app.core.contracts.concepts import ConceptCommandRequest
from app.core.contracts.errors import ErrorCode, ErrorDetail
from app.core.contracts.requests import (
    EpisodeEventsRequest,
    MemoryBatchUpdateRequest,
    MemoryCreateRequest,
    MemoryReadRequest,
    MemoryRecallRequest,
    MemoryUpdateRequest,
)
from app.entrypoints.cli.protocol.hydration import (
    hydrate_concept_payload,
    hydrate_create_payload,
    hydrate_events_payload,
    hydrate_read_payload,
    hydrate_update_payload,
)
from app.entrypoints.cli.protocol.payload_validation import (
    validate_concept_schema,
    validate_create_schema,
    validate_events_schema,
    validate_internal_create_contract,
    validate_internal_events_contract,
    validate_internal_read_contract,
    validate_internal_recall_contract,
    validate_internal_update_contract,
    validate_read_schema,
    validate_recall_schema,
    validate_update_schema,
)

T = TypeVar("T")


@dataclass(frozen=True)
class PreparedOperationRequest(Generic[T]):
    """Typed request plus any entrypoint validation failure details."""

    request: T | None
    errors: list[ErrorDetail]
    error_stage: str = "schema_validation"
    requested_limit: int | None = None


def prepare_create_request(
    payload: dict,
    *,
    inferred_repo_id: str,
    defaults: dict,
) -> PreparedOperationRequest[MemoryCreateRequest]:
    """Validate and hydrate one raw memory-add payload."""

    agent_request, errors = validate_create_schema(payload)
    if errors:
        return PreparedOperationRequest(request=None, errors=errors, error_stage="schema_validation")
    assert agent_request is not None
    hydrated, hydration_error = _hydrate_or_error(
        lambda: hydrate_create_payload(
            agent_request.model_dump(mode="python", exclude_none=True),
            inferred_repo_id=inferred_repo_id,
            defaults=defaults,
        )
    )
    if hydration_error is not None:
        return PreparedOperationRequest(request=None, errors=[hydration_error], error_stage="contract_validation")
    request, contract_errors = validate_internal_create_contract(hydrated)
    return PreparedOperationRequest(
        request=request,
        errors=contract_errors,
        error_stage="contract_validation" if contract_errors else "schema_validation",
    )


def prepare_read_request(
    payload: dict,
    *,
    inferred_repo_id: str,
    defaults: dict,
) -> PreparedOperationRequest[MemoryReadRequest]:
    """Validate and hydrate one raw read payload."""

    requested_limit = payload.get("limit") if isinstance(payload.get("limit"), int) else None
    agent_request, errors = validate_read_schema(payload)
    if errors:
        return PreparedOperationRequest(
            request=None,
            errors=errors,
            error_stage="schema_validation",
            requested_limit=requested_limit,
        )
    assert agent_request is not None
    hydrated, hydration_error = _hydrate_or_error(
        lambda: hydrate_read_payload(
            agent_request.model_dump(mode="python", exclude_none=True),
            inferred_repo_id=inferred_repo_id,
            defaults=defaults,
        )
    )
    if hydration_error is not None:
        return PreparedOperationRequest(
            request=None,
            errors=[hydration_error],
            error_stage="contract_validation",
            requested_limit=requested_limit,
        )
    request, contract_errors = validate_internal_read_contract(hydrated)
    return PreparedOperationRequest(
        request=request,
        errors=contract_errors,
        error_stage="contract_validation" if contract_errors else "schema_validation",
        requested_limit=requested_limit,
    )


def prepare_recall_request(
    payload: dict,
    *,
    inferred_repo_id: str,
) -> PreparedOperationRequest[MemoryRecallRequest]:
    """Validate and hydrate one raw recall payload."""

    agent_request, errors = validate_recall_schema(payload)
    if errors:
        return PreparedOperationRequest(request=None, errors=errors, error_stage="schema_validation")
    assert agent_request is not None
    hydrated = agent_request.model_dump(mode="python", exclude_none=True)
    hydrated.setdefault("op", "recall")
    hydrated.setdefault("repo_id", inferred_repo_id)
    request, contract_errors = validate_internal_recall_contract(hydrated)
    return PreparedOperationRequest(
        request=request,
        errors=contract_errors,
        error_stage="contract_validation" if contract_errors else "schema_validation",
    )


def prepare_events_request(
    payload: dict,
    *,
    inferred_repo_id: str,
) -> PreparedOperationRequest[EpisodeEventsRequest]:
    """Validate and hydrate one raw events payload."""

    agent_request, errors = validate_events_schema(payload)
    if errors:
        return PreparedOperationRequest(request=None, errors=errors, error_stage="schema_validation")
    assert agent_request is not None
    hydrated = hydrate_events_payload(
        agent_request.model_dump(mode="python", exclude_none=True),
        inferred_repo_id=inferred_repo_id,
    )
    request, contract_errors = validate_internal_events_contract(hydrated)
    return PreparedOperationRequest(
        request=request,
        errors=contract_errors,
        error_stage="contract_validation" if contract_errors else "schema_validation",
    )


def prepare_update_request(
    payload: dict,
    *,
    inferred_repo_id: str,
) -> PreparedOperationRequest[MemoryUpdateRequest | MemoryBatchUpdateRequest]:
    """Validate and hydrate one raw memory-update payload."""

    agent_request, errors = validate_update_schema(payload)
    if errors:
        return PreparedOperationRequest(request=None, errors=errors, error_stage="schema_validation")
    assert agent_request is not None
    hydrated = hydrate_update_payload(
        agent_request.model_dump(mode="python", exclude_none=True),
        inferred_repo_id=inferred_repo_id,
    )
    request, contract_errors = validate_internal_update_contract(hydrated)
    return PreparedOperationRequest(
        request=request,
        errors=contract_errors,
        error_stage="contract_validation" if contract_errors else "schema_validation",
    )


def prepare_concept_request(
    payload: dict,
    *,
    inferred_repo_id: str,
) -> PreparedOperationRequest[ConceptCommandRequest]:
    """Validate and hydrate one raw concept graph payload."""

    hydrated = hydrate_concept_payload(payload, inferred_repo_id=inferred_repo_id)
    request, errors = validate_concept_schema(hydrated)
    return PreparedOperationRequest(
        request=request,
        errors=errors,
        error_stage="schema_validation" if errors else "schema_validation",
    )


def _hydrate_or_error(call) -> tuple[dict, ErrorDetail | None]:
    try:
        return call(), None
    except ValueError as exc:
        return {}, ErrorDetail(code=ErrorCode.INTERNAL_ERROR, message=str(exc))
