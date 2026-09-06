"""Recall synthesis workflow for worker-facing context briefs."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import nullcontext
from typing import Any

from app.core.entities.inner_agents import InnerAgentSettings
from app.core.ports.host_apps.inner_agents import (
    InnerAgentRunRequest,
    InnerAgentRunResult,
)
from app.core.entities.settings import (
    ThresholdSettings,
    default_threshold_settings,
)
from app.core.ports.db.unit_of_work import IUnitOfWork
from app.core.ports.host_apps.inner_agents import IInnerAgentRunner
from app.core.use_cases.retrieval.deterministic_graph_recall import (
    build_deterministic_graph_pack,
    deterministic_brief_from_graph_pack,
    record_synthesis_pack_size,
    source_items_from_graph_pack,
    synthesis_pack_from_graph_pack,
)
from app.core.use_cases.retrieval.recall.request import MemoryRecallRequest
from app.core.use_cases.retrieval.recall.result import RecallMemoryResult


_DEFAULT_SETTINGS = InnerAgentSettings(
    strategy="deterministic_synthesis",
    provider="configured",
    model="configured",
    reasoning="medium",
    timeout_seconds=90,
    max_brief_tokens=500,
)


def execute_build_context(
    request: MemoryRecallRequest,
    uow: IUnitOfWork | None = None,
    *,
    uow_factory: Callable[[], IUnitOfWork] | None = None,
    threshold_settings: ThresholdSettings | None = None,
    inner_agent_runner: IInnerAgentRunner | None = None,
    build_context_settings: InnerAgentSettings | None = None,
    repo_root: str | None = None,
) -> RecallMemoryResult:
    """Build a compact worker brief."""

    threshold_settings = threshold_settings or default_threshold_settings()
    settings = build_context_settings or _DEFAULT_SETTINGS

    if uow is None and uow_factory is None:
        raise ValueError("uow or uow_factory is required for recall")
    with nullcontext(uow) if uow is not None else uow_factory() as graph_uow:
        graph_pack = build_deterministic_graph_pack(
            request=request,
            uow=graph_uow,
            threshold_settings=threshold_settings,
        )

    source_items = source_items_from_graph_pack(graph_pack)
    fallback_reason = None if source_items else "no_candidates"

    def _graph_result(
        brief: dict[str, Any],
        reason: str | None,
        inner_agent_result: InnerAgentRunResult,
    ) -> RecallMemoryResult:
        return RecallMemoryResult(
            brief=brief,
            fallback_reason=reason,
            telemetry={
                "candidate_pack": graph_pack,
                "source_items": source_items,
                "inner_agent": _with_graph_counts(
                    inner_agent_result, graph_pack=graph_pack
                ).model_dump(mode="python"),
            },
        )

    if fallback_reason == "no_candidates" or settings.strategy == "deterministic_only":
        return _graph_result(
            deterministic_brief_from_graph_pack(graph_pack),
            fallback_reason,
            InnerAgentRunResult(
                status="ok",
                provider="deterministic",
                model="none",
                reasoning="none",
                timeout_seconds=settings.timeout_seconds,
                duration_ms=int(graph_pack.get("pack_trace", {}).get("duration_ms", 0)),
            ),
        )

    synthesis_pack = synthesis_pack_from_graph_pack(graph_pack)
    record_synthesis_pack_size(
        graph_pack=graph_pack,
        synthesis_pack=synthesis_pack,
    )
    synthesis_result = _run_inner_agent(
        request=request,
        settings=settings,
        inner_agent_runner=inner_agent_runner,
        repo_root=repo_root,
        deterministic_pack=synthesis_pack,
    )
    if synthesis_result.status == "ok" and synthesis_result.brief is not None:
        return _graph_result(
            _normalize_provider_brief(synthesis_result.brief), None, synthesis_result
        )
    return _graph_result(
        deterministic_brief_from_graph_pack(graph_pack),
        fallback_reason,
        synthesis_result.model_copy(update={"fallback_used": True}),
    )


def _run_inner_agent(
    *,
    request: MemoryRecallRequest,
    settings: InnerAgentSettings,
    inner_agent_runner: IInnerAgentRunner | None,
    repo_root: str | None,
    deterministic_pack: dict[str, Any],
) -> InnerAgentRunResult:
    """Run the configured provider when available and safe to call."""

    if inner_agent_runner is None:
        return _inner_agent_result(
            settings=settings,
            status="provider_unavailable",
            fallback_used=True,
            error_code="missing_runner",
            error_message="no inner-agent runner is configured",
        )
    try:
        return inner_agent_runner.run(
            InnerAgentRunRequest(
                agent_name="build_context",
                provider=settings.provider,
                model=settings.model,
                reasoning=settings.reasoning,
                timeout_seconds=settings.timeout_seconds,
                max_brief_tokens=settings.max_brief_tokens,
                query=request.query,
                repo_root=repo_root,
                deterministic_pack=deterministic_pack,
            )
        )
    except Exception as exc:  # pragma: no cover - defensive core boundary
        return _inner_agent_result(
            settings=settings,
            status="error",
            fallback_used=True,
            error_code="runner_exception",
            error_message=str(exc),
        )


def _inner_agent_result(
    *,
    settings: InnerAgentSettings,
    status,
    fallback_used: bool,
    error_code: str | None = None,
    error_message: str | None = None,
) -> InnerAgentRunResult:
    """Build a provider-neutral result for non-provider paths."""

    return InnerAgentRunResult(
        status=status,
        provider=settings.provider,
        model=settings.model,
        reasoning=settings.reasoning,
        fallback_used=fallback_used,
        timeout_seconds=settings.timeout_seconds,
        error_code=error_code,
        error_message=error_message,
    )


def _with_graph_counts(
    result: InnerAgentRunResult, *, graph_pack: dict[str, Any]
) -> InnerAgentRunResult:
    """Attach deterministic graph traversal counters to recall telemetry."""

    concept_count = len(graph_pack.get("concepts", [])) + len(
        graph_pack.get("relation_neighbors", [])
    )
    return result.model_copy(
        update={
            "private_read_count": 0,
            "concept_expansion_count": concept_count,
        }
    )


def _normalize_provider_brief(brief: dict[str, Any]) -> dict[str, Any]:
    """Ensure provider output keeps the stable worker-facing brief shape."""

    return {
        "summary": str(brief.get("summary") or "").strip()
        or "Shellbrain synthesized relevant recall context.",
        "constraints": _string_list(brief.get("constraints")),
        "known_traps": _string_list(brief.get("known_traps")),
        "prior_cases": _string_list(brief.get("prior_cases")),
        "concept_orientation": _string_list(brief.get("concept_orientation")),
        "anchors": _string_list(brief.get("anchors")),
        "conflicts": _string_list(brief.get("conflicts")),
        "gaps": _string_list(brief.get("gaps")),
        "next_checks": _string_list(brief.get("next_checks")),
    }


def _string_list(value: Any) -> list[str]:
    """Coerce provider brief sections into stable string lists."""

    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]
