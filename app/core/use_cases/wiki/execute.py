"""Shellbrain Wiki read-only use cases."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable, Sequence
from urllib.parse import quote

from app.core.errors import DomainValidationError, ErrorCode, ErrorDetail
from app.core.entities.concepts import (
    Concept,
    ConceptClaim,
    ConceptEvidence,
    ConceptGrounding,
    ConceptMemoryLink,
    ConceptRelation,
)
from app.core.entities.evidence import EvidenceLinkView, EvidenceSource
from app.core.entities.memories import Memory
from app.core.ports.db.unit_of_work import IUnitOfWork
from app.core.policies.retrieval.bm25 import (
    BM25Document,
    admit_scored_documents,
    score_documents,
)
from app.core.policies.retrieval.lexical_query import (
    build_lexical_query,
    normalize_lexical_text,
)
from app.core.policies.retrieval.ontology_semantics import (
    lifecycle_currentness_payload,
    memory_currentness_payload,
)
from app.core.use_cases.wiki.request import (
    WikiAnchorRequest,
    WikiConceptFacetRequest,
    WikiConceptRequest,
    WikiEvidenceRequest,
    WikiIndexRequest,
    WikiMemoryRequest,
    WikiRepoRequest,
    WikiSearchRequest,
)
from app.core.use_cases.wiki.result import (
    WikiAnchorConceptLink,
    WikiAnchorPageResult,
    WikiClaimItem,
    WikiConceptFacetResult,
    WikiConceptGroup,
    WikiConceptListItem,
    WikiConceptPageResult,
    WikiConceptRef,
    WikiEvidenceItem,
    WikiEvidencePageResult,
    WikiEvidenceTargetItem,
    WikiGroundingItem,
    WikiHomeResult,
    WikiIndexResult,
    WikiMemoryConceptLink,
    WikiMemoryLinkItem,
    WikiMemoryNeighbor,
    WikiMemoryPageResult,
    WikiRepositoryItem,
    WikiRelationItem,
    WikiSearchHit,
    WikiSearchResult,
    WikiStatus,
    locator_text,
)
from app.core.use_cases.wiki.summaries import (
    build_concept_summary_snapshot,
    build_repo_summary_snapshot,
    wiki_summary_view,
)


_ACTIVE_CONCEPT_STATUSES = ("active",)
_SEARCH_LIMIT = 10


def wiki_index(request: WikiIndexRequest, uow: IUnitOfWork) -> WikiIndexResult:
    """Return the top-level repository index for Shellbrain Wiki."""

    repositories = tuple(
        WikiRepositoryItem(
            repo_id=summary.repo_id,
            repo_root=summary.repo_root,
            concept_count=summary.concept_count,
            memory_count=summary.memory_count,
            evidence_count=summary.evidence_count,
            last_seen_at=summary.last_seen_at,
            is_current=summary.repo_id == request.current_repo_id,
            popularity_score=_popularity_score(
                claim_count=summary.concept_count,
                memory_count=summary.memory_count,
                evidence_count=summary.evidence_count,
            ),
        )
        for summary in uow.repository_index.list_repositories()
    )
    ranked = tuple(_rank_repositories(repositories))
    if any(item.is_current for item in ranked):
        return WikiIndexResult(
            current_repo_id=request.current_repo_id,
            repositories=ranked,
        )
    current_item = WikiRepositoryItem(
        repo_id=request.current_repo_id,
        repo_root=None,
        concept_count=0,
        memory_count=0,
        evidence_count=0,
        last_seen_at=None,
        is_current=True,
        popularity_score=0,
    )
    return WikiIndexResult(
        current_repo_id=request.current_repo_id,
        repositories=tuple(_rank_repositories((current_item, *ranked))),
    )


def wiki_home(request: WikiRepoRequest, uow: IUnitOfWork) -> WikiHomeResult:
    """Return one repository's Shellbrain Wiki home page model."""

    now = request.now
    grouped: dict[str, list[WikiConceptListItem]] = defaultdict(list)
    for concept in uow.concepts.list_concepts(
        repo_id=request.repo_id, statuses=_ACTIVE_CONCEPT_STATUSES
    ):
        bundle = uow.concepts.get_concept_bundle(
            repo_id=request.repo_id, concept_ref=concept.id
        )
        grouped[concept.kind.value].append(_concept_list_item(concept, bundle))
    groups = tuple(
        WikiConceptGroup(kind=kind, concepts=tuple(_rank_by_popularity(items)))
        for kind, items in sorted(grouped.items())
    )
    summary_snapshot = build_repo_summary_snapshot(
        repo_id=request.repo_id, uow=uow, now=now
    )
    return WikiHomeResult(
        repo_id=request.repo_id,
        groups=groups,
        summary=wiki_summary_view(snapshot=summary_snapshot, uow=uow, now=now),
    )


