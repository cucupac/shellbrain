"""DB-level invariant contracts for write-related relational tables."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.core.entities.structural_memory_relations import (
    StructuralMemoryRelation,
    StructuralMemoryRelationPredicate,
)
from app.infrastructure.db.runtime.models.episodes import (
    episode_events,
    episodes,
    session_transfers,
)
from app.infrastructure.db.runtime.models.experiences import structural_memory_relations
from app.infrastructure.db.runtime.models.memories import memories
from app.infrastructure.db.runtime.repos.relational.experiences_repo import (
    ExperiencesRepo,
)


def test_structural_memory_relation_rows_reject_retired_predicates(
    integration_session_factory: sessionmaker,
) -> None:
    """structural relations should reject retired or generic predicates at the DB boundary."""

    with integration_session_factory() as session:
        _insert_memory_row(
            session,
            memory_id="problem-1",
            repo_id="repo-a",
            kind="problem",
            text_value="Problem.",
        )
        _insert_memory_row(
            session,
            memory_id="solution-1",
            repo_id="repo-a",
            kind="solution",
            text_value="Solution.",
        )
        session.commit()

        for predicate in ("matures_into", "depends_on", "associated_with", "related_to"):
            with pytest.raises(IntegrityError):
                session.execute(
                    structural_memory_relations.insert().values(
                        id=f"relation-{predicate}",
                        repo_id="repo-a",
                        subject_memory_id="problem-1",
                        predicate=predicate,
                        object_memory_id="solution-1",
                        status="active",
                        created_by="manual",
                        created_at=datetime.now(timezone.utc),
                        updated_at=datetime.now(timezone.utc),
                    )
                )
                session.commit()
            session.rollback()


def test_structural_memory_relation_rows_reject_identical_endpoints(
    integration_session_factory: sessionmaker,
) -> None:
    """structural relations should always reject self-relations."""

    with integration_session_factory() as session:
        _insert_memory_row(
            session,
            memory_id="same-memory",
            repo_id="repo-a",
            kind="fact",
            text_value="Same memory.",
        )
        session.commit()

        with pytest.raises(IntegrityError):
            session.execute(
                structural_memory_relations.insert().values(
                    id="relation-self",
                    repo_id="repo-a",
                    subject_memory_id="same-memory",
                    predicate="superseded_by",
                    object_memory_id="same-memory",
                    status="active",
                    created_by="manual",
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )
            )
            session.commit()
        session.rollback()


def test_structural_memory_relation_repo_rejects_invalid_memory_kind_pair(
    integration_session_factory: sessionmaker,
) -> None:
    """repo writes should reject predicate shapes the DB cannot infer from IDs alone."""

    with integration_session_factory() as session:
        _insert_memory_row(
            session,
            memory_id="problem-1",
            repo_id="repo-a",
            kind="problem",
            text_value="Problem.",
        )
        _insert_memory_row(
            session,
            memory_id="solution-1",
            repo_id="repo-a",
            kind="solution",
            text_value="Solution.",
        )
        repo = ExperiencesRepo(session)

        with pytest.raises(ValueError, match="superseded_by requires"):
            repo.upsert_structural_memory_relation(
                StructuralMemoryRelation(
                    id="relation-invalid-kind",
                    repo_id="repo-a",
                    subject_memory_id="problem-1",
                    predicate=StructuralMemoryRelationPredicate.SUPERSEDED_BY,
                    object_memory_id="solution-1",
                )
            )


def test_episode_rows_reject_end_times_before_start_times(
    integration_session_factory: sessionmaker,
) -> None:
    """episode rows should always reject ended_at values earlier than started_at."""

    with integration_session_factory() as session:
        started_at = datetime.now(timezone.utc)
        ended_at = started_at - timedelta(minutes=5)

        with pytest.raises(IntegrityError):
            session.execute(
                episodes.insert().values(
                    id="episode-1",
                    repo_id="repo-a",
                    host_app="codex",
                    thread_id="thread-1",
                    title="Episode",
                    objective="Objective",
                    status="active",
                    started_at=started_at,
                    ended_at=ended_at,
                    created_at=started_at,
                )
            )
            session.commit()
        session.rollback()


def test_session_transfer_rows_reject_self_transfers(
    integration_session_factory: sessionmaker,
) -> None:
    """session_transfer rows should always reject identical from_episode_id and to_episode_id values."""

    with integration_session_factory() as session:
        now = datetime.now(timezone.utc)
        session.execute(
            episodes.insert().values(
                id="episode-1",
                repo_id="repo-a",
                host_app="codex",
                thread_id="thread-1",
                title="Episode",
                objective="Objective",
                status="active",
                started_at=now,
                ended_at=None,
                created_at=now,
            )
        )
        session.execute(
            episode_events.insert().values(
                id="event-1",
                episode_id="episode-1",
                seq=1,
                host_event_key="event-1",
                source="assistant",
                content="event",
                created_at=now,
            )
        )
        session.commit()

        with pytest.raises(IntegrityError):
            session.execute(
                session_transfers.insert().values(
                    id="transfer-1",
                    repo_id="repo-a",
                    from_episode_id="episode-1",
                    to_episode_id="episode-1",
                    event_id="event-1",
                    transfer_kind="message_handoff",
                    rationale="handoff",
                    transferred_by="assistant",
                    created_at=now,
                )
            )
            session.commit()
        session.rollback()


def _insert_memory_row(
    session, *, memory_id: str, repo_id: str, kind: str, text_value: str
) -> None:
    """Insert one minimal shellbrain row for direct schema-level tests."""

    session.execute(
        memories.insert().values(
            id=memory_id,
            repo_id=repo_id,
            scope="repo",
            kind=kind,
            text=text_value,
            created_at=datetime.now(timezone.utc),
            status="active",
        )
    )
