"""Recall synthesis workflow for worker-facing context briefs."""

from __future__ import annotations

from typing import Any

from app.core.entities.inner_agents import InnerAgentSettings
from app.core.ports.host_apps.inner_agents import (
    InnerAgentRunRequest,
    InnerAgentRunResult,
)
from app.core.entities.settings import (
    ReadPolicySettings,
    ThresholdSettings,
    default_read_policy_settings,
    default_threshold_settings,
)
from app.core.ports.db.unit_of_work import IUnitOfWork
from app.core.ports.host_apps.inner_agents import IInnerAgentRunner
from app.core.use_cases.retrieval.read import execute_read_memory
from app.core.use_cases.retrieval.read.request import MemoryReadRequest
from app.core.use_cases.retrieval.recall.request import MemoryRecallRequest
from app.core.use_cases.retrieval.recall.result import RecallMemoryResult


_DEFAULT_SETTINGS = InnerAgentSettings(
    provider="codex",
    model="gpt-5.4-mini",
    reasoning="low",
    timeout_seconds=90,
    max_private_reads=0,
    max_candidate_tokens=10_000,
    max_brief_tokens=1_800,
)


def execute_build_context(
    request: MemoryRecallRequest,
    uow: IUnitOfWork,
    *,
    read_settings: ReadPolicySettings | None = None,
    threshold_settings: ThresholdSettings | None = None,
    inner_agent_runner: IInnerAgentRunner | None = None,
    build_context_settings: InnerAgentSettings | None = None,
    repo_root: str | None = None,
) -> RecallMemoryResult:
    """Build a compact worker brief."""

    read_settings = read_settings or default_read_policy_settings()
    threshold_settings = threshold_settings or default_threshold_settings()
    settings = build_context_settings or _DEFAULT_SETTINGS

    inner_agent_result = _run_inner_agent(
        request=request,
        settings=settings,
        inner_agent_runner=inner_agent_runner,
        repo_root=repo_root,
    )
    if inner_agent_result.status == "ok" and inner_agent_result.brief is not None:
        return _provider_result(
            inner_agent_result=inner_agent_result,
        )

    return _deterministic_result(
        request=request,
        uow=uow,
        read_settings=read_settings,
        threshold_settings=threshold_settings,
        inner_agent_result=inner_agent_result.model_copy(update={"fallback_used": True}),
    )


def _read_request_from_recall(request: MemoryRecallRequest) -> MemoryReadRequest:
    """Build the targeted read request used as private candidate context."""

    return MemoryReadRequest(
        repo_id=request.repo_id,
        mode="targeted",
        query=request.query,
        limit=request.limit,
    )


def _run_inner_agent(
    *,
    request: MemoryRecallRequest,
    settings: InnerAgentSettings,
    inner_agent_runner: IInnerAgentRunner | None,
    repo_root: str | None,
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
            )
        )
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
) -> InnerAgentRunRequest:
    """Build one provider request for autonomous read-only recall."""

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


