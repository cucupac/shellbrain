"""Selected evidence fixtures for telemetry tests; retrieval is tested separately."""

import pytest


def stub_read_pipeline(monkeypatch: pytest.MonkeyPatch, *, zero_results: bool) -> None:
    memories = (
        []
        if zero_results
        else [
            {
                "id": "direct-1",
                "kind": "problem",
                "text": "Primary direct memory.",
                "matched_lanes": ["direct"],
                "why": ["direct_match"],
            },
            {
                "id": "explicit-1",
                "kind": "solution",
                "text": "Linked solution.",
                "matched_lanes": [],
                "why": ["structural_memory_relation"],
            },
            {
                "id": "implicit-1",
                "kind": "fact",
                "text": "Related evidence.",
                "matched_lanes": [],
                "why": ["concept_evidence"],
            },
        ]
    )
    for memory in memories:
        memory.update(
            created_at="2024-01-01T00:00:00+00:00", status="active", score=0.8
        )
    monkeypatch.setattr(
        "app.core.use_cases.retrieval.read.execute.build_deterministic_graph_pack",
        lambda **kwargs: {
            "memories": memories,
            "concepts": [],
            "relation_neighbors": [],
            "conflicts": [],
        },
    )
