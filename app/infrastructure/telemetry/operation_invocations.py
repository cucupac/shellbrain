"""Helpers for assembling operation telemetry records from handler inputs and outputs."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
import json
from typing import Any

from app.core.contracts.errors import ErrorCode
from app.core.contracts.planned_effects import (
    AssociationUpsertAndObserveEffectParams,
    EffectParams,
    EffectType,
    FactUpdateCreateEffectParams,
    MemoryArchiveStateEffectParams,
    MemoryAddEffectParams,
    MemoryEmbeddingUpsertEffectParams,
    MemoryEvidenceAttachEffectParams,
    PlannedEffect,
    ProblemAttemptCreateEffectParams,
    UtilityObservationAppendEffectParams,
)
from app.core.contracts.memories import (
    MemoryBatchUpdateRequest,
    MemoryAddRequest,
    MemoryUpdateRequest,
)
from app.core.contracts.retrieval import MemoryReadRequest, MemoryRecallRequest
from app.core.entities.runtime_context import RuntimeContext, SessionSelectionSummary
from app.infrastructure.telemetry.records import (
    OperationInvocationRecord,
    RecallSourceItemRecord,
    RecallSummaryRecord,
    ReadResultItemRecord,
    ReadSummaryRecord,
    WriteEffectItemRecord,
    WriteSummaryRecord,
)


def build_operation_invocation_record(
    *,
    command: str,
    repo_id: str,
    runtime_context: RuntimeContext,
    selection_summary: SessionSelectionSummary,
    result: dict[str, Any],
    error_stage: str | None,
    total_latency_ms: int,
    created_at: datetime,
) -> OperationInvocationRecord:
    """Build the parent invocation row from one finished handler result."""

    first_error = _first_error(result)
    caller_identity = runtime_context.caller_identity
    guidance_codes = _guidance_codes(result)
    return OperationInvocationRecord(
        id=runtime_context.invocation_id,
        command=command,
        repo_id=repo_id,
        repo_root=runtime_context.repo_root,
        no_sync=runtime_context.no_sync,
        caller_id=caller_identity.canonical_id if caller_identity is not None else None,
        caller_trust_level=caller_identity.trust_level.value
        if caller_identity is not None
        else None,
        identity_failure_code=runtime_context.caller_identity_error.code.value
        if runtime_context.caller_identity_error is not None
        else None,
        selected_host_app=selection_summary.selected_host_app,
        selected_host_session_key=selection_summary.selected_host_session_key,
        selected_thread_id=selection_summary.selected_thread_id,
        selected_episode_id=selection_summary.selected_episode_id,
        matching_candidate_count=selection_summary.matching_candidate_count,
        selection_ambiguous=selection_summary.selection_ambiguous,
        outcome=str(result.get("status") or "error"),
        error_stage=error_stage,
        error_code=first_error["code"],
        error_message=first_error["message"],
        total_latency_ms=total_latency_ms,
        poller_start_attempted=False,
        poller_started=False,
        guidance_codes=guidance_codes,
        created_at=created_at,
    )


def build_read_summary_records(
    *,
    invocation_id: str,
    requested_limit: int | None,
    request: MemoryReadRequest,
    pack: dict[str, Any],
    created_at: datetime,
) -> tuple[ReadSummaryRecord, list[ReadResultItemRecord]]:
    """Build one read summary row and one item row per displayed memory."""

    direct = list(pack.get("direct", []))
    explicit_related = list(pack.get("explicit_related", []))
    implicit_related = list(pack.get("implicit_related", []))
    items: list[ReadResultItemRecord] = []
    ordinal = 1
    for section_name, bucket in (
        ("direct", direct),
        ("explicit_related", explicit_related),
        ("implicit_related", implicit_related),
    ):
        for item in bucket:
            items.append(
                ReadResultItemRecord(
                    invocation_id=invocation_id,
                    ordinal=ordinal,
                    memory_id=str(item["memory_id"]),
                    kind=str(item["kind"]),
                    section=section_name,
                    priority=ordinal,
                    why_included=str(item.get("why_included") or ""),
                    anchor_memory_id=_optional_string(item.get("anchor_memory_id")),
                    relation_type=_optional_string(item.get("relation_type")),
                )
            )
            ordinal += 1

    pack_size = estimate_read_pack_size(pack=pack)

    summary = ReadSummaryRecord(
        invocation_id=invocation_id,
        query_text=request.query,
        mode=request.mode,
        requested_limit=requested_limit,
        effective_limit=int(request.limit or len(items) or 0),
        include_global=request.include_global,
        kinds_filter=list(request.kinds) if request.kinds is not None else None,
        direct_count=len(direct),
        explicit_related_count=len(explicit_related),
        implicit_related_count=len(implicit_related),
        total_returned=len(items),
        zero_results=len(items) == 0,
        pack_char_count=int(pack_size["pack_char_count"]),
        pack_token_estimate=int(pack_size["pack_token_estimate"]),
        pack_token_estimate_method=str(pack_size["pack_token_estimate_method"]),
        direct_token_estimate=int(pack_size["direct_token_estimate"]),
        explicit_related_token_estimate=int(
            pack_size["explicit_related_token_estimate"]
        ),
        implicit_related_token_estimate=int(
            pack_size["implicit_related_token_estimate"]
        ),
        concept_count=int(pack_size["concept_count"]),
        concept_token_estimate=int(pack_size["concept_token_estimate"]),
        concept_refs_returned=list(pack_size["concept_refs_returned"]),
        concept_facets_returned=list(pack_size["concept_facets_returned"]),
        created_at=created_at,
    )
    return summary, items


def build_recall_summary_records(
    *,
    invocation_id: str,
    request: MemoryRecallRequest,
    recall_telemetry: dict[str, Any],
    brief: dict[str, Any],
    fallback_reason: str | None,
    created_at: datetime,
) -> tuple[RecallSummaryRecord, list[RecallSourceItemRecord]]:
    """Build one recall summary row and one source row per considered candidate."""

    candidate_pack = recall_telemetry.get("candidate_pack", {})
    if not isinstance(candidate_pack, dict):
        candidate_pack = {}
    candidate_size = estimate_read_pack_size(pack=candidate_pack)
    source_payloads = recall_telemetry.get("source_items")
    if not isinstance(source_payloads, list):
        source_payloads = []

    source_items: list[RecallSourceItemRecord] = []
    for item in source_payloads:
        if not isinstance(item, dict):
            continue
        source_items.append(
            RecallSourceItemRecord(
                invocation_id=invocation_id,
                ordinal=int(item["ordinal"]),
                source_kind=str(item["source_kind"]),
                source_id=str(item["source_id"]),
                input_section=str(item["input_section"]),
                output_section=_optional_string(item.get("output_section")),
            )
        )

    brief_payload = {"brief": brief, "fallback_reason": fallback_reason}
    summary = RecallSummaryRecord(
        invocation_id=invocation_id,
        query_text=request.query,
        candidate_token_estimate=int(candidate_size["pack_token_estimate"]),
        brief_token_estimate=_estimate_tokens_from_text(_compact_json(brief_payload)),
        fallback_reason=fallback_reason,
        created_at=created_at,
    )
    return summary, source_items


def estimate_read_pack_size(
    *, pack: dict[str, Any]
) -> dict[str, int | str | list[str]]:
    """Estimate one read-pack footprint with one stable local heuristic."""

    serialized_pack = _compact_json(pack)
    return {
        "pack_char_count": len(serialized_pack),
        "pack_token_estimate": _estimate_tokens_from_text(serialized_pack),
        "pack_token_estimate_method": "json_compact_chars_div4_v1",
        "direct_token_estimate": _estimate_section_tokens(pack.get("direct")),
        "explicit_related_token_estimate": _estimate_section_tokens(
            pack.get("explicit_related")
        ),
        "implicit_related_token_estimate": _estimate_section_tokens(
            pack.get("implicit_related")
        ),
        "concept_count": _concept_count(pack.get("concepts")),
        "concept_token_estimate": _estimate_section_tokens(pack.get("concepts")),
        "concept_refs_returned": _concept_refs(pack.get("concepts")),
        "concept_facets_returned": _concept_facets(pack.get("concepts")),
    }


def build_write_summary_records(
    *,
    invocation_id: str,
    command: str,
    request: MemoryAddRequest | MemoryUpdateRequest | MemoryBatchUpdateRequest,
    planned_side_effects: list[PlannedEffect | dict[str, Any]],
    created_at: datetime,
) -> tuple[WriteSummaryRecord, list[WriteEffectItemRecord]]:
    """Build one write summary row and one compact effect row per planned side effect."""

    effects = [_coerce_planned_effect(effect) for effect in planned_side_effects]
    created_memory_count = 0
    archived_memory_count = 0
    utility_observation_count = 0
    association_effect_count = 0
    fact_update_count = 0
    effect_items: list[WriteEffectItemRecord] = []

    for ordinal, effect in enumerate(effects, start=1):
        effect_type = effect.effect_type
        params = effect.params
        params_dict = _effect_params_to_dict(params)
        if effect_type is EffectType.MEMORY_CREATE:
            created_memory_count += 1
        elif (
            effect_type is EffectType.MEMORY_ARCHIVE_STATE
            and isinstance(params, MemoryArchiveStateEffectParams)
            and params.archived
        ):
            archived_memory_count += 1
        elif effect_type is EffectType.UTILITY_OBSERVATION_APPEND:
            utility_observation_count += 1
        elif effect_type is EffectType.ASSOCIATION_UPSERT_AND_OBSERVE:
            association_effect_count += 1
        elif effect_type is EffectType.FACT_UPDATE_CREATE:
            fact_update_count += 1

        effect_items.append(
            WriteEffectItemRecord(
                invocation_id=invocation_id,
                ordinal=ordinal,
                effect_type=effect_type.value,
                repo_id=str(getattr(request, "repo_id")),
                primary_memory_id=_primary_memory_id(params_dict),
                secondary_memory_id=_secondary_memory_id(params_dict),
                params_json=_compact_effect_params(params_dict),
            )
        )

    if isinstance(request, MemoryAddRequest):
        evidence_ref_count = len(request.memory.evidence_refs)
        target_memory_id = _target_memory_id_from_create(effects)
        target_kind = request.memory.kind
        update_type = None
        scope = request.memory.scope
    elif isinstance(request, MemoryBatchUpdateRequest):
        evidence_ref_count = sum(
            len(item.update.evidence_refs or []) for item in request.updates
        )
        target_memory_id = request.updates[0].update.problem_id
        target_kind = None
        update_type = "utility_vote_batch"
        scope = None
    else:
        evidence_ref_count = len(getattr(request.update, "evidence_refs", []) or [])
        target_memory_id = request.memory_id
        target_kind = None
        update_type = request.update.type
        scope = None

    summary = WriteSummaryRecord(
        invocation_id=invocation_id,
        operation_command=command,
        target_memory_id=target_memory_id,
        target_kind=target_kind,
        update_type=update_type,
        scope=scope,
        evidence_ref_count=evidence_ref_count,
        planned_effect_count=len(effects),
        created_memory_count=created_memory_count,
        archived_memory_count=archived_memory_count,
        utility_observation_count=utility_observation_count,
        association_effect_count=association_effect_count,
        fact_update_count=fact_update_count,
        created_at=created_at,
    )
    return summary, effect_items


def infer_error_stage_from_errors(
    errors: list[dict[str, Any]], *, default_stage: str
) -> str:
    """Map structured error codes to telemetry stages when validation failed."""

    if not errors:
        return default_stage
    code = errors[0].get("code")
    normalized = code.value if isinstance(code, ErrorCode) else str(code)
    if (
        normalized == ErrorCode.SCHEMA_ERROR.value
        and default_stage == "schema_validation"
    ):
        return "schema_validation"
    if (
        normalized == ErrorCode.SCHEMA_ERROR.value
        and default_stage == "contract_validation"
    ):
        return "contract_validation"
    if normalized == ErrorCode.SEMANTIC_ERROR.value:
        return "semantic_validation"
    if normalized == ErrorCode.INTEGRITY_ERROR.value:
        return "integrity_validation"
    return default_stage


def _first_error(result: dict[str, Any]) -> dict[str, str | None]:
    """Return the first response error in a stable telemetry-friendly shape."""

    errors = result.get("errors")
    if not isinstance(errors, list) or not errors:
        return {"code": None, "message": None}
    first = errors[0]
    if not isinstance(first, dict):
        return {"code": None, "message": str(first)}
    code = first.get("code")
    normalized_code = (
        code.value
        if isinstance(code, ErrorCode)
        else (str(code) if code is not None else None)
    )
    message = first.get("message")
    return {
        "code": normalized_code,
        "message": str(message) if message is not None else None,
    }


def _guidance_codes(result: dict[str, Any]) -> list[str]:
    """Return stable guidance codes from one successful result."""

    data = result.get("data")
    if not isinstance(data, dict):
        return []
    guidance = data.get("guidance")
    if not isinstance(guidance, list):
        return []
    codes: list[str] = []
    for item in guidance:
        if not isinstance(item, dict):
            continue
        code = item.get("code")
        if isinstance(code, str):
            codes.append(code)
    return codes


def _target_memory_id_from_create(planned_side_effects: list[PlannedEffect]) -> str:
    """Extract the created memory id from one create side-effect plan."""

    for effect in planned_side_effects:
        if effect.effect_type is not EffectType.MEMORY_CREATE:
            continue
        params = effect.params
        if isinstance(params, MemoryAddEffectParams):
            return params.memory_id
    raise ValueError("Create telemetry expected one memory.create side effect.")


def _coerce_planned_effect(effect: PlannedEffect | dict[str, Any]) -> PlannedEffect:
    """Normalize serialized effect payloads back to the typed core contract."""

    if isinstance(effect, PlannedEffect):
        return effect
    effect_type = effect.get("effect_type")
    params = effect.get("params")
    if not isinstance(params, dict):
        raise ValueError("Planned effect params must be a dict.")
    resolved_type = (
        effect_type if isinstance(effect_type, EffectType) else EffectType(str(effect_type))
    )
    return PlannedEffect(
        effect_type=resolved_type, params=_coerce_effect_params(resolved_type, params)
    )


def _coerce_effect_params(
    effect_type: EffectType, params: dict[str, Any]
) -> EffectParams:
    """Normalize serialized effect params back to their typed payload contract."""

    if effect_type is EffectType.MEMORY_CREATE:
        return MemoryAddEffectParams(**params)
    if effect_type is EffectType.MEMORY_EMBEDDING_UPSERT:
        return MemoryEmbeddingUpsertEffectParams(**params)
    if effect_type is EffectType.MEMORY_EVIDENCE_ATTACH:
        return MemoryEvidenceAttachEffectParams(
            memory_id=str(params["memory_id"]),
            repo_id=str(params["repo_id"]),
            refs=tuple(str(ref) for ref in params["refs"]),
        )
    if effect_type is EffectType.PROBLEM_ATTEMPT_CREATE:
        return ProblemAttemptCreateEffectParams(**params)
    if effect_type is EffectType.MEMORY_ARCHIVE_STATE:
        return MemoryArchiveStateEffectParams(**params)
    if effect_type is EffectType.UTILITY_OBSERVATION_APPEND:
        return UtilityObservationAppendEffectParams(**params)
    if effect_type is EffectType.FACT_UPDATE_CREATE:
        return FactUpdateCreateEffectParams(**params)
    if effect_type is EffectType.ASSOCIATION_UPSERT_AND_OBSERVE:
        return AssociationUpsertAndObserveEffectParams(
            repo_id=str(params["repo_id"]),
            edge_id=str(params["edge_id"]),
            from_memory_id=str(params["from_memory_id"]),
            to_memory_id=str(params["to_memory_id"]),
            relation_type=str(params["relation_type"]),
            source_mode=str(params["source_mode"]),
            state=str(params["state"]),
            strength=float(params["strength"]),
            observation_id=str(params["observation_id"]),
            observation_source=str(params["observation_source"]),
            valence=float(params["valence"]),
            salience=float(params["salience"]),
            evidence_refs=tuple(str(ref) for ref in params["evidence_refs"]),
        )
    raise ValueError(f"Unsupported planned effect type: {effect_type}")


def _effect_params_to_dict(params: EffectParams) -> dict[str, Any]:
    """Return telemetry-safe params for any typed planned effect payload."""

    return asdict(params)


def _compact_effect_params(params: dict[str, Any]) -> dict[str, Any]:
    """Drop bulky fields so telemetry stores compact, queryable side-effect metadata."""

    return {
        str(key): value
        for key, value in params.items()
        if key not in {"text", "vector"}
    }


def _primary_memory_id(params: dict[str, Any]) -> str | None:
    """Extract the primary memory identifier from one side-effect payload when present."""

    for key in (
        "memory_id",
        "from_memory_id",
        "old_fact_id",
        "problem_id",
        "change_id",
    ):
        value = params.get(key)
        if isinstance(value, str):
            return value
    return None


def _secondary_memory_id(params: dict[str, Any]) -> str | None:
    """Extract the secondary memory identifier from one side-effect payload when present."""

    for key in ("to_memory_id", "new_fact_id", "attempt_id"):
        value = params.get(key)
        if isinstance(value, str):
            return value
    return None


def _optional_string(value: object) -> str | None:
    """Return a string value or None when the field is absent."""

    return str(value) if isinstance(value, str) else None


def _estimate_section_tokens(section: Any) -> int:
    """Estimate tokens for one pack section while treating empty sections as zero."""

    if isinstance(section, list) and not section:
        return 0
    if section in (None, {}):
        return 0
    return _estimate_tokens_from_text(_compact_json(section))


def _concept_count(section: Any) -> int:
    """Return the number of concept items in one concept pack section."""

    if not isinstance(section, dict):
        return 0
    items = section.get("items")
    return len(items) if isinstance(items, list) else 0


def _concept_refs(section: Any) -> list[str]:
    """Return concept refs rendered in one concept pack section."""

    if not isinstance(section, dict):
        return []
    items = section.get("items")
    if not isinstance(items, list):
        return []
    return [
        str(item["ref"]) for item in items if isinstance(item, dict) and "ref" in item
    ]


def _concept_facets(section: Any) -> list[str]:
    """Return requested concept facets rendered in one concept pack section."""

    if not isinstance(section, dict):
        return []
    facets: set[str] = set()
    items = section.get("items")
    if not isinstance(items, list):
        return []
    for item in items:
        if not isinstance(item, dict):
            continue
        for facet in ("claims", "relations", "groundings", "memory_links", "evidence"):
            if facet in item:
                facets.add(facet)
    return sorted(facets)


def _estimate_tokens_from_text(text: str) -> int:
    """Return one stable local token estimate from compact text length."""

    if not text:
        return 0
    return (len(text) + 3) // 4


def _compact_json(value: Any) -> str:
    """Render one deterministic compact JSON string for token estimation."""

    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
