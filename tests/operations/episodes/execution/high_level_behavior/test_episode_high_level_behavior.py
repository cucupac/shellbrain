"""High-level behavior contracts for episodic transcript imports."""

from __future__ import annotations

from collections.abc import Callable
import json

from shellbrain.core.use_cases.sync_episode import sync_episode_from_host
from shellbrain.periphery.db.models.episodes import episode_events, episodes
from shellbrain.periphery.db.uow import PostgresUnitOfWork


def test_codex_and_claude_code_imports_produce_the_same_stored_event_shape_for_equivalent_flows(
    codex_transcript_fixture: dict[str, object],
    claude_code_transcript_fixture: dict[str, object],
    uow_factory: Callable[[], PostgresUnitOfWork],
    fetch_rows: Callable[..., list[dict[str, object]]],
) -> None:
    """codex and claude code imports should always produce the same stored event shape for equivalent flows."""

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
            host_app="claude_code",
            host_session_key=str(claude_code_transcript_fixture["host_session_key"]),
            uow=uow,
            search_roots=list(claude_code_transcript_fixture["search_roots"]),
        )

    codex_episode = fetch_rows(episodes, episodes.c.thread_id == codex_transcript_fixture["canonical_thread_id"])[0]
    claude_episode = fetch_rows(
        episodes,
        episodes.c.thread_id == claude_code_transcript_fixture["canonical_thread_id"],
    )[0]
    codex_events = _decoded_event_content(fetch_rows, episode_id=str(codex_episode["id"]))
    claude_events = _decoded_event_content(fetch_rows, episode_id=str(claude_episode["id"]))

    codex_shape = [(event["source"], event["content_kind"], event["content_text"]) for event in codex_events]
    claude_shape = [(event["source"], event["content_kind"], event["content_text"]) for event in claude_events]
    assert codex_shape == claude_shape


def test_episode_import_stores_compact_event_content_rather_than_raw_noisy_transcript_blobs(
    codex_transcript_fixture: dict[str, object],
    uow_factory: Callable[[], PostgresUnitOfWork],
    fetch_rows: Callable[..., list[dict[str, object]]],
) -> None:
    """episode import should always store compact event content rather than raw noisy transcript blobs."""

    with uow_factory() as uow:
        sync_episode_from_host(
            repo_id="repo-a",
            host_app="codex",
            host_session_key=str(codex_transcript_fixture["host_session_key"]),
            uow=uow,
            search_roots=list(codex_transcript_fixture["search_roots"]),
        )

    episode_row = fetch_rows(episodes, episodes.c.thread_id == codex_transcript_fixture["canonical_thread_id"])[0]
    event_rows = fetch_rows(episode_events, episode_events.c.episode_id == str(episode_row["id"]))
    decoded = [json.loads(str(row["content"])) for row in event_rows]

    base_fields = {
        "host_app",
        "host_session_key",
        "host_event_key",
        "source",
        "occurred_at",
        "content_kind",
        "content_text",
        "raw_ref",
    }
    tool_fields = {"tool_name", "status", "is_error"}
    assert all(base_fields.issubset(set(event)) for event in decoded)
    assert all(
        set(event) == base_fields if event["content_kind"] != "tool_result" else set(event) == base_fields | tool_fields
        for event in decoded
    )
    assert all("README.md" not in event["content_text"] for event in decoded)


def test_episode_import_preserves_user_and_assistant_order(
    codex_transcript_fixture: dict[str, object],
    uow_factory: Callable[[], PostgresUnitOfWork],
    fetch_rows: Callable[..., list[dict[str, object]]],
) -> None:
    """episode import should always preserve user and assistant order."""

    with uow_factory() as uow:
        sync_episode_from_host(
            repo_id="repo-a",
            host_app="codex",
            host_session_key=str(codex_transcript_fixture["host_session_key"]),
            uow=uow,
            search_roots=list(codex_transcript_fixture["search_roots"]),
        )

    episode_row = fetch_rows(episodes, episodes.c.thread_id == codex_transcript_fixture["canonical_thread_id"])[0]
    decoded = _decoded_event_content(fetch_rows, episode_id=str(episode_row["id"]))

    assert [event["source"] for event in decoded[:2]] == ["user", "assistant"]
    assert [event["content_text"] for event in decoded[:2]] == [
        "Fix the smoke workflow.",
        "I will inspect the workflow.",
    ]


def _decoded_event_content(
    fetch_rows: Callable[..., list[dict[str, object]]],
    *,
    episode_id: str,
) -> list[dict[str, object]]:
    """Fetch one stored event stream and decode normalized JSON content."""

    rows = fetch_rows(episode_events, episode_events.c.episode_id == episode_id)
    ordered = sorted(rows, key=lambda row: int(row["seq"]))
    return [json.loads(str(row["content"])) for row in ordered]
