"""Agent operation workflow for adding concept graph containers."""

from __future__ import annotations

from pathlib import Path
from time import perf_counter

from app.core.contracts.concepts import ConceptAddRequest
from app.core.contracts.errors import DomainValidationError, ErrorCode, ErrorDetail
from app.core.entities.runtime_context import OperationDispatchTelemetryContext
from app.entrypoints.cli.handlers.command_context import OperationDependencies
from app.entrypoints.cli.handlers.result_envelopes import (
    dump_errors,
    error_response,
    infer_error_stage_from_errors,
    ok_envelope,
)
from app.entrypoints.cli.handlers.command_context import (
    ensure_telemetry_context,
)
from app.core.use_cases.concepts.add import add_concepts


def run_concept_add_operation(
    request: ConceptAddRequest | None,
    *,
    dependencies: OperationDependencies,
    uow_factory,
    inferred_repo_id: str,
    validation_errors: tuple[ErrorDetail, ...] | list[ErrorDetail] = (),
    validation_error_stage: str = "schema_validation",
    telemetry_context: OperationDispatchTelemetryContext | None = None,
    repo_root: Path | None = None,
):
    """Dispatch a typed concept-add payload."""

    started_at = perf_counter()
    resolved_repo_root = (repo_root or Path.cwd()).resolve()
    resolved_telemetry_context = ensure_telemetry_context(
        dependencies=dependencies,
        telemetry_context=telemetry_context,
        repo_root=resolved_repo_root,
    )
    result: dict | None = None
    error_stage: str | None = None
    try:
        if validation_errors:
            error_stage = infer_error_stage_from_errors(
                dump_errors(validation_errors), default_stage=validation_error_stage
            )
            result = error_response(validation_errors)
        elif request is None:
            error_stage = "contract_validation"
            result = error_response(
                [
                    ErrorDetail(
                        code=ErrorCode.SCHEMA_ERROR,
                        message="concept add request is required",
                    )
                ]
            )
        else:
            with uow_factory() as uow:
                result = ok_envelope(
                    add_concepts(request, uow, id_generator=dependencies.id_generator)
                )
    except DomainValidationError as exc:
        error_stage = infer_error_stage_from_errors(
            dump_errors(exc.errors), default_stage="semantic_validation"
        )
        result = error_response(exc.errors)
    except Exception as exc:  # pragma: no cover - defensive fallback envelope
        error_stage = "internal_error"
        result = error_response(
            [ErrorDetail(code=ErrorCode.INTERNAL_ERROR, message=str(exc))]
        )

    assert result is not None
    dependencies.telemetry_sink.record(
        command="concept.add",
        uow_factory=uow_factory,
        repo_id=inferred_repo_id,
        telemetry_context=resolved_telemetry_context,
        result=result,
        error_stage=error_stage,
        request=request,
        total_latency_ms=int((perf_counter() - started_at) * 1000),
    )
    return result
