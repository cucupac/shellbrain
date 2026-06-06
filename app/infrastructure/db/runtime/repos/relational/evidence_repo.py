"""Relational repository operations for unified evidence refs and links."""

from datetime import datetime, timezone
from typing import Sequence
from uuid import uuid4

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert

from app.core.entities.evidence import (
    EvidenceDetail,
    EvidenceLinkedTarget,
    EvidenceLinkView,
    EvidenceRef,
    EvidenceRole,
    EvidenceSource,
    EvidenceSourceKind,
    EvidenceTarget,
    EvidenceTargetType,
    canonical_evidence_hash,
    evidence_source_ref,
)
from app.core.ports.db.memory_repositories import IEvidenceRepo
from app.infrastructure.db.runtime.models.evidence import evidence_links, evidence_refs


class EvidenceRepo(IEvidenceRepo):
    """This class provides unified evidence persistence operations."""

    def __init__(self, session) -> None:
        """Store the active DB session."""

        self._session = session

    def attach_evidence(
        self,
        *,
        repo_id: str,
        target: EvidenceTarget,
        sources: Sequence[EvidenceSource],
        role: EvidenceRole = EvidenceRole.SUPPORTS,
    ) -> Sequence[EvidenceLinkView]:
        """Attach evidence sources to a target through unified storage."""

        role = EvidenceRole(role)
        self._require_target_visible(repo_id=repo_id, target=target)
        return tuple(
            self._attach_one(
                repo_id=repo_id, target=target, source=source, role=role
            )
            for source in sources
        )

    def resolve_evidence(
        self, *, repo_id: str, targets: Sequence[EvidenceTarget]
    ) -> Sequence[EvidenceLinkView]:
        """Resolve evidence links for targets through unified storage."""

        links: list[EvidenceLinkView] = []
        for target in targets:
            rows = (
                self._session.execute(
                    select(
                        evidence_links.c.target_type,
                        evidence_links.c.target_id,
                        evidence_links.c.evidence_role,
                        evidence_links.c.created_at.label("link_created_at"),
                        evidence_refs,
                    )
                    .select_from(
                        evidence_links.join(
                            evidence_refs,
                            evidence_refs.c.id == evidence_links.c.evidence_id,
                        )
                    )
                    .where(
                        evidence_links.c.repo_id == repo_id,
                        evidence_links.c.target_type == target.target_type.value,
                        evidence_links.c.target_id == target.target_id,
                    )
                    .order_by(
                        evidence_links.c.created_at,
                        evidence_refs.c.kind,
                        evidence_refs.c.ref,
                    )
                )
                .mappings()
                .all()
            )
            links.extend(_link_view_from_row(row) for row in rows)
        return tuple(links)

    def get_evidence_detail(
        self, *, repo_id: str, evidence_id: str
    ) -> EvidenceDetail | None:
        """Resolve one canonical evidence source plus all linked targets."""

        evidence_row = (
            self._session.execute(
                select(evidence_refs).where(
                    evidence_refs.c.repo_id == repo_id,
                    evidence_refs.c.id == evidence_id,
                )
            )
            .mappings()
            .first()
        )
        if evidence_row is None:
            return None

        link_rows = (
            self._session.execute(
                select(
                    evidence_links.c.id,
                    evidence_links.c.target_type,
                    evidence_links.c.target_id,
                    evidence_links.c.evidence_role,
                    evidence_links.c.created_at,
                )
                .where(
                    evidence_links.c.repo_id == repo_id,
                    evidence_links.c.evidence_id == evidence_id,
                )
                .order_by(
                    evidence_links.c.target_type.asc(),
                    evidence_links.c.target_id.asc(),
                    evidence_links.c.evidence_role.asc(),
                )
            )
            .mappings()
            .all()
        )
        return EvidenceDetail(
            id=evidence_row["id"],
            repo_id=evidence_row["repo_id"],
            source=_source_from_row(evidence_row),
            linked_targets=tuple(_linked_target_from_row(row) for row in link_rows),
            created_at=evidence_row["created_at"],
        )

    def _attach_one(
        self,
        *,
        repo_id: str,
        target: EvidenceTarget,
        source: EvidenceSource,
        role: EvidenceRole,
    ) -> EvidenceLinkView:
        evidence_ref = self._upsert_ref(repo_id=repo_id, source=source)
        created_at = datetime.now(timezone.utc)
        self._session.execute(
            insert(evidence_links)
            .values(
                id=str(uuid4()),
                repo_id=repo_id,
                target_type=target.target_type.value,
                target_id=target.target_id,
                evidence_id=evidence_ref.id,
                evidence_role=role.value,
                created_at=created_at,
            )
            .on_conflict_do_nothing(
                index_elements=[
                    "repo_id",
                    "target_type",
                    "target_id",
                    "evidence_id",
                    "evidence_role",
                ]
            )
        )
        link_row = (
            self._session.execute(
                select(evidence_links.c.created_at).where(
                    evidence_links.c.repo_id == repo_id,
                    evidence_links.c.target_type == target.target_type.value,
                    evidence_links.c.target_id == target.target_id,
                    evidence_links.c.evidence_id == evidence_ref.id,
                    evidence_links.c.evidence_role == role.value,
                )
            )
            .mappings()
            .one()
        )
        return EvidenceLinkView(
            target=target,
            source=source,
            role=role,
            evidence_id=evidence_ref.id,
            created_at=link_row["created_at"],
        )

    def _upsert_ref(self, *, repo_id: str, source: EvidenceSource) -> EvidenceRef:
        values = _source_values(repo_id=repo_id, source=source)
        self._acquire_ref_guard(
            repo_id=repo_id, canonical_hash=str(values["canonical_hash"])
        )
        existing = (
            self._session.execute(
                select(evidence_refs).where(
                    evidence_refs.c.repo_id == repo_id,
                    evidence_refs.c.canonical_hash == values["canonical_hash"],
                )
            )
            .mappings()
            .first()
        )
        if existing is not None:
            return _ref_from_row(existing)
        self._session.execute(
            insert(evidence_refs)
            .values(id=str(uuid4()), created_at=datetime.now(timezone.utc), **values)
            .on_conflict_do_nothing(index_elements=["repo_id", "canonical_hash"])
        )
        row = (
            self._session.execute(
                select(evidence_refs).where(
                    evidence_refs.c.repo_id == repo_id,
                    evidence_refs.c.canonical_hash == values["canonical_hash"],
                )
            )
            .mappings()
            .one()
        )
        return _ref_from_row(row)

    def _acquire_ref_guard(self, *, repo_id: str, canonical_hash: str) -> None:
        """Serialize concurrent writes for one repo/source pair."""

        self._session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:repo_id), hashtext(:hash))"),
            {"repo_id": repo_id, "hash": canonical_hash},
        )

    def _require_target_visible(self, *, repo_id: str, target: EvidenceTarget) -> None:
        """Validate the polymorphic target before writing an evidence link."""

        query = _TARGET_VALIDATION_QUERIES.get(target.target_type)
        if query is None:
            raise ValueError(f"unsupported evidence target type: {target.target_type}")
        exists = self._session.execute(
            text(query), {"repo_id": repo_id, "target_id": target.target_id}
        ).scalar()
        if not exists:
            raise ValueError(
                f"evidence target not found for repo {repo_id}: "
                f"{target.target_type.value}:{target.target_id}"
            )


