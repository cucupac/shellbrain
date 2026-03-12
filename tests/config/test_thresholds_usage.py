"""Threshold-config usage contracts for retrieval boot helpers."""

from app.core.policies.read_policy.seed_retrieval import retrieve_seeds


class _StubSemanticRetrieval:
    """Stub semantic repo returning deterministic candidate rows."""

    def query_semantic(self, **kwargs):
        _ = kwargs
        return [
            {"memory_id": "semantic-keep", "score": 0.8},
            {"memory_id": "semantic-drop", "score": 0.2},
        ]


class _StubKeywordRetrieval:
    """Stub keyword repo returning deterministic candidate rows."""

    def query_keyword(self, **kwargs):
        _ = kwargs
        return [
            {"memory_id": "keyword-keep", "score": 0.9},
            {"memory_id": "keyword-drop", "score": 0.1},
        ]


def test_seed_retrieval_should_always_apply_configured_semantic_and_keyword_thresholds(monkeypatch) -> None:
    """seed retrieval should always apply configured semantic and keyword thresholds."""

    monkeypatch.setattr(
        "app.core.policies.read_policy.seed_retrieval.get_threshold_settings",
        lambda: {"semantic_threshold": 0.5, "keyword_threshold": 0.5},
    )

    seeds = retrieve_seeds(
        {
            "repo_id": "repo-a",
            "mode": "targeted",
            "query": "rollback issue",
            "include_global": True,
            "limit": 10,
        },
        semantic_retrieval=_StubSemanticRetrieval(),
        keyword_retrieval=_StubKeywordRetrieval(),
        vector_search=None,
    )

    assert seeds["semantic"] == [{"memory_id": "semantic-keep", "score": 0.8}]
    assert seeds["keyword"] == [{"memory_id": "keyword-keep", "score": 0.9}]
