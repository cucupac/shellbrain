"""Unified evidence repository storage contracts."""

from collections.abc import Callable
from datetime import datetime, timezone

import pytest

from app.core.entities.associations import (
    AssociationEdge,
    AssociationRelationType,
    AssociationSourceMode,
    AssociationState,
)
from app.core.entities.evidence import (
    EvidenceRole,
    EvidenceSource,
    EvidenceSourceKind,
    EvidenceTarget,
    EvidenceTargetType,
)
from app.core.entities.memories import (
    MemoryKind,
    MemoryLifecycleActor,
    MemoryLifecycleEvent,
    MemoryLifecycleStatus,
    MemoryScope,
)
from app.core.entities.structural_memory_relations import (
    StructuralMemoryRelation,
    StructuralMemoryRelationPredicate,
)
from app.core.entities.utility import UtilityObservation
from app.core.ports.system.clock import IClock
from app.core.use_cases.concepts.add import add_concepts
from app.core.use_cases.concepts.add.request import ConceptAddRequest
from app.core.use_cases.concepts.update import update_concepts
from app.core.use_cases.concepts.update.request import ConceptUpdateRequest
from app.infrastructure.db.runtime.models.concepts import (
    concept_claims,
    concept_groundings,
    concept_lifecycle_events,
    concept_memory_links,
    concept_relations,
)
from app.infrastructure.db.runtime.models.evidence import evidence_links, evidence_refs
from app.infrastructure.db.runtime.models.memories import memory_lifecycle_events
from app.infrastructure.db.runtime.uow import PostgresUnitOfWork
from tests.operations._shared.id_generators import SequenceIdGenerator


class _FixedClock(IClock):
    def now(self) -> datetime:
        return datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)


def test_unified_attach_should_write_concrete_evidence_links(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_memory: Callable[..., object],
    fetch_rows: Callable[..., list[dict[str, object]]],
) -> None:
    """Concrete evidence targets should persist through evidence_links."""

    _seed_concrete_evidence_targets(seed_memory)
    with uow_factory() as uow:
        uow.utility.append_observation(
            UtilityObservation(
                id="utility-observation-1",
                memory_id="memory-1",
                problem_id="problem-1",
                vote=1.0,
                rationale="Useful.",
            )
        )
        edge = uow.associations.upsert_edge(
            AssociationEdge(
                id="association-edge-1",
                repo_id="repo-a",
                from_memory_id="memory-1",
                to_memory_id="target-memory",
                relation_type=AssociationRelationType.ASSOCIATED_WITH,
                source_mode=AssociationSourceMode.AGENT,
                state=AssociationState.TENTATIVE,
                strength=0.5,
            )
        )
        event = uow.memories.add_lifecycle_event(
            MemoryLifecycleEvent(
                id="memory-lifecycle-event-1",
                repo_id="repo-a",
                memory_id="memory-1",
                from_status=MemoryLifecycleStatus.ACTIVE,
                to_status=MemoryLifecycleStatus.WRONG,
                rationale="Disproved by evidence.",
                actor=MemoryLifecycleActor.MANUAL,
                created_at=_FixedClock().now(),
            )
        )
        structural_relation = uow.experiences.upsert_structural_memory_relation(
            StructuralMemoryRelation(
                id="structural-memory-relation-1",
                repo_id="repo-a",
                subject_memory_id="old-fact",
                predicate=StructuralMemoryRelationPredicate.SUPERSEDED_BY,
                object_memory_id="new-fact",
            )
        )
        targets = (
            EvidenceTarget(
                target_type=EvidenceTargetType.MEMORY, target_id="memory-1"
            ),
            EvidenceTarget(
                target_type=EvidenceTargetType.UTILITY_OBSERVATION,
                target_id="utility-observation-1",
            ),
            EvidenceTarget(
                target_type=EvidenceTargetType.ASSOCIATION_EDGE,
                target_id=edge.id,
            ),
            EvidenceTarget(
                target_type=EvidenceTargetType.MEMORY_LIFECYCLE_EVENT,
                target_id=event.id,
            ),
            EvidenceTarget(
                target_type=EvidenceTargetType.STRUCTURAL_MEMORY_RELATION,
                target_id=structural_relation.id,
            ),
        )
        for target in targets:
            uow.evidence.attach_evidence(
                repo_id="repo-a",
                target=target,
                sources=(
                    EvidenceSource(
                        source_kind=EvidenceSourceKind.MANUAL,
                        note=f"{target.target_type.value} evidence.",
                    ),
                ),
            )

    assert len(fetch_rows(evidence_refs, evidence_refs.c.repo_id == "repo-a")) == 5
    assert len(fetch_rows(evidence_links, evidence_links.c.repo_id == "repo-a")) == 5
    assert len(fetch_rows(memory_lifecycle_events)) == 1

    with uow_factory() as uow:
        links = uow.evidence.resolve_evidence(repo_id="repo-a", targets=targets)

    assert {link.target.target_type for link in links} == {
        EvidenceTargetType.MEMORY,
        EvidenceTargetType.UTILITY_OBSERVATION,
        EvidenceTargetType.ASSOCIATION_EDGE,
        EvidenceTargetType.MEMORY_LIFECYCLE_EVENT,
        EvidenceTargetType.STRUCTURAL_MEMORY_RELATION,
    }
    assert {link.source.source_kind for link in links} == {EvidenceSourceKind.MANUAL}
    assert {link.role for link in links} == {EvidenceRole.SUPPORTS}


