"""This module defines a sentence-transformers-backed local embedding provider."""

from typing import Sequence

from shellbrain.core.interfaces.embeddings import IEmbeddingProvider


class SentenceTransformersEmbeddingProvider(IEmbeddingProvider):
    """This class generates embeddings with a local sentence-transformers model."""

    def __init__(self, *, model: str, cache_folder: str | None = None) -> None:
        """This method stores sentence-transformers model configuration for lazy loading."""

        self._model_name = model
        self._cache_folder = cache_folder
        self._model = None

    def _get_model(self):
        """This method lazily loads the configured sentence-transformers model."""

        if self._model is not None:
            return self._model
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self._model_name, cache_folder=self._cache_folder)
        except Exception as exc:
            raise RuntimeError("sentence-transformers is unavailable for local embedding generation") from exc
        return self._model

    def embed(self, text: str) -> Sequence[float]:
        """This method returns a dense embedding vector from the local sentence-transformers model."""

        model = self._get_model()
        vector = model.encode(text, convert_to_numpy=False, normalize_embeddings=False)
        return [float(value) for value in vector]
