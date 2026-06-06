"""Generated summary support for Shellbrain Wiki pages."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib
import json
from typing import Any, Sequence

from app.core.entities.concepts import (
    Concept,
    ConceptClaim,
    ConceptClaimType,
    ConceptLifecycleStatus,
)
from app.core.entities.inner_agents import WikiSummarySettings
from app.core.entities.memories import Memory, MemoryLifecycleStatus
from app.core.entities.wiki_summaries import (
    WikiSummaryFreshness,
    WikiSummaryInputSnapshot,
    WikiSummaryLinkTarget,
    WikiSummaryLinkTargetType,
    WikiSummarySourceVelocity,
    WikiSummaryTarget,
    WikiSummaryTargetType,
    WikiSummaryView,
)
from app.core.ports.db.unit_of_work import IUnitOfWork
from app.core.ports.host_apps.inner_agents import (
    IWikiSummaryAgentRunner,
    WikiSummaryAgentRequest,
)
from app.core.ports.system.clock import IClock
from app.core.policies.wiki_summary_freshness import (
    determine_wiki_summary_freshness,
)


UowFactory = Callable[[], IUnitOfWork]

_ACTIVE_CONCEPT_STATUSES = ("active",)
_ACTIVE_MEMORY_STATUSES = (
    MemoryLifecycleStatus.ACTIVE.value,
    MemoryLifecycleStatus.MAYBE_STALE.value,
)
_HIGH_VELOCITY_WINDOW = timedelta(days=7)
_NORMAL_VELOCITY_WINDOW = timedelta(days=30)
_MAX_REPO_CONCEPTS = 8
_MAX_REPO_RECENT_MEMORIES = 5
_MAX_CONCEPT_CLAIMS = 8
_MAX_CONCEPT_MEMORY_LINKS = 8
_MAX_CONCEPT_RELATIONS = 8
_MAX_INITIAL_CONCEPTS_PER_REPO = 25


@dataclass(frozen=True, kw_only=True)
class WikiSummaryRefreshResult:
    """Result of one summary refresh attempt."""

    target: WikiSummaryTarget
    status: str
    error_code: str | None = None
    error_message: str | None = None


def repo_summary_target(repo_id: str) -> WikiSummaryTarget:
    """Return the stable summary target for one repository home page."""

    return WikiSummaryTarget(
        repo_id=repo_id,
        target_type=WikiSummaryTargetType.REPO,
        target_id=repo_id,
    )


def concept_summary_target(*, repo_id: str, concept_id: str) -> WikiSummaryTarget:
    """Return the stable summary target for one concept page."""

    return WikiSummaryTarget(
        repo_id=repo_id,
        target_type=WikiSummaryTargetType.CONCEPT,
        target_id=concept_id,
    )


def build_repo_summary_snapshot(
    *, repo_id: str, uow: IUnitOfWork, now: datetime
) -> WikiSummaryInputSnapshot:
    """Build deterministic source input for one repository summary."""

    concept_payloads: list[dict[str, Any]] = []
    source_refs: list[str] = []
    latest_values: list[datetime] = []
    for concept in uow.concepts.list_concepts(
        repo_id=repo_id, statuses=_ACTIVE_CONCEPT_STATUSES
    ):
        bundle = uow.concepts.get_concept_bundle(
            repo_id=repo_id, concept_ref=concept.id
        )
        if bundle is None:
            continue
        payload = _concept_index_payload(bundle)
        concept_payloads.append(payload)
        source_refs.extend(_bundle_source_refs(bundle))
        latest_values.extend(_bundle_datetimes(bundle))

    concept_payloads.sort(
        key=lambda item: (-int(item["popularity_score"]), str(item["name"]))
    )
    recent_memories = tuple(
        uow.memories.list_recent(
            repo_id=repo_id,
            statuses=_ACTIVE_MEMORY_STATUSES,
            limit=_MAX_REPO_RECENT_MEMORIES,
        )
    )
    memory_payloads = [_memory_payload(memory) for memory in recent_memories]
    source_refs.extend(f"memory:{memory.id}" for memory in recent_memories)
    latest_values.extend(
        memory.created_at for memory in recent_memories if memory.created_at is not None
    )
    selected_concepts = concept_payloads[:_MAX_REPO_CONCEPTS]
    payload = {
        "target_type": WikiSummaryTargetType.REPO.value,
        "repo_id": repo_id,
        "counts": {
            "concepts": len(concept_payloads),
            "recent_memories_included": len(memory_payloads),
            "claims": sum(int(item["claim_count"]) for item in concept_payloads),
            "memory_links": sum(
                int(item["memory_count"]) for item in concept_payloads
            ),
            "evidence": sum(int(item["evidence_count"]) for item in concept_payloads),
        },
        "top_concepts": selected_concepts,
        "recent_memories": memory_payloads,
    }
    latest_source_at = _latest_datetime(latest_values)
    return _snapshot(
        target=repo_summary_target(repo_id),
        payload=payload,
        source_refs=source_refs,
        latest_source_at=latest_source_at,
        now=now,
        popularity_score=sum(int(item["popularity_score"]) for item in selected_concepts),
    )


def build_concept_summary_snapshot(
    *, repo_id: str, concept_ref: str, uow: IUnitOfWork, now: datetime
) -> WikiSummaryInputSnapshot:
    """Build deterministic source input for one concept summary."""

    bundle = uow.concepts.get_concept_bundle(repo_id=repo_id, concept_ref=concept_ref)
    if bundle is None:
        raise ValueError(f"Concept not found for summary: {concept_ref}")
    concept: Concept = bundle["concept"]
    memory_ids = [
        str(link.memory_id)
        for link in bundle["memory_links"][:_MAX_CONCEPT_MEMORY_LINKS]
    ]
    memories = {
        memory.id: memory
        for memory in uow.memories.list_by_ids(memory_ids)
    }
    relation_concept_ids = sorted(
        {
            relation.subject_concept_id
            for relation in bundle["relations"]
        }
        | {
            relation.object_concept_id
            for relation in bundle["relations"]
        }
    )
    related_concepts = {
        related.id: related
        for related in uow.concepts.list_concepts_by_ids(
            repo_id=repo_id, concept_ids=relation_concept_ids
        )
    }
    active_claims = [
        claim
        for claim in bundle["claims"]
        if claim.lifecycle.status == ConceptLifecycleStatus.ACTIVE
    ]
    payload = {
        "target_type": WikiSummaryTargetType.CONCEPT.value,
        "repo_id": repo_id,
        "concept": {
            "id": concept.id,
            "slug": concept.slug,
            "name": concept.name,
            "kind": concept.kind.value,
            "status": concept.status.value,
            "scope_note": concept.scope_note,
        },
        "counts": {
            "claims": len(bundle["claims"]),
            "memory_links": len(bundle["memory_links"]),
            "relations": len(bundle["relations"]),
            "groundings": len(bundle["groundings"]),
            "evidence": len(bundle["evidence"]),
        },
        "definition": _active_definition(bundle["claims"]),
        "key_claims": [_claim_payload(claim) for claim in active_claims[:_MAX_CONCEPT_CLAIMS]],
        "relations": [
            {
                "id": relation.id,
                "predicate": relation.predicate.value,
                "subject_id": relation.subject_concept_id,
                "subject_slug": _concept_slug(
                    related_concepts.get(relation.subject_concept_id)
                ),
                "subject": _concept_name(
                    related_concepts.get(relation.subject_concept_id),
                    fallback=relation.subject_concept_id,
                ),
                "object_id": relation.object_concept_id,
                "object_slug": _concept_slug(
                    related_concepts.get(relation.object_concept_id)
                ),
                "object": _concept_name(
                    related_concepts.get(relation.object_concept_id),
                    fallback=relation.object_concept_id,
                ),
                "status": relation.lifecycle.status.value,
            }
            for relation in bundle["relations"][:_MAX_CONCEPT_RELATIONS]
        ],
        "memory_links": [
            {
                "id": link.id,
                "role": link.role.value,
                "status": link.lifecycle.status.value,
                "memory": _memory_payload(memories[link.memory_id])
                if link.memory_id in memories
                else {"id": link.memory_id, "missing": True},
            }
            for link in bundle["memory_links"][:_MAX_CONCEPT_MEMORY_LINKS]
        ],
        "groundings": [
            {
                "id": grounding.id,
                "role": grounding.role.value,
                "anchor_id": grounding.anchor_id,
                "status": grounding.lifecycle.status.value,
            }
            for grounding in bundle["groundings"][:_MAX_CONCEPT_RELATIONS]
        ],
    }
    source_refs = _bundle_source_refs(bundle)
    source_refs.extend(f"memory:{memory.id}" for memory in memories.values())
    latest_values = _bundle_datetimes(bundle)
    latest_values.extend(
        memory.created_at for memory in memories.values() if memory.created_at is not None
    )
    return _snapshot(
        target=concept_summary_target(repo_id=repo_id, concept_id=concept.id),
        payload=payload,
        source_refs=source_refs,
        latest_source_at=_latest_datetime(latest_values),
        now=now,
        popularity_score=(
            len(bundle["claims"]) + len(bundle["memory_links"]) + len(bundle["evidence"])
        ),
    )


def wiki_summary_view(
    *, snapshot: WikiSummaryInputSnapshot, uow: IUnitOfWork, now: datetime
) -> WikiSummaryView:
    """Return cached summary state for one current source snapshot."""

    record = uow.wiki_summaries.get(snapshot.target)
    freshness, reason = determine_wiki_summary_freshness(
        record=record, snapshot=snapshot, now=now
    )
    return WikiSummaryView(
        target=snapshot.target,
        freshness=freshness,
        body=record.body if record is not None else None,
        generated_at=record.generated_at if record is not None else None,
        stale_reason=reason,
        generation_status=record.generation_status if record is not None else None,
        link_targets=_summary_link_targets(snapshot),
    )


def plan_wiki_summary_refresh_batch(
    *,
    uow: IUnitOfWork,
    now: datetime,
    limit: int,
) -> tuple[WikiSummaryInputSnapshot, ...]:
    """Return missing or stale summary snapshots ranked by supporting volume."""

    candidates: list[tuple[int, WikiSummaryInputSnapshot]] = []
    for repository in uow.repository_index.list_repositories():
        if (
            repository.concept_count
            + repository.memory_count
            + repository.evidence_count
            <= 0
        ):
            continue
        repo_snapshot = build_repo_summary_snapshot(
            repo_id=repository.repo_id, uow=uow, now=now
        )
        _add_refresh_candidate(candidates, repo_snapshot, uow, now)
        concept_snapshots = _top_concept_snapshots(
            repo_id=repository.repo_id,
            uow=uow,
            now=now,
            limit=_MAX_INITIAL_CONCEPTS_PER_REPO,
        )
        for snapshot in concept_snapshots:
            _add_refresh_candidate(candidates, snapshot, uow, now)
    candidates.sort(key=lambda item: (-item[0], item[1].target.repo_id, item[1].target.target_id))
    return tuple(snapshot for _score, snapshot in candidates[:limit])


def refresh_wiki_summary(
    *,
    target: WikiSummaryTarget,
    uow_factory: UowFactory,
    clock: IClock,
    settings: WikiSummarySettings,
    agent_runner: IWikiSummaryAgentRunner | None,
) -> WikiSummaryRefreshResult:
    """Refresh one generated wiki summary through a provider boundary."""

    now = clock.now()
    with uow_factory() as uow:
        snapshot = _snapshot_for_target(target=target, uow=uow, now=now)
        acquired = uow.wiki_summaries.acquire_refresh(
            snapshot=snapshot,
            model=settings.model,
            prompt_version=settings.prompt_version,
            now=now,
            stale_running_before=now
            - timedelta(seconds=settings.running_refresh_stale_seconds),
        )
    if not acquired:
        return WikiSummaryRefreshResult(target=target, status="skipped")
    if agent_runner is None:
        with uow_factory() as uow:
            uow.wiki_summaries.record_failure(
                snapshot=snapshot,
                model=settings.model,
                prompt_version=settings.prompt_version,
                error_code="missing_runner",
                error_message="no wiki_summary runner is configured",
                now=clock.now(),
            )
        return WikiSummaryRefreshResult(
            target=target,
            status="provider_unavailable",
            error_code="missing_runner",
        )
    result = agent_runner.run_wiki_summary(
        WikiSummaryAgentRequest(
            provider=settings.provider,
            model=settings.model,
            reasoning=settings.reasoning,
            timeout_seconds=settings.timeout_seconds,
            target_type=target.target_type.value,
            repo_id=target.repo_id,
            target_id=target.target_id,
            prompt_version=settings.prompt_version,
            max_summary_chars=settings.max_summary_chars,
            source_payload=snapshot.source_payload,
        )
    )
    with uow_factory() as uow:
        if result.status == "ok" and result.body is not None:
            uow.wiki_summaries.record_success(
                snapshot=snapshot,
                body=result.body,
                model=result.model,
                prompt_version=settings.prompt_version,
                now=clock.now(),
            )
        else:
            uow.wiki_summaries.record_failure(
                snapshot=snapshot,
                model=result.model,
                prompt_version=settings.prompt_version,
                error_code=result.error_code or str(result.status),
                error_message=result.error_message or "wiki summary generation failed",
                now=clock.now(),
            )
    return WikiSummaryRefreshResult(
        target=target,
        status=result.status,
        error_code=result.error_code,
        error_message=result.error_message,
    )


def _top_concept_snapshots(
    *,
    repo_id: str,
    uow: IUnitOfWork,
    now: datetime,
    limit: int,
) -> tuple[WikiSummaryInputSnapshot, ...]:
    snapshots = []
    for concept in uow.concepts.list_concepts(
        repo_id=repo_id, statuses=_ACTIVE_CONCEPT_STATUSES
    ):
        snapshots.append(
            build_concept_summary_snapshot(
                repo_id=repo_id, concept_ref=concept.id, uow=uow, now=now
            )
        )
    snapshots.sort(key=lambda item: (-item.popularity_score, item.target.target_id))
    return tuple(snapshots[:limit])


def _add_refresh_candidate(
    candidates: list[tuple[int, WikiSummaryInputSnapshot]],
    snapshot: WikiSummaryInputSnapshot,
    uow: IUnitOfWork,
    now: datetime,
) -> None:
    freshness, _reason = determine_wiki_summary_freshness(
        record=uow.wiki_summaries.get(snapshot.target),
        snapshot=snapshot,
        now=now,
    )
    if freshness in {
        WikiSummaryFreshness.MISSING,
        WikiSummaryFreshness.STALE,
        WikiSummaryFreshness.EXPIRED,
        WikiSummaryFreshness.FAILED,
    }:
        candidates.append((snapshot.popularity_score, snapshot))


def _snapshot_for_target(
    *, target: WikiSummaryTarget, uow: IUnitOfWork, now: datetime
) -> WikiSummaryInputSnapshot:
    if target.target_type == WikiSummaryTargetType.REPO:
        return build_repo_summary_snapshot(repo_id=target.repo_id, uow=uow, now=now)
    if target.target_type == WikiSummaryTargetType.CONCEPT:
        return build_concept_summary_snapshot(
            repo_id=target.repo_id,
            concept_ref=target.target_id,
            uow=uow,
            now=now,
        )
    raise ValueError(f"Unsupported wiki summary target type: {target.target_type}")


def _concept_index_payload(bundle: dict[str, Any]) -> dict[str, Any]:
    concept: Concept = bundle["concept"]
    return {
        "id": concept.id,
        "slug": concept.slug,
        "name": concept.name,
        "kind": concept.kind.value,
        "status": concept.status.value,
        "definition": _active_definition(bundle["claims"]),
        "key_claims": [
            _claim_payload(claim)
            for claim in bundle["claims"]
            if claim.lifecycle.status == ConceptLifecycleStatus.ACTIVE
        ][:3],
        "claim_count": len(bundle["claims"]),
        "memory_count": len(bundle["memory_links"]),
        "evidence_count": len(bundle["evidence"]),
        "popularity_score": (
            len(bundle["claims"]) + len(bundle["memory_links"]) + len(bundle["evidence"])
        ),
    }


def _active_definition(claims: Sequence[ConceptClaim]) -> str | None:
    for claim in claims:
        if (
            claim.claim_type == ConceptClaimType.DEFINITION
            and claim.lifecycle.status == ConceptLifecycleStatus.ACTIVE
        ):
            return claim.text
    return None


def _claim_payload(claim: ConceptClaim) -> dict[str, Any]:
    return {
        "id": claim.id,
        "claim_type": claim.claim_type.value,
        "text": claim.text,
        "status": claim.lifecycle.status.value,
        "confidence": claim.lifecycle.confidence,
        "validated_at": _isoformat(claim.lifecycle.validated_at),
    }


def _memory_payload(memory: Memory) -> dict[str, Any]:
    return {
        "id": memory.id,
        "kind": memory.kind.value,
        "status": memory.status.value,
        "text": memory.text,
        "created_at": _isoformat(memory.created_at),
    }


def _bundle_source_refs(bundle: dict[str, Any]) -> list[str]:
    refs = [f"concept:{bundle['concept'].id}"]
    refs.extend(f"claim:{claim.id}" for claim in bundle["claims"])
    refs.extend(f"relation:{relation.id}" for relation in bundle["relations"])
    refs.extend(f"grounding:{grounding.id}" for grounding in bundle["groundings"])
    refs.extend(f"memory_link:{link.id}" for link in bundle["memory_links"])
    refs.extend(f"evidence:{evidence.evidence_id or evidence.id}" for evidence in bundle["evidence"])
    return refs


def _bundle_datetimes(bundle: dict[str, Any]) -> list[datetime]:
    values: list[datetime] = []
    concept: Concept = bundle["concept"]
    values.extend(value for value in (concept.created_at, concept.updated_at) if value)
    for claim in bundle["claims"]:
        values.extend(
            value
            for value in (
                claim.created_at,
                claim.updated_at,
                claim.lifecycle.observed_at,
                claim.lifecycle.validated_at,
            )
            if value is not None
        )
    for relation in bundle["relations"]:
        values.extend(value for value in (relation.created_at, relation.updated_at) if value)
    for grounding in bundle["groundings"]:
        values.extend(value for value in (grounding.created_at, grounding.updated_at) if value)
    for link in bundle["memory_links"]:
        values.extend(value for value in (link.created_at, link.updated_at) if value)
    for evidence in bundle["evidence"]:
        if evidence.created_at is not None:
            values.append(evidence.created_at)
    return values


def _snapshot(
    *,
    target: WikiSummaryTarget,
    payload: dict[str, Any],
    source_refs: Sequence[str],
    latest_source_at: datetime | None,
    now: datetime,
    popularity_score: int,
) -> WikiSummaryInputSnapshot:
    canonical_payload = _canonical_payload(payload)
    return WikiSummaryInputSnapshot(
        target=target,
        input_hash=_hash_payload(canonical_payload),
        source_refs=tuple(sorted(dict.fromkeys(source_refs))),
        source_payload=canonical_payload,
        source_velocity=_source_velocity(latest_source_at=latest_source_at, now=now),
        latest_source_at=latest_source_at,
        popularity_score=popularity_score,
    )


def _canonical_payload(value: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(value, sort_keys=True, default=_json_default))


def _hash_payload(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _json_default(value: Any) -> str:
    if isinstance(value, datetime):
        return _isoformat(value) or ""
    raise TypeError(f"Object is not JSON serializable: {type(value).__name__}")


def _source_velocity(
    *, latest_source_at: datetime | None, now: datetime
) -> WikiSummarySourceVelocity:
    if latest_source_at is None:
        return WikiSummarySourceVelocity.QUIET
    age = now - latest_source_at
    if age <= _HIGH_VELOCITY_WINDOW:
        return WikiSummarySourceVelocity.HIGH
    if age <= _NORMAL_VELOCITY_WINDOW:
        return WikiSummarySourceVelocity.NORMAL
    return WikiSummarySourceVelocity.QUIET


def _latest_datetime(values: Sequence[datetime]) -> datetime | None:
    if not values:
        return None
    return max(values)


def _isoformat(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _concept_name(concept: Concept | None, *, fallback: str) -> str:
    return concept.name if concept is not None else fallback


def _concept_slug(concept: Concept | None) -> str | None:
    return concept.slug if concept is not None else None


def _summary_link_targets(
    snapshot: WikiSummaryInputSnapshot,
) -> tuple[WikiSummaryLinkTarget, ...]:
    payload = snapshot.source_payload
    targets: list[WikiSummaryLinkTarget] = []
    if snapshot.target.target_type == WikiSummaryTargetType.REPO:
        for concept in _payload_items(payload.get("top_concepts")):
            _add_concept_link_targets(targets, concept)
    elif snapshot.target.target_type == WikiSummaryTargetType.CONCEPT:
        concept = payload.get("concept")
        if isinstance(concept, dict):
            _add_concept_link_targets(targets, concept)
        for relation in _payload_items(payload.get("relations")):
            _add_concept_link_targets(
                targets,
                {
                    "id": relation.get("subject_id"),
                    "slug": relation.get("subject_slug"),
                    "name": relation.get("subject"),
                },
            )
            _add_concept_link_targets(
                targets,
                {
                    "id": relation.get("object_id"),
                    "slug": relation.get("object_slug"),
                    "name": relation.get("object"),
                },
            )
    return tuple(_unique_link_targets(targets))


def _payload_items(value: Any) -> tuple[dict[str, Any], ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, dict))


def _add_concept_link_targets(
    targets: list[WikiSummaryLinkTarget], concept: dict[str, Any]
) -> None:
    concept_id = concept.get("id")
    slug = concept.get("slug")
    name = concept.get("name")
    if not isinstance(concept_id, str) or not concept_id:
        return
    if not isinstance(slug, str) or not slug:
        return
    if isinstance(name, str) and name.strip():
        targets.append(
            WikiSummaryLinkTarget(
                target_type=WikiSummaryLinkTargetType.CONCEPT,
                target_id=concept_id,
                slug=slug,
                label=name.strip(),
            )
        )
    targets.append(
        WikiSummaryLinkTarget(
            target_type=WikiSummaryLinkTargetType.CONCEPT,
            target_id=concept_id,
            slug=slug,
            label=slug,
        )
    )


def _unique_link_targets(
    targets: list[WikiSummaryLinkTarget],
) -> tuple[WikiSummaryLinkTarget, ...]:
    seen: set[tuple[WikiSummaryLinkTargetType, str, str]] = set()
    unique: list[WikiSummaryLinkTarget] = []
    for target in targets:
        key = (target.target_type, target.target_id, target.label.casefold())
        if key in seen:
            continue
        seen.add(key)
        unique.append(target)
    return tuple(unique)
