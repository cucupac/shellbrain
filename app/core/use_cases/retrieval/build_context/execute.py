"""Read-only recall synthesis workflow for worker-facing context briefs."""

from __future__ import annotations

from typing import Any

from app.core.errors import DomainValidationError, ErrorCode, ErrorDetail
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


_DEFAULT_DISABLED_SETTINGS = InnerAgentSettings(
    enabled=False,
    provider="codex",
    model="gpt-5.4-mini",
    reasoning="low",
    timeout_seconds=90,
    max_private_reads=0,
    max_candidate_tokens=10_000,
    max_brief_tokens=1_800,
    fallback="deterministic",
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
    """Build a compact worker recall brief without mutating durable knowledge."""

    read_settings = read_settings or default_read_policy_settings()
    threshold_settings = threshold_settings or default_threshold_settings()
    settings = build_context_settings or _DEFAULT_DISABLED_SETTINGS
    read_result = execute_read_memory(
        _read_request_from_recall(request),
        uow,
        read_settings=read_settings,
        threshold_settings=threshold_settings,
    )
    pack = read_result.data.get("pack", {})
    if not isinstance(pack, dict):
        pack = {}

    initial_source_items = _source_items_from_pack(pack)
    inner_agent_result, pack = _run_inner_agent(
        request=request,
        pack=pack,
        source_items=initial_source_items,
        settings=settings,
        inner_agent_runner=inner_agent_runner,
        repo_root=repo_root,
        uow=uow,
        read_settings=read_settings,
        threshold_settings=threshold_settings,
    )
    source_items = _source_items_from_pack(pack)
    fallback_reason = None if source_items else "no_candidates"
    deterministic_brief = _deterministic_brief(
        request=request,
        pack=pack,
        source_items=source_items,
        fallback_reason=fallback_reason,
    )

    brief = deterministic_brief
    if inner_agent_result.status == "ok" and inner_agent_result.brief is not None:
        brief = _normalize_provider_brief(
            inner_agent_result.brief,
            deterministic_sources=deterministic_brief["sources"],
        )
        fallback_reason = None if source_items else "no_candidates"
    elif inner_agent_result.status == "no_context" and settings.fallback == "no_context":
        brief = _no_context_brief()
        fallback_reason = "no_candidates"
    elif inner_agent_result.status != "no_context" and settings.fallback == "error":
        raise DomainValidationError(
            [
                ErrorDetail(
                    code=ErrorCode.INNER_AGENT_ERROR,
                    message=_inner_agent_error_message(inner_agent_result),
                    field="inner_agent",
                )
            ]
        )
    else:
        inner_agent_result = inner_agent_result.model_copy(update={"fallback_used": True})

    return RecallMemoryResult(
        brief=brief,
        fallback_reason=fallback_reason,
        telemetry={
            "candidate_pack": pack,
            "source_items": source_items,
            "inner_agent": inner_agent_result.model_dump(mode="python"),
        },
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
    pack: dict[str, Any],
    source_items: list[dict[str, Any]],
    settings: InnerAgentSettings,
    inner_agent_runner: IInnerAgentRunner | None,
    repo_root: str | None,
    uow: IUnitOfWork,
    read_settings: ReadPolicySettings,
    threshold_settings: ThresholdSettings,
) -> tuple[InnerAgentRunResult, dict[str, Any]]:
    """Run the configured provider when available and safe to call."""

    if not settings.enabled:
        return (
            _inner_agent_result(
                settings=settings,
                status="disabled",
                fallback_used=True,
                error_code="disabled",
                error_message="build_context inner agent is disabled",
            ),
            pack,
        )
    if not source_items:
        return (
            _inner_agent_result(
                settings=settings,
                status="no_context",
                fallback_used=True,
                error_code="no_context",
                error_message="no relevant memories or concepts matched the query",
            ),
            pack,
        )
    if inner_agent_runner is None:
        return (
            _inner_agent_result(
                settings=settings,
                status="provider_unavailable",
                fallback_used=True,
                error_code="missing_runner",
                error_message="no inner-agent runner is configured",
            ),
            pack,
        )
    private_read_count = 0
    concept_expansion_count = 0
    current_pack = pack
    try:
        while True:
            result = inner_agent_runner.run(
                _inner_agent_request(
                    request=request,
                    settings=settings,
                    repo_root=repo_root,
                    candidate_context=current_pack,
                )
            ).model_copy(
                update={
                    "private_read_count": private_read_count,
                    "concept_expansion_count": concept_expansion_count,
                }
            )
            if (
                result.status != "ok"
                or result.brief is not None
                or not result.requested_expansions
                or private_read_count >= settings.max_private_reads
            ):
                return result, current_pack
            remaining_reads = settings.max_private_reads - private_read_count
            current_pack, reads_used, concept_expansions = _execute_private_expansions(
                request=request,
                pack=current_pack,
                requested_expansions=result.requested_expansions,
                read_budget=remaining_reads,
                uow=uow,
                read_settings=read_settings,
                threshold_settings=threshold_settings,
            )
            if reads_used == 0:
                return result, current_pack
            private_read_count += reads_used
            concept_expansion_count += concept_expansions
    except Exception as exc:  # pragma: no cover - defensive core boundary
        return (
            _inner_agent_result(
                settings=settings,
                status="error",
                fallback_used=True,
                error_code="runner_exception",
                error_message=str(exc),
            ),
            current_pack,
        )


def _inner_agent_request(
    *,
    request: MemoryRecallRequest,
    settings: InnerAgentSettings,
    repo_root: str | None,
    candidate_context: dict[str, Any],
) -> InnerAgentRunRequest:
    """Build one provider request from bounded Shellbrain context."""

    return InnerAgentRunRequest(
        agent_name="build_context",
        provider=settings.provider,
        model=settings.model,
        reasoning=settings.reasoning,
        timeout_seconds=settings.timeout_seconds,
        max_candidate_tokens=settings.max_candidate_tokens,
        max_brief_tokens=settings.max_brief_tokens,
        query=request.query,
        current_problem=request.current_problem.model_dump(mode="python")
        if request.current_problem is not None
        else None,
        repo_root=repo_root,
        candidate_context=candidate_context,
        expansion_handles=_expansion_handles_from_pack(candidate_context),
    )


def _execute_private_expansions(
    *,
    request: MemoryRecallRequest,
    pack: dict[str, Any],
    requested_expansions: list[dict[str, Any]],
    read_budget: int,
    uow: IUnitOfWork,
    read_settings: ReadPolicySettings,
    threshold_settings: ThresholdSettings,
) -> tuple[dict[str, Any], int, int]:
    """Execute approved provider-requested reads and attach their packs."""

    if read_budget <= 0:
        return pack, 0, 0

    private_expansions: list[dict[str, Any]] = []
    reads_used = 0
    concept_expansions = 0
    for expansion in requested_expansions:
        if reads_used >= read_budget:
            break
        read_request = _private_read_request_from_expansion(
            base_request=request,
            expansion=expansion,
        )
        if read_request is None:
            continue
        read_result = execute_read_memory(
            read_request,
            uow,
            read_settings=read_settings,
            threshold_settings=threshold_settings,
        )
        expansion_pack = read_result.data.get("pack", {})
        if not isinstance(expansion_pack, dict):
            expansion_pack = {}
        private_expansions.append(
            {
                "request": _safe_expansion_request(expansion),
                "pack": expansion_pack,
            }
        )
        reads_used += 1
        if _is_concept_expansion(read_request):
            concept_expansions += 1

    if not private_expansions:
        return pack, 0, 0

    existing = pack.get("private_expansions")
    merged_expansions = list(existing) if isinstance(existing, list) else []
    merged_expansions.extend(private_expansions)
    return {**pack, "private_expansions": merged_expansions}, reads_used, concept_expansions


def _private_read_request_from_expansion(
    *, base_request: MemoryRecallRequest, expansion: dict[str, Any]
) -> MemoryReadRequest | None:
    """Convert one approved expansion payload into a targeted read request."""

    payload = expansion.get("read_payload")
    if not isinstance(payload, dict):
        return None

    query = payload.get("query")
    expand = payload.get("expand")
    data: dict[str, Any] = {
        "repo_id": base_request.repo_id,
        "mode": "targeted",
        "query": query if isinstance(query, str) and query.strip() else base_request.query,
        "limit": base_request.limit,
    }
    if isinstance(expand, dict):
        data["expand"] = expand
    try:
        return MemoryReadRequest.model_validate(data)
    except ValueError:
        return None


def _safe_expansion_request(expansion: dict[str, Any]) -> dict[str, Any]:
    """Keep only JSON-like expansion request data in candidate context."""

    return {
        key: value
        for key, value in expansion.items()
        if isinstance(key, str)
        and isinstance(value, str | int | float | bool | type(None) | dict | list)
    }


def _is_concept_expansion(request: MemoryReadRequest) -> bool:
    """Return whether a private read expanded concept facets."""

    return request.expand is not None and request.expand.concepts.mode == "explicit"


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


def _inner_agent_error_message(result: InnerAgentRunResult) -> str:
    """Return a stable structured-error message for provider failures."""

    if result.error_message:
        return result.error_message
    return f"build_context inner agent failed with status={result.status}"


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


def _source_items_from_pack(pack: dict[str, Any]) -> list[dict[str, Any]]:
    """Build stable candidate provenance rows from one read pack."""

    items: list[dict[str, Any]] = []
    ordinal = 1
    seen: set[tuple[str, str, str]] = set()
    for prefix, candidate_pack in _packs_including_expansions(pack):
        ordinal = _append_source_items_from_single_pack(
            candidate_pack,
            input_prefix=prefix,
            items=items,
            seen=seen,
            next_ordinal=ordinal,
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


def _packs_including_expansions(
    pack: dict[str, Any]
) -> list[tuple[str, dict[str, Any]]]:
    """Return the initial pack plus any private expansion packs."""

    packs: list[tuple[str, dict[str, Any]]] = [("", pack)]
    expansions = pack.get("private_expansions")
    if not isinstance(expansions, list):
        return packs
    for index, expansion in enumerate(expansions, start=1):
        if not isinstance(expansion, dict):
            continue
        expansion_pack = expansion.get("pack")
        if isinstance(expansion_pack, dict):
            packs.append((f"private_expansion_{index}", expansion_pack))
    return packs


def _prefixed_section(prefix: str, section: str) -> str:
    """Render a source section name with optional private-expansion provenance."""

    if not prefix:
        return section
    return f"{prefix}.{section}"


def _memory_sections(pack: dict[str, Any]) -> list[dict[str, Any]]:
    """Return memory candidates in display order."""

    items: list[dict[str, Any]] = []
    for prefix, candidate_pack in _packs_including_expansions(pack):
        for section in ("direct", "explicit_related", "implicit_related"):
            bucket = candidate_pack.get(section)
            if not isinstance(bucket, list):
                continue
            for item in bucket:
                if isinstance(item, dict):
                    items.append(
                        {**item, "_section": _prefixed_section(prefix, section)}
                    )
    return items


def _concept_items(pack: dict[str, Any]) -> list[dict[str, Any]]:
    """Return concept candidates in display order."""

    items: list[dict[str, Any]] = []
    for prefix, candidate_pack in _packs_including_expansions(pack):
        concepts = candidate_pack.get("concepts")
        if not isinstance(concepts, dict) or not isinstance(concepts.get("items"), list):
            continue
        items.extend(
            {**item, "_section": _prefixed_section(prefix, "concept_orientation")}
            for item in concepts["items"]
            if isinstance(item, dict)
        )
    return items


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


def _expansion_handles_from_pack(pack: dict[str, Any]) -> list[dict[str, Any]]:
    """Collect concept expansion handles from one candidate pack."""

    handles: list[dict[str, Any]] = []
    for item in _concept_items(pack):
        expand = item.get("expand")
        if isinstance(expand, list):
            handles.extend(handle for handle in expand if isinstance(handle, dict))
    return handles[:10]


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
