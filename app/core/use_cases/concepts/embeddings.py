"""Concept aggregate embedding maintenance helpers."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence

from app.core.ports.db.unit_of_work import IUnitOfWork
from app.core.ports.embeddings.provider import IEmbeddingProvider
from app.core.policies.concepts.search_text import build_concept_embedding_text


def upsert_concept_embeddings(
    *,
    repo_id: str,
    concept_ids: Sequence[str],
    uow: IUnitOfWork,
    embedding_provider: IEmbeddingProvider | None,
    embedding_model: str | None,
) -> int:
    """Refresh aggregate concept embeddings for touched concepts when enabled."""

    if embedding_provider is None or embedding_model is None:
        return 0
    updated = 0
    for concept_id in dict.fromkeys(str(value) for value in concept_ids):
        bundle = uow.concepts.get_concept_bundle(repo_id=repo_id, concept_ref=concept_id)
        if bundle is None:
            continue
        text = build_concept_embedding_text(bundle)
        source_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        uow.concepts.upsert_embedding(
            concept_id=concept_id,
            repo_id=repo_id,
            model=embedding_model,
            vector=embedding_provider.embed(text),
            source_hash=source_hash,
        )
        updated += 1
    return updated
