"""Run the pinned MiniLM embedding model locally with ONNX Runtime."""

from pathlib import Path

from app.core.ports.embeddings.provider import IEmbeddingProvider

MODEL_REPOSITORY = "sentence-transformers/all-MiniLM-L6-v2"
MODEL_REVISION = "c9745ed1d9f207416be6d2e6f8de32d1f16199bf"
MODEL_FILES = ("onnx/model.onnx", "tokenizer.json")


def model_directory(cache_folder: str) -> Path:
    """Locate the pinned Hugging Face snapshot without importing its downloader."""
    return (
        Path(cache_folder)
        / "models--sentence-transformers--all-MiniLM-L6-v2"
        / "snapshots"
        / MODEL_REVISION
    )


class OnnxEmbeddingProvider(IEmbeddingProvider):
    """Preserve MiniLM tokenization, masked mean pooling, and normalization."""

    def __init__(self, *, cache_folder: str) -> None:
        self._directory = model_directory(cache_folder)
        self._session = None

    def _load_model(self) -> None:
        """Keep database-only units of work free of model loading."""
        if self._session is not None:
            return
        directory = self._directory
        if not all((directory / name).is_file() for name in MODEL_FILES):
            raise RuntimeError(
                "Shellbrain embedding files are missing. Run `shellbrain upgrade` to download them."
            )
        import numpy as np
        import onnxruntime as ort
        from tokenizers import Tokenizer

        self._np = np
        self._tokenizer = Tokenizer.from_file(str(directory / "tokenizer.json"))
        self._tokenizer.enable_truncation(max_length=256)
        options = ort.SessionOptions()
        options.intra_op_num_threads = 1
        options.inter_op_num_threads = 1
        self._session = ort.InferenceSession(
            str(directory / "onnx/model.onnx"),
            sess_options=options,
            providers=["CPUExecutionProvider"],
        )

    def embed(self, text: str) -> list[float]:
        """Return the same normalized 384-dimensional vector as MiniLM's encoder."""
        self._load_model()
        np = self._np
        encoded = self._tokenizer.encode(text.strip())
        inputs = {
            "input_ids": np.array([encoded.ids], dtype=np.int64),
            "attention_mask": np.array([encoded.attention_mask], dtype=np.int64),
            "token_type_ids": np.array([encoded.type_ids], dtype=np.int64),
        }
        vectors = self._session.run(None, inputs)[0]
        mask = inputs["attention_mask"][..., None].astype(np.float32)
        pooled = (vectors * mask).sum(axis=1) / np.maximum(mask.sum(axis=1), 1e-9)
        pooled /= np.maximum(np.linalg.norm(pooled, axis=1, keepdims=True), 1e-12)
        return pooled[0].tolist()
