"""This module defines read-policy pipeline orchestration for context-pack generation."""

from typing import Any

from app.boot.read_policy import resolve_read_payload_defaults
from app.core.interfaces.repos import IKeywordRetrievalRepo, IMemoriesRepo, IReadPolicyRepo, ISemanticRetrievalRepo
from app.core.interfaces.retrieval import IVectorSearch
from app.core.policies.read_policy.context_pack_builder import assemble_context_pack
from app.core.policies.read_policy.expansion import expand_candidates
from app.core.policies.read_policy.fusion_rrf import fuse_with_rrf
from app.core.policies.read_policy.scenario_lift import derive_scenarios
from app.core.policies.read_policy.scoring import score_candidates
from app.core.policies.read_policy.seed_retrieval import retrieve_seeds
from app.core.policies.read_policy.utility_prior import apply_utility_prior


def build_context_pack(
    payload: dict[str, Any],
    *,
    keyword_retrieval: IKeywordRetrievalRepo,
    memories: IMemoriesRepo,
    semantic_retrieval: ISemanticRetrievalRepo,
    read_policy: IReadPolicyRepo,
    vector_search: IVectorSearch | None,
) -> dict[str, Any]:
    """This function orchestrates ratified read-policy stages into a final pack."""

    payload = _resolve_read_defaults(payload)
    seeds = retrieve_seeds(
        payload,
        semantic_retrieval=semantic_retrieval,
        keyword_retrieval=keyword_retrieval,
        vector_search=vector_search,
    )
    direct_candidates = fuse_with_rrf(seeds["semantic"], seeds["keyword"])
    expanded_candidates = expand_candidates(
        direct_candidates,
        payload,
        read_policy=read_policy,
        semantic_retrieval=semantic_retrieval,
    )
    bucketed_candidates = {
        "direct": direct_candidates,
        "explicit": expanded_candidates["explicit"],
        "implicit": expanded_candidates["implicit"],
    }
    scored_candidates = score_candidates(bucketed_candidates, payload)
    adjusted_candidates = {
        bucket_name: apply_utility_prior(candidates, payload)
        for bucket_name, candidates in scored_candidates.items()
    }
    pack = assemble_context_pack(adjusted_candidates, payload)
    hydrated_pack = _hydrate_pack_items(pack, memories)
    return derive_scenarios(hydrated_pack, payload)["pack"]


def _resolve_read_defaults(payload: dict[str, Any]) -> dict[str, Any]:
    """Resolve mode-based read defaults for callers that omit a limit."""

    return resolve_read_payload_defaults(payload)


def _hydrate_pack_items(pack: dict[str, Any], memories: IMemoriesRepo) -> dict[str, Any]:
    """Fill any missing display fields on selected pack items from the memories repository."""

    missing_memory_ids: list[str] = []
    seen_memory_ids: set[str] = set()
    for section_name in ("direct", "explicit_related", "implicit_related"):
        for item in pack[section_name]:
            memory_id = str(item["memory_id"])
            if ("kind" not in item or "text" not in item) and memory_id not in seen_memory_ids:
                seen_memory_ids.add(memory_id)
                missing_memory_ids.append(memory_id)

    if missing_memory_ids:
        hydrated_memories = {
            memory.id: memory
            for memory in memories.list_by_ids(missing_memory_ids)
        }
        for section_name in ("direct", "explicit_related", "implicit_related"):
            for item in pack[section_name]:
                if "kind" in item and "text" in item:
                    continue
                memory_id = str(item["memory_id"])
                memory = hydrated_memories.get(memory_id)
                if memory is None:
                    raise ValueError(f"Missing hydrated memory for context-pack item: {memory_id}")
                item.setdefault("kind", memory.kind.value)
                item.setdefault("text", memory.text)
                if "kind" not in item or "text" not in item:
                    raise ValueError(f"Incomplete hydrated memory for context-pack item: {memory_id}")

    return pack
