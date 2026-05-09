"""Record-write contracts for write-summary telemetry."""

from __future__ import annotations

from collections.abc import Callable

from app.core.entities.memories import MemoryKind, MemoryScope
import pytest
from tests.operations._shared.handler_calls import handle_create, handle_update
from app.infrastructure.db.uow import PostgresUnitOfWork

pytestmark = pytest.mark.usefixtures("telemetry_db_reset")


def test_create_should_always_append_one_write_summary_row_with_the_created_memory_id_kind_scope_and_evidence_ref_count(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_memory,
    seed_default_evidence_events,
    stub_embedding_provider,
    assert_relation_exists,
    fetch_relation_rows,
) -> None:
    """create should always append one write summary row with the created memory id, kind, scope, and evidence-ref count."""

    seed_default_evidence_events(repo_id="repo-a")
    seed_memory(
        memory_id="target-1",
        repo_id="repo-a",
        scope=MemoryScope.REPO,
        kind=MemoryKind.FACT,
        text_value="Association target.",
    )

    result = handle_create(
        {
            "memory": {
                "text": "Create summary telemetry memory.",
                "kind": "problem",
                "evidence_refs": ["session://1", "session://2"],
                "links": {
                    "associations": [
                        {
                            "to_memory_id": "target-1",
                            "relation_type": "depends_on",
                        }
                    ]
                },
            }
        },
        uow_factory=uow_factory,
        embedding_provider_factory=lambda: stub_embedding_provider,
        embedding_model="stub-v1",
        inferred_repo_id="repo-a",
        defaults={"scope": "repo"},
    )

    assert result["status"] == "ok"
    assert_relation_exists("write_invocation_summaries")
    rows = fetch_relation_rows(
        "write_invocation_summaries", order_by="created_at DESC, invocation_id DESC"
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["operation_command"] == "create"
    assert row["target_memory_id"] == result["data"]["memory_id"]
    assert row["target_kind"] == "problem"
    assert row["scope"] == "repo"
    assert row["evidence_ref_count"] == 2


def test_create_should_always_append_one_write_effect_row_per_planned_side_effect_in_plan_order(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_memory,
    seed_default_evidence_events,
    stub_embedding_provider,
    assert_relation_exists,
    fetch_relation_rows,
) -> None:
    """create should always append one write effect row per planned side effect in plan order."""

    seed_default_evidence_events(repo_id="repo-a")
    seed_memory(
        memory_id="target-1",
        repo_id="repo-a",
        scope=MemoryScope.REPO,
        kind=MemoryKind.FACT,
        text_value="Association target.",
    )

    result = handle_create(
        {
            "memory": {
                "text": "Create effect-order telemetry memory.",
                "kind": "problem",
                "evidence_refs": ["session://1"],
                "links": {
                    "associations": [
                        {
                            "to_memory_id": "target-1",
                            "relation_type": "depends_on",
                        }
                    ]
                },
            }
        },
        uow_factory=uow_factory,
        embedding_provider_factory=lambda: stub_embedding_provider,
        embedding_model="stub-v1",
        inferred_repo_id="repo-a",
        defaults={"scope": "repo"},
    )

    assert result["status"] == "ok"
    assert_relation_exists("write_effect_items")
    rows = fetch_relation_rows(
        "write_effect_items", order_by="invocation_id ASC, ordinal ASC"
    )

    assert len(rows) >= 1
    assert [row["ordinal"] for row in rows] == list(range(1, len(rows) + 1))


def test_successful_writes_should_always_record_planned_effect_count_for_downstream_effect_aggregation(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_default_evidence_events,
    stub_embedding_provider,
    assert_relation_exists,
    fetch_relation_rows,
) -> None:
    """successful writes should always record planned-effect count for downstream effect aggregation."""

    seed_default_evidence_events(repo_id="repo-a")

    result = handle_create(
        {
            "memory": {
                "text": "Create planned-effect telemetry memory.",
                "kind": "preference",
                "evidence_refs": ["session://1"],
            }
        },
        uow_factory=uow_factory,
        embedding_provider_factory=lambda: stub_embedding_provider,
        embedding_model="stub-v1",
        inferred_repo_id="repo-a",
        defaults={"scope": "repo"},
    )

    assert result["status"] == "ok"
    assert_relation_exists("write_invocation_summaries")
    rows = fetch_relation_rows(
        "write_invocation_summaries", order_by="created_at DESC, invocation_id DESC"
    )

    assert len(rows) == 1
    assert rows[0]["planned_effect_count"] >= 1


def test_update_utility_vote_should_always_append_one_write_summary_row_with_update_type_utility_vote_and_utility_observation_count(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_memory,
    seed_default_evidence_events,
    assert_relation_exists,
    fetch_relation_rows,
) -> None:
    """update utility_vote should always append one write summary row with update type utility_vote and utility observation count."""

    seed_default_evidence_events(repo_id="repo-a")
    seed_memory(
        memory_id="target-memory",
        repo_id="repo-a",
        scope=MemoryScope.REPO,
        kind=MemoryKind.FACT,
        text_value="Telemetry update target.",
    )
    seed_memory(
        memory_id="problem-memory",
        repo_id="repo-a",
        scope=MemoryScope.REPO,
        kind=MemoryKind.PROBLEM,
        text_value="Telemetry problem context.",
    )

    result = handle_update(
        {
            "memory_id": "target-memory",
            "update": {
                "type": "utility_vote",
                "problem_id": "problem-memory",
                "vote": 1.0,
                "evidence_refs": ["session://1"],
            },
        },
        uow_factory=uow_factory,
        inferred_repo_id="repo-a",
    )

    assert result["status"] == "ok"
    assert_relation_exists("write_invocation_summaries")
    rows = fetch_relation_rows(
        "write_invocation_summaries", order_by="created_at DESC, invocation_id DESC"
    )

    assert len(rows) == 1
    assert rows[0]["update_type"] == "utility_vote"
    assert rows[0]["utility_observation_count"] == 1


def test_update_association_link_should_always_append_one_write_summary_row_with_update_type_association_link_and_association_effect_count(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_memory,
    seed_default_evidence_events,
    assert_relation_exists,
    fetch_relation_rows,
) -> None:
    """update association_link should always append one write summary row with update type association_link and association effect count."""

    seed_default_evidence_events(repo_id="repo-a")
    seed_memory(
        memory_id="source-memory",
        repo_id="repo-a",
        scope=MemoryScope.REPO,
        kind=MemoryKind.FACT,
        text_value="Association source.",
    )
    seed_memory(
        memory_id="target-memory",
        repo_id="repo-a",
        scope=MemoryScope.REPO,
        kind=MemoryKind.FACT,
        text_value="Association target.",
    )

    result = handle_update(
        {
            "memory_id": "source-memory",
            "update": {
                "type": "association_link",
                "to_memory_id": "target-memory",
                "relation_type": "depends_on",
                "evidence_refs": ["session://1"],
            },
        },
        uow_factory=uow_factory,
        inferred_repo_id="repo-a",
    )

    assert result["status"] == "ok"
    assert_relation_exists("write_invocation_summaries")
    rows = fetch_relation_rows(
        "write_invocation_summaries", order_by="created_at DESC, invocation_id DESC"
    )

    assert len(rows) == 1
    assert rows[0]["update_type"] == "association_link"
    assert rows[0]["association_effect_count"] == 1


def test_update_fact_update_link_should_always_append_one_write_summary_row_with_update_type_fact_update_link_and_fact_update_count(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_memory,
    assert_relation_exists,
    fetch_relation_rows,
) -> None:
    """update fact_update_link should always append one write summary row with update type fact_update_link and fact-update count."""

    seed_memory(
        memory_id="change-memory",
        repo_id="repo-a",
        scope=MemoryScope.REPO,
        kind=MemoryKind.CHANGE,
        text_value="Fact update change.",
    )
    seed_memory(
        memory_id="old-fact",
        repo_id="repo-a",
        scope=MemoryScope.REPO,
        kind=MemoryKind.FACT,
        text_value="Old fact.",
    )
    seed_memory(
        memory_id="new-fact",
        repo_id="repo-a",
        scope=MemoryScope.REPO,
        kind=MemoryKind.FACT,
        text_value="New fact.",
    )

    result = handle_update(
        {
            "memory_id": "change-memory",
            "update": {
                "type": "fact_update_link",
                "old_fact_id": "old-fact",
                "new_fact_id": "new-fact",
            },
        },
        uow_factory=uow_factory,
        inferred_repo_id="repo-a",
    )

    assert result["status"] == "ok"
    assert_relation_exists("write_invocation_summaries")
    rows = fetch_relation_rows(
        "write_invocation_summaries", order_by="created_at DESC, invocation_id DESC"
    )

    assert len(rows) == 1
    assert rows[0]["update_type"] == "fact_update_link"
    assert rows[0]["fact_update_count"] == 1


def test_update_archive_state_should_always_append_one_write_summary_row_with_update_type_archive_state_and_archived_memory_count(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_memory,
    assert_relation_exists,
    fetch_relation_rows,
) -> None:
    """update archive_state should always append one write summary row with update type archive_state and archived-memory count."""

    seed_memory(
        memory_id="archive-target",
        repo_id="repo-a",
        scope=MemoryScope.REPO,
        kind=MemoryKind.FACT,
        text_value="Archive target.",
    )

    result = handle_update(
        {
            "memory_id": "archive-target",
            "update": {
                "type": "archive_state",
                "archived": True,
            },
        },
        uow_factory=uow_factory,
        inferred_repo_id="repo-a",
    )

    assert result["status"] == "ok"
    assert_relation_exists("write_invocation_summaries")
    rows = fetch_relation_rows(
        "write_invocation_summaries", order_by="created_at DESC, invocation_id DESC"
    )

    assert len(rows) == 1
    assert rows[0]["update_type"] == "archive_state"
    assert rows[0]["archived_memory_count"] == 1
