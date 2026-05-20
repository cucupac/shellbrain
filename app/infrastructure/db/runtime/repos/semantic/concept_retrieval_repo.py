"""Concept retrieval adapters for keyword and semantic lanes."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Sequence

from sqlalchemy import select

from app.core.ports.db.retrieval_repositories import (
    IConceptKeywordRetrievalRepo,
    IConceptSemanticRetrievalRepo,
)
from app.infrastructure.db.runtime.models.concepts import (
    anchors,
    concept_aliases,
    concept_claims,
    concept_embeddings,
    concept_groundings,
    concepts,
)


class ConceptKeywordRetrievalRepo(IConceptKeywordRetrievalRepo):
    """Provide active concept aggregate text rows for core lexical ranking."""

    def __init__(self, session) -> None:
        """Store the active DB session."""

        self._session = session

    def list_concept_keyword_corpus(
        self,
        *,
        repo_id: str,
        query_terms: Sequence[str] | None = None,
        candidate_limit: int | None = None,
    ) -> Sequence[dict[str, Any]]:
        """Return one aggregate lexical document per active concept."""

        concept_rows = (
            self._session.execute(
                select(
                    concepts.c.id,
                    concepts.c.slug,
                    concepts.c.name,
                    concepts.c.kind,
                    concepts.c.scope_note,
                )
                .where(concepts.c.repo_id == repo_id, concepts.c.status == "active")
                .order_by(concepts.c.id.asc())
            )
            .mappings()
            .all()
        )
        parts_by_id: dict[str, list[str]] = defaultdict(list)
        ordered_ids: list[str] = []
        for row in concept_rows:
            concept_id = str(row["id"])
            ordered_ids.append(concept_id)
            _extend_parts(
                parts_by_id[concept_id],
                row["slug"],
                row["name"],
                row["kind"],
                row["scope_note"],
            )

        self._append_alias_parts(repo_id=repo_id, parts_by_id=parts_by_id)
        self._append_claim_parts(repo_id=repo_id, parts_by_id=parts_by_id)
        self._append_grounding_parts(repo_id=repo_id, parts_by_id=parts_by_id)

        rows = [
            {"concept_id": concept_id, "text": " ".join(parts_by_id[concept_id])}
            for concept_id in ordered_ids
            if parts_by_id[concept_id]
        ]
        filtered_rows = _filter_candidate_rows(rows, query_terms=query_terms)
        if candidate_limit is not None and candidate_limit > 0:
            return filtered_rows[: int(candidate_limit)]
        return filtered_rows

    def _append_alias_parts(
        self, *, repo_id: str, parts_by_id: dict[str, list[str]]
    ) -> None:
        rows = (
            self._session.execute(
                select(concept_aliases.c.concept_id, concept_aliases.c.alias)
                .select_from(
                    concept_aliases.join(
                        concepts, concepts.c.id == concept_aliases.c.concept_id
                    )
                )
                .where(
                    concept_aliases.c.repo_id == repo_id,
                    concepts.c.repo_id == repo_id,
                    concepts.c.status == "active",
                )
                .order_by(concept_aliases.c.concept_id.asc(), concept_aliases.c.alias.asc())
            )
            .mappings()
            .all()
        )
        for row in rows:
            _extend_parts(parts_by_id[str(row["concept_id"])], row["alias"])

    def _append_claim_parts(
        self, *, repo_id: str, parts_by_id: dict[str, list[str]]
    ) -> None:
        rows = (
            self._session.execute(
                select(
                    concept_claims.c.concept_id,
                    concept_claims.c.claim_type,
                    concept_claims.c.text,
                )
                .select_from(
                    concept_claims.join(
                        concepts, concepts.c.id == concept_claims.c.concept_id
                    )
                )
                .where(
                    concept_claims.c.repo_id == repo_id,
                    concept_claims.c.status == "active",
                    concepts.c.repo_id == repo_id,
                    concepts.c.status == "active",
                )
                .order_by(
                    concept_claims.c.concept_id.asc(),
                    concept_claims.c.claim_type.asc(),
                    concept_claims.c.text.asc(),
                )
            )
            .mappings()
            .all()
        )
        for row in rows:
            _extend_parts(
                parts_by_id[str(row["concept_id"])], row["claim_type"], row["text"]
            )

    def _append_grounding_parts(
        self, *, repo_id: str, parts_by_id: dict[str, list[str]]
    ) -> None:
        rows = (
            self._session.execute(
                select(
                    concept_groundings.c.concept_id,
                    concept_groundings.c.role,
                    anchors.c.kind,
                    anchors.c.locator_json,
                )
                .select_from(
                    concept_groundings.join(
                        concepts, concepts.c.id == concept_groundings.c.concept_id
                    ).join(anchors, anchors.c.id == concept_groundings.c.anchor_id)
                )
                .where(
                    concept_groundings.c.repo_id == repo_id,
                    concept_groundings.c.status == "active",
                    concepts.c.repo_id == repo_id,
                    concepts.c.status == "active",
                    anchors.c.repo_id == repo_id,
                    anchors.c.status == "active",
                )
                .order_by(
                    concept_groundings.c.concept_id.asc(),
                    concept_groundings.c.role.asc(),
                    anchors.c.kind.asc(),
                )
            )
            .mappings()
            .all()
        )
        for row in rows:
            _extend_parts(
                parts_by_id[str(row["concept_id"])],
                row["role"],
                row["kind"],
                *_locator_scalars(row["locator_json"]),
            )


class ConceptSemanticRetrievalRepo(IConceptSemanticRetrievalRepo):
    """Provide semantic retrieval candidates from aggregate concept embeddings."""

    def __init__(self, session) -> None:
        """Store the active DB session."""

        self._session = session

    def query_concepts_semantic(
        self,
        *,
        repo_id: str,
        query_vector: Sequence[float],
        limit: int,
        query_model: str | None = None,
    ) -> Sequence[dict[str, Any]]:
        """Return active concept candidates and similarity scores."""

        if not query_vector:
            return []
        query_values = [float(value) for value in query_vector]
        if _is_zero_vector(query_values):
            return []

        distance = concept_embeddings.c.vector.cosine_distance(query_values)
        score = (1.0 - distance).label("score")
        stmt = (
            select(concepts.c.id.label("concept_id"), score)
            .select_from(
                concepts.join(
                    concept_embeddings,
                    concept_embeddings.c.concept_id == concepts.c.id,
                )
            )
            .where(
                concepts.c.repo_id == repo_id,
                concepts.c.status == "active",
                concept_embeddings.c.repo_id == repo_id,
                concept_embeddings.c.dim == len(query_values),
            )
            .order_by(distance.asc(), concepts.c.id.asc())
            .limit(limit)
        )
        if query_model is not None:
            stmt = stmt.where(concept_embeddings.c.model == query_model)

        return [
            {"concept_id": str(row["concept_id"]), "score": float(row["score"])}
            for row in self._session.execute(stmt).mappings().all()
            if _is_positive_score(row["score"])
        ]


def _extend_parts(parts: list[str], *values: object) -> None:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            parts.append(text)


def _filter_candidate_rows(
    rows: list[dict[str, Any]], *, query_terms: Sequence[str] | None
) -> list[dict[str, Any]]:
    if not query_terms:
        return rows
    terms = [str(term).strip().lower() for term in query_terms if str(term).strip()]
    if not terms:
        return rows
    matched = [
        row for row in rows if any(term in str(row["text"]).lower() for term in terms)
    ]
    return matched or rows


def _locator_scalars(value: object) -> tuple[str, ...]:
    scalars: list[str] = []

    def _walk(item: object) -> None:
        if isinstance(item, dict):
            for key in sorted(item):
                _walk(item[key])
            return
        if isinstance(item, (list, tuple)):
            for value in item:
                _walk(value)
            return
        if item is None or isinstance(item, bool):
            return
        text = str(item).strip()
        if text:
            scalars.append(text)

    _walk(value)
    return tuple(scalars)


def _is_zero_vector(values: Sequence[float]) -> bool:
    return all(float(value) == 0.0 for value in values)


def _is_positive_score(value: object) -> bool:
    try:
        return float(value) > 0.0
    except (TypeError, ValueError):
        return False
