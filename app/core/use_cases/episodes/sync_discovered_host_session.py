"""Core workflow for syncing one discovered host session."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from app.core.ports.system.clock import IClock
from app.core.ports.system.idgen import IIdGenerator
from app.core.use_cases.episodes.sync_episode import SyncEpisodeRequest, sync_episode


def sync_discovered_host_session(
    *,
    repo_id: str,
    host_app: str,
    host_session_key: str,
    uow,
    search_roots: Sequence[Path],
    resolve_host_transcript_source: Callable[..., Path],
    normalize_host_transcript: Callable[..., Sequence[Any]],
    clock: IClock,
    id_generator: IIdGenerator,
    last_known_path: Path | None = None,
) -> dict[str, object]:
    """Resolve, normalize, and import one discovered host transcript."""

    transcript_path = resolve_host_transcript_source(
        host_app=host_app,
        host_session_key=host_session_key,
        search_roots=list(search_roots),
        last_known_path=last_known_path,
    )
    normalized_events = normalize_host_transcript(
        host_app=host_app,
        host_session_key=host_session_key,
        transcript_path=transcript_path,
    )
    sync_result = sync_episode(
        SyncEpisodeRequest.from_raw_events(
            repo_id=repo_id,
            host_app=host_app,
            host_session_key=host_session_key,
            thread_id=f"{host_app}:{host_session_key}",
            transcript_path=str(transcript_path),
            normalized_events=normalized_events,
        ),
        uow=uow,
        clock=clock,
        id_generator=id_generator,
    )
    return sync_result.to_response_data()
