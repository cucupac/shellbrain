"""Evidence-link contracts for create execution."""

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from app.core.use_cases.memories.add.request import MemoryAddRequest
from app.core.entities.memories import MemoryKind, MemoryScope
from app.core.ports.embeddings.provider import IEmbeddingProvider
from app.core.use_cases.memories.add import execute_create_memory
from tests.operations._shared.id_generators import SequenceIdGenerator
from app.infrastructure.db.runtime.models.associations import (
    association_edge_evidence,
    association_edges,
)
from app.infrastructure.db.runtime.models.evidence import evidence_refs
from app.infrastructure.db.runtime.models.memories import memory_evidence
from app.infrastructure.db.runtime.uow import PostgresUnitOfWork


def test_create_attaches_all_memory_evidence_refs_exactly_once(
    uow_factory: Callable[[], PostgresUnitOfWork],
    stub_embedding_provider: IEmbeddingProvider,
    fetch_rows: Callable[..., list[dict[str, object]]],
) -> None:
    """create should always attach each evidence ref exactly once in memory_evidence."""

    request = MemoryAddRequest.model_validate(
        {
            "op": "create",
            "repo_id": "repo-a",
            "memory": {
                "text": "Evidence attachment memory.",
                "scope": "repo",
                "kind": "preference",
                "evidence_refs": ["session://1", "session://2"],
            },
        }
    )

    with uow_factory() as uow:
        result = execute_create_memory(
            request,
            uow,
            embedding_provider=stub_embedding_provider,
            embedding_model="stub-v1",
            id_generator=SequenceIdGenerator(),
        )
    memory_id = result.data["memory_id"]
    link_rows = fetch_rows(memory_evidence, memory_evidence.c.memory_id == memory_id)
    assert len(link_rows) == 2

    refs = fetch_rows(evidence_refs, evidence_refs.c.repo_id == "repo-a")
    assert {row["ref"] for row in refs} == {"session://1", "session://2"}
    assert {row["episode_event_id"] for row in refs} == {"session://1", "session://2"}


def test_create_association_links_attach_edge_evidence(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_memory: Callable[..., object],
    stub_embedding_provider: IEmbeddingProvider,
    fetch_rows: Callable[..., list[dict[str, object]]],
) -> None:
    """create with associations should always link evidence refs in association_edge_evidence."""

    seed_memory(
        memory_id="target-1",
        repo_id="repo-a",
        scope=MemoryScope.REPO,
        kind=MemoryKind.FACT,
        text_value="Association target.",
    )
    request = MemoryAddRequest.model_validate(
        {
            "op": "create",
            "repo_id": "repo-a",
            "memory": {
                "text": "Association source memory.",
                "scope": "repo",
                "kind": "problem",
                "links": {
                    "associations": [
                        {
                            "to_memory_id": "target-1",
                            "relation_type": "associated_with",
                        }
                    ]
                },
                "evidence_refs": ["session://1", "session://2"],
            },
        }
    )

    with uow_factory() as uow:
        result = execute_create_memory(
            request,
            uow,
            embedding_provider=stub_embedding_provider,
            embedding_model="stub-v1",
            id_generator=SequenceIdGenerator(),
        )
    memory_id = result.data["memory_id"]
    edges = fetch_rows(
        association_edges,
        association_edges.c.repo_id == "repo-a",
        association_edges.c.from_memory_id == memory_id,
        association_edges.c.to_memory_id == "target-1",
        association_edges.c.relation_type == "associated_with",
    )
    assert len(edges) == 1

    edge_id = str(edges[0]["id"])
    edge_evidence_rows = fetch_rows(
        association_edge_evidence,
        association_edge_evidence.c.edge_id == edge_id,
    )
    assert len(edge_evidence_rows) == 2


def test_parallel_create_reuses_one_evidence_ref_row_for_shared_event(
    uow_factory: Callable[[], PostgresUnitOfWork],
    stub_embedding_provider: IEmbeddingProvider,
    fetch_rows: Callable[..., list[dict[str, object]]],
) -> None:
    """parallel creates should always share one canonical evidence row for the same event id."""

    barrier = Barrier(2)

    def _create(text: str, id_prefix: str) -> str:
        request = MemoryAddRequest.model_validate(
            {
                "op": "create",
                "repo_id": "repo-a",
                "memory": {
                    "text": text,
                    "scope": "repo",
                    "kind": "fact",
                    "evidence_refs": ["session://1"],
                },
            }
        )

        with uow_factory() as uow:
            original_upsert_ref = uow.evidence.upsert_ref

            def _synchronized_upsert_ref(*, repo_id: str, ref: str):
                barrier.wait()
                return original_upsert_ref(repo_id=repo_id, ref=ref)

            uow.evidence.upsert_ref = _synchronized_upsert_ref
            result = execute_create_memory(
                request,
                uow,
                embedding_provider=stub_embedding_provider,
                embedding_model="stub-v1",
                id_generator=SequenceIdGenerator(prefix=id_prefix),
            )
        return str(result.data["memory_id"])

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(_create, "Parallel evidence writer A.", "parallel-a"),
            executor.submit(_create, "Parallel evidence writer B.", "parallel-b"),
        ]
        memory_ids = [future.result() for future in futures]

    refs = fetch_rows(evidence_refs, evidence_refs.c.repo_id == "repo-a")
    assert len(refs) == 1

    evidence_id = str(refs[0]["id"])
    link_rows = fetch_rows(
        memory_evidence, memory_evidence.c.evidence_id == evidence_id
    )
    assert len(link_rows) == 2
    assert {str(row["memory_id"]) for row in link_rows} == set(memory_ids)