def test_unified_concept_evidence_should_resolve_across_truth_record_types(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_memory: Callable[..., object],
    fetch_rows: Callable[..., list[dict[str, object]]],
) -> None:
    """Concept evidence written by concept updates should resolve through one API."""

    seed_memory(
        memory_id="memory-1",
        repo_id="repo-a",
        scope=MemoryScope.REPO,
        kind=MemoryKind.FACT,
        text_value="Concept memory evidence.",
    )
    _seed_concepts(uow_factory)
    with uow_factory() as uow:
        update_concepts(
            ConceptUpdateRequest.model_validate(
                {
                    "schema_version": "concept.v1",
                    "repo_id": "repo-a",
                    "actions": [
                        {
                            "type": "add_relation",
                            "subject": "source-concept",
                            "predicate": "depends_on",
                            "object": "target-concept",
                            "evidence": [
                                {"kind": "manual", "note": "Relation evidence."}
                            ],
                        },
                        {
                            "type": "add_claim",
                            "concept": "source-concept",
                            "claim_type": "definition",
                            "text": "Source concept definition.",
                            "evidence": [
                                {"kind": "manual", "note": "Claim evidence."}
                            ],
                        },
                        {
                            "type": "add_grounding",
                            "concept": "source-concept",
                            "role": "implementation",
                            "anchor": {"kind": "file", "locator": {"path": "app.py"}},
                            "evidence": [
                                {"kind": "manual", "note": "Grounding evidence."}
                            ],
                        },
                        {
                            "type": "link_memory",
                            "concept": "source-concept",
                            "role": "example_of",
                            "memory_id": "memory-1",
                            "evidence": [
                                {"kind": "memory", "memory_id": "memory-1"}
                            ],
                        },
                    ],
                }
            ),
            uow,
            id_generator=SequenceIdGenerator(),
        )

    claim_id = str(fetch_rows(concept_claims)[0]["id"])
    with uow_factory() as uow:
        update_concepts(
            ConceptUpdateRequest.model_validate(
                {
                    "schema_version": "concept.v1",
                    "repo_id": "repo-a",
                    "actions": [
                        {
                            "type": "update_lifecycle",
                            "target_type": "claim",
                            "target_id": claim_id,
                            "status": "wrong",
                            "rationale": "Claim was disproven.",
                            "actor": "manual",
                            "evidence": [
                                {
                                    "kind": "manual",
                                    "note": "Lifecycle event evidence.",
                                }
                            ],
                        }
                    ],
                }
            ),
            uow,
            id_generator=SequenceIdGenerator(prefix="lifecycle"),
            clock=_FixedClock(),
        )

    targets = (
        EvidenceTarget(
            target_type=EvidenceTargetType.CONCEPT_RELATION,
            target_id=str(fetch_rows(concept_relations)[0]["id"]),
        ),
        EvidenceTarget(
            target_type=EvidenceTargetType.CONCEPT_CLAIM,
            target_id=claim_id,
        ),
        EvidenceTarget(
            target_type=EvidenceTargetType.CONCEPT_GROUNDING,
            target_id=str(fetch_rows(concept_groundings)[0]["id"]),
        ),
        EvidenceTarget(
            target_type=EvidenceTargetType.CONCEPT_MEMORY_LINK,
            target_id=str(fetch_rows(concept_memory_links)[0]["id"]),
        ),
        EvidenceTarget(
            target_type=EvidenceTargetType.CONCEPT_LIFECYCLE_EVENT,
            target_id=str(fetch_rows(concept_lifecycle_events)[0]["id"]),
        ),
    )
    with uow_factory() as uow:
        links = uow.evidence.resolve_evidence(repo_id="repo-a", targets=targets)

    assert len(fetch_rows(evidence_links, evidence_links.c.repo_id == "repo-a")) == 5
    assert {link.target.target_type for link in links} == {
        EvidenceTargetType.CONCEPT_RELATION,
        EvidenceTargetType.CONCEPT_CLAIM,
        EvidenceTargetType.CONCEPT_GROUNDING,
        EvidenceTargetType.CONCEPT_MEMORY_LINK,
        EvidenceTargetType.CONCEPT_LIFECYCLE_EVENT,
    }
    assert {link.role for link in links} == {EvidenceRole.SUPPORTS}
    assert {link.source.source_kind for link in links} == {
        EvidenceSourceKind.MANUAL,
        EvidenceSourceKind.MEMORY,
    }
    assert "Lifecycle event evidence." in {
        link.source.note for link in links if link.source.note is not None
    }


