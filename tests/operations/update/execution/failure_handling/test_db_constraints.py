"""DB-level invariant contracts for write-related relational tables."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.infrastructure.db.models.episodes import (
    episode_events,
    episodes,
    session_transfers,
)
from app.infrastructure.db.models.experiences import fact_updates, problem_attempts
from app.infrastructure.db.models.memories import memories


def test_problem_attempt_rows_reject_identical_problem_and_attempt_ids(
    integration_session_factory: sessionmaker,
) -> None:
    """problem_attempt rows should always reject identical problem_id and attempt_id values."""

    with integration_session_factory() as session:
        session.execute(
            memories.insert().values(
                id="same-memory",
                repo_id="repo-a",
                scope="repo",
                kind="problem",
                text="Problem memory.",
                created_at=datetime.now(timezone.utc),
                archived=False,
            )
        )
        session.commit()

        with pytest.raises(IntegrityError):
            session.execute(
                problem_attempts.insert().values(
                    problem_id="same-memory",
                    attempt_id="same-memory",
                    role="solution",
                    created_at=datetime.now(timezone.utc),
                )
            )
            session.commit()
        session.rollback()


def test_fact_update_rows_reject_identical_old_and_new_fact_ids(
    integration_session_factory: sessionmaker,
) -> None:
    """fact_update rows should always reject identical old_fact_id and new_fact_id values."""

    with integration_session_factory() as session:
        _insert_memory_row(
            session,
            memory_id="same-fact",
            repo_id="repo-a",
            kind="fact",
            text_value="Same fact.",
        )
        _insert_memory_row(
            session,
            memory_id="change-1",
            repo_id="repo-a",
            kind="change",
            text_value="Change.",
        )
        session.commit()

        with pytest.raises(IntegrityError):
            session.execute(
                fact_updates.insert().values(
                    id="fact-update-1",
                    old_fact_id="same-fact",
                    change_id="change-1",
                    new_fact_id="same-fact",
                    created_at=datetime.now(timezone.utc),
                )
            )
            session.commit()
        session.rollback()


def test_fact_update_rows_reject_change_memory_matching_a_fact_endpoint(
    integration_session_factory: sessionmaker,
) -> None:
    """fact_update rows should always reject change_id values that equal old_fact_id or new_fact_id."""

    with integration_session_factory() as session:
        _insert_memory_row(
            session,
            memory_id="fact-a",
            repo_id="repo-a",
            kind="fact",
            text_value="Fact A.",
        )
        _insert_memory_row(
            session,
            memory_id="fact-b",
            repo_id="repo-a",
            kind="fact",
            text_value="Fact B.",
        )
        session.commit()

        with pytest.raises(IntegrityError):
            session.execute(
                fact_updates.insert().values(
                    id="fact-update-2",
                    old_fact_id="fact-a",
                    change_id="fact-a",
                    new_fact_id="fact-b",
                    created_at=datetime.now(timezone.utc),
                )
            )
            session.commit()
        session.rollback()


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
            archived=False,
        )
    )
