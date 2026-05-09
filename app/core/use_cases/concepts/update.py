"""Concept update use case."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from app.core.contracts.concepts import (
    AddClaimAction,
    AddGroundingAction,
    AddRelationAction,
    ConceptEvidencePayload,
    ConceptUpdateRequest,
    EnsureAnchorAction,
    LinkMemoryAction,
    UpdateConceptAction,
)
from app.core.contracts.errors import DomainValidationError, ErrorCode, ErrorDetail
from app.core.contracts.responses import UseCaseResult
from app.core.entities.concepts import (
    Anchor,
    AnchorKind,
    Concept,
    ConceptClaim,
    ConceptClaimType,
    ConceptCreatedBy,
    ConceptEvidence,
    ConceptEvidenceKind,
    ConceptEvidenceTargetType,
    ConceptGrounding,
    ConceptGroundingRole,
    ConceptKind,
    ConceptLifecycle,
    ConceptMemoryLink,
    ConceptMemoryLinkRole,
    ConceptRelation,
    ConceptRelationPredicate,
    ConceptSourceKind,
    ConceptStatus,
)
from app.core.ports.runtime.idgen import IIdGenerator
from app.core.ports.db.unit_of_work import IUnitOfWork
from app.core.policies.concepts.relation_rules import validate_relation_shape
from app.core.use_cases.concepts.containment_checks import validate_contains_relation
from app.core.use_cases.concepts.reference_checks import (
    normalize_text,
    require_anchor,
    require_concept,
    require_visible_memory,
    validate_evidence_visibility,
)


def update_concepts(
    request: ConceptUpdateRequest,
    uow: IUnitOfWork,
    *,
    id_generator: IIdGenerator,
) -> UseCaseResult:
    """Update existing concepts and truth-bearing graph records."""

    results: list[dict[str, Any]] = []
    for action in request.actions:
        try:
            if isinstance(action, UpdateConceptAction):
                results.append(_update_concept(request.repo_id, action, uow))
            elif isinstance(action, AddRelationAction):
                results.append(
                    _add_relation(
                        request.repo_id, action, uow, id_generator=id_generator
                    )
                )
            elif isinstance(action, AddClaimAction):
                results.append(
                    _add_claim(request.repo_id, action, uow, id_generator=id_generator)
                )
            elif isinstance(action, EnsureAnchorAction):
                results.append(
                    _ensure_anchor(
                        request.repo_id, action, uow, id_generator=id_generator
                    )
                )
            elif isinstance(action, AddGroundingAction):
                results.append(
                    _add_grounding(
                        request.repo_id, action, uow, id_generator=id_generator
                    )
                )
            elif isinstance(action, LinkMemoryAction):
                results.append(
                    _link_memory(
                        request.repo_id, action, uow, id_generator=id_generator
                    )
                )
            else:  # pragma: no cover - discriminated contract should make this impossible.
                raise DomainValidationError(
                    [
                        ErrorDetail(
                            code=ErrorCode.SEMANTIC_ERROR,
                            message=f"Unsupported concept update action type: {getattr(action, 'type', '<unknown>')}",
                            field="actions",
                        )
                    ]
                )
        except DomainValidationError:
            raise
        except ValueError as exc:
            raise DomainValidationError(
                [ErrorDetail(code=ErrorCode.SEMANTIC_ERROR, message=str(exc))]
            ) from exc
    return UseCaseResult(data={"updated_count": len(results), "results": results})


def _update_concept(
    repo_id: str, action: UpdateConceptAction, uow: IUnitOfWork
) -> dict[str, Any]:
    existing = require_concept(repo_id, action.concept, uow)
    concept = Concept(
        id=existing.id,
        repo_id=existing.repo_id,
        slug=existing.slug,
        name=action.name if action.name is not None else existing.name,
        kind=ConceptKind(action.kind) if action.kind is not None else existing.kind,
        status=ConceptStatus(action.status)
        if action.status is not None
        else existing.status,
        scope_note=action.scope_note
        if "scope_note" in action.model_fields_set
        else existing.scope_note,
        created_at=existing.created_at,
        updated_at=existing.updated_at,
    )
    stored = uow.concepts.update_concept(concept, aliases=action.aliases or ())
    return {"type": action.type, "concept_id": stored.id, "slug": stored.slug}


def _add_relation(
    repo_id: str,
    action: AddRelationAction,
    uow: IUnitOfWork,
    *,
    id_generator: IIdGenerator,
) -> dict[str, Any]:
    subject = require_concept(repo_id, action.subject, uow)
    object_concept = require_concept(repo_id, action.object, uow)
    predicate = ConceptRelationPredicate(action.predicate)
    validate_relation_shape(
        subject=subject, predicate=predicate, object_concept=object_concept
    )
    validate_contains_relation(
        repo_id=repo_id,
        predicate=predicate,
        subject_id=subject.id,
        object_id=object_concept.id,
        uow=uow,
    )
    relation = uow.concepts.add_relation(
        ConceptRelation(
            id=id_generator.new_id(),
            repo_id=repo_id,
            subject_concept_id=subject.id,
            predicate=predicate,
            object_concept_id=object_concept.id,
            lifecycle=_lifecycle_from_action(action),
        )
    )
    _attach_evidence(
        repo_id,
        ConceptEvidenceTargetType.RELATION,
        relation.id,
        action.evidence,
        uow,
        id_generator,
    )
    return {"type": action.type, "relation_id": relation.id}


def _add_claim(
    repo_id: str,
    action: AddClaimAction,
    uow: IUnitOfWork,
    *,
    id_generator: IIdGenerator,
) -> dict[str, Any]:
    concept = require_concept(repo_id, action.concept, uow)
    claim = uow.concepts.add_claim(
        ConceptClaim(
            id=id_generator.new_id(),
            repo_id=repo_id,
            concept_id=concept.id,
            claim_type=ConceptClaimType(action.claim_type),
            text=action.text,
            normalized_text=normalize_text(action.text),
            lifecycle=_lifecycle_from_action(action),
        )
    )
    _attach_evidence(
        repo_id,
        ConceptEvidenceTargetType.CLAIM,
        claim.id,
        action.evidence,
        uow,
        id_generator,
    )
    return {"type": action.type, "claim_id": claim.id}


def _ensure_anchor(
    repo_id: str,
    action: EnsureAnchorAction,
    uow: IUnitOfWork,
    *,
    id_generator: IIdGenerator,
) -> dict[str, Any]:
    anchor = _ensure_anchor_from_payload(
        repo_id, action.kind, action.locator, uow, id_generator
    )
    return {
        "type": action.type,
        "anchor_id": anchor.id,
        "canonical_locator_hash": anchor.canonical_locator_hash,
    }


def _add_grounding(
    repo_id: str,
    action: AddGroundingAction,
    uow: IUnitOfWork,
    *,
    id_generator: IIdGenerator,
) -> dict[str, Any]:
    concept = require_concept(repo_id, action.concept, uow)
    if action.anchor.id:
        anchor = require_anchor(repo_id, action.anchor.id, uow)
    else:
        assert action.anchor.kind is not None and action.anchor.locator is not None
        anchor = _ensure_anchor_from_payload(
            repo_id, action.anchor.kind, action.anchor.locator, uow, id_generator
        )
    grounding = uow.concepts.add_grounding(
        ConceptGrounding(
            id=id_generator.new_id(),
            repo_id=repo_id,
            concept_id=concept.id,
            role=ConceptGroundingRole(action.role),
            anchor_id=anchor.id,
            lifecycle=_lifecycle_from_action(action),
        )
    )
    _attach_evidence(
        repo_id,
        ConceptEvidenceTargetType.GROUNDING,
        grounding.id,
        action.evidence,
        uow,
        id_generator,
    )
    return {"type": action.type, "grounding_id": grounding.id, "anchor_id": anchor.id}


def _link_memory(
    repo_id: str,
    action: LinkMemoryAction,
    uow: IUnitOfWork,
    *,
    id_generator: IIdGenerator,
) -> dict[str, Any]:
    concept = require_concept(repo_id, action.concept, uow)
    memory = require_visible_memory(repo_id, action.memory_id, uow)
    memory_link = uow.concepts.add_memory_link(
        ConceptMemoryLink(
            id=id_generator.new_id(),
            repo_id=repo_id,
            concept_id=concept.id,
            role=ConceptMemoryLinkRole(action.role),
            memory_id=memory.id,
            lifecycle=_lifecycle_from_action(action),
        )
    )
    _attach_evidence(
        repo_id,
        ConceptEvidenceTargetType.MEMORY_LINK,
        memory_link.id,
        action.evidence,
        uow,
        id_generator,
    )
    return {"type": action.type, "memory_link_id": memory_link.id}


def _lifecycle_from_action(action) -> ConceptLifecycle:
    return ConceptLifecycle(
        confidence=float(action.confidence),
        observed_at=action.observed_at,
        validated_at=action.validated_at,
        source_kind=ConceptSourceKind(action.source_kind)
        if action.source_kind is not None
        else None,
        source_ref=action.source_ref,
        created_by=ConceptCreatedBy(action.created_by),
    )


def _ensure_anchor_from_payload(
    repo_id: str,
    kind: str,
    locator: dict[str, Any],
    uow: IUnitOfWork,
    id_generator: IIdGenerator,
) -> Anchor:
    canonical_hash = _canonical_locator_hash(kind=kind, locator=locator)
    return uow.concepts.upsert_anchor(
        Anchor(
            id=id_generator.new_id(),
            repo_id=repo_id,
            kind=AnchorKind(kind),
            locator_json=dict(locator),
            canonical_locator_hash=canonical_hash,
        )
    )


def _attach_evidence(
    repo_id: str,
    target_type: ConceptEvidenceTargetType,
    target_id: str,
    evidence_items: list[ConceptEvidencePayload],
    uow: IUnitOfWork,
    id_generator: IIdGenerator,
) -> None:
    for item in evidence_items:
        validate_evidence_visibility(repo_id, item, uow)
        uow.concepts.add_evidence(
            ConceptEvidence(
                id=id_generator.new_id(),
                repo_id=repo_id,
                target_type=target_type,
                target_id=target_id,
                evidence_kind=ConceptEvidenceKind(item.kind),
                anchor_id=item.anchor_id,
                memory_id=item.memory_id,
                commit_ref=item.commit_ref,
                transcript_ref=item.transcript_ref,
                note=item.note,
            )
        )


def _canonical_locator_hash(*, kind: str, locator: dict[str, Any]) -> str:
    serialized = json.dumps(
        {"kind": kind, "locator": locator},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return "sha256:" + hashlib.sha256(serialized.encode("utf-8")).hexdigest()
