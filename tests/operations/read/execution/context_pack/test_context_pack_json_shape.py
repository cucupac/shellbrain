"""The shared selector keeps the read envelope useful for agents and telemetry."""

from app.core.use_cases.retrieval.read import execute_read_memory
from app.core.use_cases.retrieval.read.request import MemoryReadRequest
from tests.operations._shared.read_pipeline_stubs import stub_read_pipeline


def test_read_preserves_grouped_evidence_and_display_order(monkeypatch):
    stub_read_pipeline(monkeypatch, zero_results=False)
    pack = execute_read_memory(
        MemoryReadRequest(repo_id="repo-a", query="deployment lesson"), None
    ).data["pack"]
    assert list(pack) == [
        "meta",
        "direct",
        "explicit_related",
        "implicit_related",
        "concepts",
        "relation_neighbors",
        "conflicts",
    ]
    assert pack["meta"] == {
        "mode": "targeted",
        "limit": 8,
        "counts": {"direct": 1, "explicit_related": 1, "implicit_related": 1},
    }
    items = [
        item
        for section in ("direct", "explicit_related", "implicit_related")
        for item in pack[section]
    ]
    assert [item["priority"] for item in items] == [1, 2, 3]
    assert [item["memory_id"] for item in items] == [
        "direct-1",
        "explicit-1",
        "implicit-1",
    ]
    for item in items:
        assert item["kind"] and item["text"] and item["why_included"]
        assert item["created_at"] == "2024-01-01T00:00:00+00:00"
    assert pack["concepts"] == {"mode": "auto", "items": []}


def test_empty_read_keeps_evidence_envelope(monkeypatch):
    stub_read_pipeline(monkeypatch, zero_results=True)
    pack = execute_read_memory(
        MemoryReadRequest(
            repo_id="repo-a", query="unknown", expand={"concepts": {"mode": "none"}}
        ),
        None,
    ).data["pack"]
    assert sum(pack["meta"]["counts"].values()) == 0
    assert pack["concepts"] == {"mode": "none", "items": []}