def wiki_concept_page(
    request: WikiConceptRequest, uow: IUnitOfWork
) -> WikiConceptPageResult:
    """Return one concept wiki page model."""

    now = request.now
    bundle = _required_concept_bundle(request, uow)
    concept: Concept = bundle["concept"]
    claims = tuple(_claim_items(bundle))
    summary_snapshot = build_concept_summary_snapshot(
        repo_id=request.repo_id,
        concept_ref=concept.id,
        uow=uow,
        now=now,
    )
    return WikiConceptPageResult(
        id=concept.id,
        repo_id=concept.repo_id,
        slug=concept.slug,
        name=concept.name,
        kind=concept.kind.value,
        status=concept.status.value,
        definition=_active_definition(bundle["claims"]),
        status_rollup=_status_rollup(bundle),
        evidence_total=len(bundle["evidence"]),
        key_claims=tuple(
            claim for claim in claims if claim.status.status == "active"
        )[:3],
        summary=wiki_summary_view(snapshot=summary_snapshot, uow=uow, now=now),
    )


def wiki_concept_facet(
    request: WikiConceptFacetRequest, uow: IUnitOfWork
) -> WikiConceptFacetResult:
    """Return one progressively loaded concept facet."""

    bundle = _required_concept_bundle(request, uow)
    concept_ref = _concept_ref(bundle["concept"])
    if request.facet == "claims":
        return WikiConceptFacetResult(
            concept=concept_ref,
            repo_id=request.repo_id,
            facet=request.facet,
            claims=tuple(_claim_items(bundle)),
        )
    if request.facet == "relations":
        return WikiConceptFacetResult(
            concept=concept_ref,
            repo_id=request.repo_id,
            facet=request.facet,
            relations=tuple(_relation_items(bundle, uow)),
        )
    if request.facet == "memory-links":
        return WikiConceptFacetResult(
            concept=concept_ref,
            repo_id=request.repo_id,
            facet=request.facet,
            memory_links=tuple(_memory_link_items(bundle, uow)),
        )
    if request.facet == "groundings":
        return WikiConceptFacetResult(
            concept=concept_ref,
            repo_id=request.repo_id,
            facet=request.facet,
            groundings=tuple(_grounding_items(bundle)),
        )
    return WikiConceptFacetResult(
        concept=concept_ref,
        repo_id=request.repo_id,
        facet=request.facet,
        evidence=tuple(_concept_source_items(bundle["evidence"])),
    )


def wiki_memory_page(
    request: WikiMemoryRequest, uow: IUnitOfWork
) -> WikiMemoryPageResult:
    """Return one atomic memory wiki page model."""

    memory = _required_visible_memory(request, uow)
    concept_links = tuple(_memory_concept_links(request, memory.id, uow))
    link_roles = tuple(link.role for link in concept_links)
    evidence = tuple(_target_evidence_items(uow.evidence.resolve_evidence(
        repo_id=request.repo_id,
        targets=[_evidence_target("memory", memory.id)],
    )))
    return WikiMemoryPageResult(
        id=memory.id,
        repo_id=memory.repo_id,
        kind=memory.kind.value,
        text=memory.text,
        status=_memory_status(memory, link_roles),
        concept_links=concept_links,
        neighbors=tuple(_memory_neighbors(request, uow)),
        evidence=evidence,
    )


