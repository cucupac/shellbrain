"""Recall selection retains complete cases and respects its rendering budget."""

from copy import deepcopy

import pytest

from app.core.entities.recall_settings import RecallSettings
from app.core.policies.retrieval.synthesis_evidence import (
    fit_synthesis_evidence,
    select_synthesis_evidence,
)


def sample():
    return {
        "memories": [
            {"id": name, "text": name} for name in ["problem", "other", "solution"]
        ],
        "memory_relations": [
            {
                "subject_memory_id": "problem",
                "object_memory_id": "solution",
                "predicate": "solved_by",
                "status": "maybe_stale",
            }
        ],
        "concepts": [
            {
                "id": "c",
                "claims": [
                    {"text": "unrelated", "status": "active"},
                    {"text": "router invariant", "status": "disputed"},
                ],
                "groundings": [{"locator": "other"}, {"locator": "router.rs"}],
                "memory_links": [
                    {"memory_id": name} for name in ["problem", "other", "missing"]
                ],
                "relations": [],
            }
        ],
        "relation_neighbors": [],
    }


def test_selection_keeps_pairs_and_qualifications_without_mutation():
    source = sample()
    original = deepcopy(source)
    result = select_synthesis_evidence(
        source,
        "router",
        RecallSettings(
            max_memories=2, max_claims_per_concept=1, max_groundings_per_concept=1
        ),
    )
    assert source == original
    assert [m["id"] for m in result["memories"]] == ["problem", "solution"]
    assert result["memory_relations"][0]["status"] == "maybe_stale"
    concept = result["concepts"][0]
    assert concept["claims"] == [{"text": "router invariant", "status": "disputed"}]
    assert concept["groundings"] == [{"locator": "router.rs"}]
    assert concept["memory_links"] == [{"memory_id": "problem"}]


def test_budget_removes_whole_pairs_and_reports_impossible_budget():
    pack = sample()
    result = fit_synthesis_evidence(
        pack, max_tokens=2, measure=lambda p: len(p["memories"])
    )
    assert [m["id"] for m in result["memories"]] == ["problem", "solution"]
    assert len(result["memory_relations"]) == 1
    with pytest.raises(ValueError, match="query and instructions"):
        fit_synthesis_evidence(pack, max_tokens=1, measure=lambda _: 2)


def test_missing_endpoint_is_an_error():
    pack = sample()
    pack["memories"].pop()
    with pytest.raises(ValueError, match="missing memory"):
        select_synthesis_evidence(pack, "router", RecallSettings())
