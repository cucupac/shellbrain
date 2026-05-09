"""Prepare raw CLI retrieval payloads for typed core use cases."""

from __future__ import annotations

from app.core.contracts.retrieval import MemoryReadRequest, MemoryRecallRequest
from app.infrastructure.cli.protocol.hydration import hydrate_read_payload
from app.infrastructure.cli.protocol.payload_validation import (
    validate_internal_read_contract,
    validate_internal_recall_contract,
    validate_read_schema,
    validate_recall_schema,
)
from app.infrastructure.cli.protocol.prepared import (
    PreparedOperationRequest,
    hydrate_or_error,
)


def prepare_read_request(
    payload: dict,
    *,
    inferred_repo_id: str,
    defaults: dict,
) -> PreparedOperationRequest[MemoryReadRequest]:
    """Validate and hydrate one raw read payload."""

    requested_limit = (
        payload.get("limit") if isinstance(payload.get("limit"), int) else None
    )
    agent_request, errors = validate_read_schema(payload)
    if errors:
        return PreparedOperationRequest(
            request=None,
            errors=errors,
            error_stage="schema_validation",
            requested_limit=requested_limit,
        )
    assert agent_request is not None
    hydrated, hydration_error = hydrate_or_error(
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
        return PreparedOperationRequest(
            request=None, errors=errors, error_stage="schema_validation"
        )
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
