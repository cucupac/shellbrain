"""Unit coverage for build_context recall synthesis."""

from __future__ import annotations

import pytest


from app.core.entities.inner_agents import InnerAgentSettings
from app.core.ports.host_apps.inner_agents import InnerAgentRunResult
from app.core.use_cases.retrieval.recall.request import MemoryRecallRequest
from app.core.use_cases.retrieval.build_context import execute_build_context


class _FakeRunner:
    """Fake inner-agent runner for build_context tests."""

    def __init__(self) -> None:
        self.request = None

    def run(self, request):
        self.request = request
        return InnerAgentRunResult(
            status="ok",
            provider=request.provider,
            model=request.model,
            reasoning=request.reasoning,
            brief={
                "memories": [
                    "Use the migration timeout precedent.",
                    "Keep startup wiring out of core.",
                ],
                "code": ["app/infrastructure/db/admin"],
            },
            input_tokens=100,
            output_tokens=40,
            capture_quality="estimated",
        )


class _ErrorRunner:
    """Fake inner-agent runner that cannot produce a valid brief."""

    def run(self, request):
        return InnerAgentRunResult(
            status="invalid_output",
            provider=request.provider,
            model=request.model,
            reasoning=request.reasoning,
            fallback_used=False,
            error_code="invalid_output",
            error_message="bad JSON",
        )


def test_build_context_default_uses_deterministic_graph_synthesis(monkeypatch) -> None:
    """default build_context should synthesize once from the deterministic graph pack."""

    graph_pack = _graph_pack()
    _stub_graph_pack(monkeypatch, pack=graph_pack)
    runner = _FakeRunner()

    result = execute_build_context(
        MemoryRecallRequest.model_validate(
            {
                "repo_id": "repo-a",
                "query": "migration timeout",
            }
        ),
        object(),
        inner_agent_runner=runner,
    )

    assert result.data["brief"]["memories"][0] == "Use the migration timeout precedent."
    assert "sources" not in result.data["brief"]
    assert result.data["fallback_reason"] is None
    assert runner.request is not None
    synthesis_pack = runner.request.deterministic_pack
    assert synthesis_pack is not None
    assert synthesis_pack["memories"] == graph_pack["memories"]
    assert synthesis_pack["concepts"] == graph_pack["concepts"]
    assert "query_lanes" not in synthesis_pack
    assert "pack_trace" not in synthesis_pack
    assert "synthesis_trace" not in synthesis_pack
    assert (
        graph_pack["pack_trace"]["pack_budget"]["synthesis_candidate_tokens_estimated"]
        > 0
    )
    telemetry = result.data["_telemetry"]["inner_agent"]
    assert telemetry["private_read_count"] == 0
    assert telemetry["concept_expansion_count"] == 1


def test_build_context_missing_provider_reports_failure(
    monkeypatch,
) -> None:
    """Missing providers produce explicit failure metadata without invented context."""

    _stub_graph_pack(monkeypatch, pack=_graph_pack())

    result = execute_build_context(
        MemoryRecallRequest.model_validate(
            {
                "repo_id": "repo-a",
                "query": "migration timeout",
            }
        ),
        object(),
        inner_agent_runner=None,
        build_context_settings=_recall_settings(),
    )

    assert result.data["brief"] == {}
    assert "sources" not in result.data["brief"]
    assert result.data["fallback_reason"] == "provider_unavailable"
    telemetry = result.data["_telemetry"]["inner_agent"]
    assert telemetry["provider"] == "codex"
    assert telemetry["model"] == "gpt-5.4-mini"


def test_build_context_provider_unavailable_returns_no_brief(
    monkeypatch,
) -> None:
    """Unavailable synthesis cannot become successful raw retrieval."""

    _stub_graph_pack(monkeypatch, pack=_graph_pack())

    result = execute_build_context(
        MemoryRecallRequest.model_validate(
            {
                "repo_id": "repo-a",
                "query": "migration timeout",
            }
        ),
        object(),
    )

    assert result.data["brief"] == {}
    telemetry = result.data["_telemetry"]["inner_agent"]
    assert telemetry["status"] == "provider_unavailable"
    assert telemetry["fallback_used"] is False


def test_build_context_closes_owned_uow_before_synthesis(
    monkeypatch,
) -> None:
    """Recall closes its owned read transaction before running the provider."""

    opened = 0
    closed = False

    class _FakeUow:
        def __enter__(self):
            nonlocal opened
            opened += 1
            return self

        def __exit__(self, exc_type, exc_val, exc_tb) -> None:
            nonlocal closed
            closed = True

    class _RunnerAfterRead(_FakeRunner):
        def run(self, request):
            assert closed
            return super().run(request)

    _stub_graph_pack(monkeypatch, pack=_graph_pack())

    result = execute_build_context(
        MemoryRecallRequest.model_validate(
            {
                "repo_id": "repo-a",
                "query": "migration timeout",
            }
        ),
        None,
        uow_factory=_FakeUow,
        inner_agent_runner=_RunnerAfterRead(),
    )

    assert opened == 1
    assert result.data["fallback_reason"] is None


def test_build_context_truthfully_reports_no_context(monkeypatch) -> None:
    """build_context should return a no-context brief when retrieval finds nothing."""

    _stub_graph_pack(monkeypatch, pack=_empty_graph_pack())

    result = execute_build_context(
        MemoryRecallRequest.model_validate(
            {
                "repo_id": "repo-a",
                "query": "nothing",
            }
        ),
        object(),
    )

    assert result.data["fallback_reason"] == "no_candidates"
    assert "sources" not in result.data["brief"]
    assert result.data["brief"] == {"memories": [], "code": []}


