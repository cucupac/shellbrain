"""Record-write contracts for episodic transcript imports."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from collections.abc import Callable
import json
from pathlib import Path
from threading import Barrier

from app.core.use_cases.sync_episode import sync_episode_from_host
from app.periphery.db.models.episodes import episode_events, episodes
from app.periphery.db.uow import PostgresUnitOfWork


def test_first_episode_import_creates_one_episode_and_ordered_episode_events(
    codex_transcript_fixture: dict[str, object],
    uow_factory: Callable[[], PostgresUnitOfWork],
    fetch_rows: Callable[..., list[dict[str, object]]],
) -> None:
    """first episode import should always create one episode and ordered episode events."""

    with uow_factory() as uow:
        sync_episode_from_host(
            repo_id="repo-a",
            host_app="codex",
            host_session_key=str(codex_transcript_fixture["host_session_key"]),
            uow=uow,
            search_roots=list(codex_transcript_fixture["search_roots"]),
        )

    episode_rows = fetch_rows(episodes, episodes.c.repo_id == "repo-a")
    assert len(episode_rows) == 1
    assert episode_rows[0]["thread_id"] == codex_transcript_fixture["canonical_thread_id"]

    event_rows = _sorted_event_rows(fetch_rows, episode_id=str(episode_rows[0]["id"]))
    assert [row["seq"] for row in event_rows] == [1, 2, 3]
    assert [row["source"] for row in event_rows] == ["user", "assistant", "tool"]


def test_reimport_of_the_same_host_session_does_not_duplicate_episode_events(
    codex_transcript_fixture: dict[str, object],
    uow_factory: Callable[[], PostgresUnitOfWork],
    count_rows: Callable[[str], int],
) -> None:
    """re-import of the same host session should always not duplicate episode events."""

    with uow_factory() as uow:
        sync_episode_from_host(
            repo_id="repo-a",
            host_app="codex",
            host_session_key=str(codex_transcript_fixture["host_session_key"]),
            uow=uow,
            search_roots=list(codex_transcript_fixture["search_roots"]),
        )
    with uow_factory() as uow:
        sync_episode_from_host(
            repo_id="repo-a",
            host_app="codex",
            host_session_key=str(codex_transcript_fixture["host_session_key"]),
            uow=uow,
            search_roots=list(codex_transcript_fixture["search_roots"]),
        )

    assert count_rows("episodes") == 1
    assert count_rows("episode_events") == 3


def test_incremental_reimport_appends_only_newly_seen_events(
    codex_transcript_fixture: dict[str, object],
    uow_factory: Callable[[], PostgresUnitOfWork],
    fetch_rows: Callable[..., list[dict[str, object]]],
) -> None:
    """incremental re-import should always append only newly seen events."""

    transcript_path = Path(str(codex_transcript_fixture["transcript_path"]))
    with uow_factory() as uow:
        sync_episode_from_host(
            repo_id="repo-a",
            host_app="codex",
            host_session_key=str(codex_transcript_fixture["host_session_key"]),
            uow=uow,
            search_roots=list(codex_transcript_fixture["search_roots"]),
        )

    with transcript_path.open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "event_id": "codex-assistant-2",
                    "timestamp": "2026-03-12T01:45:00Z",
                    "type": "message",
                    "role": "assistant",
                    "text": "I updated the workflow.",
                }
            )
            + "\n"
        )

    with uow_factory() as uow:
        sync_episode_from_host(
            repo_id="repo-a",
            host_app="codex",
            host_session_key=str(codex_transcript_fixture["host_session_key"]),
            uow=uow,
            search_roots=list(codex_transcript_fixture["search_roots"]),
        )

    episode_rows = fetch_rows(episodes, episodes.c.repo_id == "repo-a")
    event_rows = _sorted_event_rows(fetch_rows, episode_id=str(episode_rows[0]["id"]))
    assert len(event_rows) == 4


def test_the_same_host_session_always_maps_to_the_same_stored_episode(
    codex_transcript_fixture: dict[str, object],
    uow_factory: Callable[[], PostgresUnitOfWork],
    fetch_rows: Callable[..., list[dict[str, object]]],
) -> None:
    """the same host session should always map to the same stored episode."""

    with uow_factory() as uow:
        sync_episode_from_host(
            repo_id="repo-a",
            host_app="codex",
            host_session_key=str(codex_transcript_fixture["host_session_key"]),
            uow=uow,
            search_roots=list(codex_transcript_fixture["search_roots"]),
        )
    with uow_factory() as uow:
        sync_episode_from_host(
            repo_id="repo-a",
            host_app="codex",
            host_session_key=str(codex_transcript_fixture["host_session_key"]),
            uow=uow,
            search_roots=list(codex_transcript_fixture["search_roots"]),
        )

    episode_rows = fetch_rows(episodes, episodes.c.repo_id == "repo-a")
    assert len(episode_rows) == 1
    assert episode_rows[0]["thread_id"] == codex_transcript_fixture["canonical_thread_id"]


def test_parallel_first_import_of_the_same_host_session_creates_one_episode_and_one_copy_of_each_event(
    codex_transcript_fixture: dict[str, object],
    uow_factory: Callable[[], PostgresUnitOfWork],
    fetch_rows: Callable[..., list[dict[str, object]]],
) -> None:
    """parallel first import should always produce one canonical episode stream."""

    _run_parallel_syncs(
        uow_factory=uow_factory,
        host_app="codex",
        host_session_key=str(codex_transcript_fixture["host_session_key"]),
        search_roots=list(codex_transcript_fixture["search_roots"]),
    )

    episode_rows = fetch_rows(episodes, episodes.c.repo_id == "repo-a")
    assert len(episode_rows) == 1

    event_rows = _sorted_event_rows(fetch_rows, episode_id=str(episode_rows[0]["id"]))
    assert len(event_rows) == 3
    assert [row["seq"] for row in event_rows] == [1, 2, 3]
    assert len({str(row["host_event_key"]) for row in event_rows}) == 3


def test_parallel_incremental_reimport_appends_one_new_event_without_duplicate_sequences(
    codex_transcript_fixture: dict[str, object],
    uow_factory: Callable[[], PostgresUnitOfWork],
    fetch_rows: Callable[..., list[dict[str, object]]],
) -> None:
    """parallel incremental re-import should always append one new event exactly once."""

    transcript_path = Path(str(codex_transcript_fixture["transcript_path"]))
    with uow_factory() as uow:
        sync_episode_from_host(
            repo_id="repo-a",
            host_app="codex",
            host_session_key=str(codex_transcript_fixture["host_session_key"]),
            uow=uow,
            search_roots=list(codex_transcript_fixture["search_roots"]),
        )

    with transcript_path.open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "event_id": "codex-assistant-2",
                    "timestamp": "2026-03-12T01:45:00Z",
                    "type": "message",
                    "role": "assistant",
                    "text": "I updated the workflow.",
                }
            )
            + "\n"
        )

    _run_parallel_syncs(
        uow_factory=uow_factory,
        host_app="codex",
        host_session_key=str(codex_transcript_fixture["host_session_key"]),
        search_roots=list(codex_transcript_fixture["search_roots"]),
    )

    episode_rows = fetch_rows(episodes, episodes.c.repo_id == "repo-a")
    assert len(episode_rows) == 1

    event_rows = _sorted_event_rows(fetch_rows, episode_id=str(episode_rows[0]["id"]))
    assert len(event_rows) == 4
    assert [row["seq"] for row in event_rows] == [1, 2, 3, 4]
    assert len({str(row["host_event_key"]) for row in event_rows}) == 4


def _sorted_event_rows(
    fetch_rows: Callable[..., list[dict[str, object]]],
    *,
    episode_id: str,
) -> list[dict[str, object]]:
    """Fetch one episode stream and return rows in sequence order."""

    rows = fetch_rows(episode_events, episode_events.c.episode_id == episode_id)
    return sorted(rows, key=lambda row: int(row["seq"]))


def _run_parallel_syncs(
    *,
    uow_factory: Callable[[], PostgresUnitOfWork],
    host_app: str,
    host_session_key: str,
    search_roots: list[Path],
) -> None:
    """Run two concurrent syncs for the same host session with independent transactions."""

    barrier = Barrier(2)

    def _sync() -> None:
        barrier.wait()
        with uow_factory() as uow:
            sync_episode_from_host(
                repo_id="repo-a",
                host_app=host_app,
                host_session_key=host_session_key,
                uow=uow,
                search_roots=search_roots,
            )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(_sync) for _ in range(2)]
        for future in futures:
            future.result()
