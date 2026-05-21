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
                "summary": "Use the migration timeout precedent.",
                "constraints": ["Keep startup wiring out of core."],
                "known_traps": ["Do not make Docker calls from startup."],
                "prior_cases": ["A prior migration hang was caused by missing timeout."],
                "concept_orientation": ["DB admin work belongs under infrastructure."],
                "anchors": ["app/infrastructure/db/admin"],
                "conflicts": [
                    "Older guidance about startup-owned DB admin wiring is stale."
                ],
                "gaps": [],
                "next_checks": ["Inspect db/admin migration wiring first."],
            },
            input_tokens=100,
            output_tokens=40,
            capture_quality="estimated",
            read_trace={
                "commands": [
                    {
                        "command": "shellbrain read --json '{\"query\":\"migration timeout\"}'",
                        "source_ids": ["direct-1"],
                        "concept_refs": ["db-admin"],
                    },
                    {
                        "command": "shellbrain concept show --json '{\"schema_version\":\"concept.v1\",\"concept\":\"db-admin\"}'",
                        "concept_refs": ["db-admin"],
                    },
                ],
                "source_ids": ["direct-1"],
                "concept_refs": ["db-admin"],
            },
        )


class _ErrorRunner:
    """Fake inner-agent runner that cannot produce a valid brief."""

    def run(self, request):
        return InnerAgentRunResult(
            status="invalid_output",
            provider=request.provider,
            model=request.model,
            reasoning=request.reasoning,
            fallback_used=True,
            error_code="invalid_output",
            error_message="bad JSON",
        )


def test_build_context_uses_fake_provider_for_structured_synthesis(monkeypatch) -> None:
    """build_context should accept provider synthesis through a core port."""

    monkeypatch.setattr(
        "app.core.use_cases.retrieval.build_context.execute.build_deterministic_graph_pack",
        lambda *args, **kwargs: pytest.fail("provider path must not build fallback pack"),
    )
    runner = _FakeRunner()

    result = execute_build_context(
        MemoryRecallRequest.model_validate(
            {
                "op": "recall",
                "repo_id": "repo-a",
                "query": "migration timeout",
                "current_problem": _current_problem(),
            }
        ),
        None,
        inner_agent_runner=runner,
        build_context_settings=_autonomous_build_context_settings(),
    )

    assert result.data["brief"]["summary"] == "Use the migration timeout precedent."
    assert result.data["brief"]["conflicts"] == [
        "Older guidance about startup-owned DB admin wiring is stale."
    ]
    assert result.data["brief"]["next_checks"] == [
        "Inspect db/admin migration wiring first."
    ]
    assert result.data["brief"]["sources"]
    assert result.data["fallback_reason"] is None
    assert runner.request is not None
    assert runner.request.current_problem == _current_problem()
    assert not hasattr(runner.request, "candidate_" "context")
    telemetry = result.data["_telemetry"]["inner_agent"]
    assert telemetry["input_tokens"] == 100
    assert telemetry["output_tokens"] == 40
    assert telemetry["capture_quality"] == "estimated"
    assert telemetry["private_read_count"] == 2
    assert telemetry["concept_expansion_count"] == 1


def test_build_context_default_uses_deterministic_graph_synthesis(monkeypatch) -> None:
    """default build_context should synthesize once from the deterministic graph pack."""

    graph_pack = _graph_pack()
    _stub_graph_pack(monkeypatch, pack=graph_pack)
    runner = _FakeRunner()

    result = execute_build_context(
        MemoryRecallRequest.model_validate(
            {
                "op": "recall",
                "repo_id": "repo-a",
                "query": "migration timeout",
                "current_problem": _current_problem(),
            }
        ),
        object(),
        inner_agent_runner=runner,
    )

    assert result.data["brief"]["summary"] == "Use the migration timeout precedent."
    assert result.data["brief"]["sources"] == [
        {"kind": "memory", "id": "direct-1", "section": "direct"},
        {"kind": "concept", "id": "concept-1", "section": "concept_orientation"},
    ]
    assert result.data["fallback_reason"] is None
    assert runner.request is not None
    assert runner.request.synthesis_only is True
    synthesis_pack = runner.request.deterministic_pack
    assert synthesis_pack is not None
    assert synthesis_pack["memories"] == graph_pack["memories"]
    assert synthesis_pack["concepts"] == graph_pack["concepts"]
    assert "query_lanes" not in synthesis_pack
    assert "pack_trace" not in synthesis_pack
    assert "synthesis_trace" not in synthesis_pack
    assert (
        graph_pack["pack_trace"]["pack_budget"][
            "synthesis_candidate_tokens_estimated"
        ]
        > 0
    )
    telemetry = result.data["_telemetry"]["inner_agent"]
    assert telemetry["private_read_count"] == 0
    assert telemetry["concept_expansion_count"] == 1


def test_build_context_deterministic_only_skips_provider(monkeypatch) -> None:
    """deterministic_only should return a graph brief without running a model."""

    _stub_graph_pack(monkeypatch, pack=_graph_pack())

    class _FailingRunner:
        def run(self, request):
            raise AssertionError("deterministic_only must not call provider")

    result = execute_build_context(
        MemoryRecallRequest.model_validate(
            {
                "op": "recall",
                "repo_id": "repo-a",
                "query": "migration timeout",
                "current_problem": _current_problem(),
            }
        ),
        object(),
        inner_agent_runner=_FailingRunner(),
        build_context_settings=_deterministic_only_settings(),
    )

    assert result.data["brief"]["summary"] == (
        "Shellbrain found 1 memory source(s) and 1 concept source(s) for this recall query."
    )
    assert result.data["fallback_reason"] is None
    telemetry = result.data["_telemetry"]["inner_agent"]
    assert telemetry["provider"] == "deterministic"
    assert telemetry["model"] == "none"


