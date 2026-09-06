"""Shared helper builders for read execution tests."""

from app.core.use_cases.retrieval.read.request import MemoryReadRequest


def make_read_request(
    **overrides: object,
) -> MemoryReadRequest:
    """Build a read request with deterministic defaults and caller overrides."""

    payload = {"repo_id": "repo-a", "query": "deployment issue", "limit": 20}
    payload.update(overrides)
    return MemoryReadRequest.model_validate(payload)


def item_ids(result) -> list[str]:
    """Extract ordered shellbrain IDs from a read operation result."""
    assert "pack" in result.data
    pack = result.data["pack"]
    return [
        *[item["memory_id"] for item in pack["direct"]],
        *[item["memory_id"] for item in pack["explicit_related"]],
        *[item["memory_id"] for item in pack["implicit_related"]],
    ]
