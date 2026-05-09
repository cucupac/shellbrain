"""Concept add use case."""

from __future__ import annotations

from typing import Any

from app.core.contracts.concepts import ConceptAddRequest
from app.core.contracts.errors import DomainValidationError, ErrorCode, ErrorDetail
from app.core.contracts.responses import UseCaseResult
from app.core.entities.concepts import Concept, ConceptKind, ConceptStatus
from app.core.ports.runtime.idgen import IIdGenerator
from app.core.ports.db.unit_of_work import IUnitOfWork
from app.core.use_cases.concepts.reference_checks import require_missing_concept


def add_concepts(
    request: ConceptAddRequest,
    uow: IUnitOfWork,
    *,
    id_generator: IIdGenerator,
) -> UseCaseResult:
    """Create concept containers, failing when any target concept already exists."""

    normalized_slugs: list[str] = []
    seen_slugs: set[str] = set()
    for action in request.actions:
        normalized_slug = require_missing_concept(request.repo_id, action.slug, uow)
        if normalized_slug in seen_slugs:
            raise DomainValidationError(
                [
                    ErrorDetail(
                        code=ErrorCode.SEMANTIC_ERROR,
                        message=f"Concept add request contains duplicate slug: {normalized_slug}",
                        field="actions.slug",
                    )
                ]
            )
        normalized_slugs.append(normalized_slug)
        seen_slugs.add(normalized_slug)

    results: list[dict[str, Any]] = []
    for action, normalized_slug in zip(request.actions, normalized_slugs, strict=True):
        concept = uow.concepts.add_concept(
            Concept(
                id=id_generator.new_id(),
                repo_id=request.repo_id,
                slug=normalized_slug,
                name=action.name,
                kind=ConceptKind(action.kind),
                status=ConceptStatus(action.status),
                scope_note=action.scope_note,
            ),
            aliases=action.aliases,
        )
        results.append(
            {"type": action.type, "concept_id": concept.id, "slug": concept.slug}
        )

    return UseCaseResult(data={"added_count": len(results), "results": results})