_TARGET_VALIDATION_QUERIES = {
    EvidenceTargetType.MEMORY: """
        SELECT 1
        FROM memories
        WHERE id = :target_id
          AND (repo_id = :repo_id OR scope = 'global')
        LIMIT 1
    """,
    EvidenceTargetType.ASSOCIATION_EDGE: """
        SELECT 1
        FROM association_edges
        WHERE id = :target_id
          AND repo_id = :repo_id
        LIMIT 1
    """,
    EvidenceTargetType.UTILITY_OBSERVATION: """
        SELECT 1
        FROM utility_observations uo
        JOIN memories memory ON memory.id = uo.memory_id
        JOIN memories problem ON problem.id = uo.problem_id
        WHERE uo.id = :target_id
          AND memory.repo_id = :repo_id
          AND problem.repo_id = :repo_id
        LIMIT 1
    """,
    EvidenceTargetType.CONCEPT_CLAIM: """
        SELECT 1
        FROM concept_claims
        WHERE id = :target_id
          AND repo_id = :repo_id
        LIMIT 1
    """,
    EvidenceTargetType.CONCEPT_RELATION: """
        SELECT 1
        FROM concept_relations
        WHERE id = :target_id
          AND repo_id = :repo_id
        LIMIT 1
    """,
    EvidenceTargetType.CONCEPT_GROUNDING: """
        SELECT 1
        FROM concept_groundings
        WHERE id = :target_id
          AND repo_id = :repo_id
        LIMIT 1
    """,
    EvidenceTargetType.CONCEPT_MEMORY_LINK: """
        SELECT 1
        FROM concept_memory_links
        WHERE id = :target_id
          AND repo_id = :repo_id
        LIMIT 1
    """,
    EvidenceTargetType.CONCEPT_LIFECYCLE_EVENT: """
        SELECT 1
        FROM concept_lifecycle_events
        WHERE id = :target_id
          AND repo_id = :repo_id
        LIMIT 1
    """,
    EvidenceTargetType.MEMORY_LIFECYCLE_EVENT: """
        SELECT 1
        FROM memory_lifecycle_events
        WHERE id = :target_id
          AND repo_id = :repo_id
        LIMIT 1
    """,
    EvidenceTargetType.STRUCTURAL_MEMORY_RELATION: """
        SELECT 1
        FROM structural_memory_relations
        WHERE id = :target_id
          AND repo_id = :repo_id
        LIMIT 1
    """,
}


