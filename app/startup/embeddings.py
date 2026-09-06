"""This module defines boot-time wiring for embedding provider construction."""

from app.infrastructure.local_state.paths import get_machine_models_dir
from app.startup.settings import DEFAULT_EMBEDDING_MODEL
from app.core.ports.embeddings.provider import IEmbeddingProvider
from app.infrastructure.local_state.machine_config_store import load_machine_config
from app.infrastructure.embeddings.local_provider import (
    SentenceTransformersEmbeddingProvider,
)


def get_embedding_model_name() -> str:
    """Return the model name persisted alongside embedding vectors."""
    return DEFAULT_EMBEDDING_MODEL


def get_embedding_provider() -> IEmbeddingProvider:
    """This function constructs the configured local embedding provider."""

    model = get_embedding_model_name()
    machine_config = load_machine_config()
    cache_folder = str(get_machine_models_dir())
    local_files_only = False
    if machine_config is not None:
        cache_folder = machine_config.embeddings.cache_path
        if machine_config.embeddings.readiness_state != "ready":
            raise RuntimeError(
                "Shellbrain embeddings are not ready. Rerun `shellbrain init` to finish model setup."
            )
        local_files_only = True
    return SentenceTransformersEmbeddingProvider(
        model=model,
        cache_folder=cache_folder,
        local_files_only=local_files_only,
    )
