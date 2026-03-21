"""This module defines boot-time wiring for embedding provider construction."""

from app.boot.home import get_machine_models_dir
from app.boot.config import get_config_provider
from app.core.interfaces.embeddings import IEmbeddingProvider
from app.periphery.admin.machine_state import load_machine_config
from app.periphery.embeddings.local_provider import SentenceTransformersEmbeddingProvider


def _get_embedding_config() -> dict:
    """This function returns runtime embedding configuration values."""

    runtime = get_config_provider().get_runtime()
    values = runtime.get("embeddings")
    if not isinstance(values, dict):
        raise ValueError("runtime.embeddings must be configured")
    return values


def get_embedding_model_name() -> str:
    """This function resolves the model name persisted alongside embedding vectors."""

    config = _get_embedding_config()
    provider = config.get("provider")
    model = config.get("model")
    if not isinstance(provider, str) or not provider:
        raise ValueError("runtime.embeddings.provider must be configured")
    if not isinstance(model, str) or not model:
        raise ValueError("runtime.embeddings.model must be configured")
    if provider == "sentence_transformers":
        return model
    raise ValueError(f"Unsupported embedding provider: {provider}")


def get_embedding_provider() -> IEmbeddingProvider:
    """This function constructs the configured local embedding provider."""

    config = _get_embedding_config()
    provider = config.get("provider")
    model = config.get("model")
    if not isinstance(provider, str) or not provider:
        raise ValueError("runtime.embeddings.provider must be configured")
    if not isinstance(model, str) or not model:
        raise ValueError("runtime.embeddings.model must be configured")
    if provider == "sentence_transformers":
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
    raise ValueError(f"Unsupported embedding provider: {provider}")
