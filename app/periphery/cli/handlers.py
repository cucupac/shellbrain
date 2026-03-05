"""This module defines CLI command handlers that dispatch to core use-case functions."""

from app.core.contracts.errors import ErrorCode, ErrorDetail
from app.core.contracts.responses import OperationResult
from app.core.use_cases.create_memory import execute_create_memory
from app.core.use_cases.read_memory import execute_read_memory
from app.core.use_cases.update_memory import execute_update_memory
from app.core.validation.schema_validation import validate_create_schema, validate_read_schema, validate_update_schema


def _error_response(errors: list[ErrorDetail]) -> dict:
    """This function builds a standardized error response envelope for CLI handlers."""

    return OperationResult(status="error", errors=errors).model_dump(mode="python")


def handle_create(payload: dict, *, uow_factory, embedding_provider_factory, embedding_model: str):
    """This function validates and dispatches a create payload to the create use-case."""

    request, errors = validate_create_schema(payload)
    if errors:
        return _error_response(errors)
    assert request is not None
    try:
        with uow_factory() as uow:
            embedding_provider = embedding_provider_factory()
            return execute_create_memory(
                request,
                uow,
                embedding_provider=embedding_provider,
                embedding_model=embedding_model,
            ).model_dump(mode="python")
    except Exception as exc:  # pragma: no cover - defensive fallback envelope
        return _error_response([ErrorDetail(code=ErrorCode.INTERNAL_ERROR, message=str(exc))])


def handle_read(payload: dict, *, uow_factory):
    """This function validates and dispatches a read payload to the read use-case."""

    request, errors = validate_read_schema(payload)
    if errors:
        return _error_response(errors)
    assert request is not None
    try:
        with uow_factory() as uow:
            return execute_read_memory(request, uow).model_dump(mode="python")
    except Exception as exc:  # pragma: no cover - defensive fallback envelope
        return _error_response([ErrorDetail(code=ErrorCode.INTERNAL_ERROR, message=str(exc))])


def handle_update(payload: dict, *, uow_factory):
    """This function validates and dispatches an update payload to the update use-case."""

    request, errors = validate_update_schema(payload)
    if errors:
        return _error_response(errors)
    assert request is not None
    try:
        with uow_factory() as uow:
            return execute_update_memory(request, uow).model_dump(mode="python")
    except Exception as exc:  # pragma: no cover - defensive fallback envelope
        return _error_response([ErrorDetail(code=ErrorCode.INTERNAL_ERROR, message=str(exc))])
