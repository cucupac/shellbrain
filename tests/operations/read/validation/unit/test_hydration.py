"""Read hydration uses typed defaults and preserves explicit caller controls."""

from app.entrypoints.cli.request_parsing.hydration import hydrate_read_payload
from app.startup.read_policy import get_read_hydration_defaults
from app.core.use_cases.retrieval.read.request import MemoryReadRequest


def test_read_hydration_infers_missing_defaults():
    hydrated = hydrate_read_payload(
        {"query": "deployment lesson"},
        inferred_repo_id="repo-a",
        defaults=get_read_hydration_defaults(),
    )
    assert hydrated == {
        "op": "read",
        "repo_id": "repo-a",
        "query": "deployment lesson",
        "mode": "targeted",
        "include_global": True,
        "limit": 8,
    }
    assert MemoryReadRequest.model_validate(hydrated).expand.concepts.max_auto == 2


def test_read_hydration_preserves_explicit_values():
    payload = {
        "repo_id": "repo-b",
        "query": "deployment lesson",
        "mode": "ambient",
        "include_global": False,
        "limit": 3,
        "expand": {"concepts": {"mode": "none"}},
    }
    hydrated = hydrate_read_payload(
        payload, inferred_repo_id="repo-a", defaults=get_read_hydration_defaults()
    )
    assert hydrated == {"op": "read", **payload}
    assert MemoryReadRequest.model_validate(hydrated).expand.concepts.mode == "none"