def wiki_memory_neighbors(
    request: WikiMemoryRequest, uow: IUnitOfWork
) -> WikiMemoryPageResult:
    """Return one memory page model focused on progressively loaded neighbors."""

    memory = _required_visible_memory(request, uow)
    return WikiMemoryPageResult(
        id=memory.id,
        repo_id=memory.repo_id,
        kind=memory.kind.value,
        text=memory.text,
        status=_memory_status(memory, ()),
        concept_links=(),
        neighbors=tuple(_memory_neighbors(request, uow)),
        evidence=(),
    )


def wiki_memory_sources(
    request: WikiMemoryRequest, uow: IUnitOfWork
) -> WikiMemoryPageResult:
    """Return one memory page model focused on progressively loaded evidence."""

    memory = _required_visible_memory(request, uow)
    evidence = tuple(_target_evidence_items(uow.evidence.resolve_evidence(
        repo_id=request.repo_id,
        targets=[_evidence_target("memory", memory.id)],
    )))
    return WikiMemoryPageResult(
        id=memory.id,
        repo_id=memory.repo_id,
        kind=memory.kind.value,
        text=memory.text,
        status=_memory_status(memory, ()),
        concept_links=(),
        neighbors=(),
        evidence=evidence,
    )


def wiki_anchor_page(
    request: WikiAnchorRequest, uow: IUnitOfWork
) -> WikiAnchorPageResult:
    """Return one anchor wiki page model."""

    anchor = uow.concepts.get_anchor(repo_id=request.repo_id, anchor_id=request.anchor_id)
    if anchor is None:
        _raise_not_found("Anchor", request.anchor_id, field="anchor_id")
    links = []
    for row in uow.concepts.find_concepts_for_anchor_ids(
        repo_id=request.repo_id, anchor_ids=[request.anchor_id]
    ):
        links.append(
            WikiAnchorConceptLink(
                concept=WikiConceptRef(
                    id=str(row["concept_id"]),
                    slug=str(row["slug"]),
                    name=str(row["name"]),
                    kind=str(row["kind"]),
                ),
                grounding_id=str(row["grounding_id"]),
                role=str(row["role"]),
                status=WikiStatus(
                    status=str(row["status"]),
                    confidence=float(row["confidence"]),
                ),
            )
        )
    return WikiAnchorPageResult(
        id=anchor.id,
        repo_id=anchor.repo_id,
        kind=anchor.kind.value,
        locator=locator_text(anchor.locator_json),
        status=anchor.status.value,
        concept_links=tuple(links),
    )


def wiki_evidence_page(
    request: WikiEvidenceRequest, uow: IUnitOfWork
) -> WikiEvidencePageResult:
    """Return one evidence source wiki page model."""

    evidence = uow.evidence.get_evidence_detail(
        repo_id=request.repo_id, evidence_id=request.evidence_id
    )
    if evidence is None:
        _raise_not_found("Evidence", request.evidence_id, field="evidence_id")
    return WikiEvidencePageResult(
        id=evidence.id,
        repo_id=evidence.repo_id,
        source_kind=evidence.source.source_kind.value,
        source_ref=_source_ref(evidence.source),
        created_at=_iso(evidence.created_at),
        linked_targets=tuple(
            WikiEvidenceTargetItem(
                link_id=target.link_id,
                target_type=target.target.target_type.value,
                target_id=target.target.target_id,
                role=target.role.value,
                created_at=_iso(target.created_at),
            )
            for target in evidence.linked_targets
        ),
    )


def wiki_search(request: WikiSearchRequest, uow: IUnitOfWork) -> WikiSearchResult:
    """Return bounded keyword-only wiki search results."""

    lexical_query = build_lexical_query(request.query)
    if not lexical_query.terms:
        return WikiSearchResult(repo_id=request.repo_id, query=request.query, hits=())
    concept_hits = _concept_search_hits(request, lexical_query, uow)
    memory_hits = _memory_search_hits(request, lexical_query, uow)
    return WikiSearchResult(
        repo_id=request.repo_id,
        query=request.query,
        hits=tuple((concept_hits + memory_hits)[: request.limit]),
    )


