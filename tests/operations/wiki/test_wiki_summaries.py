"""Core coverage for generated Shellbrain Wiki summaries."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.core.entities.inner_agents import WikiSummarySettings
from app.core.entities.wiki_summaries import (
    WikiSummaryFreshness,
    WikiSummaryGenerationStatus,
    WikiSummaryInputSnapshot,
    WikiSummaryRecord,
    WikiSummarySourceVelocity,
    WikiSummaryTarget,
)
from app.core.policies.wiki_summary_freshness import determine_wiki_summary_freshness
from app.core.ports.host_apps.inner_agents import (
    WikiSummaryAgentRequest,
    WikiSummaryAgentResult,
)
from app.core.use_cases.wiki.summaries import (
    build_repo_summary_snapshot,
    refresh_wiki_summary,
    repo_summary_target,
)


NOW = datetime(2026, 6, 5, tzinfo=timezone.utc)


def test_wiki_summary_input_hash_is_stable_and_changes_with_source_facts() -> None:
    uow = _FakeUow()

    first = build_repo_summary_snapshot(repo_id="repo", uow=uow, now=NOW)
    second = build_repo_summary_snapshot(repo_id="repo", uow=uow, now=NOW)
    uow.memories.text = "A new fact changed the source facts."
    changed = build_repo_summary_snapshot(repo_id="repo", uow=uow, now=NOW)

    assert first.input_hash == second.input_hash
    assert first.input_hash != changed.input_hash


def test_wiki_summary_freshness_policy_returns_explicit_states() -> None:
    target = repo_summary_target("repo")
    snapshot = _snapshot(target=target, input_hash="hash-1")
    fresh_record = _record(
        target=target,
        input_hash="hash-1",
        status=WikiSummaryGenerationStatus.OK,
        generated_at=NOW - timedelta(days=1),
    )
    stale_record = _record(
        target=target,
        input_hash="hash-2",
        status=WikiSummaryGenerationStatus.OK,
        generated_at=NOW - timedelta(days=1),
    )
    expired_record = _record(
        target=target,
        input_hash="hash-1",
        status=WikiSummaryGenerationStatus.OK,
        generated_at=NOW - timedelta(days=20),
    )
    pending_record = _record(
        target=target,
        input_hash="hash-1",
        status=WikiSummaryGenerationStatus.PENDING,
        generated_at=None,
    )
    failed_record = _record(
        target=target,
        input_hash="hash-1",
        status=WikiSummaryGenerationStatus.FAILED,
        generated_at=NOW - timedelta(days=1),
    )

    assert (
        determine_wiki_summary_freshness(record=None, snapshot=snapshot, now=NOW)[0]
        == WikiSummaryFreshness.MISSING
    )
    assert (
        determine_wiki_summary_freshness(
            record=fresh_record, snapshot=snapshot, now=NOW
        )[0]
        == WikiSummaryFreshness.FRESH
    )
    assert (
        determine_wiki_summary_freshness(
            record=stale_record, snapshot=snapshot, now=NOW
        )[0]
        == WikiSummaryFreshness.STALE
    )
    assert (
        determine_wiki_summary_freshness(
            record=expired_record, snapshot=snapshot, now=NOW
        )[0]
        == WikiSummaryFreshness.EXPIRED
    )
    assert (
        determine_wiki_summary_freshness(
            record=pending_record, snapshot=snapshot, now=NOW
        )[0]
        == WikiSummaryFreshness.PENDING
    )
    assert (
        determine_wiki_summary_freshness(
            record=failed_record, snapshot=snapshot, now=NOW
        )[0]
        == WikiSummaryFreshness.FAILED
    )


def test_refresh_wiki_summary_saves_generated_body_with_provenance() -> None:
    uow = _FakeUow()
    runner = _FakeRunner()

    result = refresh_wiki_summary(
        target=repo_summary_target("repo"),
        uow_factory=lambda: uow,
        clock=_Clock(),
        settings=WikiSummarySettings(
            provider="codex",
            model="model",
            reasoning="medium",
            timeout_seconds=10,
            prompt_version="test",
            max_summary_chars=500,
        ),
        agent_runner=runner,
    )

    assert result.status == "ok"
    assert uow.wiki_summaries.saved_body == "Shellbrain knows one recent fact."
    assert uow.wiki_summaries.saved_snapshot is not None
    assert runner.request is not None
    assert runner.request.source_payload["recent_memories"][0]["text"] == uow.memories.text


class _Clock:
    def now(self) -> datetime:
        return NOW


class _FakeRunner:
    def __init__(self) -> None:
        self.request: WikiSummaryAgentRequest | None = None

    def run_wiki_summary(
        self, request: WikiSummaryAgentRequest
    ) -> WikiSummaryAgentResult:
        self.request = request
        return WikiSummaryAgentResult(
            status="ok",
            provider=request.provider,
            model=request.model,
            reasoning=request.reasoning,
            timeout_seconds=request.timeout_seconds,
            body="Shellbrain knows one recent fact.",
        )


class _FakeUow:
    def __init__(self) -> None:
        self.concepts = _FakeConceptsRepo()
        self.memories = _FakeMemoriesRepo()
        self.wiki_summaries = _FakeWikiSummaryRepo()

    def __enter__(self):
        return self

    def __exit__(self, *_exc) -> None:
        return None


class _FakeConceptsRepo:
    def list_concepts(self, *, repo_id: str, statuses):
        assert repo_id == "repo"
        return []


class _FakeMemoriesRepo:
    def __init__(self) -> None:
        self.text = "Shellbrain knows one recent fact."

    def list_recent(self, *, repo_id: str, statuses, limit: int):
        assert repo_id == "repo"
        return [_Memory(text=self.text)][:limit]


class _FakeWikiSummaryRepo:
    def __init__(self) -> None:
        self.saved_body: str | None = None
        self.saved_snapshot: WikiSummaryInputSnapshot | None = None

    def get(self, target):
        return None

    def acquire_refresh(self, **_kwargs):
        return True

    def record_success(self, *, snapshot, body, **_kwargs):
        self.saved_snapshot = snapshot
        self.saved_body = body

    def record_failure(self, **_kwargs):
        return None

    def list_existing_targets(self, *, repo_ids):
        return ()


class _Memory:
    def __init__(self, *, text: str) -> None:
        self.id = "memory-1"
        self.repo_id = "repo"
        self.kind = _Value("fact")
        self.scope = _Value("repo")
        self.text = text
        self.created_at = NOW
        self.status = _Value("active")


class _Value:
    def __init__(self, value: str) -> None:
        self.value = value


def _snapshot(*, target: WikiSummaryTarget, input_hash: str) -> WikiSummaryInputSnapshot:
    return WikiSummaryInputSnapshot(
        target=target,
        input_hash=input_hash,
        source_refs=(),
        source_payload={},
        source_velocity=WikiSummarySourceVelocity.NORMAL,
        popularity_score=1,
    )


def _record(
    *,
    target: WikiSummaryTarget,
    input_hash: str,
    status: WikiSummaryGenerationStatus,
    generated_at: datetime | None,
) -> WikiSummaryRecord:
    return WikiSummaryRecord(
        target=target,
        body="summary",
        input_hash=input_hash,
        source_refs=(),
        generation_status=status,
        generated_at=generated_at,
        model="model",
        prompt_version="test",
        last_error_code="error" if status == WikiSummaryGenerationStatus.FAILED else None,
        last_error_message=None,
        created_at=NOW,
        updated_at=NOW,
    )
