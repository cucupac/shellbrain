"""Semantic contracts for update-path requests."""

from app.core.use_cases.memories.update.request import MemoryUpdateRequest
from app.core.policies.memories.link_rules import validate_update_semantics


def test_update_association_rejects_self_link() -> None:
    """association_link updates should always reject self-links."""

    request = MemoryUpdateRequest.model_validate(
        {
            "op": "update",
            "repo_id": "repo-a",
            "memory_id": "memory-1",
            "update": {
                "type": "association_link",
                "to_memory_id": "memory-1",
                "relation_type": "depends_on",
                "evidence_refs": ["session://1"],
            },
        }
    )

    errors = validate_update_semantics(request)

    assert any(error.code.value == "semantic_error" for error in errors)
    assert any(error.field == "update.to_memory_id" for error in errors)


def test_fact_update_requires_distinct_endpoints_and_reserves_memory_id() -> None:
    """fact_update_link updates should always require distinct fact endpoints and reserve memory_id for the change memory."""

    duplicate_endpoint_request = MemoryUpdateRequest.model_validate(
        {
            "op": "update",
            "repo_id": "repo-a",
            "memory_id": "change-1",
            "update": {
                "type": "fact_update_link",
                "old_fact_id": "fact-1",
                "new_fact_id": "fact-1",
            },
        }
    )
    duplicate_endpoint_errors = validate_update_semantics(duplicate_endpoint_request)

    assert any(
        error.code.value == "semantic_error" for error in duplicate_endpoint_errors
    )
    assert any(
        error.field == "update.new_fact_id" for error in duplicate_endpoint_errors
    )

    reused_memory_id_request = MemoryUpdateRequest.model_validate(
        {
            "op": "update",
            "repo_id": "repo-a",
            "memory_id": "change-1",
            "update": {
                "type": "fact_update_link",
                "old_fact_id": "change-1",
                "new_fact_id": "fact-2",
            },
        }
    )
    reused_memory_id_errors = validate_update_semantics(reused_memory_id_request)

    assert any(
        error.code.value == "semantic_error" for error in reused_memory_id_errors
    )
    assert any(error.field == "memory_id" for error in reused_memory_id_errors)