def _required_concept_bundle(
    request: WikiConceptRequest, uow: IUnitOfWork
) -> dict[str, Any]:
    bundle = uow.concepts.get_concept_bundle(
        repo_id=request.repo_id, concept_ref=request.concept_ref
    )
    if bundle is None:
        _raise_not_found("Concept", request.concept_ref, field="concept_ref")
    return bundle


def _required_visible_memory(request: WikiMemoryRequest, uow: IUnitOfWork) -> Memory:
    memory = uow.memories.get(request.memory_id)
    if memory is None or not memory.is_visible_in(request.repo_id):
        _raise_not_found("Memory", request.memory_id, field="memory_id")
    return memory


def _raise_not_found(label: str, value: str, *, field: str) -> None:
    raise DomainValidationError(
        [
            ErrorDetail(
                code=ErrorCode.NOT_FOUND,
                message=f"{label} not found: {value}",
                field=field,
            )
        ]
    )


def _concept_list_item(
    concept: Concept, bundle: dict[str, Any] | None
) -> WikiConceptListItem:
    claims = bundle["claims"] if bundle is not None else ()
    memory_links = bundle["memory_links"] if bundle is not None else ()
    evidence = bundle["evidence"] if bundle is not None else ()
    return WikiConceptListItem(
        id=concept.id,
        slug=concept.slug,
        name=concept.name,
        kind=concept.kind.value,
        status=concept.status.value,
        scope_note=concept.scope_note,
        definition=_active_definition(claims),
        claim_count=len(claims),
        memory_count=len(memory_links),
        evidence_count=len(evidence),
        popularity_score=_popularity_score(
            claim_count=len(claims),
            memory_count=len(memory_links),
            evidence_count=len(evidence),
        ),
    )


def _rank_by_popularity(
    concepts: Sequence[WikiConceptListItem],
) -> list[WikiConceptListItem]:
    return sorted(
        concepts,
        key=lambda item: (-item.popularity_score, item.name.lower(), item.slug),
    )


def _rank_repositories(
    repositories: Sequence[WikiRepositoryItem],
) -> list[WikiRepositoryItem]:
    return sorted(
        repositories,
        key=lambda item: (-item.popularity_score, item.repo_id.lower()),
    )


def _popularity_score(
    *, claim_count: int, memory_count: int, evidence_count: int
) -> int:
    return claim_count + memory_count + evidence_count


def _concept_ref(concept: Concept) -> WikiConceptRef:
    return WikiConceptRef(
        id=concept.id, slug=concept.slug, name=concept.name, kind=concept.kind.value
    )


def _claim_items(bundle: dict[str, Any]) -> list[WikiClaimItem]:
    evidence_counts = _evidence_counts(bundle["evidence"])
    claims: Sequence[ConceptClaim] = bundle["claims"]
    return [
        WikiClaimItem(
            id=claim.id,
            claim_type=claim.claim_type.value,
            text=claim.text,
            status=_lifecycle_status(
                claim.lifecycle,
                evidence_count=evidence_counts.get(("claim", claim.id), 0),
                active_reason="active concept claim",
                validated_reason="claim has validated_at evidence",
            ),
        )
        for claim in sorted(claims, key=lambda item: (item.claim_type.value, item.text))
    ]


def _relation_items(bundle: dict[str, Any], uow: IUnitOfWork) -> list[WikiRelationItem]:
    evidence_counts = _evidence_counts(bundle["evidence"])
    relations: Sequence[ConceptRelation] = bundle["relations"]
    endpoint_ids = tuple(
        dict.fromkeys(
            endpoint_id
            for relation in relations
            for endpoint_id in (relation.subject_concept_id, relation.object_concept_id)
        )
    )
    endpoints = {
        concept.id: _concept_ref(concept)
        for concept in uow.concepts.list_concepts_by_ids(
            repo_id=bundle["concept"].repo_id, concept_ids=endpoint_ids
        )
    }
    return [
        WikiRelationItem(
            id=relation.id,
            predicate=relation.predicate.value,
            subject=endpoints[relation.subject_concept_id],
            object=endpoints[relation.object_concept_id],
            status=_lifecycle_status(
                relation.lifecycle,
                evidence_count=evidence_counts.get(("relation", relation.id), 0),
                active_reason="active concept relation",
                validated_reason="relation has validated_at evidence",
            ),
        )
        for relation in sorted(
            relations,
            key=lambda item: (
                item.predicate.value,
                item.subject_concept_id,
                item.object_concept_id,
            ),
        )
        if relation.subject_concept_id in endpoints
        and relation.object_concept_id in endpoints
    ]


