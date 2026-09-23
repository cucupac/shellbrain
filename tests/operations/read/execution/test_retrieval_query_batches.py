"""Database query reductions preserve visibility, ranking, and relation order."""

import pytest
from sqlalchemy import desc, event, func, select

from app.core.policies.retrieval.expansion import (
    select_structural_memory_relation_neighbors,
)
from app.infrastructure.db.runtime.models.memories import memories
from app.infrastructure.db.runtime.repos.memory_visibility import visible_memory_filters
from app.infrastructure.db.runtime.repos.semantic.keyword_retrieval_repo import (
    _ENGLISH_REGCONFIG,
    _websearch_or_query,
)


def test_structural_batch_has_two_queries_and_stable_visible_neighbors(
    uow_factory,
    seed_read_memory,
    seed_structural_memory_relation,
):
    for memory_id, repo_id in [("a", "repo-a"), ("b", "repo-a"), ("hidden", "repo-b")]:
        seed_read_memory(
            memory_id=memory_id,
            repo_id=repo_id,
            scope="repo",
            kind="fact",
            text_value="routing state",
        )
    for relation_id, predicate, target, status in [
        ("r1", "superseded_by", "b", "active"),
        ("r2", "explained_by_change", "b", "active"),
        ("r3", "superseded_by", "hidden", "active"),
        ("r4", "explained_by_change", "hidden", "archived"),
    ]:
        seed_structural_memory_relation(
            relation_id=relation_id,
            repo_id="repo-a",
            subject_memory_id="a",
            predicate=predicate,
            object_memory_id=target,
            status=status,
        )
    with uow_factory() as uow:
        statements = []
        connection = uow.read_policy._session.connection()

        def count(*args):
            statements.append(args[2])

        event.listen(connection, "before_cursor_execute", count)
        try:
            args = dict(
                repo_id="repo-a",
                include_global=False,
                kinds=["fact"],
                predicates=["explained_by_change", "superseded_by"],
            )
            assert (
                uow.read_policy.list_structural_memory_relation_rows(
                    **args, anchor_memory_ids=[]
                )
                == []
            )
            assert statements == []
            rows = uow.read_policy.list_structural_memory_relation_rows(
                **args, anchor_memory_ids=["b", "a", "a"]
            )
            assert len(statements) == 2
            assert [(r["predicate"], r["object_memory_id"]) for r in rows] == [
                ("explained_by_change", "b"),
                ("superseded_by", "b"),
                ("superseded_by", "hidden"),
            ]
            assert all("hidden" not in r["visible_memory_ids"] for r in rows)
            assert select_structural_memory_relation_neighbors(
                rows, anchor_memory_id="a"
            ) == [
                {
                    "memory_id": "b",
                    "relation_type": "superseded_by",
                    "expansion_type": "fact_update",
                }
            ]
            assert rows == uow.read_policy.list_structural_memory_relation_rows(
                **args, anchor_memory_ids=["a", "b"]
            )
        finally:
            event.remove(connection, "before_cursor_execute", count)


@pytest.mark.parametrize("include_global", [False, True])
@pytest.mark.parametrize(
    "terms", [["router"], ["router", "discovery"], ["QZX917"], ["découverte"]]
)
def test_indexed_prefilter_preserves_full_text_rank_and_visibility(
    uow_factory,
    seed_read_memory,
    include_global,
    terms,
):
    for memory_id, repo_id, scope, kind, status, text in [
        ("a", "repo-a", "repo", "fact", "active", "router discovery"),
        ("b", "repo-a", "repo", "fact", "maybe_stale", "router discovery"),
        ("c", "repo-b", "global", "fact", "active", "router router"),
        ("d", "repo-b", "repo", "fact", "active", "router router router"),
        ("e", "repo-a", "repo", "problem", "active", "router"),
        ("f", "repo-a", "repo", "fact", "archived", "router"),
        ("g", "repo-a", "repo", "fact", "active", "découverte du routeur"),
    ]:
        seed_read_memory(
            memory_id=memory_id,
            repo_id=repo_id,
            scope=scope,
            kind=kind,
            status=status,
            text_value=text,
        )
    with uow_factory() as uow:
        vector = func.to_tsvector(_ENGLISH_REGCONFIG, memories.c.text)
        query = func.websearch_to_tsquery(
            _ENGLISH_REGCONFIG, _websearch_or_query(terms)
        )
        expected = list(
            uow.keyword_retrieval._session.execute(
                select(memories.c.id)
                .where(
                    *visible_memory_filters(
                        repo_id="repo-a", include_global=include_global, kinds=["fact"]
                    ),
                    vector.op("@@")(query),
                )
                .order_by(desc(func.ts_rank_cd(vector, query)), memories.c.id)
                .limit(2)
            ).scalars()
        )
        actual = uow.keyword_retrieval._ranked_fts_rows(
            repo_id="repo-a",
            include_global=include_global,
            kinds=["fact"],
            query_terms=terms,
            candidate_limit=2,
        )
        assert [row["memory_id"] for row in actual] == expected
