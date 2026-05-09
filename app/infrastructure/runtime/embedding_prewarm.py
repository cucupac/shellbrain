"""Concrete embedding prewarm mechanics for runtime initialization."""

from __future__ import annotations

from dataclasses import replace
import importlib.metadata
import os
from pathlib import Path

from app.infrastructure.embeddings.local_provider import (
    SentenceTransformersEmbeddingProvider,
)
from app.infrastructure.local_state.machine_config_store import (
    BOOTSTRAP_STATE_REPAIR_NEEDED,
    EmbeddingRuntimeState,
    MachineConfig,
)


def prewarm_embeddings(
    config: MachineConfig, *, skip_model_download: bool
) -> tuple[bool, MachineConfig]:
    """Prewarm the configured embedding backend and pin its runtime metadata."""

    backend_version = _sentence_transformers_version()
    if skip_model_download:
        updated = replace(
            config,
            embeddings=_embedding_state(
                config,
                backend_version=backend_version,
                readiness_state="skipped",
                last_error="Model prewarm was skipped during init.",
            ),
        )
        return True, updated

    os.environ["HF_HOME"] = config.embeddings.cache_path
    Path(config.embeddings.cache_path).mkdir(parents=True, exist_ok=True)
    provider = SentenceTransformersEmbeddingProvider(
        model=config.embeddings.model,
        cache_folder=config.embeddings.cache_path,
    )
    try:
        provider.embed("shellbrain init warmup")
    except Exception as exc:
        updated = replace(
            config,
            bootstrap_state=BOOTSTRAP_STATE_REPAIR_NEEDED,
            current_step="embeddings",
            last_error=str(exc),
            embeddings=_embedding_state(
                config,
                backend_version=backend_version,
                readiness_state="failed",
                last_error=str(exc),
            ),
        )
        return True, updated
    updated = replace(
        config,
        embeddings=_embedding_state(
            config,
            backend_version=backend_version,
            readiness_state="ready",
            last_error=None,
        ),
    )
    return (
        config.embeddings.readiness_state != "ready"
        or config.embeddings.backend_version != backend_version,
        updated,
    )


def _embedding_state(
    config: MachineConfig,
    *,
    backend_version: str | None,
    readiness_state: str,
    last_error: str | None,
) -> EmbeddingRuntimeState:
    return EmbeddingRuntimeState(
        provider=config.embeddings.provider,
        model=config.embeddings.model,
        model_revision=config.embeddings.model_revision,
        backend_version=backend_version,
        cache_path=config.embeddings.cache_path,
        readiness_state=readiness_state,
        last_error=last_error,
    )


def _sentence_transformers_version() -> str | None:
    try:
        return importlib.metadata.version("sentence-transformers")
    except importlib.metadata.PackageNotFoundError:
        return None