def _memory_link_items(
    bundle: dict[str, Any], uow: IUnitOfWork
) -> list[WikiMemoryLinkItem]:
    evidence_counts = _evidence_counts(bundle["evidence"])
    memory_links: Sequence[ConceptMemoryLink] = bundle["memory_links"]
    memories = {
        memory.id: memory
        for memory in uow.memories.list_by_ids(
            [link.memory_id for link in memory_links]
        )
    }
    return [
        WikiMemoryLinkItem(
            id=link.id,
            role=link.role.value,
            memory_id=link.memory_id,
            memory_kind=memories[link.memory_id].kind.value,
            memory_text=memories[link.memory_id].text,
            memory_status=memories[link.memory_id].status.value,
            status=_lifecycle_status(
                link.lifecycle,
                evidence_count=evidence_counts.get(("memory_link", link.id), 0),
                active_reason="active concept memory link",
                validated_reason="memory link has validated_at evidence",
            ),
        )
        for link in sorted(memory_links, key=lambda item: (item.role.value, item.memory_id))
        if link.memory_id in memories
    ]


def _grounding_items(bundle: dict[str, Any]) -> list[WikiGroundingItem]:
    evidence_counts = _evidence_counts(bundle["evidence"])
    anchors_by_id = {anchor.id: anchor for anchor in bundle["anchors"]}
    groundings: Sequence[ConceptGrounding] = bundle["groundings"]
    return [
        WikiGroundingItem(
            id=grounding.id,
            role=grounding.role.value,
            anchor_id=grounding.anchor_id,
            anchor_kind=anchors_by_id[grounding.anchor_id].kind.value,
            locator=locator_text(anchors_by_id[grounding.anchor_id].locator_json),
            anchor_status=anchors_by_id[grounding.anchor_id].status.value,
            status=_lifecycle_status(
                grounding.lifecycle,
                evidence_count=evidence_counts.get(("grounding", grounding.id), 0),
                active_reason="active concept grounding",
                validated_reason="grounding has validated_at evidence",
            ),
        )
        for grounding in sorted(groundings, key=lambda item: (item.role.value, item.anchor_id))
        if grounding.anchor_id in anchors_by_id
    ]


def _memory_concept_links(
    request: WikiMemoryRequest, memory_id: str, uow: IUnitOfWork
) -> Iterable[WikiMemoryConceptLink]:
    rows = uow.concepts.find_concepts_for_memory_ids(
        repo_id=request.repo_id, memory_ids=[memory_id]
    )
    concepts = {
        concept.id: concept
        for concept in uow.concepts.list_concepts_by_ids(
            repo_id=request.repo_id,
            concept_ids=[str(row["concept_id"]) for row in rows],
        )
    }
    for row in rows:
        concept = concepts.get(str(row["concept_id"]))
        if concept is None:
            continue
        yield WikiMemoryConceptLink(
            concept=_concept_ref(concept),
            role=str(row["role"]),
            status=WikiStatus(
                status=str(row["status"]),
                confidence=float(row["confidence"]),
            ),
        )


