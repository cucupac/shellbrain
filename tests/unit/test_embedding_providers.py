"""This test module validates local sentence-transformers embedding provider behavior."""

import sys
import types

import pytest

from app.periphery.embeddings.local_provider import SentenceTransformersEmbeddingProvider


def test_sentence_transformers_provider_uses_local_library_when_available(monkeypatch: pytest.MonkeyPatch) -> None:
    """This test verifies the local provider calls sentence-transformers and returns response embeddings."""

    class _FakeModel:
        """This helper class returns a fixed embedding payload for test assertions."""

        def encode(self, text: str, *, convert_to_numpy: bool, normalize_embeddings: bool):
            _ = (text, convert_to_numpy, normalize_embeddings)
            return [0.1, 0.2, 0.3]

    class _FakeSentenceTransformer:
        """This helper class mimics the sentence-transformers model constructor."""

        def __init__(self, model_name: str) -> None:
            _ = model_name
            self._model = _FakeModel()

        def encode(self, text: str, *, convert_to_numpy: bool, normalize_embeddings: bool):
            return self._model.encode(text, convert_to_numpy=convert_to_numpy, normalize_embeddings=normalize_embeddings)

    monkeypatch.setitem(
        sys.modules,
        "sentence_transformers",
        types.SimpleNamespace(SentenceTransformer=_FakeSentenceTransformer),
    )

    provider = SentenceTransformersEmbeddingProvider(model="all-MiniLM-L6-v2")
    assert provider.embed("hello") == [0.1, 0.2, 0.3]


def test_sentence_transformers_provider_raises_without_library(monkeypatch: pytest.MonkeyPatch) -> None:
    """This test verifies the local provider fails fast when sentence-transformers is unavailable."""

    monkeypatch.setitem(sys.modules, "sentence_transformers", types.ModuleType("sentence_transformers"))
    provider = SentenceTransformersEmbeddingProvider(model="all-MiniLM-L6-v2")
    with pytest.raises(RuntimeError):
        provider.embed("hello")
