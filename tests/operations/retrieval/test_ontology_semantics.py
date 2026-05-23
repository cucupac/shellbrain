"""Conformance tests for shared read/recall ontology semantics."""

import pytest

from app.core.policies.retrieval.ontology_semantics import (
    aggregate_currentness_payload,
    concept_bundle_retrieval_multiplier,
    lifecycle_retrieval_multiplier,
    memory_currentness_payload,
    structural_relation_expansion_type,
    why_included_for_expansion,
)


def test_lifecycle_statuses_have_one_retrieval_semantics_table() -> None:
    assert lifecycle_retrieval_multiplier("active") == 1.0
    assert lifecycle_retrieval_multiplier("maybe_stale") == 0.65
    assert lifecycle_retrieval_multiplier("stale") == 0.25
    assert lifecycle_retrieval_multiplier("superseded") == 0.0
    assert lifecycle_retrieval_multiplier("wrong") == 0.0
    assert lifecycle_retrieval_multiplier("archived") == 0.0


def test_aggregate_currentness_uses_the_same_precedence_for_read_and_recall() -> None:
    assert aggregate_currentness_payload(
        ["active", "stale"], record_label="concept facets"
    ) == {
        "currentness": "stale",
        "temporal_reason": "one or more concept facets are marked stale",
    }
    assert concept_bundle_retrieval_multiplier(["active", "superseded"]) == 0.0


def test_memory_currentness_keeps_warning_and_change_semantics_separate() -> None:
    assert memory_currentness_payload(
        status="active", kind="failed_tactic", link_roles=[]
    )["currentness"] == "historical_warning"
    assert memory_currentness_payload(
        status="active", kind="fact", link_roles=["change_relevant_to"]
    )["temporal_reason"].startswith("change_relevant_to")
    assert memory_currentness_payload(
        status="wrong", kind="fact", link_roles=[]
    ) == {
        "currentness": "wrong",
        "temporal_reason": "memory lifecycle status is wrong",
    }


def test_structural_relation_predicates_map_to_stable_read_labels() -> None:
    assert structural_relation_expansion_type("solved_by") == "problem_attempt"
    assert structural_relation_expansion_type("failed_with") == "problem_attempt"
    assert structural_relation_expansion_type("superseded_by") == "fact_update"
    assert structural_relation_expansion_type("explained_by_change") == "fact_update"
    assert why_included_for_expansion("association") == "association_link"
    with pytest.raises(ValueError, match="unsupported structural"):
        structural_relation_expansion_type("matures_into")
    with pytest.raises(ValueError, match="unsupported read expansion"):
        why_included_for_expansion("related_memory")
