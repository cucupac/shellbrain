"""This module defines boot-time wiring for embedding provider construction."""

from app.boot.config import get_config_provider
from app.core.interfaces.embeddings import IEmbeddingProvider
from app.periphery.embeddings.local_provider import SentenceTransformersEmbeddingProvider


def _get_embedding_config() -> dict:
    """This function returns runtime embedding configuration values with safe defaults."""

    runtime = get_config_provider().get_runtime()
    values = runtime.get("embeddings", {})
    if not isinstance(values, dict):
        return {}
    return values


def get_embedding_model_name() -> str:
    """This function resolves the model name persisted alongside embedding vectors."""

    config = _get_embedding_config()
    provider = config.get("provider", "sentence_transformers")
    if provider == "sentence_transformers":
        return str(config.get("model", "all-MiniLM-L6-v2"))
    raise ValueError(f"Unsupported embedding provider: {provider}")


def get_embedding_provider() -> IEmbeddingProvider:
    """This function constructs the configured local embedding provider."""

    config = _get_embedding_config()
    provider = config.get("provider", "sentence_transformers")
    if provider == "sentence_transformers":
        return SentenceTransformersEmbeddingProvider(
            model=str(config.get("model", "all-MiniLM-L6-v2"))
        )
    raise ValueError(f"Unsupported embedding provider: {provider}")
