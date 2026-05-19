"""Adapters that expose query-vector generation through the read retrieval interface."""

from app.core.ports.embeddings.provider import IEmbeddingProvider
from app.core.ports.embeddings.retrieval import IVectorSearch


class EmbeddingBackedVectorSearch(IVectorSearch):
    """Use the configured embedding provider as the read-path query-vector source."""

    def __init__(self, embedding_provider: IEmbeddingProvider, model_name: str) -> None:
        """Store the embedding provider used to build query vectors."""

        self._embedding_provider = embedding_provider
        self._model_name = model_name

    @property
    def model_name(self) -> str:
        """Return the model used to produce read-path query vectors."""

        return self._model_name

    def embed_query(self, text: str) -> list[float]:
        """Generate a query vector using the same embedding space as stored memories."""

        return [float(value) for value in self._embedding_provider.embed(text)]
