"""Threshold-config usage contracts for retrieval boot helpers."""

from app.core.use_cases.memory_retrieval.seed_retrieval import retrieve_seeds


class _StubSemanticRetrieval:
    """Stub semantic repo returning deterministic candidate rows."""

    def query_semantic(self, **kwargs):
        _ = kwargs
        return [
            {"memory_id": "semantic-keep", "score": 0.8},
            {"memory_id": "semantic-drop", "score": 0.2},
        ]


class _StubKeywordRetrieval:
    """Stub keyword corpus repo returning deterministic text rows."""

    def list_keyword_corpus(self, **kwargs):
        _ = kwargs
        return [
            {"memory_id": "keyword-keep", "text": "rollback issue"},
            {"memory_id": "keyword-drop", "text": "rollback"},
        ]


def test_seed_retrieval_should_always_apply_configured_semantic_and_keyword_thresholds(monkeypatch) -> None:
    """seed retrieval should always apply configured semantic and keyword thresholds."""

    monkeypatch.setattr(
        "app.core.use_cases.memory_retrieval.seed_retrieval.get_threshold_settings",
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
    assert [candidate["memory_id"] for candidate in seeds["keyword"]] == ["keyword-keep"]
    assert float(seeds["keyword"][0]["score"]) >= 0.5
