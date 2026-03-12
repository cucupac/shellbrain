"""This module defines CLI command handlers that dispatch to core use-case functions."""

from app.boot.create_policy import get_create_hydration_defaults, get_create_policy_settings, validate_create_policy_settings
from app.boot.read_policy import get_read_hydration_defaults
from app.boot.update_policy import get_update_policy_settings, validate_update_policy_settings
from app.core.contracts.errors import ErrorCode, ErrorDetail
from app.core.contracts.requests import MemoryCreateRequest, MemoryUpdateRequest
from app.core.contracts.responses import OperationResult
from app.core.use_cases.create_memory import execute_create_memory
from app.core.use_cases.read_memory import execute_read_memory
from app.core.use_cases.update_memory import execute_update_memory
from app.periphery.cli.hydration import hydrate_create_payload, hydrate_read_payload, hydrate_update_payload
from app.periphery.cli.schema_validation import (
    validate_create_schema,
    validate_internal_create_contract,
    validate_internal_read_contract,
    validate_internal_update_contract,
    validate_read_schema,
    validate_update_schema,
)
from app.periphery.validation.integrity_validation import validate_create_integrity, validate_update_integrity
from app.periphery.validation.semantic_validation import validate_create_semantics, validate_update_semantics


def _error_response(errors: list[ErrorDetail]) -> dict:
    """This function builds a standardized error response envelope for CLI handlers."""

    return OperationResult(status="error", errors=errors).model_dump(mode="python")


def _validate_create_request(request: MemoryCreateRequest, *, uow, gates: list[str]) -> list[ErrorDetail]:
    """Run non-schema create validations before invoking core execution."""

    if "semantic" in gates:
        semantic_errors = validate_create_semantics(request)
        if semantic_errors:
            return semantic_errors
    if "integrity" in gates:
        return validate_create_integrity(request, uow)
    return []


def _validate_update_request(request: MemoryUpdateRequest, *, uow, gates: list[str]) -> list[ErrorDetail]:
    """Run non-schema update validations before invoking core execution."""

    if "semantic" in gates:
        semantic_errors = validate_update_semantics(request)
        if semantic_errors:
            return semantic_errors
    if "integrity" in gates:
        return validate_update_integrity(request, uow)
    return []


def handle_create(
    payload: dict,
    *,
    uow_factory,
    embedding_provider_factory,
    embedding_model: str,
    inferred_repo_id: str,
    defaults: dict | None = None,
):
    """This function validates and dispatches a create payload to the create use-case."""

    policy_errors = validate_create_policy_settings()
    if policy_errors:
        return _error_response(policy_errors)
    policy = get_create_policy_settings()
    agent_request, errors = validate_create_schema(payload)
    if errors:
        return _error_response(errors)
    assert agent_request is not None
    resolved_defaults = defaults if defaults is not None else get_create_hydration_defaults()
    hydrated_payload = hydrate_create_payload(
        agent_request.model_dump(mode="python", exclude_none=True),
        inferred_repo_id=inferred_repo_id,
        defaults=resolved_defaults,
    )
    request, contract_errors = validate_internal_create_contract(hydrated_payload)
    if contract_errors:
        return _error_response(contract_errors)
    assert request is not None
    try:
        with uow_factory() as uow:
            validation_errors = _validate_create_request(request, uow=uow, gates=policy["gates"])
            if validation_errors:
                return _error_response(validation_errors)
            embedding_provider = embedding_provider_factory()
            return execute_create_memory(
                request,
                uow,
                embedding_provider=embedding_provider,
                embedding_model=embedding_model,
            ).model_dump(mode="python")
    except Exception as exc:  # pragma: no cover - defensive fallback envelope
        return _error_response([ErrorDetail(code=ErrorCode.INTERNAL_ERROR, message=str(exc))])


def handle_read(payload: dict, *, uow_factory, inferred_repo_id: str, defaults: dict | None = None):
    """This function validates and dispatches a read payload to the read use-case."""

    agent_request, errors = validate_read_schema(payload)
    if errors:
        return _error_response(errors)
    assert agent_request is not None
    resolved_defaults = defaults if defaults is not None else get_read_hydration_defaults()
    hydrated_payload = hydrate_read_payload(
        agent_request.model_dump(mode="python", exclude_none=True),
        inferred_repo_id=inferred_repo_id,
        defaults=resolved_defaults,
    )
    request, contract_errors = validate_internal_read_contract(hydrated_payload)
    if contract_errors:
        return _error_response(contract_errors)
    assert request is not None
    try:
        with uow_factory() as uow:
            return execute_read_memory(request, uow).model_dump(mode="python")
    except Exception as exc:  # pragma: no cover - defensive fallback envelope
        return _error_response([ErrorDetail(code=ErrorCode.INTERNAL_ERROR, message=str(exc))])


def handle_update(payload: dict, *, uow_factory, inferred_repo_id: str):
    """This function validates and dispatches an update payload to the update use-case."""

    policy_errors = validate_update_policy_settings()
    if policy_errors:
        return _error_response(policy_errors)
    policy = get_update_policy_settings()
    agent_request, errors = validate_update_schema(payload)
    if errors:
        return _error_response(errors)
    assert agent_request is not None
    hydrated_payload = hydrate_update_payload(
        agent_request.model_dump(mode="python", exclude_none=True),
        inferred_repo_id=inferred_repo_id,
    )
    request, contract_errors = validate_internal_update_contract(hydrated_payload)
    if contract_errors:
        return _error_response(contract_errors)
    assert request is not None
    try:
        with uow_factory() as uow:
            validation_errors = _validate_update_request(request, uow=uow, gates=policy["gates"])
            if validation_errors:
                return _error_response(validation_errors)
            return execute_update_memory(request, uow).model_dump(mode="python")
    except Exception as exc:  # pragma: no cover - defensive fallback envelope
        return _error_response([ErrorDetail(code=ErrorCode.INTERNAL_ERROR, message=str(exc))])
