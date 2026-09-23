"""Persist the machine-local recall synthesis provider."""

import os
from pathlib import Path
import tempfile
import tomllib
from typing import get_args

from app.core.entities.recall_provider import RecallProvider

from app.infrastructure.local_state.paths import get_shellbrain_home

PROVIDERS = get_args(RecallProvider)


def load_recall_provider() -> str:
    """Default to Codex only when no provider has been configured."""
    path = get_shellbrain_home() / "recall-provider.toml"
    try:
        payload = tomllib.loads(path.read_text())
    except FileNotFoundError:
        return "codex"
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"Invalid recall provider configuration: {path}") from exc
    if set(payload) != {"provider"} or payload["provider"] not in PROVIDERS:
        raise ValueError(f"Invalid recall provider configuration: {path}")
    return payload["provider"]


def save_recall_provider(provider: str) -> None:
    """Atomically replace the selection without contacting a provider."""
    if provider not in PROVIDERS:
        raise ValueError(f"Provider must be one of: {', '.join(PROVIDERS)}")
    path = get_shellbrain_home() / "recall-provider.toml"
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        try:
            handle.write(f'provider = "{provider}"\n')
            handle.flush()
            os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
