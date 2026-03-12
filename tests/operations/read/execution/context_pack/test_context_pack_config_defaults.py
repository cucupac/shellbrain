"""Read execution contracts for context-pack YAML-backed defaults."""

from app.boot.config import get_config_provider
from app.boot.retrieval import get_retrieval_defaults
from app.core.policies.read_policy.context_pack_builder import assemble_context_pack


def test_read_context_pack_config_should_always_define_mode_specific_limits_in_read_policy_yaml() -> None:
    """read context pack config should always define mode-specific limits in read policy yaml."""

    read_policy = get_config_provider().get_read_policy()

    assert read_policy["limits"] == {"targeted": 8, "ambient": 12}


def test_read_context_pack_config_should_always_define_direct_heavy_quotas_by_mode_in_read_policy_yaml() -> None:
    """read context pack config should always define direct-heavy quotas by mode in read policy yaml."""

    read_policy = get_config_provider().get_read_policy()

    assert read_policy["quotas"] == {
        "targeted": {"direct": 4, "explicit": 3, "implicit": 1},
        "ambient": {"direct": 4, "explicit": 5, "implicit": 3},
    }


def test_read_context_pack_config_should_always_load_rrf_defaults_from_the_read_policy_yaml() -> None:
    """read context pack config should always load RRF defaults from the read policy yaml."""

    read_policy = get_config_provider().get_read_policy()
    retrieval_defaults = get_retrieval_defaults()

    assert retrieval_defaults["k_rrf"] == read_policy["fusion"]["k_rrf"]
    assert retrieval_defaults["semantic_weight"] == read_policy["weights"]["semantic"]
    assert retrieval_defaults["keyword_weight"] == read_policy["weights"]["keyword"]


def test_context_pack_builder_should_always_use_targeted_mode_as_eight_items_by_default() -> None:
    """context pack builder should always use targeted mode as eight items by default."""

    pack = assemble_context_pack(_make_scored_candidates(total=20), {"repo_id": "repo-a", "mode": "targeted", "query": "q"})

    assert len(_all_ids(pack)) == 8


def test_context_pack_builder_should_always_use_ambient_mode_as_twelve_items_by_default() -> None:
    """context pack builder should always use ambient mode as twelve items by default."""

    pack = assemble_context_pack(_make_scored_candidates(total=20), {"repo_id": "repo-a", "mode": "ambient", "query": "q"})

    assert len(_all_ids(pack)) == 12


def _make_scored_candidates(*, total: int) -> dict[str, list[dict[str, object]]]:
    """Build a large scored candidate pool for default-limit tests."""

    return {
        "direct": [
            {"memory_id": f"direct-{index}", "score": 1.0 - (index * 0.01), "kind": "problem", "text": f"Direct {index}.", "why_included": "direct_match"}
            for index in range(1, total + 1)
        ],
        "explicit": [],
        "implicit": [],
    }


def _all_ids(pack: dict[str, object]) -> list[str]:
    """Extract all ordered memory identifiers from the grouped pack."""

    return [
        *[str(item["memory_id"]) for item in pack["direct"]],
        *[str(item["memory_id"]) for item in pack["explicit_related"]],
        *[str(item["memory_id"]) for item in pack["implicit_related"]],
    ]
