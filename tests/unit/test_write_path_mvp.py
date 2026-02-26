"""This test module covers write-path MVP behavior for create and update orchestration."""

from dataclasses import dataclass

from app.core.contracts.requests import MemoryCreateRequest, MemoryUpdateRequest
from app.core.entities.associations import AssociationEdge, AssociationObservation
from app.core.entities.evidence import EvidenceRef
from app.core.entities.facts import FactUpdate, ProblemAttempt
from app.core.entities.memory import Memory, MemoryKind, MemoryScope
from app.core.entities.utility import UtilityObservation
from app.core.use_cases.create_memory import execute_create_memory
from app.core.use_cases.update_memory import execute_update_memory


@dataclass
class _MemoriesRepo:
    """This helper class provides a minimal in-memory memories repository for tests."""

    store: dict[str, Memory]
    embeddings: dict[str, dict[str, object]]

    def create(self, memory: Memory) -> None:
        """This method inserts a memory entity into the in-memory store."""

        self.store[memory.id] = memory

    def get(self, memory_id: str) -> Memory | None:
        """This method loads a memory entity by id from the in-memory store."""

        return self.store.get(memory_id)

    def set_archived(self, *, memory_id: str, archived: bool) -> bool:
        """This method toggles the archived flag for a stored memory."""

        memory = self.store.get(memory_id)
        if memory is None:
            return False
        self.store[memory_id] = Memory(
            id=memory.id,
            repo_id=memory.repo_id,
            scope=memory.scope,
            kind=memory.kind,
            text=memory.text,
            create_confidence=memory.create_confidence,
            archived=archived,
        )
        return True

    def upsert_embedding(self, *, memory_id: str, model: str, vector) -> None:
        """This method stores the latest embedding payload for a memory id."""

        self.embeddings[memory_id] = {"model": model, "vector": list(vector)}


@dataclass
class _ExperiencesRepo:
    """This helper class provides a minimal in-memory experiences repository for tests."""

    attempts: list[ProblemAttempt]
    fact_updates: list[FactUpdate]

    def create_problem_attempt(self, attempt: ProblemAttempt) -> None:
        """This method appends a problem-attempt record in memory."""

        self.attempts.append(attempt)

    def create_fact_update(self, fact_update: FactUpdate) -> None:
        """This method appends a fact-update record in memory."""

        self.fact_updates.append(fact_update)


@dataclass
class _AssociationsRepo:
    """This helper class provides a minimal in-memory associations repository for tests."""

    edges: dict[tuple[str, str, str, str], AssociationEdge]
    observations: list[AssociationObservation]

    def upsert_edge(self, edge: AssociationEdge) -> AssociationEdge:
        """This method stores or replaces association edges by unique business key."""

        key = (edge.repo_id, edge.from_memory_id, edge.to_memory_id, edge.relation_type.value)
        existing = self.edges.get(key)
        if existing is not None:
            return existing
        self.edges[key] = edge
        return edge

    def append_observation(self, observation: AssociationObservation) -> None:
        """This method appends an association observation row."""

        self.observations.append(observation)


@dataclass
class _UtilityRepo:
    """This helper class provides a minimal in-memory utility repository for tests."""

    observations: list[UtilityObservation]

    def append_observation(self, observation: UtilityObservation) -> None:
        """This method appends a utility observation record in memory."""

        self.observations.append(observation)


@dataclass
class _EvidenceRepo:
    """This helper class provides a minimal in-memory evidence repository for tests."""

    refs: dict[tuple[str, str], EvidenceRef]
    memory_links: list[tuple[str, str]]
    edge_links: list[tuple[str, str]]

    def upsert_ref(self, repo_id: str, ref: str) -> EvidenceRef:
        """This method inserts or returns an in-memory evidence reference."""

        key = (repo_id, ref)
        existing = self.refs.get(key)
        if existing is not None:
            return existing
        evidence = EvidenceRef(id=f"evidence:{len(self.refs) + 1}", repo_id=repo_id, ref=ref)
        self.refs[key] = evidence
        return evidence

    def link_memory_evidence(self, memory_id: str, evidence_id: str) -> None:
        """This method appends a memory-evidence link in memory."""

        self.memory_links.append((memory_id, evidence_id))

    def link_association_edge_evidence(self, edge_id: str, evidence_id: str) -> None:
        """This method appends an edge-evidence link in memory."""

        self.edge_links.append((edge_id, evidence_id))