def _memory_neighbors(
    request: WikiMemoryRequest, uow: IUnitOfWork
) -> list[WikiMemoryNeighbor]:
    neighbor_rows: list[dict[str, str]] = []
    structural_rows = uow.read_policy.list_structural_memory_relation_rows(
        repo_id=request.repo_id,
        include_global=request.include_global,
        anchor_memory_id=request.memory_id,
        kinds=None,
        predicates=(
            "solved_by",
            "failed_with",
            "superseded_by",
            "explained_by_change",
        ),
    )
    for row in structural_rows:
        for memory_id in row["visible_memory_ids"]:
            if memory_id != request.memory_id:
                neighbor_rows.append(
                    {
                        "memory_id": memory_id,
                        "relation_type": str(row["predicate"]),
                    }
                )
    association_rows = uow.read_policy.list_association_edge_rows(
        repo_id=request.repo_id,
        include_global=request.include_global,
        anchor_memory_id=request.memory_id,
        kinds=None,
    )
    for row in association_rows:
        neighbor_rows.append(
            {
                "memory_id": str(row["memory_id"]),
                "relation_type": str(row["relation_type"]),
            }
        )
    neighbor_ids = tuple(dict.fromkeys(row["memory_id"] for row in neighbor_rows))
    memories = {memory.id: memory for memory in uow.memories.list_by_ids(neighbor_ids)}
    results: list[WikiMemoryNeighbor] = []
    seen: set[tuple[str, str]] = set()
    for row in neighbor_rows:
        memory = memories.get(row["memory_id"])
        key = (row["memory_id"], row["relation_type"])
        if memory is None or key in seen:
            continue
        seen.add(key)
        results.append(
            WikiMemoryNeighbor(
                memory_id=memory.id,
                kind=memory.kind.value,
                text=memory.text,
                status=memory.status.value,
                relation_type=row["relation_type"],
            )
        )
    return results


def _concept_source_items(evidence_items: Sequence[ConceptEvidence]) -> list[WikiEvidenceItem]:
    return [
        WikiEvidenceItem(
            evidence_id=evidence.evidence_id or evidence.id,
            target_type=evidence.target_type.value,
            target_id=evidence.target_id,
            role="supports",
            source_kind=evidence.evidence_kind.value,
            source_ref=_concept_source_ref(evidence),
            created_at=_iso(evidence.created_at),
        )
        for evidence in sorted(
            evidence_items,
            key=lambda item: (item.target_type.value, item.target_id, item.id),
        )
    ]


def _target_evidence_items(links: Sequence[EvidenceLinkView]) -> list[WikiEvidenceItem]:
    return [
        WikiEvidenceItem(
            evidence_id=str(link.evidence_id),
            target_type=link.target.target_type.value,
            target_id=link.target.target_id,
            role=link.role.value,
            source_kind=link.source.source_kind.value,
            source_ref=_source_ref(link.source),
            created_at=_iso(link.created_at),
        )
        for link in links
        if link.evidence_id is not None
    ]


def _concept_search_hits(
    request: WikiSearchRequest, lexical_query: Any, uow: IUnitOfWork
) -> list[WikiSearchHit]:
    rows = uow.concept_keyword_retrieval.list_concept_keyword_corpus(
        repo_id=request.repo_id,
        query_terms=lexical_query.terms,
        candidate_limit=max(request.limit * 10, 100),
    )
    ranked = _rank_keyword_rows(
        rows,
        lexical_query=lexical_query,
        id_key="concept_id",
        text_key="text",
        limit=_SEARCH_LIMIT,
    )
    concepts = uow.concepts.list_concepts_by_ids(
        repo_id=request.repo_id,
        concept_ids=[str(row["concept_id"]) for row in ranked],
    )
    return [
        WikiSearchHit(
            record_type="concept",
            id=concept.id,
            title=concept.name,
            subtitle=f"{concept.kind.value} concept",
            url=_repo_concept_url(request.repo_id, concept.slug),
        )
        for concept in concepts
    ]