def test_unified_attach_should_validate_targets_and_persist_roles(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_memory: Callable[..., object],
    fetch_rows: Callable[..., list[dict[str, object]]],
) -> None:
    """Target validation should run before writes and roles should persist."""

    seed_memory(
        memory_id="memory-1",
        repo_id="repo-a",
        scope=MemoryScope.REPO,
        kind=MemoryKind.FACT,
        text_value="Evidence target.",
    )
    memory_target = EvidenceTarget(
        target_type=EvidenceTargetType.MEMORY, target_id="memory-1"
    )
    missing_target = EvidenceTarget(
        target_type=EvidenceTargetType.MEMORY, target_id="missing-memory"
    )

    with pytest.raises(ValueError, match="evidence target not found"):
        with uow_factory() as uow:
            uow.evidence.attach_evidence(
                repo_id="repo-a",
                target=missing_target,
                sources=(
                    EvidenceSource(
                        source_kind=EvidenceSourceKind.MANUAL,
                        note="Missing target evidence.",
                    ),
                ),
            )

    with uow_factory() as uow:
        uow.evidence.attach_evidence(
            repo_id="repo-a",
            target=memory_target,
            sources=(
                EvidenceSource(
                    source_kind=EvidenceSourceKind.MANUAL,
                    note="Memory evidence.",
                ),
            ),
            role=EvidenceRole.CONTRADICTS,
        )
        links = uow.evidence.resolve_evidence(repo_id="repo-a", targets=(memory_target,))

    assert {link.role for link in links} == {EvidenceRole.CONTRADICTS}
    assert fetch_rows(evidence_links)[0]["evidence_role"] == "contradicts"


def test_unified_attach_should_be_idempotent(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_memory: Callable[..., object],
    fetch_rows: Callable[..., list[dict[str, object]]],
) -> None:
    """Repeated unified evidence attaches should not duplicate rows."""

    seed_memory(
        memory_id="memory-1",
        repo_id="repo-a",
        scope=MemoryScope.REPO,
        kind=MemoryKind.FACT,
        text_value="Evidence target.",
    )
    target = EvidenceTarget(
        target_type=EvidenceTargetType.MEMORY, target_id="memory-1"
    )
    source = EvidenceSource(
        source_kind=EvidenceSourceKind.MANUAL, note="Repeated evidence."
    )

    with uow_factory() as uow:
        first_links = uow.evidence.attach_evidence(
            repo_id="repo-a", target=target, sources=(source,)
        )
        second_links = uow.evidence.attach_evidence(
            repo_id="repo-a", target=target, sources=(source,)
        )

    assert len(fetch_rows(evidence_refs)) == 1
    assert len(fetch_rows(evidence_links)) == 1
    assert first_links[0].created_at == second_links[0].created_at


def _seed_concrete_evidence_targets(seed_memory: Callable[..., object]) -> None:
    """Seed the memories needed by concrete evidence target rows."""

    for memory_id, kind in (
        ("memory-1", MemoryKind.FACT),
        ("target-memory", MemoryKind.FACT),
        ("old-fact", MemoryKind.FACT),
        ("change-memory", MemoryKind.CHANGE),
        ("new-fact", MemoryKind.FACT),
        ("problem-1", MemoryKind.PROBLEM),
    ):
        seed_memory(
            memory_id=memory_id,
            repo_id="repo-a",
            scope=MemoryScope.REPO,
            kind=kind,
            text_value=f"{memory_id} text.",
        )


def _seed_concepts(uow_factory: Callable[[], PostgresUnitOfWork]) -> None:
    """Seed the concept containers used by concept evidence tests."""

    with uow_factory() as uow:
        add_concepts(
            ConceptAddRequest.model_validate(
                {
                    "schema_version": "concept.v1",
                    "repo_id": "repo-a",
                    "actions": [
                        {
                            "type": "add_concept",
                            "slug": "source-concept",
                            "name": "Source Concept",
                            "kind": "component",
                        },
                        {
                            "type": "add_concept",
                            "slug": "target-concept",
                            "name": "Target Concept",
                            "kind": "component",
                        },
                    ],
                }
            ),
            uow,
            id_generator=SequenceIdGenerator(),
        )
