"""This module defines relational repository operations for evidence references and links."""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert

from app.core.entities.evidence import EvidenceRef
from app.core.interfaces.repos import IEvidenceRepo
from app.periphery.db.models.associations import association_edge_evidence
from app.periphery.db.models.evidence import evidence_refs
from app.periphery.db.models.memories import memory_evidence


class EvidenceRepo(IEvidenceRepo):
    """This class provides persistence operations for evidence references and links."""

    def __init__(self, session) -> None:
        """This method stores the active DB session for repository operations."""

        self._session = session

    def upsert_ref(self, repo_id: str, ref: str) -> EvidenceRef:
        """This method inserts or returns a canonical evidence reference row."""

        existing = (
            self._session.execute(
                select(evidence_refs).where(
                    evidence_refs.c.repo_id == repo_id,
                    (evidence_refs.c.episode_event_id == ref) | (evidence_refs.c.ref == ref),
                )
            )
            .mappings()
            .first()
        )
        if existing:
            if existing["episode_event_id"] is None:
                self._session.execute(
                    update(evidence_refs)
                    .where(evidence_refs.c.id == existing["id"])
                    .values(episode_event_id=ref, ref=ref)
                )
                existing = dict(existing)
                existing["episode_event_id"] = ref
                existing["ref"] = ref
            return EvidenceRef(
                id=existing["id"],
                repo_id=existing["repo_id"],
                ref=existing["ref"],
                episode_event_id=existing["episode_event_id"],
            )

        evidence_id = str(uuid4())
        self._session.execute(
            evidence_refs.insert().values(
                id=evidence_id,
                repo_id=repo_id,
                ref=ref,
                episode_event_id=ref,
                created_at=datetime.now(timezone.utc),
            )
        )
        return EvidenceRef(id=evidence_id, repo_id=repo_id, ref=ref, episode_event_id=ref)

    def link_memory_evidence(self, memory_id: str, evidence_id: str) -> None:
        """This method creates memory-to-evidence link rows."""

        self._session.execute(
            insert(memory_evidence)
            .values(memory_id=memory_id, evidence_id=evidence_id)
            .on_conflict_do_nothing(index_elements=["memory_id", "evidence_id"])
        )

    def link_association_edge_evidence(self, edge_id: str, evidence_id: str) -> None:
        """This method creates association-edge-to-evidence link rows."""

        self._session.execute(
            insert(association_edge_evidence)
            .values(edge_id=edge_id, evidence_id=evidence_id)
            .on_conflict_do_nothing(index_elements=["edge_id", "evidence_id"])
        )
