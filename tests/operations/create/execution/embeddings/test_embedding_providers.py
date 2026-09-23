"""Check local-only embedding execution and MiniLM pooling semantics."""

import sys
from types import SimpleNamespace

import numpy as np
import pytest

from app.infrastructure.embeddings.local_provider import (
    MODEL_FILES,
    OnnxEmbeddingProvider,
    model_directory,
)


def test_missing_artifacts_require_upgrade_without_downloading(tmp_path):
    provider = OnnxEmbeddingProvider(cache_folder=str(tmp_path))
    with pytest.raises(RuntimeError, match="shellbrain upgrade"):
        provider.embed("query")


def test_embedding_masks_padding_normalizes_and_preserves_tokenizer_rules(
    tmp_path, monkeypatch
):
    directory = model_directory(str(tmp_path))
    for name in MODEL_FILES:
        path = directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
    calls = []

    class Tokenizer:
        @staticmethod
        def from_file(path):
            assert path == str(directory / "tokenizer.json")
            return Tokenizer()

        def enable_truncation(self, *, max_length):
            assert max_length == 256

        def encode(self, text):
            calls.append(text)
            return SimpleNamespace(
                ids=[101, 42, 0], attention_mask=[1, 1, 0], type_ids=[0, 0, 0]
            )

    class Session:
        def __init__(self, path, *, sess_options, providers):
            assert path == str(directory / "onnx/model.onnx")
            assert (
                sess_options.intra_op_num_threads
                == sess_options.inter_op_num_threads
                == 1
            )
            assert providers == ["CPUExecutionProvider"]

        def run(self, outputs, inputs):
            assert all(value.dtype == np.int64 for value in inputs.values())
            return [np.array([[[3, 0], [0, 4], [999, 999]]], dtype=np.float32)]

    monkeypatch.setitem(sys.modules, "tokenizers", SimpleNamespace(Tokenizer=Tokenizer))
    monkeypatch.setitem(
        sys.modules,
        "onnxruntime",
        SimpleNamespace(SessionOptions=SimpleNamespace, InferenceSession=Session),
    )
    provider = OnnxEmbeddingProvider(cache_folder=str(tmp_path))
    assert provider.embed("  query \n") == pytest.approx([0.6, 0.8])
    assert provider.embed("") == pytest.approx([0.6, 0.8])
    assert calls == ["query", ""]
