"""Write telemetry record builders."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any

from app.core.use_cases.memories.add.request import MemoryAddRequest
from app.core.use_cases.memories.effect_plan import (
    AssociationUpsertAndObserveEffectParams,
    EffectParams,
    EffectType,
    FactUpdateCreateEffectParams,
    MemoryAddEffectParams,
    MemoryArchiveStateEffectParams,
    MemoryEmbeddingUpsertEffectParams,
    MemoryEvidenceAttachEffectParams,
    PlannedEffect,
    ProblemAttemptCreateEffectParams,
    UtilityObservationAppendEffectParams,
)
from app.core.use_cases.memories.update.request import (
    MemoryBatchUpdateRequest,
    MemoryUpdateRequest,
)
from app.infrastructure.telemetry.records import (
    WriteEffectItemRecord,
    WriteSummaryRecord,
)

__all__ = ["build_write_summary_records"]


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
