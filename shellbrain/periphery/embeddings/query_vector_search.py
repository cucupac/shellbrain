"""Adapters that expose query-vector generation through the read retrieval interface."""

from shellbrain.core.interfaces.embeddings import IEmbeddingProvider
from shellbrain.core.interfaces.retrieval import IVectorSearch


class EmbeddingBackedVectorSearch(IVectorSearch):
    """Use the configured embedding provider as the read-path query-vector source."""

    def __init__(self, embedding_provider: IEmbeddingProvider) -> None:
        """Store the embedding provider used to build query vectors."""

        self._embedding_provider = embedding_provider

    def embed_query(self, text: str) -> list[float]:
        """Generate a query vector using the same embedding space as stored memories."""

        return [float(value) for value in self._embedding_provider.embed(text)]