def test_build_context_provider_unavailable_uses_deterministic_graph_fallback(
    monkeypatch,
) -> None:
    """autonomous build_context should use graph fallback when no runner exists."""

    _stub_graph_pack(monkeypatch, pack=_graph_pack())

    result = execute_build_context(
        MemoryRecallRequest.model_validate(
            {
                "op": "recall",
                "repo_id": "repo-a",
                "query": "migration timeout",
                "current_problem": _current_problem(),
            }
        ),
        object(),
        build_context_settings=_autonomous_build_context_settings(),
    )

    assert result.data["brief"]["summary"] == (
        "Shellbrain found 1 memory source(s) and 1 concept source(s) for this recall query."
    )
    assert result.data["brief"]["conflicts"] == []
    assert result.data["brief"]["next_checks"] == [
        "Check implementation anchor: app/infrastructure/db/admin"
    ]
    telemetry = result.data["_telemetry"]["inner_agent"]
    assert telemetry["status"] == "provider_unavailable"
    assert telemetry["fallback_used"] is True


def test_build_context_lazy_fallback_opens_uow_only_for_internal_read(
    monkeypatch,
) -> None:
    """default deterministic recall should open a DB transaction only when needed."""

    opened = 0

    class _FakeUow:
        def __enter__(self):
            nonlocal opened
            opened += 1
            return self

        def __exit__(self, exc_type, exc_val, exc_tb) -> None:
            return None

    _stub_graph_pack(monkeypatch, pack=_graph_pack())

    result = execute_build_context(
        MemoryRecallRequest.model_validate(
            {
                "op": "recall",
                "repo_id": "repo-a",
                "query": "migration timeout",
                "current_problem": _current_problem(),
            }
        ),
        None,
        uow_factory=_FakeUow,
    )

    assert opened == 1
    assert result.data["fallback_reason"] is None


def test_build_context_truthfully_reports_no_context(monkeypatch) -> None:
    """build_context should return a no-context brief when retrieval finds nothing."""

    _stub_graph_pack(monkeypatch, pack=_empty_graph_pack())

    result = execute_build_context(
        MemoryRecallRequest.model_validate(
            {
                "op": "recall",
                "repo_id": "repo-a",
                "query": "nothing",
                "current_problem": _current_problem(),
            }
        ),
        object(),
    )

    assert result.data["fallback_reason"] == "no_candidates"
    assert result.data["brief"]["sources"] == []
    assert result.data["brief"]["conflicts"] == []
    assert result.data["brief"]["next_checks"] == []
    assert "no relevant memories" in result.data["brief"]["gaps"][0]


def test_build_context_provider_error_uses_deterministic_fallback(
    monkeypatch,
) -> None:
    """build_context should use deterministic fallback when the provider fails."""

    _stub_graph_pack(monkeypatch, pack=_graph_pack())

    result = execute_build_context(
        MemoryRecallRequest.model_validate(
            {
                "op": "recall",
                "repo_id": "repo-a",
                "query": "migration timeout",
                "current_problem": _current_problem(),
            }
        ),
        object(),
        inner_agent_runner=_ErrorRunner(),
        build_context_settings=_autonomous_build_context_settings(),
    )

    assert result.data["fallback_reason"] is None
    assert result.data["brief"]["summary"] == (
        "Shellbrain found 1 memory source(s) and 1 concept source(s) for this recall query."
    )
    telemetry = result.data["_telemetry"]["inner_agent"]
    assert telemetry["status"] == "invalid_output"
    assert telemetry["fallback_used"] is True
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


def _autonomous_build_context_settings() -> InnerAgentSettings:
    """Return autonomous build_context settings for legacy provider-path tests."""

    return InnerAgentSettings(
        strategy="autonomous",
        provider="codex",
        model="gpt-5.4-mini",
        reasoning="medium",
        timeout_seconds=90,
        max_private_reads=3,
        max_brief_tokens=1_800,
    )


def _deterministic_only_settings() -> InnerAgentSettings:
    """Return deterministic-only build_context settings."""

    return InnerAgentSettings(
        strategy="deterministic_only",
        provider="codex",
        model="gpt-5.4-mini",
        reasoning="medium",
        timeout_seconds=90,
        max_private_reads=0,
        max_brief_tokens=1_800,
    )


def _current_problem() -> dict[str, str]:
    """Return the mandatory worker problem context for recall tests."""

    return {
        "goal": "fix migration",
        "surface": "db admin",
        "obstacle": "lock timeout",
        "hypothesis": "missing timeout guard",
    }


def _graph_pack() -> dict:
    """Return one compact deterministic graph pack."""

    return {
        "strategy": "deterministic_graph",
        "request": {"query": "migration timeout", "current_problem": _current_problem()},
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
        "request": {"query": "nothing", "current_problem": _current_problem()},
        "query_lanes": [],
        "memories": [],
        "concepts": [],
        "relation_neighbors": [],
        "anchors": [],
        "conflicts": [],
        "pack_trace": {"duration_ms": 1},
    }