def test_build_context_provider_error_returns_no_brief(
    monkeypatch,
) -> None:
    """Failed synthesis retains telemetry but does not create a brief."""

    _stub_graph_pack(monkeypatch, pack=_graph_pack())

    result = execute_build_context(
        MemoryRecallRequest.model_validate(
            {
                "repo_id": "repo-a",
                "query": "migration timeout",
            }
        ),
        object(),
        inner_agent_runner=_ErrorRunner(),
    )

    assert result.data["fallback_reason"] is not None
    assert result.data["brief"] == {}
    telemetry = result.data["_telemetry"]["inner_agent"]
    assert telemetry["status"] == "invalid_output"
    assert telemetry["fallback_used"] is False
    assert telemetry["error_code"] == "invalid_output"


def _stub_graph_pack(monkeypatch, *, pack: dict) -> None:
    """Patch build_context's deterministic graph dependency."""

    def _fake_build_graph_pack(**kwargs) -> dict:
        del kwargs
        return pack

    monkeypatch.setattr(
        "app.core.use_cases.retrieval.build_context.execute.build_deterministic_graph_pack",
        _fake_build_graph_pack,
    )


def _recall_settings() -> InnerAgentSettings:
    """Return configured build_context settings."""

    return InnerAgentSettings(
        provider="codex",
        model="gpt-5.4-mini",
        reasoning="medium",
        timeout_seconds=90,
        max_brief_tokens=1_800,
    )


def _graph_pack() -> dict:
    """Return one compact deterministic graph pack."""

    return {
        "strategy": "deterministic_graph",
        "request": {"query": "migration timeout"},
        "memory_relations": [],
        "query_lanes": [{"lane": "original", "query": "migration timeout"}],
        "memories": [
            {
                "id": "direct-1",
                "kind": "fact",
                "text": "Startup must not own Docker mechanics.",
                "matched_lanes": ["original"],
                "concept_refs": ["db-admin"],
                "link_roles": [],
                "why": ["memory_fanout"],
            }
        ],
        "concepts": [
            {
                "id": "concept-1",
                "ref": "db-admin",
                "name": "DB Admin",
                "kind": "process",
                "orientation": "DB lifecycle work is infrastructure.",
                "claims": [],
                "relations": [],
                "groundings": [
                    {
                        "role": "implementation",
                        "locator": "app/infrastructure/db/admin",
                    }
                ],
                "memory_links": [],
            }
        ],
        "relation_neighbors": [],
        "anchors": [
            {
                "id": "anchor-1",
                "concept_ref": "db-admin",
                "role": "implementation",
                "kind": "file",
                "locator": "app/infrastructure/db/admin",
            }
        ],
        "conflicts": [],
        "pack_trace": {
            "duration_ms": 5,
            "lane_results": [],
            "concept_candidates": {"selected": 1},
            "graph_traversal": {},
            "pack_budget": {},
        },
    }


def _empty_graph_pack() -> dict:
    """Return an empty deterministic graph pack."""

    return {
        "strategy": "deterministic_graph",
        "request": {"query": "nothing"},
        "memory_relations": [],
        "query_lanes": [],
        "memories": [],
        "concepts": [],
        "relation_neighbors": [],
        "anchors": [],
        "conflicts": [],
        "pack_trace": {"duration_ms": 1},
    }


@pytest.mark.parametrize(
    "brief",
    [
        None,
        {"memories": [], "code": ["app/infrastructure/db/admin"]},
        {"memories": ["Useful context."], "code": ["invented/file.py"]},
        {"memories": [" "], "code": []},
    ],
)
def test_build_context_rejects_unusable_provider_results(monkeypatch, brief):
    """All providers share schema and supplied-reference validation."""

    class Runner(_FakeRunner):
        def run(self, request):
            return super().run(request).model_copy(update={"brief": brief})

    _stub_graph_pack(monkeypatch, pack=_graph_pack())
    result = execute_build_context(
        MemoryRecallRequest(repo_id="repo-a", query="migration timeout"),
        object(),
        inner_agent_runner=Runner(),
    )
    assert result.brief == {}
    assert result.fallback_reason == "invalid_output"
    assert result.telemetry["inner_agent"]["status"] == "invalid_output"


def test_retrieved_candidates_can_produce_no_relevant_memory(monkeypatch):
    """The synthesizer can reject all retrieved candidates without an error."""

    class Runner(_FakeRunner):
        def run(self, request):
            return (
                super()
                .run(request)
                .model_copy(update={"brief": {"memories": [], "code": []}})
            )

    _stub_graph_pack(monkeypatch, pack=_graph_pack())
    result = execute_build_context(
        MemoryRecallRequest(repo_id="repo-a", query="unrelated question"),
        object(),
        inner_agent_runner=Runner(),
    )
    assert result.brief == {"memories": [], "code": []}
    assert result.fallback_reason is None


def test_code_reference_can_come_from_memory_text(monkeypatch):
    """A remembered location remains useful without a concept grounding."""
    pack = _graph_pack()
    pack["memories"][0]["text"] = (
        "Retry logic is in src/invoice/retry.py; its policy was not recorded."
    )

    class Runner(_FakeRunner):
        def run(self, request):
            return (
                super()
                .run(request)
                .model_copy(
                    update={
                        "brief": {
                            "memories": [pack["memories"][0]["text"]],
                            "code": ["src/invoice/retry.py"],
                        }
                    }
                )
            )

    _stub_graph_pack(monkeypatch, pack=pack)
    result = execute_build_context(
        MemoryRecallRequest(repo_id="repo-a", query="Where is retry logic?"),
        object(),
        inner_agent_runner=Runner(),
    )
    assert result.fallback_reason is None
    assert result.brief["code"] == ["src/invoice/retry.py"]
