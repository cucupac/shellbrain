"""Concept show use case."""

from __future__ import annotations

from app.core.contracts.concepts import ConceptShowRequest
from app.core.contracts.errors import DomainValidationError, ErrorCode, ErrorDetail
from app.core.contracts.responses import UseCaseResult
from app.core.ports.db.unit_of_work import IUnitOfWork
from app.core.use_cases.concepts.views import serialize_concept_bundle


def show_concept(request: ConceptShowRequest, uow: IUnitOfWork) -> UseCaseResult:
    """Return one concept with requested facets."""

    bundle = uow.concepts.get_concept_bundle(
        repo_id=request.repo_id, concept_ref=request.concept
    )
    if bundle is None:
        raise DomainValidationError(
            [
                ErrorDetail(
                    code=ErrorCode.NOT_FOUND,
                    message=f"Concept not found: {request.concept}",
                    field="concept",
                )
            ]
        )
    return UseCaseResult(
        data={
            "concept": serialize_concept_bundle(bundle, include=set(request.include))
        },
    )
