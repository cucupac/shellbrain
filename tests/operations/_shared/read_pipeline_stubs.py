"""Shared read-pipeline stubs for telemetry record-write tests."""

from __future__ import annotations

import pytest


def stub_read_pipeline(monkeypatch: pytest.MonkeyPatch, *, zero_results: bool) -> None:
    """Patch the read pipeline to return deterministic candidate sets."""

    monkeypatch.setattr(
        "app.core.use_cases.retrieval.context_pack_pipeline.retrieve_seeds",
        lambda payload, **kwargs: {"semantic": [], "keyword": []},
    )
    monkeypatch.setattr(
        "app.core.use_cases.retrieval.context_pack_pipeline.fuse_with_rrf",
        lambda semantic, keyword, **kwargs: (
            []
            if zero_results
            else [
                {
                    "memory_id": "direct-1",
                    "rrf_score": 0.99,
                    "score": 0.99,
                    "kind": "problem",
                    "text": "Primary direct memory.",
                    "created_at": "2024-01-01T00:00:00+00:00",
                    "status": "active",
                    "why_included": "direct_match",
                }
            ]
        ),
    )
    monkeypatch.setattr(
        "app.core.use_cases.retrieval.context_pack_pipeline.expand_candidates",
        lambda direct_candidates, payload, **kwargs: (
            {"explicit": [], "implicit": []}
            if zero_results
            else {
                "explicit": [
                    {
                        "memory_id": "explicit-1",
                        "score": 0.88,
                        "kind": "solution",
                        "text": "Linked association memory.",
                        "created_at": "2024-01-01T00:00:00+00:00",
                        "status": "active",
                        "why_included": "association_link",
                        "anchor_memory_id": "direct-1",
                        "relation_type": "depends_on",
                    }
                ],
                "implicit": [
                    {
                        "memory_id": "implicit-1",
                        "score": 0.77,
                        "kind": "fact",
                        "text": "Nearby semantic memory.",
                        "created_at": "2024-01-01T00:00:00+00:00",
                        "status": "active",
                        "why_included": "semantic_neighbor",
                        "anchor_memory_id": "direct-1",
                    }
                ],
            }
        ),
    )
    monkeypatch.setattr(
        "app.core.use_cases.retrieval.context_pack_pipeline.score_candidates",
        lambda bucketed_candidates: bucketed_candidates,
    )
