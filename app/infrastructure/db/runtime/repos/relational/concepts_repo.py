"""Relational repository operations for the concept-context graph."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Sequence

from sqlalchemy import and_, or_, select, update
from sqlalchemy.dialects.postgresql import insert

from app.core.entities.concepts import (
    Anchor,
    AnchorKind,
    AnchorStatus,
    Concept,
    ConceptAlias,
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
    ConceptLifecycleEvent,
    ConceptLifecycleStatus,
    ConceptLifecycleTargetType,
    ConceptMemoryLink,
    ConceptMemoryLinkRole,
    ConceptRelation,
    ConceptRelationPredicate,
    ConceptSourceKind,
    ConceptStatus,
    GraphPatch,
)
from app.core.ports.db.concept_repositories import IConceptsRepo
from app.infrastructure.db.runtime.models.concepts import (
    anchors,
    concept_aliases,
    concept_claims,
    concept_embeddings,
    concept_groundings,
    concept_lifecycle_events,
    concept_memory_links,
    concept_relations,
    concepts,
    graph_patches,
)
from app.infrastructure.db.runtime.models.evidence import evidence_links, evidence_refs


class ConceptsRepo(IConceptsRepo):
    """This class provides concept graph persistence operations."""

    def __init__(self, session) -> None:
        """Store the active SQLAlchemy session."""

        self._session = session

    def add_concept(self, concept: Concept, aliases: Sequence[str]) -> Concept:
        """Insert a new concept and its aliases."""

        now = datetime.now(timezone.utc)
        self._session.execute(
            concepts.insert().values(
                id=concept.id,
                repo_id=concept.repo_id,
                slug=concept.slug,
                name=concept.name,
                kind=concept.kind.value,
                status=concept.status.value,
                scope_note=concept.scope_note,
                created_at=now,
                updated_at=now,
            )
        )
        self._add_aliases(
            concept_id=concept.id, repo_id=concept.repo_id, aliases=aliases, now=now
        )
        return concept

    def update_concept(self, concept: Concept, aliases: Sequence[str]) -> Concept:
        """Update an existing concept and add aliases."""

        now = datetime.now(timezone.utc)
        self._session.execute(
            update(concepts)
            .where(concepts.c.id == concept.id, concepts.c.repo_id == concept.repo_id)
            .values(
                name=concept.name,
                kind=concept.kind.value,
                status=concept.status.value,
                scope_note=concept.scope_note,
                updated_at=now,
            )
        )
        self._add_aliases(
            concept_id=concept.id, repo_id=concept.repo_id, aliases=aliases, now=now
        )
        return Concept(
            id=concept.id,
            repo_id=concept.repo_id,
            slug=concept.slug,
            name=concept.name,
            kind=concept.kind,
            status=concept.status,
            scope_note=concept.scope_note,
            created_at=concept.created_at,
            updated_at=now,
        )

    def _add_aliases(
        self, *, concept_id: str, repo_id: str, aliases: Sequence[str], now: datetime
    ) -> None:
        """Insert or refresh aliases for one concept."""

        for alias in aliases:
            normalized = _normalize_text(alias)
            if not normalized:
                continue
            self._session.execute(
                insert(concept_aliases)
                .values(
                    concept_id=concept_id,
                    repo_id=repo_id,
                    alias=alias,
                    normalized_alias=normalized,
                    created_at=now,
                )
                .on_conflict_do_update(
                    index_elements=["concept_id", "normalized_alias"],
                    set_={"alias": alias, "repo_id": repo_id},
                )
            )

    def get_concept_by_ref(self, *, repo_id: str, concept_ref: str) -> Concept | None:
        """Resolve a concept by id or slug."""

        row = (
            self._session.execute(
                select(concepts).where(
                    concepts.c.repo_id == repo_id,
                    (concepts.c.id == concept_ref) | (concepts.c.slug == concept_ref),
                )
            )
            .mappings()
            .first()
        )
        return _to_concept(row) if row is not None else None

    def list_concepts_by_ids(
        self, *, repo_id: str, concept_ids: Sequence[str]
    ) -> Sequence[Concept]:
        """Return concept rows in input order."""

        unique_ids = list(dict.fromkeys(str(concept_id) for concept_id in concept_ids))
        if not unique_ids:
            return []
        rows = (
            self._session.execute(
                select(concepts).where(
                    concepts.c.repo_id == repo_id, concepts.c.id.in_(unique_ids)
                )
            )
            .mappings()
            .all()
        )
        by_id = {str(row["id"]): _to_concept(row) for row in rows}
        return [by_id[concept_id] for concept_id in unique_ids if concept_id in by_id]

    def list_concepts(
        self, *, repo_id: str, statuses: Sequence[str]
    ) -> Sequence[Concept]:
        """Return concepts for one repo and status set."""

        status_values = tuple(dict.fromkeys(str(status) for status in statuses))
        if not status_values:
            return []
        rows = (
            self._session.execute(
                select(concepts)
                .where(
                    concepts.c.repo_id == repo_id,
                    concepts.c.status.in_(status_values),
                )
                .order_by(
                    concepts.c.kind.asc(), concepts.c.name.asc(), concepts.c.slug.asc()
                )
            )
            .mappings()
            .all()
        )
        return [_to_concept(row) for row in rows]

    def list_contains_edges(self, *, repo_id: str) -> Sequence[ConceptRelation]:
        """Return active contains edges for one repo."""

        rows = (
            self._session.execute(
                select(concept_relations).where(
                    concept_relations.c.repo_id == repo_id,
                    concept_relations.c.predicate
                    == ConceptRelationPredicate.CONTAINS.value,
                    concept_relations.c.status == ConceptLifecycleStatus.ACTIVE.value,
                )
            )
            .mappings()
            .all()
        )
        return [_to_relation(row) for row in rows]

    def add_relation(self, relation: ConceptRelation) -> ConceptRelation:
        """Insert or return an active concept relation."""

        existing = (
            self._session.execute(
                select(concept_relations).where(
                    concept_relations.c.repo_id == relation.repo_id,
                    concept_relations.c.subject_concept_id
                    == relation.subject_concept_id,
                    concept_relations.c.predicate == relation.predicate.value,
                    concept_relations.c.object_concept_id == relation.object_concept_id,
                    concept_relations.c.status == ConceptLifecycleStatus.ACTIVE.value,
                )
            )
            .mappings()
            .first()
        )
        if existing is not None:
            return _to_relation(existing)
        now = datetime.now(timezone.utc)
        lifecycle = relation.lifecycle
        self._session.execute(
            concept_relations.insert().values(
                id=relation.id,
                repo_id=relation.repo_id,
                subject_concept_id=relation.subject_concept_id,
                predicate=relation.predicate.value,
                object_concept_id=relation.object_concept_id,
                **_lifecycle_values(lifecycle, now),
                created_at=now,
                updated_at=now,
            )
        )
        return relation

    def add_claim(self, claim: ConceptClaim) -> ConceptClaim:
        """Insert or return a concept claim by natural key."""

        existing = (
            self._session.execute(
                select(concept_claims).where(
                    concept_claims.c.repo_id == claim.repo_id,
                    concept_claims.c.concept_id == claim.concept_id,
                    concept_claims.c.claim_type == claim.claim_type.value,
                    concept_claims.c.normalized_text == claim.normalized_text,
                )
            )
            .mappings()
            .first()
        )
        if existing is not None:
            return _to_claim(existing)
        now = datetime.now(timezone.utc)
        self._session.execute(
            concept_claims.insert().values(
                id=claim.id,
                repo_id=claim.repo_id,
                concept_id=claim.concept_id,
                claim_type=claim.claim_type.value,
                text=claim.text,
                normalized_text=claim.normalized_text,
                **_lifecycle_values(claim.lifecycle, now),
                created_at=now,
                updated_at=now,
            )
        )
        return claim

    def upsert_anchor(self, anchor: Anchor) -> Anchor:
        """Insert or return an anchor by canonical locator."""

        existing = (
            self._session.execute(
                select(anchors).where(
                    anchors.c.repo_id == anchor.repo_id,
                    anchors.c.kind == anchor.kind.value,
                    anchors.c.canonical_locator_hash == anchor.canonical_locator_hash,
                )
            )
            .mappings()
            .first()
        )
        if existing is not None:
            return _to_anchor(existing)
        now = datetime.now(timezone.utc)
        self._session.execute(
            anchors.insert().values(
                id=anchor.id,
                repo_id=anchor.repo_id,
                kind=anchor.kind.value,
                locator_json=anchor.locator_json,
                canonical_locator_hash=anchor.canonical_locator_hash,
                status=anchor.status.value,
                created_at=now,
                updated_at=now,
            )
        )
        return anchor

    def get_anchor(self, *, repo_id: str, anchor_id: str) -> Anchor | None:
        """Fetch one anchor by id."""

        row = (
            self._session.execute(
                select(anchors).where(
                    anchors.c.repo_id == repo_id, anchors.c.id == anchor_id
                )
            )
            .mappings()
            .first()
        )
        return _to_anchor(row) if row is not None else None

    def add_grounding(self, grounding: ConceptGrounding) -> ConceptGrounding:
        """Insert or return an active concept grounding."""

        existing = (
            self._session.execute(
                select(concept_groundings).where(
                    concept_groundings.c.repo_id == grounding.repo_id,
                    concept_groundings.c.concept_id == grounding.concept_id,
                    concept_groundings.c.role == grounding.role.value,
                    concept_groundings.c.anchor_id == grounding.anchor_id,
                    concept_groundings.c.status == ConceptLifecycleStatus.ACTIVE.value,
                )
            )
            .mappings()
            .first()
        )
        if existing is not None:
            return _to_grounding(existing)
        now = datetime.now(timezone.utc)
        self._session.execute(
            concept_groundings.insert().values(
                id=grounding.id,
                repo_id=grounding.repo_id,
                concept_id=grounding.concept_id,
                role=grounding.role.value,
                anchor_id=grounding.anchor_id,
                **_lifecycle_values(grounding.lifecycle, now),
                created_at=now,
                updated_at=now,
            )
        )
        return grounding

    def add_memory_link(self, memory_link: ConceptMemoryLink) -> ConceptMemoryLink:
        """Insert or return an active concept-memory link."""

        existing = (
            self._session.execute(
                select(concept_memory_links).where(
                    concept_memory_links.c.repo_id == memory_link.repo_id,
                    concept_memory_links.c.concept_id == memory_link.concept_id,
                    concept_memory_links.c.role == memory_link.role.value,
                    concept_memory_links.c.memory_id == memory_link.memory_id,
                    concept_memory_links.c.status
                    == ConceptLifecycleStatus.ACTIVE.value,
                )
            )
            .mappings()
            .first()
        )
        if existing is not None:
            return _to_memory_link(existing)
        now = datetime.now(timezone.utc)
        self._session.execute(
            concept_memory_links.insert().values(
                id=memory_link.id,
                repo_id=memory_link.repo_id,
                concept_id=memory_link.concept_id,
                role=memory_link.role.value,
                memory_id=memory_link.memory_id,
                **_lifecycle_values(memory_link.lifecycle, now),
                created_at=now,
                updated_at=now,
            )
        )
        return memory_link

    def get_lifecycle_target(
        self, *, repo_id: str, target_type: ConceptLifecycleTargetType, target_id: str
    ) -> ConceptRelation | ConceptClaim | ConceptGrounding | ConceptMemoryLink | None:
        """Fetch one truth-bearing concept record by lifecycle target."""

        table, converter = _lifecycle_target_table(target_type)
        row = (
            self._session.execute(
                select(table).where(
                    table.c.repo_id == repo_id, table.c.id == target_id
                )
            )
            .mappings()
            .first()
        )
        return converter(row) if row is not None else None

    def update_lifecycle_target(
        self,
        target: ConceptRelation | ConceptClaim | ConceptGrounding | ConceptMemoryLink,
    ) -> ConceptRelation | ConceptClaim | ConceptGrounding | ConceptMemoryLink:
        """Update lifecycle fields for one truth-bearing concept record."""

        target_type = _target_type_for_record(target)
        table, converter = _lifecycle_target_table(target_type)
        now = datetime.now(timezone.utc)
        self._session.execute(
            update(table)
            .where(table.c.repo_id == target.repo_id, table.c.id == target.id)
            .values(
                **_lifecycle_values(target.lifecycle, now),
                updated_at=now,
            )
        )
        row = (
            self._session.execute(
                select(table).where(
                    table.c.repo_id == target.repo_id, table.c.id == target.id
                )
            )
            .mappings()
            .one()
        )
        return converter(row)

    def add_lifecycle_event(
        self, event: ConceptLifecycleEvent
    ) -> ConceptLifecycleEvent:
        """Append one auditable concept lifecycle transition."""

        self._session.execute(
            concept_lifecycle_events.insert().values(
                id=event.id,
                repo_id=event.repo_id,
                target_type=event.target_type.value,
                target_id=event.target_id,
                from_status=event.from_status.value,
                to_status=event.to_status.value,
                rationale=event.rationale,
                actor=event.actor.value,
                superseded_by_id=event.superseded_by_id,
                created_at=datetime.now(timezone.utc),
            )
        )
        return event

    def create_graph_patch(self, patch: GraphPatch) -> GraphPatch:
        """Store one graph patch proposal record."""

        self._session.execute(
            graph_patches.insert().values(
                id=patch.id,
                repo_id=patch.repo_id,
                schema_version=patch.schema_version,
                status=patch.status.value,
                proposed_by=patch.proposed_by.value,
                operations_json=patch.operations_json,
                evidence_summary=patch.evidence_summary,
                created_at=datetime.now(timezone.utc),
                applied_at=patch.applied_at,
            )
        )
        return patch

    def get_concept_bundle(
        self,
        *,
        repo_id: str,
        concept_ref: str,
        include_lifecycle_events: bool = False,
    ) -> dict[str, Any] | None:
        """Return one concept plus directly related graph records."""

        concept = self.get_concept_by_ref(repo_id=repo_id, concept_ref=concept_ref)
        if concept is None:
            return None
        relation_rows = (
            self._session.execute(
                select(concept_relations).where(
                    concept_relations.c.repo_id == repo_id,
                    (
                        (concept_relations.c.subject_concept_id == concept.id)
                        | (concept_relations.c.object_concept_id == concept.id)
                    ),
                )
            )
            .mappings()
            .all()
        )
        claim_rows = (
            self._session.execute(
                select(concept_claims).where(
                    concept_claims.c.repo_id == repo_id,
                    concept_claims.c.concept_id == concept.id,
                )
            )
            .mappings()
            .all()
        )
        grounding_rows = (
            self._session.execute(
                select(concept_groundings).where(
                    concept_groundings.c.repo_id == repo_id,
                    concept_groundings.c.concept_id == concept.id,
                )
            )
            .mappings()
            .all()
        )
        memory_link_rows = (
            self._session.execute(
                select(concept_memory_links).where(
                    concept_memory_links.c.repo_id == repo_id,
                    concept_memory_links.c.concept_id == concept.id,
                )
            )
            .mappings()
            .all()
        )
        alias_rows = (
            self._session.execute(
                select(concept_aliases).where(
                    concept_aliases.c.repo_id == repo_id,
                    concept_aliases.c.concept_id == concept.id,
                )
            )
            .mappings()
            .all()
        )
        anchor_ids = [str(row["anchor_id"]) for row in grounding_rows]
        anchor_rows = []
        if anchor_ids:
            anchor_rows = (
                self._session.execute(
                    select(anchors).where(
                        anchors.c.repo_id == repo_id, anchors.c.id.in_(anchor_ids)
                    )
                )
                .mappings()
                .all()
            )
        target_pairs = (
            [("relation", "concept_relation", str(row["id"])) for row in relation_rows]
            + [("claim", "concept_claim", str(row["id"])) for row in claim_rows]
            + [
                ("grounding", "concept_grounding", str(row["id"]))
                for row in grounding_rows
            ]
            + [
                ("memory_link", "concept_memory_link", str(row["id"]))
                for row in memory_link_rows
            ]
        )
        lifecycle_event_rows = []
        if include_lifecycle_events and target_pairs:
            lifecycle_event_rows = (
                self._session.execute(
                    select(concept_lifecycle_events).where(
                        concept_lifecycle_events.c.repo_id == repo_id,
                        or_(
                            *[
                                and_(
                                    concept_lifecycle_events.c.target_type
                                    == lifecycle_target_type,
                                    concept_lifecycle_events.c.target_id
                                    == target_id,
                                )
                                for lifecycle_target_type, _, target_id in target_pairs
                            ]
                        ),
                    )
                )
                .mappings()
                .all()
            )
        event_pairs = [
            ("lifecycle_event", "concept_lifecycle_event", str(row["id"]))
            for row in lifecycle_event_rows
        ]
        evidence_rows = []
        evidence_pairs = target_pairs + event_pairs
        if evidence_pairs:
            evidence_rows = self._unified_evidence_rows(
                repo_id=repo_id, evidence_pairs=evidence_pairs
            )
        return {
            "concept": concept,
            "aliases": [_to_alias(row) for row in alias_rows],
            "relations": [_to_relation(row) for row in relation_rows],
            "claims": [_to_claim(row) for row in claim_rows],
            "groundings": [_to_grounding(row) for row in grounding_rows],
            "memory_links": [_to_memory_link(row) for row in memory_link_rows],
            "lifecycle_events": [
                _to_lifecycle_event(row) for row in lifecycle_event_rows
            ],
            "anchors": [_to_anchor(row) for row in anchor_rows],
            "evidence": [_to_evidence(row) for row in evidence_rows],
        }

    def _unified_evidence_rows(
        self, *, repo_id: str, evidence_pairs: Sequence[tuple[str, str, str]]
    ) -> list[dict[str, Any]]:
        """Return concept evidence rows from unified evidence storage."""

        rows = (
            self._session.execute(
                select(
                    evidence_links.c.id.label("id"),
                    evidence_links.c.repo_id,
                    evidence_links.c.target_type,
                    evidence_links.c.target_id,
                    evidence_links.c.created_at,
                    evidence_refs.c.id.label("evidence_id"),
                    evidence_refs.c.kind,
                    evidence_refs.c.ref,
                    evidence_refs.c.episode_event_id,
                    evidence_refs.c.anchor_id,
                    evidence_refs.c.memory_id,
                    evidence_refs.c.commit_ref,
                    evidence_refs.c.transcript_ref,
                    evidence_refs.c.note,
                )
                .select_from(
                    evidence_links.join(
                        evidence_refs,
                        evidence_refs.c.id == evidence_links.c.evidence_id,
                    )
                )
                .where(
                    evidence_links.c.repo_id == repo_id,
                    or_(
                        *[
                            and_(
                                evidence_links.c.target_type == unified_target_type,
                                evidence_links.c.target_id == target_id,
                            )
                            for _, unified_target_type, target_id in evidence_pairs
                        ]
                    ),
                )
                .order_by(evidence_links.c.created_at, evidence_links.c.id)
            )
            .mappings()
            .all()
        )
        return [_unified_evidence_to_concept_row(row) for row in rows]

    def find_concepts_for_memory_ids(
        self, *, repo_id: str, memory_ids: Sequence[str]
    ) -> Sequence[dict[str, Any]]:
        """Return concept-link matches for displayed memory ids."""

        unique_memory_ids = list(
            dict.fromkeys(str(memory_id) for memory_id in memory_ids)
        )
        if not unique_memory_ids:
            return []
        rows = (
            self._session.execute(
                select(
                    concept_memory_links.c.concept_id,
                    concept_memory_links.c.memory_id,
                    concept_memory_links.c.role,
                    concept_memory_links.c.status,
                    concept_memory_links.c.confidence,
                ).where(
                    concept_memory_links.c.repo_id == repo_id,
                    concept_memory_links.c.memory_id.in_(unique_memory_ids),
                )
            )
            .mappings()
            .all()
        )
        return [dict(row) for row in rows]

    def find_concepts_for_anchor_ids(
        self, *, repo_id: str, anchor_ids: Sequence[str]
    ) -> Sequence[dict[str, Any]]:
        """Return concept-grounding matches for displayed anchors."""

        unique_anchor_ids = list(dict.fromkeys(str(anchor_id) for anchor_id in anchor_ids))
        if not unique_anchor_ids:
            return []
        rows = (
            self._session.execute(
                select(
                    concepts.c.id.label("concept_id"),
                    concepts.c.slug,
                    concepts.c.name,
                    concepts.c.kind,
                    concept_groundings.c.id.label("grounding_id"),
                    concept_groundings.c.anchor_id,
                    concept_groundings.c.role,
                    concept_groundings.c.status,
                    concept_groundings.c.confidence,
                )
                .select_from(
                    concept_groundings.join(
                        concepts, concepts.c.id == concept_groundings.c.concept_id
                    )
                )
                .where(
                    concept_groundings.c.repo_id == repo_id,
                    concept_groundings.c.anchor_id.in_(unique_anchor_ids),
                    concepts.c.repo_id == repo_id,
                )
                .order_by(concepts.c.name.asc(), concept_groundings.c.role.asc())
            )
            .mappings()
            .all()
        )
        return [dict(row) for row in rows]

    def upsert_embedding(
        self,
        *,
        concept_id: str,
        repo_id: str,
        model: str,
        vector: Sequence[float],
        source_hash: str,
    ) -> None:
        """Insert or update the aggregate concept embedding vector."""

        now = datetime.now(timezone.utc)
        self._session.execute(
            insert(concept_embeddings)
            .values(
                concept_id=concept_id,
                repo_id=repo_id,
                model=model,
                dim=len(vector),
                vector=list(vector),
                source_hash=source_hash,
                created_at=now,
                updated_at=now,
            )
            .on_conflict_do_update(
                index_elements=["concept_id"],
                set_={
                    "repo_id": repo_id,
                    "model": model,
                    "dim": len(vector),
                    "vector": list(vector),
                    "source_hash": source_hash,
                    "updated_at": now,
                },
            )
        )


def _lifecycle_values(lifecycle: ConceptLifecycle, now: datetime) -> dict[str, Any]:
    """Convert lifecycle fields into DB insert values."""

    return {
        "status": lifecycle.status.value,
        "confidence": lifecycle.confidence,
        "observed_at": lifecycle.observed_at or now,
        "validated_at": lifecycle.validated_at,
        "invalidated_at": lifecycle.invalidated_at,
        "source_kind": lifecycle.source_kind.value
        if lifecycle.source_kind is not None
        else None,
        "source_ref": lifecycle.source_ref,
        "superseded_by_id": lifecycle.superseded_by_id,
        "created_by": lifecycle.created_by.value,
        "updated_by": lifecycle.updated_by.value
        if lifecycle.updated_by is not None
        else None,
    }


def _to_lifecycle(row) -> ConceptLifecycle:
    """Convert one row mapping into shared lifecycle fields."""

    return ConceptLifecycle(
        status=ConceptLifecycleStatus(row["status"]),
        confidence=float(row["confidence"]),
        observed_at=row["observed_at"],
        validated_at=row["validated_at"],
        invalidated_at=row["invalidated_at"],
        source_kind=ConceptSourceKind(row["source_kind"])
        if row["source_kind"] is not None
        else None,
        source_ref=row["source_ref"],
        superseded_by_id=row["superseded_by_id"],
        created_by=ConceptCreatedBy(row["created_by"]),
        updated_by=ConceptCreatedBy(row["updated_by"])
        if row["updated_by"] is not None
        else None,
    )


def _to_concept(row) -> Concept:
    return Concept(
        id=row["id"],
        repo_id=row["repo_id"],
        slug=row["slug"],
        name=row["name"],
        kind=ConceptKind(row["kind"]),
        status=ConceptStatus(row["status"]),
        scope_note=row["scope_note"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _to_alias(row) -> ConceptAlias:
    return ConceptAlias(
        concept_id=row["concept_id"],
        repo_id=row["repo_id"],
        alias=row["alias"],
        normalized_alias=row["normalized_alias"],
        created_at=row["created_at"],
    )


def _to_relation(row) -> ConceptRelation:
    return ConceptRelation(
        id=row["id"],
        repo_id=row["repo_id"],
        subject_concept_id=row["subject_concept_id"],
        predicate=ConceptRelationPredicate(row["predicate"]),
        object_concept_id=row["object_concept_id"],
        lifecycle=_to_lifecycle(row),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _to_claim(row) -> ConceptClaim:
    return ConceptClaim(
        id=row["id"],
        repo_id=row["repo_id"],
        concept_id=row["concept_id"],
        claim_type=ConceptClaimType(row["claim_type"]),
        text=row["text"],
        normalized_text=row["normalized_text"],
        lifecycle=_to_lifecycle(row),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _to_anchor(row) -> Anchor:
    return Anchor(
        id=row["id"],
        repo_id=row["repo_id"],
        kind=AnchorKind(row["kind"]),
        locator_json=dict(row["locator_json"]),
        canonical_locator_hash=row["canonical_locator_hash"],
        status=AnchorStatus(row["status"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _to_grounding(row) -> ConceptGrounding:
    return ConceptGrounding(
        id=row["id"],
        repo_id=row["repo_id"],
        concept_id=row["concept_id"],
        role=ConceptGroundingRole(row["role"]),
        anchor_id=row["anchor_id"],
        lifecycle=_to_lifecycle(row),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _to_memory_link(row) -> ConceptMemoryLink:
    return ConceptMemoryLink(
        id=row["id"],
        repo_id=row["repo_id"],
        concept_id=row["concept_id"],
        role=ConceptMemoryLinkRole(row["role"]),
        memory_id=row["memory_id"],
        lifecycle=_to_lifecycle(row),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _to_evidence(row) -> ConceptEvidence:
    return ConceptEvidence(
        id=row["id"],
        repo_id=row["repo_id"],
        target_type=ConceptEvidenceTargetType(row["target_type"]),
        target_id=row["target_id"],
        evidence_kind=ConceptEvidenceKind(row["evidence_kind"]),
        anchor_id=row["anchor_id"],
        memory_id=row["memory_id"],
        commit_ref=row["commit_ref"],
        transcript_ref=row["transcript_ref"],
        note=row["note"],
        evidence_id=row.get("evidence_id"),
        created_at=row["created_at"],
    )


def _unified_evidence_to_concept_row(row) -> dict[str, Any]:
    """Convert unified evidence storage rows into concept evidence view rows."""

    source_kind = str(row["kind"])
    evidence_kind = _CONCEPT_EVIDENCE_KIND_BY_SOURCE_KIND[source_kind]
    values: dict[str, Any] = {
        "id": row["id"],
        "repo_id": row["repo_id"],
        "target_type": _CONCEPT_TARGET_TYPE_BY_UNIFIED[str(row["target_type"])],
        "target_id": row["target_id"],
        "evidence_kind": evidence_kind,
        "evidence_id": row["evidence_id"],
        "anchor_id": row["anchor_id"],
        "memory_id": row["memory_id"],
        "commit_ref": row["commit_ref"],
        "transcript_ref": row["transcript_ref"],
        "note": row["note"],
        "created_at": row["created_at"],
    }
    if source_kind == "episode_event":
        values["evidence_kind"] = "transcript"
        values["transcript_ref"] = row["episode_event_id"] or row["ref"]
    return values


def _to_lifecycle_event(row) -> ConceptLifecycleEvent:
    return ConceptLifecycleEvent(
        id=row["id"],
        repo_id=row["repo_id"],
        target_type=ConceptLifecycleTargetType(row["target_type"]),
        target_id=row["target_id"],
        from_status=ConceptLifecycleStatus(row["from_status"]),
        to_status=ConceptLifecycleStatus(row["to_status"]),
        rationale=row["rationale"],
        actor=ConceptCreatedBy(row["actor"]),
        superseded_by_id=row["superseded_by_id"],
        created_at=row["created_at"],
    )


def _lifecycle_target_table(target_type: ConceptLifecycleTargetType):
    if target_type == ConceptLifecycleTargetType.RELATION:
        return concept_relations, _to_relation
    if target_type == ConceptLifecycleTargetType.CLAIM:
        return concept_claims, _to_claim
    if target_type == ConceptLifecycleTargetType.GROUNDING:
        return concept_groundings, _to_grounding
    if target_type == ConceptLifecycleTargetType.MEMORY_LINK:
        return concept_memory_links, _to_memory_link
    raise ValueError(f"Unsupported lifecycle target type: {target_type.value}")


def _target_type_for_record(
    target: ConceptRelation | ConceptClaim | ConceptGrounding | ConceptMemoryLink,
) -> ConceptLifecycleTargetType:
    if isinstance(target, ConceptRelation):
        return ConceptLifecycleTargetType.RELATION
    if isinstance(target, ConceptClaim):
        return ConceptLifecycleTargetType.CLAIM
    if isinstance(target, ConceptGrounding):
        return ConceptLifecycleTargetType.GROUNDING
    if isinstance(target, ConceptMemoryLink):
        return ConceptLifecycleTargetType.MEMORY_LINK
    raise ValueError(f"Unsupported lifecycle target record: {type(target).__name__}")


_CONCEPT_TARGET_TYPE_BY_UNIFIED = {
    "concept_relation": "relation",
    "concept_claim": "claim",
    "concept_grounding": "grounding",
    "concept_memory_link": "memory_link",
    "concept_lifecycle_event": "lifecycle_event",
}
_CONCEPT_EVIDENCE_KIND_BY_SOURCE_KIND = {
    "anchor": "anchor",
    "memory": "memory",
    "commit": "commit",
    "transcript": "transcript",
    "test": "test",
    "manual": "manual",
    "episode_event": "transcript",
}


def _normalize_text(value: str) -> str:
    """Normalize natural keys for aliases and claim text."""

    return " ".join(value.strip().lower().split())
