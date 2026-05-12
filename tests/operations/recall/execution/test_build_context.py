"""Unit coverage for read-only build_context recall synthesis."""

from __future__ import annotations

import pytest

from app.core.errors import DomainValidationError, ErrorCode
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
        )


class _ExpansionRunner:
    """Fake provider that requests one private concept expansion before synthesis."""

    def __init__(self) -> None:
        self.requests = []

    def run(self, request):
        self.requests.append(request)
        if len(self.requests) == 1:
            return InnerAgentRunResult(
                status="ok",
                provider=request.provider,
                model=request.model,
                reasoning=request.reasoning,
                requested_expansions=[
                    {
                        "read_payload": {
                            "query": request.query,
                            "expand": {
                                "concepts": {
                                    "mode": "explicit",
                                    "refs": ["db-admin"],
                                    "facets": ["groundings"],
                                }
                            },
                        }
                    }
                ],
            )
        return InnerAgentRunResult(
            status="ok",
            provider=request.provider,
            model=request.model,
            reasoning=request.reasoning,
            brief={
                "summary": "Expanded concept context points to admin migrations.",
                "constraints": [],
                "known_traps": [],
                "prior_cases": [],
                "concept_orientation": ["Use DB admin grounding details."],
                "anchors": ["app/infrastructure/db/admin/migrations.py"],
                "gaps": [],
            },
        )


def test_build_context_uses_fake_provider_for_structured_synthesis(monkeypatch) -> None:
    """build_context should accept provider synthesis through a core port."""

    _stub_internal_read(monkeypatch, pack=_candidate_pack())
    runner = _FakeRunner()

    result = execute_build_context(
        MemoryRecallRequest.model_validate(
            {
                "op": "recall",
                "repo_id": "repo-a",
                "query": "migration timeout",
                "current_problem": {"goal": "fix migration"},
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
    assert runner.request.current_problem == {
        "goal": "fix migration",
        "surface": None,
        "obstacle": None,
        "hypothesis": None,
    }


def test_build_context_executes_bounded_private_expansion_requests(monkeypatch) -> None:
    """build_context should execute approved private reads before final synthesis."""

    read_requests = []

    def _fake_execute_read_memory(request, uow, **kwargs) -> ReadMemoryResult:
        del uow, kwargs
        read_requests.append(request)
        pack = _candidate_pack() if len(read_requests) == 1 else _expansion_pack()
        return ReadMemoryResult(pack=pack)

    monkeypatch.setattr(
        "app.core.use_cases.retrieval.build_context.execute.execute_read_memory",
        _fake_execute_read_memory,
    )
    runner = _ExpansionRunner()

    result = execute_build_context(
        MemoryRecallRequest.model_validate(
            {"op": "recall", "repo_id": "repo-a", "query": "migration timeout"}
        ),
        object(),
        inner_agent_runner=runner,
        build_context_settings=_enabled_build_context_settings(),
    )

    assert len(read_requests) == 2
    assert len(runner.requests) == 2
    assert "private_expansions" in runner.requests[1].candidate_context
    assert result.data["brief"]["summary"] == (
        "Expanded concept context points to admin migrations."
    )
    telemetry = result.data["_telemetry"]["inner_agent"]
    assert telemetry["private_read_count"] == 1
    assert telemetry["concept_expansion_count"] == 1
    assert any(
        source["input_section"].startswith("private_expansion_1")
        for source in result.data["_telemetry"]["source_items"]
    )


def test_build_context_truthfully_reports_no_context(monkeypatch) -> None:
    """build_context should return a no-context brief when retrieval finds nothing."""

    _stub_internal_read(monkeypatch, pack=_empty_pack())

    result = execute_build_context(
        MemoryRecallRequest.model_validate(
            {"op": "recall", "repo_id": "repo-a", "query": "nothing"}
        ),
        object(),
    )

    assert result.data["fallback_reason"] == "no_candidates"
    assert result.data["brief"]["sources"] == []
    assert "no relevant memories" in result.data["brief"]["gaps"][0]


def test_build_context_error_fallback_returns_structured_provider_error(
    monkeypatch,
) -> None:
    """build_context should honor fallback=error for provider failures."""

    _stub_internal_read(monkeypatch, pack=_candidate_pack())

    with pytest.raises(DomainValidationError) as exc_info:
        execute_build_context(
            MemoryRecallRequest.model_validate(
                {"op": "recall", "repo_id": "repo-a", "query": "migration timeout"}
            ),
            object(),
            inner_agent_runner=None,
            build_context_settings=_enabled_build_context_settings(fallback="error"),
        )

    assert exc_info.value.errors[0].code == ErrorCode.INNER_AGENT_ERROR
    assert exc_info.value.errors[0].field == "inner_agent"


def _stub_internal_read(monkeypatch, *, pack: dict) -> None:
    """Patch build_context's internal read dependency."""

    def _fake_execute_read_memory(request, uow, **kwargs) -> ReadMemoryResult:
        del request, uow, kwargs
        return ReadMemoryResult(pack=pack)

    monkeypatch.setattr(
        "app.core.use_cases.retrieval.build_context.execute.execute_read_memory",
        _fake_execute_read_memory,
    )


def _enabled_build_context_settings(
    *, fallback: str = "deterministic"
) -> InnerAgentSettings:
    """Return enabled build_context settings for provider-path tests."""

    return InnerAgentSettings(
        enabled=True,
        provider="codex",
        model="gpt-5.4-mini",
        reasoning="low",
        timeout_seconds=90,
        max_private_reads=3,
        max_candidate_tokens=10_000,
        max_brief_tokens=1_800,
        fallback=fallback,
    )


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


def _expansion_pack() -> dict:
    """Return one private concept expansion pack."""

    return {
        "meta": {
            "mode": "targeted",
            "limit": 2,
            "counts": {"direct": 1, "explicit_related": 0, "implicit_related": 0},
        },
        "direct": [
            {
                "memory_id": "expanded-1",
                "kind": "solution",
                "text": "Admin migrations need bounded lock acquisition.",
                "why_included": "concept_grounding",
            }
        ],
        "explicit_related": [],
        "implicit_related": [],
        "concepts": {
            "mode": "explicit",
            "items": [
                {
                    "id": "concept-1",
                    "ref": "db-admin",
                    "name": "DB Admin",
                    "kind": "workflow",
                    "orientation": "Admin migrations are lifecycle operations.",
                }
            ],
            "missing_refs": [],
            "guidance": "Grounding details included.",
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
