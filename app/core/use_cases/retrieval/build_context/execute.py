"""Recall synthesis workflow for worker-facing context briefs."""

from __future__ import annotations

from collections.abc import Callable
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
    source_items_from_graph_pack,
)
from app.core.use_cases.retrieval.recall.request import MemoryRecallRequest
from app.core.use_cases.retrieval.recall.result import RecallMemoryResult


_DEFAULT_SETTINGS = InnerAgentSettings(
    strategy="deterministic_synthesis",
    provider="configured",
    model="configured",
    reasoning="low",
    timeout_seconds=90,
    max_private_reads=0,
    max_candidate_tokens=10_000,
    max_brief_tokens=1_800,
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

    if settings.strategy != "autonomous":
        return _deterministic_graph_result_with_uow(
            request=request,
            uow=uow,
            uow_factory=uow_factory,
            threshold_settings=threshold_settings,
            settings=settings,
            inner_agent_runner=inner_agent_runner,
            repo_root=repo_root,
        )

    inner_agent_result = _run_inner_agent(
        request=request,
        settings=settings,
        inner_agent_runner=inner_agent_runner,
        repo_root=repo_root,
    )
    if inner_agent_result.status == "ok" and inner_agent_result.brief is not None:
        trace_state = _provider_trace_state(inner_agent_result)
        if trace_state == "has_sources":
            return _provider_result(
                inner_agent_result=inner_agent_result,
            )
        if trace_state == "no_context":
            return _provider_no_context_result(inner_agent_result=inner_agent_result)
        inner_agent_result = inner_agent_result.model_copy(
            update={
                "status": "invalid_output",
                "fallback_used": True,
                "error_code": trace_state,
                "error_message": _provider_trace_error_message(trace_state),
            }
        )

    return _autonomous_fallback_graph_result_with_uow(
        request=request,
        uow=uow,
        uow_factory=uow_factory,
        threshold_settings=threshold_settings,
        inner_agent_result=inner_agent_result.model_copy(update={"fallback_used": True}),
        settings=settings,
        inner_agent_runner=inner_agent_runner,
        repo_root=repo_root,
    )


def _run_inner_agent(
    *,
    request: MemoryRecallRequest,
    settings: InnerAgentSettings,
    inner_agent_runner: IInnerAgentRunner | None,
    repo_root: str | None,
    synthesis_only: bool = False,
    deterministic_pack: dict[str, Any] | None = None,
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
        result = inner_agent_runner.run(
            _inner_agent_request(
                request=request,
                settings=settings,
                repo_root=repo_root,
                synthesis_only=synthesis_only,
                deterministic_pack=deterministic_pack,
            )
        )
        if synthesis_only:
            return result
        return _with_read_trace_counts(result)
    except Exception as exc:  # pragma: no cover - defensive core boundary
        return _inner_agent_result(
            settings=settings,
            status="error",
            fallback_used=True,
            error_code="runner_exception",
            error_message=str(exc),
        )


def _inner_agent_request(
    *,
    request: MemoryRecallRequest,
    settings: InnerAgentSettings,
    repo_root: str | None,
    synthesis_only: bool = False,
    deterministic_pack: dict[str, Any] | None = None,
) -> InnerAgentRunRequest:
    """Build one provider request for autonomous or synthesis-only recall."""

    return InnerAgentRunRequest(
        agent_name="build_context",
        provider=settings.provider,
        model=settings.model,
        reasoning=settings.reasoning,
        timeout_seconds=settings.timeout_seconds,
        max_private_reads=settings.max_private_reads,
        max_candidate_tokens=settings.max_candidate_tokens,
        max_brief_tokens=settings.max_brief_tokens,
        query=request.query,
        current_problem=request.current_problem.model_dump(mode="python"),
        repo_root=repo_root,
        synthesis_only=synthesis_only,
        deterministic_pack=deterministic_pack,
    )


def _provider_result(
    *,
    inner_agent_result: InnerAgentRunResult,
) -> RecallMemoryResult:
    """Convert one successful provider result into the public recall result."""

    read_trace = _read_trace(inner_agent_result)
    source_items = _source_items_from_read_trace(read_trace)
    brief = _normalize_provider_brief(
        inner_agent_result.brief or {},
        deterministic_sources=_sources_from_source_items(source_items),
    )
    fallback_reason = (
        "no_candidates"
        if not source_items and _read_trace_no_context_reason(read_trace)
        else None
    )
    return RecallMemoryResult(
        brief=brief,
        fallback_reason=fallback_reason,
        telemetry={
            "candidate_pack": {"read_trace": read_trace},
            "source_items": source_items,
            "inner_agent": _with_read_trace_counts(inner_agent_result).model_dump(
                mode="python"
            ),
        },
    )


def _provider_no_context_result(
    *,
    inner_agent_result: InnerAgentRunResult,
) -> RecallMemoryResult:
    """Convert an explicit provider no-context trace into the public result."""

    read_trace = _read_trace(inner_agent_result)
    no_context_result = inner_agent_result.model_copy(
        update={"status": "no_context"}
    )
    return RecallMemoryResult(
        brief=_no_context_brief(),
        fallback_reason="no_candidates",
        telemetry={
            "candidate_pack": {"read_trace": read_trace},
            "source_items": [],
            "inner_agent": _with_read_trace_counts(no_context_result).model_dump(
                mode="python"
            ),
        },
    )


def _deterministic_graph_result(
    *,
    request: MemoryRecallRequest,
    uow: IUnitOfWork,
    threshold_settings: ThresholdSettings,
    settings: InnerAgentSettings,
    inner_agent_runner: IInnerAgentRunner | None,
    repo_root: str | None,
    prior_inner_agent_result: InnerAgentRunResult | None = None,
) -> RecallMemoryResult:
    """Build graph-first recall and optionally synthesize it once."""

    graph_pack = build_deterministic_graph_pack(
        request=request,
        uow=uow,
        threshold_settings=threshold_settings,
    )
    source_items = source_items_from_graph_pack(graph_pack)
    fallback_reason = None if source_items else "no_candidates"
    if fallback_reason == "no_candidates" or settings.strategy == "deterministic_only":
        inner_agent_result = prior_inner_agent_result or _deterministic_strategy_result(
            settings=settings,
            graph_pack=graph_pack,
            fallback_used=False,
        )
        return RecallMemoryResult(
            brief=deterministic_brief_from_graph_pack(graph_pack),
            fallback_reason=fallback_reason,
            telemetry={
                "candidate_pack": graph_pack,
                "source_items": source_items,
                "inner_agent": _with_graph_counts(
                    inner_agent_result, graph_pack=graph_pack
                ).model_dump(mode="python"),
            },
        )

    synthesis_result = _run_inner_agent(
        request=request,
        settings=settings,
        inner_agent_runner=inner_agent_runner,
        repo_root=repo_root,
        synthesis_only=True,
        deterministic_pack=graph_pack,
    )
    if synthesis_result.status == "ok" and synthesis_result.brief is not None:
        return RecallMemoryResult(
            brief=_normalize_provider_brief(
                synthesis_result.brief,
                deterministic_sources=_sources_from_source_items(source_items),
            ),
            fallback_reason=None,
            telemetry={
                "candidate_pack": graph_pack,
                "source_items": source_items,
                "inner_agent": _with_graph_counts(
                    synthesis_result, graph_pack=graph_pack
                ).model_dump(mode="python"),
            },
        )

    fallback_result = synthesis_result.model_copy(
        update={"fallback_used": True}
    )
    return RecallMemoryResult(
        brief=deterministic_brief_from_graph_pack(graph_pack),
        fallback_reason=fallback_reason,
        telemetry={
            "candidate_pack": graph_pack,
            "source_items": source_items,
            "inner_agent": _with_graph_counts(
                fallback_result, graph_pack=graph_pack
            ).model_dump(mode="python"),
        },
    )


def _deterministic_graph_result_with_uow(
    *,
    request: MemoryRecallRequest,
    uow: IUnitOfWork | None,
    uow_factory: Callable[[], IUnitOfWork] | None,
    threshold_settings: ThresholdSettings,
    settings: InnerAgentSettings,
    inner_agent_runner: IInnerAgentRunner | None,
    repo_root: str | None,
    prior_inner_agent_result: InnerAgentRunResult | None = None,
) -> RecallMemoryResult:
    """Open a DB transaction for graph-first recall when needed."""

    if uow is not None:
        return _deterministic_graph_result(
            request=request,
            uow=uow,
            threshold_settings=threshold_settings,
            settings=settings,
            inner_agent_runner=inner_agent_runner,
            repo_root=repo_root,
            prior_inner_agent_result=prior_inner_agent_result,
        )
    if uow_factory is None:
        raise ValueError("uow or uow_factory is required for deterministic recall")
    with uow_factory() as graph_uow:
        return _deterministic_graph_result(
            request=request,
            uow=graph_uow,
            threshold_settings=threshold_settings,
            settings=settings,
            inner_agent_runner=inner_agent_runner,
            repo_root=repo_root,
            prior_inner_agent_result=prior_inner_agent_result,
        )


def _autonomous_fallback_graph_result_with_uow(
    *,
    request: MemoryRecallRequest,
    uow: IUnitOfWork | None,
    uow_factory: Callable[[], IUnitOfWork] | None,
    threshold_settings: ThresholdSettings,
    inner_agent_result: InnerAgentRunResult,
    settings: InnerAgentSettings,
    inner_agent_runner: IInnerAgentRunner | None,
    repo_root: str | None,
) -> RecallMemoryResult:
    """Build graph-first fallback after an autonomous provider fails validation."""

    return _deterministic_graph_result_with_uow(
        request=request,
        uow=uow,
        uow_factory=uow_factory,
        threshold_settings=threshold_settings,
        settings=settings,
        inner_agent_runner=inner_agent_runner,
        repo_root=repo_root,
        prior_inner_agent_result=inner_agent_result,
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


def _deterministic_strategy_result(
    *, settings: InnerAgentSettings, graph_pack: dict[str, Any], fallback_used: bool
) -> InnerAgentRunResult:
    """Return telemetry for deterministic-only recall paths."""

    return InnerAgentRunResult(
        status="ok",
        provider="deterministic",
        model="none",
        reasoning="none",
        fallback_used=fallback_used,
        timeout_seconds=settings.timeout_seconds,
        duration_ms=int(
            graph_pack.get("pack_trace", {}).get("duration_ms", 0)
        ),
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


def _no_context_brief() -> dict[str, Any]:
    """Return the truthful no-context brief shape."""

    return {
        "summary": "No stored Shellbrain context matched this recall query.",
        "constraints": [],
        "known_traps": [],
        "prior_cases": [],
        "concept_orientation": [],
        "anchors": [],
        "conflicts": [],
        "gaps": ["Shellbrain has no relevant memories or concepts for this query."],
        "next_checks": [],
        "sources": [],
    }


def _normalize_provider_brief(
    brief: dict[str, Any], *, deterministic_sources: list[dict[str, Any]]
) -> dict[str, Any]:
    """Ensure provider output keeps the stable worker-facing brief shape."""

    normalized = {
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
        "sources": deterministic_sources,
    }
    return normalized


def _string_list(value: Any) -> list[str]:
    """Coerce provider brief sections into stable string lists."""

    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _read_trace(result: InnerAgentRunResult) -> dict[str, Any]:
    """Return the provider's best-effort read trace."""

    return result.read_trace if isinstance(result.read_trace, dict) else {}


def _with_read_trace_counts(result: InnerAgentRunResult) -> InnerAgentRunResult:
    """Derive provider telemetry counters from the returned read trace."""

    read_trace = _read_trace(result)
    return result.model_copy(
        update={
            "private_read_count": _private_read_count_from_trace(read_trace),
            "concept_expansion_count": _concept_expansion_count_from_trace(read_trace),
        }
    )


def _provider_trace_state(result: InnerAgentRunResult) -> str:
    """Classify whether a successful provider result has usable provenance."""

    read_trace = _read_trace(result)
    if not read_trace:
        return "missing_read_trace"
    malformed_reason = _malformed_read_trace_reason(read_trace)
    if malformed_reason is not None:
        return malformed_reason
    if _source_items_from_read_trace(read_trace):
        return "has_sources"
    if _read_trace_no_context_reason(read_trace):
        return "no_context"
    return "missing_read_trace_sources"


def _provider_trace_error_message(trace_state: str) -> str:
    """Return a stable provider-trace validation error message."""

    return {
        "missing_read_trace": "provider returned a brief without read_trace provenance",
        "missing_read_trace_sources": (
            "provider returned a brief without source_ids, concept_refs, "
            "or an explicit no_context_reason"
        ),
        "malformed_read_trace": "provider returned malformed read_trace provenance",
    }.get(trace_state, trace_state)


def _malformed_read_trace_reason(read_trace: dict[str, Any]) -> str | None:
    """Return a validation error code when provider provenance is malformed."""

    for key in ("source_ids", "concept_refs"):
        if key in read_trace and _trace_string_list(read_trace[key]) is None:
            return "malformed_read_trace"
    if "no_context_reason" in read_trace and not isinstance(
        read_trace["no_context_reason"], str
    ):
        return "malformed_read_trace"

    commands = read_trace.get("commands")
    if commands is not None and not isinstance(commands, list):
        return "malformed_read_trace"
    if not isinstance(commands, list):
        return None
    for command in commands:
        if not isinstance(command, str) and not isinstance(command, dict):
            return "malformed_read_trace"
        if isinstance(command, dict):
            for key in ("source_ids", "concept_refs"):
                if key in command and _trace_string_list(command[key]) is None:
                    return "malformed_read_trace"
    return None


def _private_read_count_from_trace(read_trace: dict[str, Any]) -> int:
    """Count read-only Shellbrain commands the provider reports using."""

    commands = read_trace.get("commands")
    if not isinstance(commands, list):
        return 0
    return sum(1 for item in commands if _trace_command_text(item).startswith("shellbrain "))


def _concept_expansion_count_from_trace(read_trace: dict[str, Any]) -> int:
    """Count concept detail refs reported by the provider."""

    refs = set(_trace_strings(read_trace, "concept_refs"))
    command_expansions_without_ref = 0
    commands = read_trace.get("commands")
    if isinstance(commands, list):
        for item in commands:
            command_refs = _trace_strings(item, "concept_refs")
            refs.update(command_refs)
            command = _trace_command_text(item)
            if not command_refs and ("concept show" in command or '"expand"' in command):
                command_expansions_without_ref += 1
    return len({ref for ref in refs if ref}) + command_expansions_without_ref


def _source_items_from_read_trace(read_trace: dict[str, Any]) -> list[dict[str, Any]]:
    """Build recall provenance rows from an autonomous provider read trace."""

    items: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    source_ids = _trace_strings(read_trace, "source_ids")
    concept_refs = _trace_strings(read_trace, "concept_refs")
    commands = read_trace.get("commands")
    if isinstance(commands, list):
        for command in commands:
            source_ids.extend(_trace_strings(command, "source_ids"))
            concept_refs.extend(_trace_strings(command, "concept_refs"))

    ordinal = 1
    for source_id in source_ids:
        source_kind = _source_kind_from_trace_id(source_id)
        key = (source_kind, source_id)
        if key in seen:
            continue
        seen.add(key)
        items.append(
            {
                "ordinal": ordinal,
                "source_kind": source_kind,
                "source_id": source_id,
                "input_section": "inner_agent.read_trace",
                "output_section": "sources",
            }
        )
        ordinal += 1
    for concept_ref in concept_refs:
        key = ("concept", concept_ref)
        if key in seen:
            continue
        seen.add(key)
        items.append(
            {
                "ordinal": ordinal,
                "source_kind": "concept",
                "source_id": concept_ref,
                "input_section": "inner_agent.read_trace",
                "output_section": "sources",
            }
        )
        ordinal += 1
    return items


def _sources_from_source_items(
    source_items: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Render brief sources from telemetry provenance rows."""

    return [
        {
            "kind": item["source_kind"],
            "id": item["source_id"],
            "section": item["input_section"],
        }
        for item in source_items
        if item.get("output_section") is not None
    ]


def _read_trace_no_context_reason(read_trace: dict[str, Any]) -> str | None:
    """Return an explicit no-context reason from provider trace, when present."""

    reason = read_trace.get("no_context_reason")
    if not isinstance(reason, str):
        return None
    text = reason.strip()
    return text or None


def _trace_strings(container: Any, key: str) -> list[str]:
    """Return non-empty string values from one trace field."""

    if not isinstance(container, dict):
        return []
    value = container.get(key)
    strings = _trace_string_list(value)
    return [] if strings is None else strings


def _trace_string_list(value: Any) -> list[str] | None:
    """Return non-empty strings from a trace list, or None when malformed."""

    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return None
    strings: list[str] = []
    for item in value:
        if not isinstance(item, str):
            return None
        text = item.strip()
        if text:
            strings.append(text)
    return strings


def _trace_command_text(item: Any) -> str:
    """Return one normalized command string from a trace command item."""

    if isinstance(item, str):
        return item.strip()
    if not isinstance(item, dict):
        return ""
    value = item.get("command")
    if isinstance(value, list):
        return " ".join(str(part) for part in value).strip()
    return str(value or "").strip()


def _source_kind_from_trace_id(source_id: str) -> str:
    """Infer a conservative source kind from a provider-reported id."""

    if source_id.startswith("evt-") or source_id.startswith("episode"):
        return "episode_event"
    if source_id.startswith("concept:"):
        return "concept"
    return "memory"
