"""Unit coverage for build_context recall synthesis."""

from __future__ import annotations

import pytest

from app.core.entities.inner_agents import InnerAgentSettings
from app.core.ports.host_apps.inner_agents import InnerAgentRunResult
from app.core.use_cases.retrieval.read.result import ReadMemoryResult
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
                "gaps": [],
            },
            input_token_estimate=100,
            output_token_estimate=40,
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
        "app.core.use_cases.retrieval.build_context.execute.execute_read_memory",
        lambda *args, **kwargs: pytest.fail("provider path must not pre-read"),
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
        object(),
        inner_agent_runner=runner,
        build_context_settings=_enabled_build_context_settings(),
    )

    assert result.data["brief"]["summary"] == "Use the migration timeout precedent."
    assert result.data["brief"]["sources"]
    assert result.data["fallback_reason"] is None
    assert runner.request is not None
    assert runner.request.current_problem == _current_problem()
    assert not hasattr(runner.request, "candidate_" "context")
    telemetry = result.data["_telemetry"]["inner_agent"]
    assert telemetry["private_read_count"] == 2
    assert telemetry["concept_expansion_count"] == 1


def test_build_context_provider_unavailable_uses_deterministic_fallback(
    monkeypatch,
) -> None:
    """build_context should read internally only when the provider path cannot run."""

    read_requests = []

    def _fake_execute_read_memory(request, uow, **kwargs) -> ReadMemoryResult:
        del uow, kwargs
        read_requests.append(request)
        return ReadMemoryResult(pack=_candidate_pack())

    monkeypatch.setattr(
        "app.core.use_cases.retrieval.build_context.execute.execute_read_memory",
        _fake_execute_read_memory,
    )

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
        build_context_settings=_enabled_build_context_settings(),
    )

    assert len(read_requests) == 1
    assert result.data["brief"]["summary"] == "Shellbrain synthesized 2 recall source(s) for this query."
    telemetry = result.data["_telemetry"]["inner_agent"]
    assert telemetry["status"] == "provider_unavailable"
    assert telemetry["fallback_used"] is True


def test_build_context_truthfully_reports_no_context(monkeypatch) -> None:
    """build_context should return a no-context brief when retrieval finds nothing."""

    _stub_internal_read(monkeypatch, pack=_empty_pack())

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
    assert "no relevant memories" in result.data["brief"]["gaps"][0]


def test_build_context_provider_error_uses_deterministic_fallback(
    monkeypatch,
) -> None:
    """build_context should use deterministic fallback when the provider fails."""

    _stub_internal_read(monkeypatch, pack=_candidate_pack())

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
        build_context_settings=_enabled_build_context_settings(),
    )

    assert result.data["fallback_reason"] is None
    assert result.data["brief"]["summary"] == (
        "Shellbrain synthesized 2 recall source(s) for this query."
    )
    telemetry = result.data["_telemetry"]["inner_agent"]
    assert telemetry["status"] == "invalid_output"
    assert telemetry["fallback_used"] is True
    assert telemetry["error_code"] == "invalid_output"


def _stub_internal_read(monkeypatch, *, pack: dict) -> None:
    """Patch build_context's internal read dependency."""

    def _fake_execute_read_memory(request, uow, **kwargs) -> ReadMemoryResult:
        del request, uow, kwargs
        return ReadMemoryResult(pack=pack)

    monkeypatch.setattr(
        "app.core.use_cases.retrieval.build_context.execute.execute_read_memory",
        _fake_execute_read_memory,
    )


def _enabled_build_context_settings() -> InnerAgentSettings:
    """Return enabled build_context settings for provider-path tests."""

    return InnerAgentSettings(
        provider="codex",
        model="gpt-5.4-mini",
        reasoning="low",
        timeout_seconds=90,
        max_private_reads=3,
        max_candidate_tokens=10_000,
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


def _candidate_pack() -> dict:
    """Return one compact candidate pack."""

    return {
        "meta": {
            "mode": "targeted",
            "limit": 2,
            "counts": {"direct": 1, "explicit_related": 0, "implicit_related": 0},
        },
        "direct": [
            {
                "memory_id": "direct-1",
                "kind": "fact",
                "text": "Startup must not own Docker mechanics.",
                "why_included": "direct_match",
            }
        ],
        "explicit_related": [],
        "implicit_related": [],
        "concepts": {
            "mode": "auto",
            "items": [
                {
                    "id": "concept-1",
                    "ref": "db-admin",
                    "name": "DB Admin",
                    "kind": "workflow",
                    "orientation": "DB lifecycle work is infrastructure.",
                }
            ],
            "missing_refs": [],
            "guidance": "Use the compact brief.",
        },
    }



def _empty_pack() -> dict:
    """Return an empty candidate pack."""

    return {
        "meta": {
            "mode": "targeted",
            "limit": 8,
            "counts": {"direct": 0, "explicit_related": 0, "implicit_related": 0},
        },
        "direct": [],
        "explicit_related": [],
        "implicit_related": [],
        "concepts": {
            "mode": "auto",
            "items": [],
            "missing_refs": [],
            "guidance": "No concepts matched.",
        },
    }
