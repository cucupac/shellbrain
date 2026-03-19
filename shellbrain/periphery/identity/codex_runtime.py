"""Codex runtime identity helpers."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Sequence

from shellbrain.core.entities.identity import CallerIdentity, IdentityTrustLevel
from shellbrain.periphery.episodes.codex import resolve_codex_transcript_path


def resolve_codex_caller_identity() -> CallerIdentity | None:
    """Resolve one trusted Codex caller from the runtime environment when present."""

    thread_id = os.getenv("CODEX_THREAD_ID")
    if not thread_id:
        return None
    return CallerIdentity(
        host_app="codex",
        host_session_key=thread_id,
        trust_level=IdentityTrustLevel.TRUSTED,
    )


def resolve_codex_transcript_for_caller(*, caller_identity: CallerIdentity, search_roots: Sequence[Path]) -> Path:
    """Resolve the Codex transcript path for one trusted caller."""

    return resolve_codex_transcript_path(
        host_session_key=caller_identity.host_session_key,
        search_roots=list(search_roots),
    )
