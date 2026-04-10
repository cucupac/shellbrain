"""Shared helper builders for read execution tests."""

from app.core.contracts.requests import MemoryReadRequest


def make_read_request(
    *,
    expand_defaults: dict[str, object] | None = None,
    **overrides: object,
) -> MemoryReadRequest:
    """Build a read request with deterministic defaults and caller overrides."""

    payload: dict[str, object] = {
        "op": "read",
        "repo_id": "repo-a",
        "mode": "targeted",
        "query": "deployment issue",
        "include_global": True,
        "limit": 20,
        "expand": {
            "semantic_hops": 2,
            "include_problem_links": True,
            "include_fact_update_links": True,
            "include_association_links": True,
            "max_association_depth": 2,
            "min_association_strength": 0.25,
        },
    }
    if expand_defaults is not None:
        payload["expand"].update(expand_defaults)  # type: ignore[union-attr]
    if "expand" in overrides:
        expanded = dict(payload["expand"])  # type: ignore[arg-type]
        expanded.update(overrides["expand"])  # type: ignore[arg-type]
        payload["expand"] = expanded
        overrides = {key: value for key, value in overrides.items() if key != "expand"}
    payload.update(overrides)
    return MemoryReadRequest.model_validate(payload)


def item_ids(result) -> list[str]:
    """Extract ordered shellbrain IDs from a read operation result."""

    assert result.status == "ok"
    assert "pack" in result.data
    pack = result.data["pack"]
    return [
        *[item["memory_id"] for item in pack["direct"]],
        *[item["memory_id"] for item in pack["explicit_related"]],
        *[item["memory_id"] for item in pack["implicit_related"]],
    ]