def _memory_search_hits(
    request: WikiSearchRequest, lexical_query: Any, uow: IUnitOfWork
) -> list[WikiSearchHit]:
    rows = uow.keyword_retrieval.list_keyword_corpus(
        repo_id=request.repo_id,
        include_global=request.include_global,
        kinds=None,
        query_terms=lexical_query.terms,
        candidate_limit=max(request.limit * 10, 100),
    )
    ranked = _rank_keyword_rows(
        rows,
        lexical_query=lexical_query,
        id_key="memory_id",
        text_key="text",
        limit=_SEARCH_LIMIT,
    )
    memories = uow.memories.list_by_ids([str(row["memory_id"]) for row in ranked])
    return [
        WikiSearchHit(
            record_type="memory",
            id=memory.id,
            title=f"{memory.kind.value}: {memory.text[:80]}",
            subtitle=f"{memory.status.value} memory",
            url=_repo_memory_url(request.repo_id, memory.id),
        )
        for memory in memories
    ]


def _repo_concept_url(repo_id: str, concept_slug: str) -> str:
    return f"/repo/{_url_segment(repo_id)}/concept/{_url_segment(concept_slug)}"


def _repo_memory_url(repo_id: str, memory_id: str) -> str:
    return f"/repo/{_url_segment(repo_id)}/memory/{_url_segment(memory_id)}"


def _url_segment(value: str) -> str:
    return quote(value, safe="")


def _rank_keyword_rows(
    rows: Sequence[dict[str, Any]],
    *,
    lexical_query: Any,
    id_key: str,
    text_key: str,
    limit: int,
) -> list[dict[str, object]]:
    documents = [
        BM25Document(
            document_id=str(row[id_key]),
            terms=normalize_lexical_text(str(row[text_key])).terms_for(lexical_query),
        )
        for row in rows
    ]
    scored = score_documents(lexical_query.terms, documents)
    return admit_scored_documents(
        scored,
        mode="targeted",
        output_id_key=id_key,  # type: ignore[arg-type]
        coverage_threshold=0.25,
    )[:limit]


def _lifecycle_status(
    lifecycle: Any,
    *,
    evidence_count: int,
    active_reason: str,
    validated_reason: str,
) -> WikiStatus:
    currentness = lifecycle_currentness_payload(
        lifecycle,
        active_reason=active_reason,
        validated_reason=validated_reason,
    )
    return WikiStatus(
        status=lifecycle.status.value,
        confidence=lifecycle.confidence,
        currentness=currentness["currentness"],
        temporal_reason=currentness["temporal_reason"],
        evidence_count=evidence_count,
    )


def _memory_status(memory: Memory, link_roles: Iterable[str]) -> WikiStatus:
    currentness = memory_currentness_payload(
        status=memory.status, kind=memory.kind, link_roles=link_roles
    )
    return WikiStatus(
        status=memory.status.value,
        currentness=currentness["currentness"],
        temporal_reason=currentness["temporal_reason"],
    )


def _evidence_counts(evidence_items: Sequence[ConceptEvidence]) -> dict[tuple[str, str], int]:
    counts: dict[tuple[str, str], int] = {}
    for item in evidence_items:
        key = (item.target_type.value, item.target_id)
        counts[key] = counts.get(key, 0) + 1
    return counts


def _status_rollup(bundle: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for key in ("claims", "relations", "groundings", "memory_links"):
        for item in bundle[key]:
            status = item.lifecycle.status.value
            counts[status] = counts.get(status, 0) + 1
    return counts


def _active_definition(claims: Sequence[ConceptClaim]) -> str | None:
    for claim in sorted(claims, key=lambda item: item.text):
        if claim.claim_type.value == "definition" and claim.lifecycle.status.value == "active":
            return claim.text
    return None


def _evidence_target(target_type: str, target_id: str):
    from app.core.entities.evidence import EvidenceTarget, EvidenceTargetType

    return EvidenceTarget(target_type=EvidenceTargetType(target_type), target_id=target_id)


def _concept_source_ref(evidence: ConceptEvidence) -> str:
    return (
        evidence.transcript_ref
        or evidence.commit_ref
        or evidence.memory_id
        or evidence.anchor_id
        or evidence.note
        or evidence.id
    )


def _source_ref(source: EvidenceSource) -> str:
    return (
        source.episode_event_id
        or source.ref
        or source.anchor_id
        or source.memory_id
        or source.commit_ref
        or source.transcript_ref
        or source.note
        or ""
    )


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()