def _source_values(*, repo_id: str, source: EvidenceSource) -> dict[str, str | None]:
    values: dict[str, str | None] = {
        "repo_id": repo_id,
        "kind": source.source_kind.value,
        "ref": evidence_source_ref(source),
        "canonical_hash": canonical_evidence_hash(source),
        "episode_event_id": None,
        "anchor_id": None,
        "memory_id": None,
        "commit_ref": None,
        "transcript_ref": None,
        "note": None,
    }
    if source.source_kind is EvidenceSourceKind.EPISODE_EVENT:
        values["episode_event_id"] = source.episode_event_id
        return values
    field = _SOURCE_FIELD_BY_KIND[source.source_kind]
    values[field] = getattr(source, field)
    return values


def _ref_from_row(row) -> EvidenceRef:
    return EvidenceRef(
        id=row["id"],
        repo_id=row["repo_id"],
        kind=EvidenceSourceKind(row["kind"]),
        ref=row["ref"],
        canonical_hash=row["canonical_hash"],
        episode_event_id=row["episode_event_id"],
        anchor_id=row["anchor_id"],
        memory_id=row["memory_id"],
        commit_ref=row["commit_ref"],
        transcript_ref=row["transcript_ref"],
        note=row["note"],
    )


def _link_view_from_row(row) -> EvidenceLinkView:
    return EvidenceLinkView(
        target=EvidenceTarget(
            target_type=EvidenceTargetType(row["target_type"]),
            target_id=row["target_id"],
        ),
        source=_source_from_row(row),
        role=EvidenceRole(row["evidence_role"]),
        evidence_id=row["id"],
        created_at=row["link_created_at"],
    )


def _linked_target_from_row(row) -> EvidenceLinkedTarget:
    return EvidenceLinkedTarget(
        link_id=row["id"],
        target=EvidenceTarget(
            target_type=EvidenceTargetType(row["target_type"]),
            target_id=row["target_id"],
        ),
        role=EvidenceRole(row["evidence_role"]),
        created_at=row["created_at"],
    )


def _source_from_row(row) -> EvidenceSource:
    source_kind = EvidenceSourceKind(row["kind"])
    if source_kind is EvidenceSourceKind.EPISODE_EVENT:
        return EvidenceSource(
            source_kind=source_kind,
            ref=row["ref"],
            episode_event_id=row["episode_event_id"] or row["ref"],
        )
    return EvidenceSource(
        source_kind=source_kind,
        anchor_id=row["anchor_id"],
        memory_id=row["memory_id"],
        commit_ref=row["commit_ref"],
        transcript_ref=row["transcript_ref"],
        note=row["note"],
    )


_SOURCE_FIELD_BY_KIND = {
    EvidenceSourceKind.ANCHOR: "anchor_id",
    EvidenceSourceKind.MEMORY: "memory_id",
    EvidenceSourceKind.COMMIT: "commit_ref",
    EvidenceSourceKind.TRANSCRIPT: "transcript_ref",
    EvidenceSourceKind.TEST: "note",
    EvidenceSourceKind.MANUAL: "note",
}
