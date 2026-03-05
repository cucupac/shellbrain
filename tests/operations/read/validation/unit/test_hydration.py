"""Hydration contracts for read-path requests."""

from app.periphery.cli.hydration import hydrate_read_payload


def test_read_hydration_infers_missing_defaults() -> None:
    """read hydration should always infer repo_id and default knobs when omitted."""

    payload = {"query": "find deployment issue memory"}
    defaults = {
        "default_mode": "ambient",
        "include_global": False,
        "limit": 42,
        "semantic_hops": 1,
        "include_problem_links": False,
        "include_fact_update_links": True,
        "include_association_links": False,
        "max_association_depth": 3,
        "min_association_strength": 0.4,
    }

    hydrated = hydrate_read_payload(payload, inferred_repo_id="repo-inferred", defaults=defaults)

    assert hydrated["op"] == "read"
    assert hydrated["repo_id"] == "repo-inferred"
    assert hydrated["mode"] == "ambient"
    assert hydrated["include_global"] is False
    assert hydrated["limit"] == 42
    assert hydrated["expand"] == {
        "semantic_hops": 1,
        "include_problem_links": False,
        "include_fact_update_links": True,
        "include_association_links": False,
        "max_association_depth": 3,
        "min_association_strength": 0.4,
    }


def test_read_hydration_preserves_explicit_values() -> None:
    """read hydration should always preserve explicit payload values over inferred defaults."""

    payload = {
        "op": "read",
        "repo_id": "repo-explicit",
        "mode": "targeted",
        "query": "explicit payload query",
        "include_global": True,
        "limit": 7,
        "expand": {
            "semantic_hops": 0,
            "include_problem_links": True,
            "include_fact_update_links": False,
            "include_association_links": True,
            "max_association_depth": 2,
            "min_association_strength": 0.1,
        },
    }
    defaults = {
        "default_mode": "ambient",
        "include_global": False,
        "limit": 42,
        "semantic_hops": 3,
        "include_problem_links": False,
        "include_fact_update_links": True,
        "include_association_links": False,
        "max_association_depth": 4,
        "min_association_strength": 0.9,
    }

    hydrated = hydrate_read_payload(payload, inferred_repo_id="repo-inferred", defaults=defaults)

    assert hydrated["op"] == "read"
    assert hydrated["repo_id"] == "repo-explicit"
    assert hydrated["mode"] == "targeted"
    assert hydrated["include_global"] is True
    assert hydrated["limit"] == 7
    assert hydrated["expand"] == payload["expand"]
