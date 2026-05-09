"""Read-policy config usage contracts for runtime default resolution."""

from app.startup.read_policy import resolve_read_payload_defaults


def test_read_policy_should_always_resolve_missing_read_knobs_from_config(
    monkeypatch,
) -> None:
    """read policy should always resolve missing read knobs from config."""

    monkeypatch.setattr(
        "app.startup.read_policy.get_read_settings",
        lambda: {
            "default_mode": "ambient",
            "include_global": False,
            "limits_by_mode": {"targeted": 8, "ambient": 12},
            "expand": {
                "semantic_hops": 1,
                "include_problem_links": False,
                "include_fact_update_links": True,
                "include_association_links": False,
                "max_association_depth": 3,
                "min_association_strength": 0.4,
            },
            "quotas_by_mode": {
                "targeted": {"direct": 4, "explicit": 3, "implicit": 1},
                "ambient": {"direct": 4, "explicit": 5, "implicit": 3},
            },
            "retrieval": {"semantic_weight": 1.0, "keyword_weight": 1.0, "k_rrf": 20.0},
        },
    )

    resolved = resolve_read_payload_defaults(
        {
            "repo_id": "repo-a",
            "mode": "ambient",
            "query": "rollback issue",
        }
    )

    assert resolved["include_global"] is False
    assert resolved["limit"] == 12
    assert resolved["kinds"] == [
        "problem",
        "solution",
        "failed_tactic",
        "fact",
        "preference",
        "change",
    ]
    assert resolved["expand"] == {
        "semantic_hops": 1,
        "include_problem_links": False,
        "include_fact_update_links": True,
        "include_association_links": False,
        "max_association_depth": 3,
        "min_association_strength": 0.4,
    }


def test_read_policy_should_always_merge_partial_expand_over_config_defaults(
    monkeypatch,
) -> None:
    """read policy should always merge partial expand over config defaults."""

    monkeypatch.setattr(
        "app.startup.read_policy.get_read_settings",
        lambda: {
            "default_mode": "targeted",
            "include_global": True,
            "limits_by_mode": {"targeted": 8, "ambient": 12},
            "expand": {
                "semantic_hops": 2,
                "include_problem_links": True,
                "include_fact_update_links": True,
                "include_association_links": True,
                "max_association_depth": 2,
                "min_association_strength": 0.25,
            },
            "quotas_by_mode": {
                "targeted": {"direct": 4, "explicit": 3, "implicit": 1},
                "ambient": {"direct": 4, "explicit": 5, "implicit": 3},
            },
            "retrieval": {"semantic_weight": 1.0, "keyword_weight": 1.0, "k_rrf": 20.0},
        },
    )

    resolved = resolve_read_payload_defaults(
        {
            "repo_id": "repo-a",
            "mode": "targeted",
            "query": "rollback issue",
            "expand": {
                "semantic_hops": 0,
                "include_association_links": False,
            },
        }
    )

    assert resolved["expand"] == {
        "semantic_hops": 0,
        "include_problem_links": True,
        "include_fact_update_links": True,
        "include_association_links": False,
        "max_association_depth": 2,
        "min_association_strength": 0.25,
    }
