"""Prepare raw CLI memory payloads for typed core use cases."""

from __future__ import annotations

from app.core.use_cases.memories.add.request import MemoryAddRequest
from app.core.use_cases.memories.update.request import (
    MemoryBatchUpdateRequest,
    MemoryUpdateRequest,
)
from app.entrypoints.cli.request_parsing.hydration import (
    hydrate_memory_add_payload,
    hydrate_update_payload,
)
from app.entrypoints.cli.request_parsing.payload_validation import (
    validate_create_schema,
    validate_internal_create_contract,
    validate_internal_update_contract,
    validate_update_schema,
)
from app.entrypoints.cli.request_parsing.prepared import (
    PreparedOperationRequest,
    hydrate_or_error,
)


def prepare_memory_add_request(
    payload: dict,
    *,
    inferred_repo_id: str,
    defaults: dict,
) -> PreparedOperationRequest[MemoryAddRequest]:
    """Validate and hydrate one raw memory-add payload."""

    agent_request, errors = validate_create_schema(payload)
    if errors:
        return PreparedOperationRequest(
            request=None, errors=errors, error_stage="schema_validation"
        )
    assert agent_request is not None
    hydrated, hydration_error = hydrate_or_error(
        lambda: hydrate_memory_add_payload(
            agent_request.model_dump(mode="python", exclude_none=True),
            inferred_repo_id=inferred_repo_id,
            defaults=defaults,
        )
    )
    if hydration_error is not None:
        return PreparedOperationRequest(
            request=None, errors=[hydration_error], error_stage="contract_validation"
        )
    request, contract_errors = validate_internal_create_contract(hydrated)
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
        return PreparedOperationRequest(
            request=None, errors=errors, error_stage="schema_validation"
        )
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
