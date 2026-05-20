"""Deterministic graph-first recall pack construction."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from time import perf_counter
from typing import Any, Iterable, Sequence

from app.core.entities.concepts import (
    Concept,
    ConceptClaim,
    ConceptLifecycleStatus,
    ConceptMemoryLink,
    ConceptRelation,
    ConceptStatus,
)
from app.core.entities.memories import MATURE_MEMORY_KIND_VALUES, Memory
from app.core.entities.settings import (
    ThresholdSettings,
    default_threshold_settings,
)
from app.core.ports.db.unit_of_work import IUnitOfWork
from app.core.policies.retrieval.fusion_rrf import fuse_with_rrf
from app.core.use_cases.retrieval.concept_seed_retrieval import retrieve_concept_seeds
from app.core.use_cases.retrieval.recall.request import MemoryRecallRequest
from app.core.use_cases.retrieval.seed_retrieval import retrieve_seeds


_MEMORY_LANE_LIMIT = 12
_FINAL_MEMORY_TARGET = 24
_FINAL_MEMORY_HARD_CAP = 32
_CONCEPT_TARGET = 6
_CONCEPT_HARD_CAP = 8
_RELATION_NEIGHBOR_CAP = 4
_HIGH_SIGNAL_LINK_ROLES = {
    "solution_for",
    "failed_tactic_for",
    "warned_about",
    "changed",
    "contradicted",
    "validated",
}
_HIGH_SIGNAL_RELATIONS = {"depends_on", "constrains", "precedes", "contains"}
_HIGH_SIGNAL_CLAIMS = {"invariant", "failure_mode", "usage_note", "behavior"}
_PLACEHOLDER_VALUES = {"none", "none yet", "n/a", "na", "unknown", "not sure"}


@dataclass(frozen=True)
class _QueryLane:
    name: str
    query: str
    terms: tuple[str, ...]


def build_deterministic_graph_pack(
    *,
    request: MemoryRecallRequest,
    uow: IUnitOfWork,
    threshold_settings: ThresholdSettings | None = None,
) -> dict[str, Any]:
    """Build a bounded graph-aware recall pack without autonomous reads."""

    thresholds = threshold_settings or default_threshold_settings()
    started = perf_counter()
    lanes = _build_query_lanes(request)
    memory_candidates: dict[str, dict[str, Any]] = {}
    lane_results: list[dict[str, Any]] = []
    for lane in lanes:
        lane_result = _run_memory_lane(
            lane=lane,
            request=request,
            uow=uow,
            thresholds=thresholds,
            memory_candidates=memory_candidates,
        )
        lane_results.append(lane_result)

    if _should_add_broad_lane(lane_results, memory_candidates):
        broad_lane = _broad_domain_lane(request)
        if broad_lane is not None:
            lanes.append(broad_lane)
            lane_results.append(
                _run_memory_lane(
                    lane=broad_lane,
                    request=request,
                    uow=uow,
                    thresholds=thresholds,
                    memory_candidates=memory_candidates,
                )
            )

    concept_candidates = _discover_concepts(
        request=request,
        lanes=lanes,
        memory_candidates=memory_candidates,
        uow=uow,
        thresholds=thresholds,
    )
    selected_concepts, concept_trace = _select_concepts(
        request=request,
        concept_candidates=concept_candidates,
        uow=uow,
    )
    traversal = _traverse_selected_concepts(
        request=request,
        selected_concepts=selected_concepts,
        memory_candidates=memory_candidates,
        uow=uow,
    )
    selected_memories, ranking_trace = _select_final_memories(
        request=request,
        memory_candidates=memory_candidates,
    )
    concepts_payload = [
        _compact_concept_payload(entry["bundle"], why_selected=entry["why"])
        for entry in selected_concepts
    ]
    neighbor_payload = [
        _compact_concept_payload(entry["bundle"], why_selected=entry["why"])
        for entry in traversal["relation_neighbors"]
    ]
    anchors = _anchors_from_concepts(selected_concepts, traversal["relation_neighbors"])
    pack = {
        "strategy": "deterministic_graph",
        "request": {
            "query": request.query,
            "current_problem": request.current_problem.model_dump(mode="python"),
        },
        "query_lanes": [
            {"lane": lane.name, "query": lane.query, "terms": list(lane.terms)}
            for lane in lanes
        ],
        "memories": [_memory_payload(item) for item in selected_memories],
        "concepts": concepts_payload,
        "relation_neighbors": neighbor_payload,
        "anchors": anchors[:16],
        "conflicts": _conflicts_from_concepts(concepts_payload, neighbor_payload),
        "pack_trace": {
            "strategy": "deterministic_synthesis",
            "duration_ms": _duration_ms(started),
            "lane_results": lane_results,
            "concept_candidates": concept_trace,
            "graph_traversal": traversal["trace"],
            "pack_composition": _pack_composition(selected_memories, anchors),
            "pack_budget": _pack_budget(
                selected_memories=selected_memories,
                concepts=concepts_payload,
                neighbors=neighbor_payload,
                ranking_trace=ranking_trace,
            ),
            "ranking": ranking_trace,
        },
    }
    return pack


def deterministic_brief_from_graph_pack(pack: dict[str, Any]) -> dict[str, Any]:
    """Render a compact worker brief from a deterministic graph pack."""

    memories = [item for item in pack.get("memories", []) if isinstance(item, dict)]
    concepts = [item for item in pack.get("concepts", []) if isinstance(item, dict)]
    neighbors = [
        item for item in pack.get("relation_neighbors", []) if isinstance(item, dict)
    ]
    if not memories and not concepts and not neighbors:
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
    concept_items = concepts + neighbors
    constraints = _brief_memory_texts(
        memories,
        kinds={"fact", "preference", "change"},
        link_roles={"validated", "changed"},
    )
    constraints.extend(_claim_texts(concept_items, {"invariant", "behavior"}))
    known_traps = _brief_memory_texts(
        memories,
        kinds={"problem", "failed_tactic"},
        link_roles={"failed_tactic_for", "warned_about"},
    )
    known_traps.extend(_claim_texts(concept_items, {"failure_mode"}))
    prior_cases = _brief_memory_texts(
        memories,
        kinds={"solution"},
        link_roles={"solution_for", "example_of"},
    )
    return {
        "summary": _summary(memories=memories, concepts=concept_items),
        "constraints": _truncate_list(constraints, 6),
        "known_traps": _truncate_list(known_traps, 6),
        "prior_cases": _truncate_list(prior_cases, 6),
        "concept_orientation": _truncate_list(
            [
                _truncate(
                    f"{item.get('name') or item.get('ref')}: "
                    f"{item.get('orientation') or ''}",
                    320,
                )
                for item in concept_items
                if item.get("orientation") or item.get("name") or item.get("ref")
            ],
            8,
        ),
        "anchors": _truncate_list(
            [str(anchor.get("locator")) for anchor in pack.get("anchors", [])], 12
        ),
        "conflicts": _truncate_list(
            [_conflict_summary(item) for item in pack.get("conflicts", [])], 6
        ),
        "gaps": [],
        "next_checks": _next_checks(pack),
        "sources": _sources_from_graph_pack(pack),
    }


def source_items_from_graph_pack(pack: dict[str, Any]) -> list[dict[str, Any]]:
    """Return telemetry source items from a deterministic graph pack."""

    source_items: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    ordinal = 1
    for memory in pack.get("memories", []):
        if not isinstance(memory, dict) or memory.get("id") is None:
            continue
        source_id = str(memory["id"])
        if ("memory", source_id) in seen:
            continue
        seen.add(("memory", source_id))
        source_items.append(
            {
                "ordinal": ordinal,
                "source_kind": "memory",
                "source_id": source_id,
                "input_section": _source_section_for_memory(memory),
                "output_section": "sources",
            }
        )
        ordinal += 1
    for concept_section in ("concepts", "relation_neighbors"):
        for concept in pack.get(concept_section, []):
            if not isinstance(concept, dict):
                continue
            source_id = concept.get("id") or concept.get("ref")
            if source_id is None:
                continue
            concept_key = ("concept", str(source_id))
            if concept_key in seen:
                continue
            seen.add(concept_key)
            source_items.append(
                {
                    "ordinal": ordinal,
                    "source_kind": "concept",
                    "source_id": str(source_id),
                    "input_section": "concept_orientation",
                    "output_section": "sources",
                }
            )
            ordinal += 1
    return source_items


def _build_query_lanes(request: MemoryRecallRequest) -> list[_QueryLane]:
    original = _lane("original", request.query)
    current_problem = _current_problem_lane(request)
    identifiers = _identifier_lane(request)
    traps = _prior_cases_lane(request)
    lanes = [lane for lane in (original, current_problem, identifiers, traps) if lane]
    deduped: list[_QueryLane] = []
    seen_queries: set[str] = set()
    for lane in lanes:
        normalized = " ".join(lane.query.lower().split())
        if normalized in seen_queries:
            continue
        seen_queries.add(normalized)
        deduped.append(lane)
    return deduped


def _lane(name: str, query: str) -> _QueryLane | None:
    text = " ".join(query.split())
    if not text:
        return None
    terms = tuple(dict.fromkeys(_tokenize(text)))
    return _QueryLane(name=name, query=text, terms=terms)


def _current_problem_lane(request: MemoryRecallRequest) -> _QueryLane | None:
    problem = request.current_problem.model_dump(mode="python")
    parts = [
        value
        for key in ("surface", "obstacle", "hypothesis", "goal")
        if _useful_problem_part(value := str(problem.get(key) or ""))
    ]
    return _lane("current_problem", " ".join(parts))


def _identifier_lane(request: MemoryRecallRequest) -> _QueryLane | None:
    problem_text = " ".join(request.current_problem.model_dump(mode="python").values())
    identifiers = _extract_identifiers(f"{request.query} {problem_text}")
    return _lane("identifiers", " ".join(identifiers))


def _prior_cases_lane(request: MemoryRecallRequest) -> _QueryLane | None:
    terms = list(dict.fromkeys(_tokenize(f"{request.query} {request.current_problem.obstacle}")))
    strongest = " ".join(terms[:8])
    if not strongest:
        return None
    return _lane(
        "prior_cases_traps_constraints",
        f"{strongest} prior case failed tactic warning constraint changed contradicted",
    )


def _broad_domain_lane(request: MemoryRecallRequest) -> _QueryLane | None:
    terms = _tokenize(f"{request.current_problem.surface} {request.current_problem.goal}")
    if not terms:
        return None
    return _lane("broad_domain", " ".join(dict.fromkeys(terms[:8])))


def _should_add_broad_lane(
    lane_results: list[dict[str, Any]], memory_candidates: dict[str, dict[str, Any]]
) -> bool:
    if len(memory_candidates) >= 4:
        return False
    return any(result["zero_result"] for result in lane_results)


def _run_memory_lane(
    *,
    lane: _QueryLane,
    request: MemoryRecallRequest,
    uow: IUnitOfWork,
    thresholds: ThresholdSettings,
    memory_candidates: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    started = perf_counter()
    request_data = _lane_request_data(request=request, query=lane.query)
    seeds = retrieve_seeds(
        request_data,
        semantic_retrieval=uow.semantic_retrieval,
        keyword_retrieval=uow.keyword_retrieval,
        vector_search=uow.vector_search,
        thresholds=thresholds,
    )
    fused = fuse_with_rrf(seeds["semantic"], seeds["keyword"])
    selected = fused[:_MEMORY_LANE_LIMIT]
    hydrated = _visible_memories_by_id(
        uow=uow,
        repo_id=request.repo_id,
        memory_ids=[str(item["memory_id"]) for item in selected],
    )
    for rank, candidate in enumerate(selected, start=1):
        memory_id = str(candidate["memory_id"])
        memory = hydrated.get(memory_id)
        if memory is None:
            continue
        entry = memory_candidates.setdefault(
            memory_id,
            {
                "memory": memory,
                "score": 0.0,
                "matched_lanes": [],
                "lane_ranks": {},
                "concept_refs": set(),
                "link_roles": set(),
                "why": set(),
            },
        )
        entry["score"] = max(float(entry["score"]), float(candidate["rrf_score"]))
        entry["matched_lanes"].append(lane.name)
        entry["lane_ranks"][lane.name] = rank
        entry["why"].add("memory_fanout")
    raw_count = len(seeds["semantic"]) + len(seeds["keyword"])
    unique_ids = {str(item["memory_id"]) for item in selected}
    return {
        "lane": lane.name,
        "duration_ms": _duration_ms(started),
        "raw_count": raw_count,
        "unique_memory_count": len(unique_ids),
        "selected_memory_count": len(selected),
        "selected_memory_ids": [str(item["memory_id"]) for item in selected],
        "zero_result": raw_count == 0,
        "duplicate_heavy": raw_count > 0 and len(unique_ids) <= max(1, raw_count // 3),
    }


def _discover_concepts(
    *,
    request: MemoryRecallRequest,
    lanes: Sequence[_QueryLane],
    memory_candidates: dict[str, dict[str, Any]],
    uow: IUnitOfWork,
    thresholds: ThresholdSettings,
) -> dict[str, dict[str, Any]]:
    candidates: dict[str, dict[str, Any]] = {}
    memory_ids = list(memory_candidates)
    for link in uow.concepts.find_concepts_for_memory_ids(
        repo_id=request.repo_id,
        memory_ids=memory_ids,
    ):
        concept_id = str(link["concept_id"])
        candidate = candidates.setdefault(concept_id, {"score": 0.0, "why": []})
        confidence = float(link.get("confidence") or 0.5)
        role = str(link.get("role") or "")
        candidate["score"] += 10.0 * _lifecycle_multiplier(str(link["status"])) * max(
            confidence, 0.1
        )
        candidate["why"].append(
            {"reason": "linked_memory", "role": role, "memory_id": str(link["memory_id"])}
        )
        memory_entry = memory_candidates.get(str(link["memory_id"]))
        if memory_entry is not None:
            memory_entry["concept_refs"].add(concept_id)
            memory_entry["link_roles"].add(role)

    for lane in lanes:
        query_vector, query_model = _query_embedding(uow, lane.query)
        seeds = retrieve_concept_seeds(
            _lane_request_data(request=request, query=lane.query),
            concept_keyword_retrieval=uow.concept_keyword_retrieval,
            concept_semantic_retrieval=uow.concept_semantic_retrieval,
            query_vector=query_vector,
            query_model=query_model,
            thresholds=thresholds,
            limit=20,
        )
        for retrieved in seeds["fused"]:
            concept_id = str(retrieved["concept_id"])
            candidate = candidates.setdefault(concept_id, {"score": 0.0, "why": []})
            candidate["score"] += 20.0 * float(retrieved["rrf_score"])
            if retrieved.get("rank_keyword") is not None:
                candidate["why"].append(
                    {
                        "reason": "concept_keyword",
                        "lane": lane.name,
                        "rank": int(retrieved["rank_keyword"]),
                    }
                )
            if retrieved.get("rank_semantic") is not None:
                candidate["why"].append(
                    {
                        "reason": "concept_semantic",
                        "lane": lane.name,
                        "rank": int(retrieved["rank_semantic"]),
                    }
                )
    return candidates


def _select_concepts(
    *,
    request: MemoryRecallRequest,
    concept_candidates: dict[str, dict[str, Any]],
    uow: IUnitOfWork,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    selected: list[tuple[float, str, dict[str, Any]]] = []
    rejected_count = 0
    for concept_id, candidate in concept_candidates.items():
        bundle = uow.concepts.get_concept_bundle(
            repo_id=request.repo_id, concept_ref=concept_id
        )
        if bundle is None:
            rejected_count += 1
            continue
        if not _active_concept(bundle["concept"]):
            rejected_count += 1
            continue
        score = float(candidate["score"]) + _bundle_signal_score(
            bundle=bundle,
            query_terms=_tokenize(request.query),
            identifiers=_extract_identifiers(request.query),
        )
        score *= _concept_freshness_multiplier(bundle)
        selected.append(
            (
                score,
                str(bundle["concept"].slug),
                {
                    "score": score,
                    "bundle": bundle,
                    "why": _dedupe_reasons(candidate["why"]),
                },
            )
        )
    selected.sort(key=lambda item: (-item[0], item[1]))
    chosen = [entry for _, _, entry in selected[:_CONCEPT_HARD_CAP]]
    return chosen[:_CONCEPT_TARGET], {
        "candidate_count": len(concept_candidates),
        "selected": len(chosen[:_CONCEPT_TARGET]),
        "rejected": rejected_count + max(0, len(selected) - _CONCEPT_TARGET),
        "selected_refs": [entry["bundle"]["concept"].slug for entry in chosen[:_CONCEPT_TARGET]],
    }


def _traverse_selected_concepts(
    *,
    request: MemoryRecallRequest,
    selected_concepts: list[dict[str, Any]],
    memory_candidates: dict[str, dict[str, Any]],
    uow: IUnitOfWork,
) -> dict[str, Any]:
    linked_memory_ids: list[str] = []
    relation_neighbor_ids: list[str] = []
    counts = Counter()
    for entry in selected_concepts:
        bundle = entry["bundle"]
        counts["claims_loaded"] += len(bundle["claims"])
        counts["groundings_loaded"] += len(bundle["groundings"])
        counts["relations_loaded"] += len(bundle["relations"])
        counts["memory_links_loaded"] += len(bundle["memory_links"])
        for link in bundle["memory_links"]:
            if not _active(link.lifecycle.status):
                continue
            role = link.role.value
            if role not in _HIGH_SIGNAL_LINK_ROLES:
                continue
            linked_memory_ids.append(link.memory_id)
        concept_id = bundle["concept"].id
        for relation in bundle["relations"]:
            if not _active(relation.lifecycle.status):
                continue
            if relation.predicate.value not in _HIGH_SIGNAL_RELATIONS:
                continue
            neighbor_id = (
                relation.object_concept_id
                if relation.subject_concept_id == concept_id
                else relation.subject_concept_id
            )
            relation_neighbor_ids.append(neighbor_id)

    linked_memories = _visible_memories_by_id(
        uow=uow,
        repo_id=request.repo_id,
        memory_ids=linked_memory_ids,
    )
    link_role_by_memory = defaultdict(set)
    concept_ref_by_memory = defaultdict(set)
    for entry in selected_concepts:
        concept = entry["bundle"]["concept"]
        for link in entry["bundle"]["memory_links"]:
            if link.memory_id in linked_memories:
                link_role_by_memory[link.memory_id].add(link.role.value)
                concept_ref_by_memory[link.memory_id].add(concept.slug)
    for memory_id, memory in linked_memories.items():
        candidate = memory_candidates.setdefault(
            memory_id,
            {
                "memory": memory,
                "score": 0.0,
                "matched_lanes": [],
                "lane_ranks": {},
                "concept_refs": set(),
                "link_roles": set(),
                "why": set(),
            },
        )
        candidate["score"] = max(float(candidate["score"]), 1.0)
        candidate["concept_refs"].update(concept_ref_by_memory[memory_id])
        candidate["link_roles"].update(link_role_by_memory[memory_id])
        candidate["why"].add("graph_linked_memory")
    unique_neighbor_ids = tuple(dict.fromkeys(relation_neighbor_ids))[
        :_RELATION_NEIGHBOR_CAP
    ]
    neighbors = []
    selected_ids = {entry["bundle"]["concept"].id for entry in selected_concepts}
    for neighbor_id in unique_neighbor_ids:
        if neighbor_id in selected_ids:
            continue
        bundle = uow.concepts.get_concept_bundle(
            repo_id=request.repo_id, concept_ref=neighbor_id
        )
        if bundle is None or not _active_concept(bundle["concept"]):
            continue
        neighbors.append(
            {
                "score": 0.0,
                "bundle": bundle,
                "why": [{"reason": "relation_neighbor"}],
            }
        )
    counts["linked_memories_loaded"] = len(linked_memories)
    counts["relation_neighbors_loaded"] = len(neighbors)
    return {
        "relation_neighbors": neighbors,
        "trace": dict(counts),
    }


def _select_final_memories(
    *,
    request: MemoryRecallRequest,
    memory_candidates: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    ordered = sorted(
        memory_candidates.values(),
        key=lambda item: (-_memory_candidate_score(item), str(item["memory"].id)),
    )
    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()
    rejected: list[dict[str, Any]] = []

    def take(predicate, limit: int) -> None:
        for item in ordered:
            if len(selected) >= _FINAL_MEMORY_HARD_CAP:
                return
            memory_id = str(item["memory"].id)
            if memory_id in selected_ids or not predicate(item):
                continue
            selected.append(item)
            selected_ids.add(memory_id)
            if len([entry for entry in selected if predicate(entry)]) >= limit:
                return

    take(_is_trap_memory, 3)
    take(_is_changed_or_contradicted_memory, 2)
    take(_is_validated_memory, 2)
    take(_is_fact_preference_change, 3)
    take(lambda item: "graph_linked_memory" in item["why"], 4)
    take(lambda item: bool(item["matched_lanes"]), 12)

    prior_case_query = _is_prior_case_query(request.query)
    problem_solution_count = sum(1 for item in selected if _problem_or_solution(item))
    for item in ordered:
        if len(selected) >= _FINAL_MEMORY_TARGET:
            break
        memory_id = str(item["memory"].id)
        if memory_id in selected_ids:
            continue
        if (
            not prior_case_query
            and _problem_or_solution(item)
            and problem_solution_count >= 10
        ):
            rejected.append(_rejected_memory(item, "problem_solution_cap"))
            continue
        selected.append(item)
        selected_ids.add(memory_id)
        if _problem_or_solution(item):
            problem_solution_count += 1

    for item in ordered:
        memory_id = str(item["memory"].id)
        if memory_id not in selected_ids:
            rejected.append(_rejected_memory(item, "budget_or_role_balance"))

    return selected[:_FINAL_MEMORY_HARD_CAP], {
        "selected_memory_count": len(selected[:_FINAL_MEMORY_HARD_CAP]),
        "rejected_memory_count": len(rejected),
        "top_rejected_memory_ids": [item["memory_id"] for item in rejected[:10]],
        "rejected": rejected[:20],
    }


def _lane_request_data(*, request: MemoryRecallRequest, query: str) -> dict[str, Any]:
    return {
        "repo_id": request.repo_id,
        "mode": "targeted",
        "query": query,
        "limit": _MEMORY_LANE_LIMIT,
        "include_global": True,
        "kinds": list(MATURE_MEMORY_KIND_VALUES),
    }


def _visible_memories_by_id(
    *, uow: IUnitOfWork, repo_id: str, memory_ids: Sequence[str]
) -> dict[str, Memory]:
    memories = uow.memories.list_by_ids(tuple(dict.fromkeys(memory_ids)))
    return {
        str(memory.id): memory
        for memory in memories
        if not memory.archived and memory.is_visible_in(repo_id)
    }


def _query_embedding(uow: IUnitOfWork, query: str) -> tuple[list[float], str | None]:
    vector_search = getattr(uow, "vector_search", None)
    if vector_search is None:
        return [], None
    vector = list(vector_search.embed_query(query))
    if not vector:
        raise ValueError("Query embedding provider returned an empty vector")
    return vector, vector_search.model_name


def _bundle_signal_score(
    *, bundle: dict[str, Any], query_terms: Sequence[str], identifiers: Sequence[str]
) -> float:
    score = 0.0
    query_set = {term.lower() for term in query_terms}
    identifiers_lower = [item.lower() for item in identifiers]
    for claim in bundle["claims"]:
        if claim.claim_type.value in _HIGH_SIGNAL_CLAIMS and _active(
            claim.lifecycle.status
        ):
            if any(term in claim.text.lower() for term in query_set):
                score += 4.0
    for link in bundle["memory_links"]:
        if link.role.value in _HIGH_SIGNAL_LINK_ROLES and _active(
            link.lifecycle.status
        ):
            score += 5.0 * max(float(link.lifecycle.confidence), 0.1)
    for relation in bundle["relations"]:
        if relation.predicate.value in _HIGH_SIGNAL_RELATIONS and _active(
            relation.lifecycle.status
        ):
            score += 2.0
    for locator in _bundle_anchor_locators(bundle):
        lower_locator = locator.lower()
        if identifiers_lower and any(item in lower_locator for item in identifiers_lower):
            score += 9.0
    return score


def _concept_freshness_multiplier(bundle: dict[str, Any]) -> float:
    statuses: list[str] = []
    for key in ("claims", "relations", "groundings", "memory_links"):
        for record in bundle[key]:
            statuses.append(record.lifecycle.status.value)
    if ConceptLifecycleStatus.WRONG.value in statuses:
        return 0.35
    if ConceptLifecycleStatus.STALE.value in statuses:
        return 0.45
    if ConceptLifecycleStatus.SUPERSEDED.value in statuses:
        return 0.55
    if ConceptLifecycleStatus.MAYBE_STALE.value in statuses:
        return 0.75
    return 1.0


def _compact_concept_payload(
    bundle: dict[str, Any], *, why_selected: list[dict[str, Any]]
) -> dict[str, Any]:
    concept: Concept = bundle["concept"]
    claims = _claim_payloads(bundle["claims"], limit=6)
    temporal = _concept_currentness_payload(bundle)
    return {
        "id": concept.id,
        "ref": concept.slug,
        "name": concept.name,
        "kind": concept.kind.value,
        "status": concept.status.value,
        **temporal,
        "orientation": _orientation(concept, bundle["claims"]),
        "why_selected": why_selected,
        "claims": claims,
        "relations": _relation_payloads(bundle["relations"], concept_id=concept.id),
        "groundings": _grounding_payloads(bundle),
        "memory_links": _memory_link_payloads(bundle["memory_links"]),
        "freshness": _freshness_payload(bundle),
    }


def _claim_payloads(claims: Sequence[ConceptClaim], *, limit: int) -> list[dict[str, Any]]:
    sorted_claims = sorted(
        claims,
        key=lambda item: (
            item.lifecycle.status.value != ConceptLifecycleStatus.ACTIVE.value,
            item.claim_type.value,
            item.text,
        ),
    )
    return [
        {
            "id": claim.id,
            "type": claim.claim_type.value,
            "text": claim.text,
            "status": claim.lifecycle.status.value,
            "confidence": claim.lifecycle.confidence,
            "observed_at": _iso(claim.lifecycle.observed_at),
            "validated_at": _iso(claim.lifecycle.validated_at),
            "superseded_by": claim.lifecycle.superseded_by_id,
            **_lifecycle_currentness_payload(
                claim.lifecycle,
                active_reason="active concept claim",
                validated_reason="claim has validated_at evidence",
            ),
        }
        for claim in sorted_claims[:limit]
    ]


def _relation_payloads(
    relations: Sequence[ConceptRelation], *, concept_id: str
) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for relation in sorted(
        relations,
        key=lambda item: (
            item.predicate.value,
            item.subject_concept_id,
            item.object_concept_id,
        ),
    )[:6]:
        neighbor_id = (
            relation.object_concept_id
            if relation.subject_concept_id == concept_id
            else relation.subject_concept_id
        )
        payloads.append(
            {
                "id": relation.id,
                "predicate": relation.predicate.value,
                "neighbor_id": neighbor_id,
                "status": relation.lifecycle.status.value,
                "confidence": relation.lifecycle.confidence,
                "observed_at": _iso(relation.lifecycle.observed_at),
                "validated_at": _iso(relation.lifecycle.validated_at),
                "superseded_by": relation.lifecycle.superseded_by_id,
                **_lifecycle_currentness_payload(
                    relation.lifecycle,
                    active_reason="active concept relation",
                    validated_reason="relation has validated_at evidence",
                ),
            }
        )
    return payloads


def _grounding_payloads(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    anchors_by_id = {anchor.id: anchor for anchor in bundle["anchors"]}
    payloads = []
    for grounding in sorted(
        bundle["groundings"], key=lambda item: (item.role.value, item.anchor_id)
    )[:8]:
        anchor = anchors_by_id.get(grounding.anchor_id)
        payloads.append(
            {
                "id": grounding.id,
                "role": grounding.role.value,
                "anchor_id": grounding.anchor_id,
                "anchor_kind": anchor.kind.value if anchor else None,
                "locator": _locator_text(anchor.locator_json) if anchor else None,
                "status": grounding.lifecycle.status.value,
                "confidence": grounding.lifecycle.confidence,
                "observed_at": _iso(grounding.lifecycle.observed_at),
                "validated_at": _iso(grounding.lifecycle.validated_at),
                "superseded_by": grounding.lifecycle.superseded_by_id,
                **_lifecycle_currentness_payload(
                    grounding.lifecycle,
                    active_reason="active concept grounding",
                    validated_reason="grounding has validated_at evidence",
                ),
            }
        )
    return payloads


def _memory_link_payloads(
    memory_links: Sequence[ConceptMemoryLink],
) -> list[dict[str, Any]]:
    return [
        {
            "id": link.id,
            "role": link.role.value,
            "memory_id": link.memory_id,
            "status": link.lifecycle.status.value,
            "confidence": link.lifecycle.confidence,
            "observed_at": _iso(link.lifecycle.observed_at),
            "validated_at": _iso(link.lifecycle.validated_at),
            "superseded_by": link.lifecycle.superseded_by_id,
            **_lifecycle_currentness_payload(
                link.lifecycle,
                active_reason="active concept memory link",
                validated_reason="memory link has validated_at evidence",
            ),
        }
        for link in sorted(
            memory_links, key=lambda item: (item.role.value, item.memory_id)
        )[:10]
    ]


def _freshness_payload(bundle: dict[str, Any]) -> dict[str, int]:
    counter = Counter()
    for key in ("claims", "relations", "groundings", "memory_links"):
        for record in bundle[key]:
            counter[record.lifecycle.status.value] += 1
    return dict(counter)


def _memory_payload(candidate: dict[str, Any]) -> dict[str, Any]:
    memory: Memory = candidate["memory"]
    return {
        "id": str(memory.id),
        "kind": memory.kind.value,
        "text": memory.text,
        "created_at": _iso(memory.created_at),
        **_memory_currentness_payload(candidate),
        "score": round(_memory_candidate_score(candidate), 6),
        "matched_lanes": list(dict.fromkeys(candidate["matched_lanes"])),
        "concept_refs": sorted(str(value) for value in candidate["concept_refs"]),
        "link_roles": sorted(str(value) for value in candidate["link_roles"]),
        "why": sorted(str(value) for value in candidate["why"]),
    }


def _anchors_from_concepts(
    selected_concepts: list[dict[str, Any]], neighbors: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    anchors: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in selected_concepts + neighbors:
        concept = entry["bundle"]["concept"]
        anchors_by_id = {anchor.id: anchor for anchor in entry["bundle"]["anchors"]}
        for grounding in entry["bundle"]["groundings"]:
            if grounding.anchor_id in seen:
                continue
            anchor = anchors_by_id.get(grounding.anchor_id)
            if anchor is None:
                continue
            seen.add(grounding.anchor_id)
            anchors.append(
                {
                    "id": anchor.id,
                    "concept_ref": concept.slug,
                    "role": grounding.role.value,
                    "kind": anchor.kind.value,
                    "locator": _locator_text(anchor.locator_json),
                    "status": grounding.lifecycle.status.value,
                    "confidence": grounding.lifecycle.confidence,
                    "observed_at": _iso(grounding.lifecycle.observed_at),
                    "validated_at": _iso(grounding.lifecycle.validated_at),
                    **_lifecycle_currentness_payload(
                        grounding.lifecycle,
                        active_reason="active grounding anchor",
                        validated_reason="anchor grounding has validated_at evidence",
                    ),
                }
            )
    return anchors


def _conflicts_from_concepts(
    concepts: Sequence[dict[str, Any]], neighbors: Sequence[dict[str, Any]]
) -> list[dict[str, Any]]:
    conflicts: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(conflict: dict[str, Any]) -> None:
        key = str(conflict.get("id") or conflict.get("summary") or conflict)
        if key in seen:
            return
        seen.add(key)
        conflicts.append(conflict)

    for concept in list(concepts) + list(neighbors):
        ref = concept.get("ref") or concept.get("id")
        for claim in concept.get("claims", []):
            status = claim.get("status")
            if status in {"maybe_stale", "stale", "superseded", "wrong"}:
                claim_id = str(claim.get("id") or "")
                add(
                    {
                        "id": (
                            f"claim:{claim_id}"
                            if claim_id
                            else f"claim:{ref}:{status}"
                        ),
                        "type": f"{status}_claim",
                        "items": [claim_id] if claim_id else [],
                        "preferred_current_item": None,
                        "reason": claim.get("temporal_reason")
                        or f"claim lifecycle status is {status}",
                        "summary": _truncate(
                            f"{ref} claim is {status}: {claim.get('text')}", 280
                        ),
                    }
                )
        for grounding in concept.get("groundings", []):
            status = grounding.get("status")
            if status in {"maybe_stale", "stale", "superseded", "wrong"}:
                grounding_id = str(grounding.get("id") or "")
                add(
                    {
                        "id": f"grounding:{grounding_id}"
                        if grounding_id
                        else f"grounding:{ref}:{status}",
                        "type": (
                            "stale_anchor"
                            if status in {"maybe_stale", "stale"}
                            else f"{status}_anchor"
                        ),
                        "items": [grounding_id] if grounding_id else [],
                        "preferred_current_item": None,
                        "reason": grounding.get("temporal_reason")
                        or f"grounding lifecycle status is {status}",
                        "summary": _truncate(
                            f"{ref} anchor is {status}: {grounding.get('locator')}", 280
                        ),
                    }
                )
        for link in concept.get("memory_links", []):
            role = link.get("role")
            if role == "changed":
                memory_id = str(link.get("memory_id") or "")
                add(
                    {
                        "id": f"memory_link:{link.get('id') or memory_id}:changed",
                        "type": "changed_memory_link",
                        "items": [memory_id] if memory_id else [],
                        "preferred_current_item": memory_id or None,
                        "reason": "changed links record a revision or supersession",
                        "summary": f"{ref} has changed memory link: {memory_id}",
                    }
                )
            if role == "contradicted":
                memory_id = str(link.get("memory_id") or "")
                add(
                    {
                        "id": f"memory_link:{link.get('id') or memory_id}:contradicted",
                        "type": "contradicted_memory_link",
                        "items": [memory_id] if memory_id else [],
                        "preferred_current_item": None,
                        "reason": "contradicted links mark unresolved or resolved disagreement",
                        "summary": f"{ref} has contradicted memory link: {memory_id}",
                    }
                )
    return conflicts


def _pack_composition(
    selected_memories: Sequence[dict[str, Any]], anchors: Sequence[dict[str, Any]]
) -> dict[str, Any]:
    kind_counts = Counter(item["memory"].kind.value for item in selected_memories)
    link_counts = Counter()
    for item in selected_memories:
        link_counts.update(item["link_roles"])
    anchor_counts = Counter(str(anchor.get("role")) for anchor in anchors)
    return {
        "memory_count_by_kind": dict(kind_counts),
        "memory_count_by_link_role": dict(link_counts),
        "anchor_count_by_role": dict(anchor_counts),
    }


def _pack_budget(
    *,
    selected_memories: Sequence[dict[str, Any]],
    concepts: Sequence[dict[str, Any]],
    neighbors: Sequence[dict[str, Any]],
    ranking_trace: dict[str, Any],
) -> dict[str, Any]:
    payload = {
        "memories": [_memory_payload(item) for item in selected_memories],
        "concepts": concepts,
        "relation_neighbors": neighbors,
    }
    return {
        "candidate_tokens_estimated": max(1, len(json.dumps(payload)) // 4),
        "truncated_items": int(ranking_trace.get("rejected_memory_count", 0)),
        "truncation_reason": "role_budget" if ranking_trace.get("rejected") else None,
    }


def _brief_memory_texts(
    memories: Sequence[dict[str, Any]],
    *,
    kinds: set[str],
    link_roles: set[str],
) -> list[str]:
    rendered: list[str] = []
    for memory in memories:
        memory_roles = set(memory.get("link_roles") or [])
        if str(memory.get("kind")) not in kinds and not (memory_roles & link_roles):
            continue
        rendered.append(_truncate(f"{memory.get('kind')}: {memory.get('text')}", 300))
    return rendered


def _claim_texts(
    concepts: Sequence[dict[str, Any]], claim_types: set[str]
) -> list[str]:
    rendered: list[str] = []
    for concept in concepts:
        ref = concept.get("ref") or concept.get("id")
        for claim in concept.get("claims", []):
            if claim.get("type") in claim_types and claim.get("status") == "active":
                rendered.append(_truncate(f"{ref} {claim.get('type')}: {claim.get('text')}", 300))
    return rendered


def _next_checks(pack: dict[str, Any]) -> list[str]:
    checks = []
    for anchor in pack.get("anchors", []):
        role = anchor.get("role")
        locator = anchor.get("locator")
        if role in {"implementation", "entrypoint", "test", "configuration"} and locator:
            checks.append(f"Check {role} anchor: {locator}")
    return list(dict.fromkeys(checks))[:3]


def _sources_from_graph_pack(pack: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {
            "kind": item["source_kind"],
            "id": item["source_id"],
            "section": item["input_section"],
        }
        for item in source_items_from_graph_pack(pack)
        if item.get("output_section") is not None
    ]


def _conflict_summary(item: object) -> str:
    if isinstance(item, dict):
        return str(item.get("summary") or item.get("reason") or item)
    return str(item)


def _source_section_for_memory(memory: dict[str, Any]) -> str:
    if "graph_linked_memory" in set(memory.get("why") or []):
        return "explicit_related"
    if memory.get("matched_lanes"):
        return "direct"
    return "implicit_related"


def _summary(*, memories: Sequence[dict[str, Any]], concepts: Sequence[dict[str, Any]]) -> str:
    return (
        f"Shellbrain found {len(memories)} memory source(s) and "
        f"{len(concepts)} concept source(s) for this recall query."
    )


def _memory_candidate_score(candidate: dict[str, Any]) -> float:
    base = float(candidate["score"])
    if candidate["link_roles"] & _HIGH_SIGNAL_LINK_ROLES:
        base += 1.0
    if "graph_linked_memory" in candidate["why"]:
        base += 0.75
    return base


def _memory_currentness_payload(candidate: dict[str, Any]) -> dict[str, str]:
    memory: Memory = candidate["memory"]
    roles = set(candidate["link_roles"])
    if "contradicted" in roles:
        return {
            "currentness": "conflicted",
            "temporal_reason": "contradicted link marks this memory as disputed",
        }
    if "changed" in roles:
        return {
            "currentness": "current",
            "temporal_reason": "changed link marks this memory as revision evidence",
        }
    if memory.kind.value == "change":
        return {
            "currentness": "current",
            "temporal_reason": "change memory may supersede older guidance",
        }
    if "validated" in roles:
        return {
            "currentness": "current",
            "temporal_reason": "validated link strengthens this memory",
        }
    if roles & {"failed_tactic_for", "warned_about"} or memory.kind.value == "failed_tactic":
        return {
            "currentness": "historical_warning",
            "temporal_reason": "failed tactic or warning should be treated as trap context",
        }
    return {
        "currentness": "current",
        "temporal_reason": "visible memory with no supersession signal in this pack",
    }


def _concept_currentness_payload(bundle: dict[str, Any]) -> dict[str, str]:
    statuses = Counter()
    for key in ("claims", "relations", "groundings", "memory_links"):
        for record in bundle[key]:
            statuses[record.lifecycle.status.value] += 1
    if statuses[ConceptLifecycleStatus.WRONG.value]:
        return {
            "currentness": "wrong",
            "temporal_reason": "one or more concept facets are marked wrong",
        }
    if statuses[ConceptLifecycleStatus.SUPERSEDED.value]:
        return {
            "currentness": "superseded",
            "temporal_reason": "one or more concept facets are marked superseded",
        }
    if statuses[ConceptLifecycleStatus.STALE.value]:
        return {
            "currentness": "stale",
            "temporal_reason": "one or more concept facets are marked stale",
        }
    if statuses[ConceptLifecycleStatus.MAYBE_STALE.value]:
        return {
            "currentness": "maybe_stale",
            "temporal_reason": "one or more concept facets are marked maybe_stale",
        }
    return {
        "currentness": "current",
        "temporal_reason": "all included concept facets are active",
    }


def _lifecycle_currentness_payload(
    lifecycle: Any, *, active_reason: str, validated_reason: str
) -> dict[str, str]:
    status = lifecycle.status.value
    if status == ConceptLifecycleStatus.ACTIVE.value:
        if lifecycle.validated_at is not None:
            return {
                "currentness": "current",
                "temporal_reason": validated_reason,
            }
        return {"currentness": "current", "temporal_reason": active_reason}
    return {
        "currentness": status,
        "temporal_reason": f"lifecycle status is {status}",
    }


def _is_trap_memory(candidate: dict[str, Any]) -> bool:
    memory: Memory = candidate["memory"]
    return memory.kind.value == "failed_tactic" or bool(
        candidate["link_roles"] & {"failed_tactic_for", "warned_about"}
    )


def _is_changed_or_contradicted_memory(candidate: dict[str, Any]) -> bool:
    return candidate["memory"].kind.value == "change" or bool(
        candidate["link_roles"] & {"changed", "contradicted"}
    )


def _is_validated_memory(candidate: dict[str, Any]) -> bool:
    return bool(candidate["link_roles"] & {"validated"})


def _is_fact_preference_change(candidate: dict[str, Any]) -> bool:
    return candidate["memory"].kind.value in {"fact", "preference", "change"}


def _problem_or_solution(candidate: dict[str, Any]) -> bool:
    return candidate["memory"].kind.value in {"problem", "solution"}


def _is_prior_case_query(query: str) -> bool:
    lowered = query.lower()
    return any(term in lowered for term in ("prior", "case", "before", "seen", "similar"))


def _rejected_memory(candidate: dict[str, Any], reason: str) -> dict[str, Any]:
    return {
        "memory_id": str(candidate["memory"].id),
        "reason": reason,
        "score": round(_memory_candidate_score(candidate), 6),
    }


def _orientation(concept: Concept, claims: Sequence[ConceptClaim]) -> str:
    definition = next(
        (
            claim.text
            for claim in claims
            if claim.claim_type.value == "definition" and _active(claim.lifecycle.status)
        ),
        None,
    )
    return _truncate(definition or f"{concept.name} is a {concept.kind.value} concept.", 600)


def _bundle_anchor_locators(bundle: dict[str, Any]) -> tuple[str, ...]:
    return tuple(_locator_text(anchor.locator_json) for anchor in bundle["anchors"])


def _locator_text(locator: dict[str, Any]) -> str:
    return " ".join(_locator_scalars(locator))


def _locator_scalars(value: object) -> tuple[str, ...]:
    scalars: list[str] = []

    def walk(item: object) -> None:
        if isinstance(item, dict):
            for key in sorted(item):
                walk(item[key])
            return
        if isinstance(item, (list, tuple)):
            for nested in item:
                walk(nested)
            return
        if item is None or isinstance(item, bool):
            return
        text = str(item).strip()
        if text:
            scalars.append(text)

    walk(value)
    return tuple(scalars)


def _extract_identifiers(text: str) -> tuple[str, ...]:
    patterns = (
        r"`([^`]+)`",
        r"\"([^\"]+)\"",
        r"'([^']+)'",
        r"(?:[\w.-]+/)+[\w./:-]+",
        r"[A-Za-z_][A-Za-z0-9_]*::[A-Za-z_][A-Za-z0-9_]*",
        r"[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_.]*",
        r"[A-Z][A-Z0-9_]{2,}",
        r"[A-Za-z][A-Za-z0-9_]*(?:Error|Exception|Timeout|Failure|Failed|Denied)",
        r"v?\d+\.\d+(?:\.\d+)?",
        r"[A-Z]{2,}-\d+|#\d+",
        r"/[A-Za-z0-9_{}:./-]+",
    )
    matches: list[str] = []
    for pattern in patterns:
        for match in re.findall(pattern, text):
            value = match if isinstance(match, str) else next((part for part in match if part), "")
            if value and value not in matches:
                matches.append(value)
    return tuple(matches)


def _tokenize(text: str) -> tuple[str, ...]:
    return tuple(re.findall(r"[a-z0-9_./:-]+", text.lower()))


def _useful_problem_part(value: str) -> bool:
    text = value.strip().lower()
    return bool(text and text not in _PLACEHOLDER_VALUES)


def _dedupe_reasons(reasons: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped = []
    for reason in reasons:
        key = json.dumps(reason, sort_keys=True, default=str)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(reason)
    return deduped


def _active(status: ConceptLifecycleStatus) -> bool:
    return status == ConceptLifecycleStatus.ACTIVE


def _active_concept(concept: Concept) -> bool:
    return concept.status == ConceptStatus.ACTIVE


def _lifecycle_multiplier(status: str) -> float:
    return {
        "active": 1.0,
        "maybe_stale": 0.65,
        "stale": 0.25,
        "superseded": 0.1,
        "wrong": 0.0,
    }[ConceptLifecycleStatus(status).value]


def _truncate_list(values: Sequence[str], limit: int) -> list[str]:
    return [value for value in values if value][:limit]


def _truncate(value: str, max_chars: int) -> str:
    collapsed = " ".join(str(value).split())
    if len(collapsed) <= max_chars:
        return collapsed
    return f"{collapsed[: max_chars - 3].rstrip()}..."


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def _duration_ms(started: float) -> int:
    return int((perf_counter() - started) * 1000)
