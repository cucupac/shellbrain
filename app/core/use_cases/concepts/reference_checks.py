"""Repository-backed concept reference checks."""

from __future__ import annotations

from app.core.contracts.concepts import ConceptEvidencePayload
from app.core.contracts.errors import DomainValidationError, ErrorCode, ErrorDetail
from app.core.entities.concepts import Anchor, Concept
from app.core.entities.memories import Memory, MemoryScope
from app.core.ports.db.unit_of_work import IUnitOfWork


def require_concept(repo_id: str, concept_ref: str, uow: IUnitOfWork) -> Concept:
    """Resolve one concept by id or slug and fail when it is missing."""

    concept = uow.concepts.get_concept_by_ref(
        repo_id=repo_id, concept_ref=normalize_slug(concept_ref)
    )
    if concept is None:
        concept = uow.concepts.get_concept_by_ref(
            repo_id=repo_id, concept_ref=concept_ref
        )
    if concept is None:
        _raise_concept_error(
            ErrorCode.NOT_FOUND, f"Concept not found: {concept_ref}", field="concept"
        )
    return concept


def require_missing_concept(repo_id: str, slug: str, uow: IUnitOfWork) -> str:
    """Normalize a new concept slug and fail when it already exists."""

    normalized_slug = normalize_slug(slug)
    concept = uow.concepts.get_concept_by_ref(
        repo_id=repo_id, concept_ref=normalized_slug
    )
    if concept is not None:
        _raise_concept_error(
            ErrorCode.CONFLICT,
            f"Concept already exists: {normalized_slug}",
            field="slug",
        )
    return normalized_slug


def require_anchor(repo_id: str, anchor_id: str, uow: IUnitOfWork) -> Anchor:
    """Resolve one anchor and fail when it is missing."""

    anchor = uow.concepts.get_anchor(repo_id=repo_id, anchor_id=anchor_id)
    if anchor is None:
        _raise_concept_error(
            ErrorCode.NOT_FOUND, f"Anchor not found: {anchor_id}", field="anchor_id"
        )
    return anchor


def require_visible_memory(repo_id: str, memory_id: str, uow: IUnitOfWork) -> Memory:
    """Resolve one memory and fail unless it is visible to the repo."""

    memory = uow.memories.get(memory_id)
    if memory is None:
        _raise_concept_error(
            ErrorCode.NOT_FOUND, f"Memory not found: {memory_id}", field="memory_id"
        )
    if memory.repo_id != repo_id and memory.scope != MemoryScope.GLOBAL:
        _raise_concept_error(
            ErrorCode.INTEGRITY_ERROR,
            f"Memory is not visible for repo {repo_id}: {memory_id}",
            field="memory_id",
        )
    return memory


def validate_evidence_visibility(
    repo_id: str, item: ConceptEvidencePayload, uow: IUnitOfWork
) -> None:
    """Validate local references used by inline evidence."""

    if item.anchor_id:
        require_anchor(repo_id, item.anchor_id, uow)
    if item.memory_id:
        memory = uow.memories.get(item.memory_id)
        if memory is None:
            _raise_concept_error(
                ErrorCode.NOT_FOUND,
                f"Evidence memory not found: {item.memory_id}",
                field="evidence.memory_id",
            )
        if memory.repo_id != repo_id and memory.scope != MemoryScope.GLOBAL:
            _raise_concept_error(
                ErrorCode.INTEGRITY_ERROR,
                f"Evidence memory is not visible for repo {repo_id}: {item.memory_id}",
                field="evidence.memory_id",
            )


def normalize_text(value: str) -> str:
    """Normalize free text for natural-key comparison."""

    return " ".join(value.strip().lower().split())


def normalize_slug(value: str) -> str:
    """Normalize a concept slug or human label to the canonical slug format."""

    return "-".join(normalize_text(value).replace("_", "-").split())


def _raise_concept_error(
    code: ErrorCode, message: str, *, field: str | None = None
) -> None:
    raise DomainValidationError([ErrorDetail(code=code, message=message, field=field)])
