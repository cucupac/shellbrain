"""Concept show use case."""

from __future__ import annotations

from app.core.errors import DomainValidationError, ErrorCode, ErrorDetail
from app.core.ports.db.unit_of_work import IUnitOfWork
from app.core.use_cases.concepts.show.request import ConceptShowRequest
from app.core.use_cases.concepts.show.result import ConceptShowResult
from app.core.use_cases.concepts.views import serialize_concept_show


def show_concept(request: ConceptShowRequest, uow: IUnitOfWork) -> ConceptShowResult:
    """Return one concept with requested facets."""

    bundle = uow.concepts.get_concept_bundle(
        repo_id=request.repo_id,
        concept_ref=request.concept,
        include_lifecycle_events="lifecycle_events" in request.include,
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
    include = set(request.include)
    endpoint_ids = {
        concept_id
        for relation in bundle["relations"]
        if "relations" in include
        for concept_id in (relation.subject_concept_id, relation.object_concept_id)
    }
    memory_ids = {
        link.memory_id for link in bundle["memory_links"] if "memory_links" in include
    }
    related_concepts = (
        uow.concepts.list_concepts_by_ids(
            repo_id=request.repo_id, concept_ids=sorted(endpoint_ids)
        )
        if endpoint_ids
        else []
    )
    related_memories = (
        uow.memories.list_by_ids(sorted(memory_ids)) if memory_ids else []
    )
    return ConceptShowResult(
        concept=serialize_concept_show(
            bundle,
            include=include,
            related_concepts={concept.id: concept for concept in related_concepts},
            related_memories={memory.id: memory for memory in related_memories},
        )
    )
