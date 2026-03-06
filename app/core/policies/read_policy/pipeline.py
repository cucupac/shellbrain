"""This module defines read-policy pipeline orchestration for context-pack generation."""

from typing import Any

from app.core.interfaces.repos import IKeywordRetrievalRepo, IReadPolicyRepo, ISemanticRetrievalRepo
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
    semantic_retrieval: ISemanticRetrievalRepo,
    read_policy: IReadPolicyRepo,
) -> dict[str, Any]:
    """This function orchestrates ratified read-policy stages into a final pack."""

    seeds = retrieve_seeds(
        payload,
        semantic_retrieval=semantic_retrieval,
        keyword_retrieval=keyword_retrieval,
    )
    direct_candidates = fuse_with_rrf(seeds["semantic"], seeds["keyword"])
    expanded_candidates = expand_candidates(direct_candidates, payload, read_policy=read_policy)
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
    return derive_scenarios(pack, payload)["pack"]
