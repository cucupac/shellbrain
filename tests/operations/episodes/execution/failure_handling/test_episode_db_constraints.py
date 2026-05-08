"""DB-level invariant contracts for episode-specific deduplication guarantees."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.infrastructure.db.models.episodes import episode_events, episodes


def test_episode_rows_reject_duplicate_repo_and_thread_pairs(
    integration_session_factory: sessionmaker,
) -> None:
    """episode rows should always reject duplicate repo_id and thread_id pairs."""

    now = datetime.now(timezone.utc)
    with integration_session_factory() as session:
        session.execute(
            episodes.insert().values(
                id="episode-1",
                repo_id="repo-a",
                host_app="codex",
                thread_id="codex:thread-1",
                title="Episode one",
                objective="Objective one",
                status="active",
                started_at=now,
                ended_at=None,
                created_at=now,
            )
        )
        session.commit()

        with pytest.raises(IntegrityError):
            session.execute(
                episodes.insert().values(
                    id="episode-2",
                    repo_id="repo-a",
                    host_app="codex",
                    thread_id="codex:thread-1",
                    title="Episode two",
                    objective="Objective two",
                    status="active",
                    started_at=now,
                    ended_at=None,
                    created_at=now,
                )
            )
            session.commit()
        session.rollback()


def test_episode_event_rows_reject_duplicate_host_event_keys_within_one_episode(
    integration_session_factory: sessionmaker,
) -> None:
    """episode_event rows should always reject duplicate host_event_key values within one episode."""

    assert "host_event_key" in episode_events.c, (
        "episode_events must add host_event_key before upstream event dedupe can be enforced."
    )

    now = datetime.now(timezone.utc)
    with integration_session_factory() as session:
        session.execute(
            episodes.insert().values(
                id="episode-1",
                repo_id="repo-a",
                host_app="codex",
                thread_id="codex:thread-1",
                title="Episode",
                objective="Objective",
                status="active",
                started_at=now,
                ended_at=None,
                created_at=now,
            )
        )
        session.commit()

        with pytest.raises(IntegrityError):
            session.execute(
                episode_events.insert().values(
                    id="event-1",
                    episode_id="episode-1",
                    seq=1,
                    host_event_key="codex-user-1",
                    source="user",
                    content="{}",
                    created_at=now,
                )
            )
            session.execute(
                episode_events.insert().values(
                    id="event-2",
                    episode_id="episode-1",
                    seq=2,
                    host_event_key="codex-user-1",
                    source="assistant",
                    content="{}",
                    created_at=now,
                )
            )
            session.commit()
        session.rollback()