def _deterministic_result(
    *,
    request: MemoryRecallRequest,
    uow: IUnitOfWork,
    read_settings: ReadPolicySettings,
    threshold_settings: ThresholdSettings,
    inner_agent_result: InnerAgentRunResult,
) -> RecallMemoryResult:
    """Build the deterministic fallback brief from internal read candidates."""

    read_result = execute_read_memory(
        _read_request_from_recall(request),
        uow,
        read_settings=read_settings,
        threshold_settings=threshold_settings,
    )
    pack = read_result.data.get("pack", {})
    if not isinstance(pack, dict):
        pack = {}
    source_items = _source_items_from_pack(pack)
    fallback_reason = None if source_items else "no_candidates"
    return RecallMemoryResult(
        brief=_deterministic_brief(
            request=request,
            pack=pack,
            source_items=source_items,
            fallback_reason=fallback_reason,
        ),
        fallback_reason=fallback_reason,
        telemetry={
            "candidate_pack": pack,
            "source_items": source_items,
            "inner_agent": inner_agent_result.model_dump(mode="python"),
        },
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


def _deterministic_brief(
    *,
    request: MemoryRecallRequest,
    pack: dict[str, Any],
    source_items: list[dict[str, Any]],
    fallback_reason: str | None,
) -> dict[str, Any]:
    """Create a compact deterministic brief from read-pack candidates."""

    if fallback_reason == "no_candidates":
        return _no_context_brief()

    memory_sections = _memory_sections(pack)
    concept_items = _concept_items(pack)
    return {
        "summary": _summary_text(
            source_count=len(source_items), fallback_reason=fallback_reason
        ),
        "constraints": _memory_texts_by_kind(
            memory_sections, {"fact", "preference", "change"}
        ),
        "known_traps": _memory_texts_by_kind(
            memory_sections, {"problem", "failed_tactic"}
        ),
        "prior_cases": _memory_texts_by_kind(memory_sections, {"solution"}),
        "concept_orientation": [
            _truncate(
                f"{item.get('name') or item.get('ref')}: {item.get('orientation') or ''}",
                280,
            )
            for item in concept_items
            if item.get("orientation") or item.get("name") or item.get("ref")
        ],
        "anchors": _anchors(memory_sections=memory_sections, concept_items=concept_items),
        "gaps": [],
        "sources": [
            {
                "kind": item["source_kind"],
                "id": item["source_id"],
                "section": item["input_section"],
            }
            for item in source_items
            if item["output_section"] is not None
        ],
    }


def _no_context_brief() -> dict[str, Any]:
    """Return the truthful no-context brief shape."""

    return {
        "summary": "No stored Shellbrain context matched this recall query.",
        "constraints": [],
        "known_traps": [],
        "prior_cases": [],
        "concept_orientation": [],
        "anchors": [],
        "gaps": ["Shellbrain has no relevant memories or concepts for this query."],
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
        "gaps": _string_list(brief.get("gaps")),
        "sources": brief.get("sources")
        if isinstance(brief.get("sources"), list)
        else deterministic_sources,
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
    return [str(item).strip() for item in value if str(item).strip()]


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


def _source_items_from_pack(pack: dict[str, Any]) -> list[dict[str, Any]]:
    """Build stable candidate provenance rows from one read pack."""

    items: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    _append_source_items_from_single_pack(
        pack,
        input_prefix="",
        items=items,
        seen=seen,
        next_ordinal=1,
    )
    return items


def _append_source_items_from_single_pack(
    pack: dict[str, Any],
    *,
    input_prefix: str,
    items: list[dict[str, Any]],
    seen: set[tuple[str, str, str]],
    next_ordinal: int,
) -> int:
    """Append provenance rows for one context pack."""

    ordinal = next_ordinal
    for input_section, bucket_name in (
        ("direct", "direct"),
        ("explicit_related", "explicit_related"),
        ("implicit_related", "implicit_related"),
    ):
        bucket = pack.get(bucket_name)
        if not isinstance(bucket, list):
            continue
        for item in bucket:
            if not isinstance(item, dict) or "memory_id" not in item:
                continue
            source_id = str(item["memory_id"])
            section = _prefixed_section(input_prefix, input_section)
            key = ("memory", source_id, section)
            if key in seen:
                continue
            seen.add(key)
            items.append(
                {
                    "ordinal": ordinal,
                    "source_kind": "memory",
                    "source_id": source_id,
                    "input_section": section,
                    "output_section": "sources",
                }
            )
            ordinal += 1

    concepts = pack.get("concepts")
    if isinstance(concepts, dict) and isinstance(concepts.get("items"), list):
        for item in concepts["items"]:
            if not isinstance(item, dict):
                continue
            source_id = item.get("id") or item.get("ref")
            if source_id is None:
                continue
            section = _prefixed_section(input_prefix, "concept_orientation")
            key = ("concept", str(source_id), section)
            if key in seen:
                continue
            seen.add(key)
            items.append(
                {
                    "ordinal": ordinal,
                    "source_kind": "concept",
                    "source_id": str(source_id),
                    "input_section": section,
                    "output_section": "sources",
                }
            )
            ordinal += 1
    return ordinal


def _prefixed_section(prefix: str, section: str) -> str:
    """Render a source section name with optional provenance prefix."""

    if not prefix:
        return section
    return f"{prefix}.{section}"


def _memory_sections(pack: dict[str, Any]) -> list[dict[str, Any]]:
    """Return memory candidates in display order."""

    items: list[dict[str, Any]] = []
    for section in ("direct", "explicit_related", "implicit_related"):
        bucket = pack.get(section)
        if not isinstance(bucket, list):
            continue
        for item in bucket:
            if isinstance(item, dict):
                items.append({**item, "_section": _prefixed_section("", section)})
    return items


def _concept_items(pack: dict[str, Any]) -> list[dict[str, Any]]:
    """Return concept candidates in display order."""

    concepts = pack.get("concepts")
    if not isinstance(concepts, dict) or not isinstance(concepts.get("items"), list):
        return []
    return [
        {**item, "_section": _prefixed_section("", "concept_orientation")}
        for item in concepts["items"]
        if isinstance(item, dict)
    ]


def _memory_texts_by_kind(
    memory_sections: list[dict[str, Any]], kinds: set[str]
) -> list[str]:
    """Render candidate memories by kind for deterministic synthesis sections."""

    rendered: list[str] = []
    for item in memory_sections:
        kind = str(item.get("kind") or "")
        text = str(item.get("text") or "").strip()
        if kind not in kinds or not text:
            continue
        rendered.append(_truncate(f"{kind}: {text}", 280))
    return rendered[:5]


def _anchors(
    *, memory_sections: list[dict[str, Any]], concept_items: list[dict[str, Any]]
) -> list[str]:
    """Build compact actionable anchors from memory and concept provenance."""

    anchors: list[str] = []
    for item in memory_sections:
        memory_id = item.get("memory_id")
        if memory_id is None:
            continue
        section = item.get("_section") or "memory"
        anchors.append(f"memory:{memory_id} ({section})")
    for item in concept_items:
        concept_ref = item.get("ref") or item.get("id")
        if concept_ref is not None:
            anchors.append(f"concept:{concept_ref}")
    return anchors[:12]


def _summary_text(*, source_count: int, fallback_reason: str | None) -> str:
    """Return deterministic recall summary text."""

    if fallback_reason == "no_candidates":
        return "No stored Shellbrain context matched this recall query."
    return f"Shellbrain synthesized {source_count} recall source(s) for this query."


def _truncate(value: str, max_chars: int) -> str:
    """Return a compact single-line representation."""

    collapsed = " ".join(value.split())
    if len(collapsed) <= max_chars:
        return collapsed
    return f"{collapsed[: max_chars - 3].rstrip()}..."
