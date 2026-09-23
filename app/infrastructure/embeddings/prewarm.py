"""Download and verify embedding artifacts during installation and upgrades."""

from dataclasses import replace
from importlib.metadata import version
from pathlib import Path

from app.core.entities.machine_config import (
    BOOTSTRAP_STATE_REPAIR_NEEDED,
    MachineConfig,
)
from app.infrastructure.embeddings.local_provider import (
    MODEL_FILES,
    MODEL_REPOSITORY,
    MODEL_REVISION,
    OnnxEmbeddingProvider,
)


def prewarm_embeddings(
    config: MachineConfig, *, skip_model_download: bool
) -> tuple[bool, MachineConfig]:
    """Verify the local model before marking an installation ready."""
    if skip_model_download:
        updated = replace(
            config,
            embeddings=replace(
                config.embeddings,
                readiness_state="skipped",
                last_error="Model prewarm was skipped during init.",
            ),
        )
        return updated != config, updated
    try:
        _verify_model_revision(config)
        try:
            OnnxEmbeddingProvider(cache_folder=config.embeddings.cache_path).embed(
                "shellbrain upgrade warmup"
            )
        except Exception:
            # Only bootstrap may fetch or replace missing/corrupt model files.
            from huggingface_hub import snapshot_download

            snapshot_download(
                MODEL_REPOSITORY,
                revision=MODEL_REVISION,
                cache_dir=config.embeddings.cache_path,
                allow_patterns=list(MODEL_FILES),
                force_download=True,
            )
            OnnxEmbeddingProvider(cache_folder=config.embeddings.cache_path).embed(
                "shellbrain upgrade warmup"
            )
        updated = replace(
            config,
            embeddings=replace(
                config.embeddings,
                provider="onnxruntime",
                model_revision=MODEL_REVISION,
                backend_version=version("onnxruntime"),
                readiness_state="ready",
                last_error=None,
            ),
        )
    except Exception as exc:
        updated = replace(
            config,
            bootstrap_state=BOOTSTRAP_STATE_REPAIR_NEEDED,
            current_step="embeddings",
            last_error=str(exc),
            embeddings=replace(
                config.embeddings, readiness_state="failed", last_error=str(exc)
            ),
        )
    return updated != config, updated


def _verify_model_revision(config: MachineConfig) -> None:
    """Do not mix existing vectors with an unverified model revision."""
    revision = config.embeddings.model_revision
    if revision is None:
        cached_ref = (
            Path(config.embeddings.cache_path)
            / "models--sentence-transformers--all-MiniLM-L6-v2"
            / "refs/main"
        )
        if cached_ref.is_file():
            revision = cached_ref.read_text().strip()
    if config.embeddings.model != "all-MiniLM-L6-v2" or revision not in (
        None,
        MODEL_REVISION,
    ):
        raise RuntimeError(
            "The existing embedding model differs from the pinned MiniLM revision. Re-embed stored memories and concepts before changing models."
        )
