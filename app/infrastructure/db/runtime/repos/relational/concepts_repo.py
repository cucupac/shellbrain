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
    ConceptLifecycleStatus,
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
    concept_evidence,
    concept_groundings,
    concept_memory_links,
    concept_relations,
    concepts,
    graph_patches,
)


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

    def add_evidence(self, evidence: ConceptEvidence) -> ConceptEvidence:
        """Append one evidence pointer for a concept graph record."""

        existing = (
            self._session.execute(
                select(concept_evidence).where(
                    concept_evidence.c.repo_id == evidence.repo_id,
                    concept_evidence.c.target_type == evidence.target_type.value,
                    concept_evidence.c.target_id == evidence.target_id,
                    concept_evidence.c.evidence_kind == evidence.evidence_kind.value,
                    concept_evidence.c.anchor_id == evidence.anchor_id,
                    concept_evidence.c.memory_id == evidence.memory_id,
                    concept_evidence.c.commit_ref == evidence.commit_ref,
                    concept_evidence.c.transcript_ref == evidence.transcript_ref,
                    concept_evidence.c.note == evidence.note,
                )
            )
            .mappings()
            .first()
        )
        if existing is not None:
            return _to_evidence(existing)
        self._session.execute(
            concept_evidence.insert().values(
                id=evidence.id,
                repo_id=evidence.repo_id,
                target_type=evidence.target_type.value,
                target_id=evidence.target_id,
                evidence_kind=evidence.evidence_kind.value,
                anchor_id=evidence.anchor_id,
                memory_id=evidence.memory_id,
                commit_ref=evidence.commit_ref,
                transcript_ref=evidence.transcript_ref,
                note=evidence.note,
                created_at=datetime.now(timezone.utc),
            )
        )
        return evidence

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
        self, *, repo_id: str, concept_ref: str
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
            [("relation", str(row["id"])) for row in relation_rows]
            + [("claim", str(row["id"])) for row in claim_rows]
            + [("grounding", str(row["id"])) for row in grounding_rows]
            + [("memory_link", str(row["id"])) for row in memory_link_rows]
        )
        evidence_rows = []
        if target_pairs:
            evidence_rows = (
                self._session.execute(
                    select(concept_evidence).where(
                        concept_evidence.c.repo_id == repo_id,
                        or_(
                            *[
                                and_(
                                    concept_evidence.c.target_type == target_type,
                                    concept_evidence.c.target_id == target_id,
                                )
                                for target_type, target_id in target_pairs
                            ]
                        ),
                    )
                )
                .mappings()
                .all()
            )
        return {
            "concept": concept,
            "aliases": [_to_alias(row) for row in alias_rows],
            "relations": [_to_relation(row) for row in relation_rows],
            "claims": [_to_claim(row) for row in claim_rows],
            "groundings": [_to_grounding(row) for row in grounding_rows],
            "memory_links": [_to_memory_link(row) for row in memory_link_rows],
            "anchors": [_to_anchor(row) for row in anchor_rows],
            "evidence": [_to_evidence(row) for row in evidence_rows],
        }

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

    def list_concept_search_rows(self, *, repo_id: str) -> Sequence[dict[str, Any]]:
        """Return active concept text rows for core query matching."""

        concept_rows = (
            self._session.execute(
                select(concepts).where(
                    concepts.c.repo_id == repo_id,
                    concepts.c.status == ConceptStatus.ACTIVE.value,
                )
            )
            .mappings()
            .all()
        )
        alias_rows = (
            self._session.execute(
                select(concept_aliases).where(concept_aliases.c.repo_id == repo_id)
            )
            .mappings()
            .all()
        )
        claim_rows = (
            self._session.execute(
                select(concept_claims).where(
                    concept_claims.c.repo_id == repo_id,
                    concept_claims.c.status == ConceptLifecycleStatus.ACTIVE.value,
                )
            )
            .mappings()
            .all()
        )
        search_rows: list[dict[str, Any]] = []
        for row in concept_rows:
            concept_id = str(row["id"])
            search_rows.append(
                {
                    "concept_id": concept_id,
                    "field": "slug",
                    "text": str(row["slug"]),
                    "display": str(row["slug"]),
                }
            )
            search_rows.append(
                {
                    "concept_id": concept_id,
                    "field": "name",
                    "text": str(row["name"]),
                    "display": str(row["name"]),
                }
            )
        for row in alias_rows:
            search_rows.append(
                {
                    "concept_id": str(row["concept_id"]),
                    "field": "alias",
                    "text": str(row["normalized_alias"]),
                    "display": str(row["alias"]),
                }
            )
        for row in claim_rows:
            search_rows.append(
                {
                    "concept_id": str(row["concept_id"]),
                    "field": "claim",
                    "text": str(row["normalized_text"]),
                    "display": str(row["text"]),
                }
            )
        return search_rows


def _lifecycle_values(lifecycle: ConceptLifecycle, now: datetime) -> dict[str, Any]:
    """Convert lifecycle fields into DB insert values."""

    return {
        "status": lifecycle.status.value,
        "confidence": lifecycle.confidence,
        "observed_at": lifecycle.observed_at or now,
        "validated_at": lifecycle.validated_at,
        "source_kind": lifecycle.source_kind.value
        if lifecycle.source_kind is not None
        else None,
        "source_ref": lifecycle.source_ref,
        "superseded_by_id": lifecycle.superseded_by_id,
        "created_by": lifecycle.created_by.value,
    }


def _to_lifecycle(row) -> ConceptLifecycle:
    """Convert one row mapping into shared lifecycle fields."""

    return ConceptLifecycle(
        status=ConceptLifecycleStatus(row["status"]),
        confidence=float(row["confidence"]),
        observed_at=row["observed_at"],
        validated_at=row["validated_at"],
        source_kind=ConceptSourceKind(row["source_kind"])
        if row["source_kind"] is not None
        else None,
        source_ref=row["source_ref"],
        superseded_by_id=row["superseded_by_id"],
        created_by=ConceptCreatedBy(row["created_by"]),
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
        created_at=row["created_at"],
    )


def _normalize_text(value: str) -> str:
    """Normalize natural keys for aliases and claim text."""

    return " ".join(value.strip().lower().split())
