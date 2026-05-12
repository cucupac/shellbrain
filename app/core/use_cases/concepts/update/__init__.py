"""Concept update use case."""

from app.core.use_cases.concepts.update.request import (
    AddClaimAction,
    AddGroundingAction,
    AddRelationAction,
    AnchorSelector,
    ConceptEvidencePayload,
    ConceptUpdateAction,
    ConceptUpdateRequest,
    EnsureAnchorAction,
    LinkMemoryAction,
    UpdateConceptAction,
)
from app.core.use_cases.concepts.update.result import ConceptUpdateResult

__all__ = [
    "AddClaimAction",
    "AddGroundingAction",
    "AddRelationAction",
    "AnchorSelector",
    "ConceptEvidencePayload",
    "ConceptUpdateAction",
    "ConceptUpdateRequest",
    "ConceptUpdateResult",
    "EnsureAnchorAction",
    "LinkMemoryAction",
    "UpdateConceptAction",
    "update_concepts",
]


def __getattr__(name: str):
    if name == "update_concepts":
        from app.core.use_cases.concepts.update.execute import update_concepts

        return update_concepts
    raise AttributeError(name)
