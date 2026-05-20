"""Concept add use case."""

from __future__ import annotations

from typing import Any

from app.core.errors import DomainValidationError, ErrorCode, ErrorDetail
from app.core.entities.concepts import Concept, ConceptKind, ConceptStatus
from app.core.ports.embeddings.provider import IEmbeddingProvider
from app.core.ports.system.idgen import IIdGenerator
from app.core.ports.db.unit_of_work import IUnitOfWork
from app.core.use_cases.concepts.embeddings import upsert_concept_embeddings
from app.core.use_cases.concepts.add.request import ConceptAddRequest
from app.core.use_cases.concepts.add.result import ConceptAddResult
from app.core.use_cases.concepts.reference_checks import require_missing_concept


def add_concepts(
    request: ConceptAddRequest,
    uow: IUnitOfWork,
    *,
    id_generator: IIdGenerator,
    embedding_provider: IEmbeddingProvider | None = None,
    embedding_model: str | None = None,
) -> ConceptAddResult:
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
    concept_ids: list[str] = []
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
        concept_ids.append(concept.id)
        results.append(
            {"type": action.type, "concept_id": concept.id, "slug": concept.slug}
        )
    upsert_concept_embeddings(
        repo_id=request.repo_id,
        concept_ids=concept_ids,
        uow=uow,
        embedding_provider=embedding_provider,
        embedding_model=embedding_model,
    )

    return ConceptAddResult(added_count=len(results), results=results)
