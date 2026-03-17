"""This module defines boot-time wiring for embedding provider construction."""

from shellbrain.boot.config import get_config_provider
from shellbrain.core.interfaces.embeddings import IEmbeddingProvider
from shellbrain.periphery.embeddings.local_provider import SentenceTransformersEmbeddingProvider


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
        return SentenceTransformersEmbeddingProvider(model=model)
    raise ValueError(f"Unsupported embedding provider: {provider}")