class _NoopRepo:
    """This helper class provides no-op methods for unused repository slots in tests."""

    def __getattr__(self, _: str):  # pragma: no cover - defensive fallback
        """This method returns a callable no-op for undefined repository methods."""

        return lambda *args, **kwargs: None


class _FakeUow:
    """This helper class provides a minimal unit-of-work facade for use-case tests."""

    def __init__(self) -> None:
        """This method initializes all in-memory repositories required by the use-cases."""

        self.memories = _MemoriesRepo(store={}, embeddings={})
        self.experiences = _ExperiencesRepo(attempts=[], fact_updates=[])
        self.associations = _AssociationsRepo(edges={}, observations=[])
        self.utility = _UtilityRepo(observations=[])
        self.evidence = _EvidenceRepo(refs={}, memory_links=[], edge_links=[])
        self.episodes = _NoopRepo()
        self.semantic_retrieval = _NoopRepo()
        self.keyword_retrieval = _NoopRepo()


def test_create_problem_commits_memory_and_evidence() -> None:
    """This test verifies create(problem) writes memory rows and evidence links."""

    uow = _FakeUow()
    request = MemoryCreateRequest.model_validate(
        {
            "op": "create",
            "repo_id": "repo-a",
            "memory": {
                "text": "The API times out under load.",
                "scope": "repo",
                "kind": "problem",
                "confidence": 0.8,
                "evidence_refs": ["session://abc"],
            },
        }
    )

    result = execute_create_memory(request, uow)
    assert result.status == "ok"
    memory_id = result.data["memory_id"]
    assert uow.memories.get(memory_id) is not None
    assert memory_id in uow.memories.embeddings
    assert len(uow.memories.embeddings[memory_id]["vector"]) == 32
    assert len(uow.evidence.memory_links) == 1


def test_create_solution_without_problem_id_fails_semantic_gate() -> None:
    """This test verifies create(solution) requires links.problem_id at semantic validation."""

    uow = _FakeUow()
    request = MemoryCreateRequest.model_validate(
        {
            "op": "create",
            "repo_id": "repo-a",
            "memory": {
                "text": "Increase client timeout to 90s.",
                "scope": "repo",
                "kind": "solution",
                "confidence": 0.7,
                "evidence_refs": ["session://abc"],
            },
        }
    )

    result = execute_create_memory(request, uow)
    assert result.status == "error"
    assert result.errors[0].code.value == "semantic_error"


def test_update_archive_state_dry_run_does_not_mutate() -> None:
    """This test verifies dry-run update returns side effects without mutating data."""

    uow = _FakeUow()
    target = Memory(
        id="m-1",
        repo_id="repo-a",
        scope=MemoryScope.REPO,
        kind=MemoryKind.FACT,
        text="Feature flag is enabled.",
    )
    uow.memories.create(target)
    request = MemoryUpdateRequest.model_validate(
        {
            "op": "update",
            "repo_id": "repo-a",
            "memory_id": "m-1",
            "mode": "dry_run",
            "update": {"type": "archive_state", "archived": True},
        }
    )

    result = execute_update_memory(request, uow)
    assert result.status == "ok"
    assert result.data["accepted"] is True
    assert uow.memories.get("m-1").archived is False


def test_fact_update_link_requires_change_memory() -> None:
    """This test verifies fact_update_link enforces memory_id kind == change at integrity gate."""

    uow = _FakeUow()
    uow.memories.create(
        Memory(
            id="old-fact",
            repo_id="repo-a",
            scope=MemoryScope.REPO,
            kind=MemoryKind.FACT,
            text="Old fact.",
        )
    )
    uow.memories.create(
        Memory(
            id="new-fact",
            repo_id="repo-a",
            scope=MemoryScope.REPO,
            kind=MemoryKind.FACT,
            text="New fact.",
        )
    )
    uow.memories.create(
        Memory(
            id="not-change",
            repo_id="repo-a",
            scope=MemoryScope.REPO,
            kind=MemoryKind.PROBLEM,
            text="Wrong kind for change_id.",
        )
    )

    request = MemoryUpdateRequest.model_validate(
        {
            "op": "update",
            "repo_id": "repo-a",
            "memory_id": "not-change",
            "mode": "commit",
            "update": {
                "type": "fact_update_link",
                "old_fact_id": "old-fact",
                "new_fact_id": "new-fact",
            },
        }
    )

    result = execute_update_memory(request, uow)
    assert result.status == "error"
    assert any(error.code.value == "integrity_error" for error in result.errors)
