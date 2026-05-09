"""Repository-backed containment checks for concept relations."""

from __future__ import annotations

from app.core.entities.concepts import ConceptRelationPredicate
from app.core.ports.unit_of_work import IUnitOfWork
from app.core.policies.concepts.relation_rules import validate_no_contains_cycle


def validate_contains_relation(
    *,
    repo_id: str,
    predicate: ConceptRelationPredicate,
    subject_id: str,
    object_id: str,
    uow: IUnitOfWork,
) -> None:
    """Validate repo-backed contains constraints for one proposed relation."""

    if predicate != ConceptRelationPredicate.CONTAINS:
        return
    validate_no_contains_cycle(
        contains_edges=uow.concepts.list_contains_edges(repo_id=repo_id),
        subject_id=subject_id,
        object_id=object_id,
    )
