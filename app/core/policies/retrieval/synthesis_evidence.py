"""Select bounded recall evidence while preserving related memory cases."""

from copy import deepcopy
import re
from collections.abc import Callable
from typing import Any

from app.core.entities.recall_settings import RecallSettings


def _rank_details(items: list[dict], query: str) -> list[dict]:
    terms = set(re.findall(r"[a-z0-9_]+", query.lower()))

    def score(item: dict) -> tuple:
        text = str(item.get("text", item.get("locator", ""))).lower()
        overlap = sum(term in text for term in terms)
        # Rank for relevance without deleting lifecycle qualifications.
        return (-overlap, item.get("status") != "active", not item.get("validated_at"))

    return sorted(items, key=score)


def _memory_groups(pack: dict) -> list[list[dict]]:
    memories = pack.get("memories", [])
    neighbors = {m["id"]: set() for m in memories}
    for relation in pack.get("memory_relations", []):
        left, right = relation["subject_memory_id"], relation["object_memory_id"]
        if left not in neighbors or right not in neighbors:
            raise ValueError("Recall relationship references a missing memory")
        neighbors[left].add(right)
        neighbors[right].add(left)
    groups, seen = [], set()
    for memory in memories:
        if memory["id"] in seen:
            continue
        pending, members = [memory["id"]], set()
        while pending:
            identifier = pending.pop()
            if identifier in members:
                continue
            members.add(identifier)
            pending.extend(neighbors[identifier] - members)
        seen.update(members)
        groups.append([m for m in memories if m["id"] in members])
    return groups


def _prune_references(pack: dict) -> None:
    ids = {m["id"] for m in pack.get("memories", [])}
    pack["memory_relations"] = [
        r
        for r in pack.get("memory_relations", [])
        if r["subject_memory_id"] in ids and r["object_memory_id"] in ids
    ]
    concepts = pack.get("concepts", []) + pack.get("relation_neighbors", [])
    concept_ids = {c["id"] for c in concepts}
    for concept in concepts:
        concept["memory_links"] = [
            link for link in concept.get("memory_links", []) if link["memory_id"] in ids
        ]
        concept["relations"] = [
            link
            for link in concept.get("relations", [])
            if link["neighbor_id"] in concept_ids
        ]
    # Top-level anchors are derived from the selected concept groundings. Keeping
    # them here would duplicate evidence and retain anchors of removed concepts.
    pack.pop("anchors", None)


def select_synthesis_evidence(pack: dict, query: str, settings: RecallSettings) -> dict:
    """Select recall-only evidence without changing the stored graph or read path."""
    result = deepcopy(pack)
    selected = []
    for group in _memory_groups(result):
        if len(selected) + len(group) <= settings.max_memories:
            selected.extend(group)
    ids = {m["id"] for m in selected}
    result["memories"] = [m for m in result.get("memories", []) if m["id"] in ids]
    for key, limit in [
        ("concepts", settings.max_concepts),
        ("relation_neighbors", settings.max_neighbor_concepts),
    ]:
        result[key] = result.get(key, [])[:limit]
        for concept in result[key]:
            concept["claims"] = _rank_details(concept.get("claims", []), query)[
                : settings.max_claims_per_concept
            ]
            concept["groundings"] = _rank_details(concept.get("groundings", []), query)[
                : settings.max_groundings_per_concept
            ]
            concept.pop("why_selected", None)
    _prune_references(result)
    return result


def fit_synthesis_evidence(
    pack: dict[str, Any], *, max_tokens: int, measure: Callable[[dict], int]
) -> dict[str, Any]:
    """Remove complete low-priority units until the rendered estimate fits."""
    result = deepcopy(pack)
    while measure(result) > max_tokens:
        if result.get("relation_neighbors"):
            result["relation_neighbors"].pop()
        elif len(result.get("concepts", [])) > 1:
            result["concepts"].pop()
        elif len(_memory_groups(result)) > 1:
            removed = {m["id"] for m in _memory_groups(result)[-1]}
            result["memories"] = [
                m for m in result["memories"] if m["id"] not in removed
            ]
        elif result.get("concepts"):
            result["concepts"].pop()
        elif result.get("memories"):
            result["memories"] = []
        elif result.get("conflicts"):
            result["conflicts"] = []
        else:
            raise ValueError("Recall query and instructions exceed the input budget")
        _prune_references(result)
    had_evidence = (
        pack.get("memories") or pack.get("concepts") or pack.get("relation_neighbors")
    )
    if had_evidence and not (
        result.get("memories")
        or result.get("concepts")
        or result.get("relation_neighbors")
    ):
        raise ValueError("Recall input budget cannot fit a complete evidence unit")
    return result
