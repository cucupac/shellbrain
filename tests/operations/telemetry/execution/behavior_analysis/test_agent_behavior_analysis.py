"""Integration coverage for the agent behavior analysis report."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path

import pytest

from app.periphery.admin.agent_behavior_analysis import build_agent_behavior_report
from app.periphery.db.models.episodes import episode_events, episodes
from app.periphery.db.models.telemetry import operation_invocations, read_invocation_summaries, write_invocation_summaries


pytestmark = pytest.mark.usefixtures("telemetry_db_reset")


def test_build_agent_behavior_report_should_compare_pre_and_post_rollout_behavior(integration_engine) -> None:
    """The behavior report should surface timing, checkpoint, and writeback quality shifts."""

    cutoff_at = datetime(2026, 4, 7, 0, 0, tzinfo=timezone.utc)
    _seed_behavior_dataset(integration_engine, cutoff_at=cutoff_at)

    report = build_agent_behavior_report(engine=integration_engine, cutoff_at=cutoff_at, window_days=2)

    pre = report["pre"]["overall"]
    post = report["post"]["overall"]
    by_host = report["post"]["by_host"]

    assert pre["multi_read_thread_rate"] == 0.0
    assert pre["startup_window_read_concentration"] == 1.0

    assert post["mid_session_reread_rate"] == 0.5
    assert post["multi_read_thread_rate"] == 0.5
    assert post["read_after_other_action_rate"] == 0.5
    assert post["startup_window_read_concentration"] == 0.6667
    assert post["events_before_write_compliance"] == 1.0
    assert post["utility_vote_followthrough"] == 1.0
    assert post["same_signature_reread_rate"] == 1.0
    assert post["checkpoint_to_read_rate"] == 0.5
    assert post["checkpoint_skip_rate"] == 0.3333
    assert post["read_to_useful_write_rate"] == 1.0

    assert by_host["codex"]["avg_invocation_latency_ms"] == 23.4
    assert by_host["claude"]["avg_invocation_latency_ms"] == 20.0
    assert report["delta"]["multi_read_thread_rate"] == 0.5


def test_agent_behavior_analysis_script_should_print_json_report(monkeypatch, capsys, integration_engine) -> None:
    """The internal analysis script should resolve DSNs and emit JSON to stdout."""

    cutoff_at = datetime(2026, 4, 7, 0, 0, tzinfo=timezone.utc)
    _seed_behavior_dataset(integration_engine, cutoff_at=cutoff_at)
    script_path = Path(__file__).resolve().parents[5] / "scripts" / "agent_behavior_analysis.py"
    spec = importlib.util.spec_from_file_location("agent_behavior_analysis_script", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    dsn = str(integration_engine.url)
    monkeypatch.setattr(module, "get_optional_db_dsn", lambda: dsn)
    monkeypatch.setattr(module, "get_optional_admin_db_dsn", lambda: None)

    exit_code = module.main(["--cutoff", cutoff_at.isoformat(), "--days", "2"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert '"window"' in output
    assert '"post"' in output
    assert '"checkpoint_to_read_rate"' in output


def _seed_behavior_dataset(integration_engine, *, cutoff_at: datetime) -> None:
    """Insert one deterministic telemetry and episode dataset for behavior analysis."""

    repo_primary = "github.com/example/attention"
    repo_secondary = "github.com/example/claude"
    pre_base = cutoff_at - timedelta(hours=20)
    post_base = cutoff_at + timedelta(hours=1)
    claude_base = cutoff_at + timedelta(hours=2)

    op_rows = [
        _operation_row(
            invocation_id="pre-read-1",
            command="read",
            repo_id=repo_primary,
            host_app="codex",
            thread_id="codex:pre-1",
            created_at=pre_base,
            total_latency_ms=9,
        ),
        _operation_row(
            invocation_id="post-read-1",
            command="read",
            repo_id=repo_primary,
            host_app="codex",
            thread_id="codex:post-1",
            created_at=post_base,
            total_latency_ms=10,
        ),
        _operation_row(
            invocation_id="post-events-1",
            command="events",
            repo_id=repo_primary,
            host_app="codex",
            thread_id="codex:post-1",
            created_at=post_base + timedelta(minutes=15),
            total_latency_ms=18,
        ),
        _operation_row(
            invocation_id="post-read-2",
            command="read",
            repo_id=repo_primary,
            host_app="codex",
            thread_id="codex:post-1",
            created_at=post_base + timedelta(minutes=20),
            total_latency_ms=12,
            guidance_codes=["pending_utility_votes"],
        ),
        _operation_row(
            invocation_id="post-create-1",
            command="create",
            repo_id=repo_primary,
            host_app="codex",
            thread_id="codex:post-1",
            created_at=post_base + timedelta(minutes=25),
            total_latency_ms=40,
        ),
        _operation_row(
            invocation_id="post-update-1",
            command="update",
            repo_id=repo_primary,
            host_app="codex",
            thread_id="codex:post-1",
            created_at=post_base + timedelta(minutes=36),
            total_latency_ms=37,
        ),
        _operation_row(
            invocation_id="claude-read-1",
            command="read",
            repo_id=repo_secondary,
            host_app="claude",
            thread_id="claude:post-1",
            created_at=claude_base,
            total_latency_ms=20,
        ),
    ]
    read_rows = [
        _read_row(invocation_id="pre-read-1", created_at=pre_base, query_text="pre startup read", zero_results=False),
        _read_row(invocation_id="post-read-1", created_at=post_base, query_text="post startup read", zero_results=False),
        _read_row(
            invocation_id="post-read-2",
            created_at=post_base + timedelta(minutes=20),
            query_text="oauth callback loop in staging",
            zero_results=False,
        ),
        _read_row(invocation_id="claude-read-1", created_at=claude_base, query_text="claude startup read", zero_results=False),
    ]
    write_rows = [
        _write_row(
            invocation_id="post-create-1",
            command="create",
            target_memory_id="mem-problem-1",
            update_type=None,
            created_at=post_base + timedelta(minutes=25),
        ),
        _write_row(
            invocation_id="post-update-1",
            command="update",
            target_memory_id="mem-problem-1",
            update_type="utility_vote_batch",
            created_at=post_base + timedelta(minutes=36),
        ),
    ]
    episode_rows = [
        _episode_row(episode_id="episode-pre-1", repo_id=repo_primary, host_app="codex", thread_id="codex:pre-1", started_at=pre_base),
        _episode_row(episode_id="episode-post-1", repo_id=repo_primary, host_app="codex", thread_id="codex:post-1", started_at=post_base),
        _episode_row(episode_id="episode-claude-1", repo_id=repo_secondary, host_app="claude", thread_id="claude:post-1", started_at=claude_base),
    ]
    event_rows = [
        _event_row(
            event_id="evt-post-1",
            episode_id="episode-post-1",
            seq=1,
            source="assistant",
            content="SB: read | fix auth callback | api | oauth callback loop | new hypothesis",
            created_at=post_base + timedelta(minutes=14),
        ),
        _event_row(
            event_id="evt-post-2",
            episode_id="episode-post-1",
            seq=2,
            source="assistant",
            content="SB: read | fix auth callback | api | oauth callback loop | new hypothesis",
            created_at=post_base + timedelta(minutes=18),
        ),
        _event_row(
            event_id="evt-post-3",
            episode_id="episode-post-1",
            seq=3,
            source="assistant",
            content="SB: skip | same signature | no new evidence",
            created_at=post_base + timedelta(minutes=40),
        ),
    ]

    with integration_engine.begin() as conn:
        conn.execute(operation_invocations.insert(), op_rows)
        conn.execute(read_invocation_summaries.insert(), read_rows)
        conn.execute(write_invocation_summaries.insert(), write_rows)
        conn.execute(episodes.insert(), episode_rows)
        conn.execute(episode_events.insert(), event_rows)


def _operation_row(
    *,
    invocation_id: str,
    command: str,
    repo_id: str,
    host_app: str,
    thread_id: str,
    created_at: datetime,
    total_latency_ms: int,
    guidance_codes: list[str] | None = None,
) -> dict[str, object]:
    """Return one operation_invocations row."""

    return {
        "id": invocation_id,
        "command": command,
        "repo_id": repo_id,
        "repo_root": f"/tmp/{repo_id.rsplit('/', 1)[-1]}",
        "no_sync": False,
        "selected_host_app": host_app,
        "selected_host_session_key": thread_id.split(":", 1)[-1],
        "selected_thread_id": thread_id,
        "selected_episode_id": f"episode-{thread_id.split(':', 1)[-1]}",
        "matching_candidate_count": 0,
        "selection_ambiguous": False,
        "outcome": "ok",
        "error_stage": None,
        "error_code": None,
        "error_message": None,
        "total_latency_ms": total_latency_ms,
        "poller_start_attempted": False,
        "poller_started": False,
        "guidance_codes": guidance_codes or [],
        "created_at": created_at,
    }


def _read_row(*, invocation_id: str, created_at: datetime, query_text: str, zero_results: bool) -> dict[str, object]:
    """Return one read_invocation_summaries row."""

    return {
        "invocation_id": invocation_id,
        "query_text": query_text,
        "mode": "targeted",
        "requested_limit": 8,
        "effective_limit": 8,
        "include_global": True,
        "kinds_filter": ["problem", "solution"],
        "direct_count": 1,
        "explicit_related_count": 0,
        "implicit_related_count": 0,
        "total_returned": 1,
        "zero_results": zero_results,
        "created_at": created_at,
    }


def _write_row(
    *,
    invocation_id: str,
    command: str,
    target_memory_id: str,
    update_type: str | None,
    created_at: datetime,
) -> dict[str, object]:
    """Return one write_invocation_summaries row."""

    return {
        "invocation_id": invocation_id,
        "operation_command": command,
        "target_memory_id": target_memory_id,
        "target_kind": "problem",
        "update_type": update_type,
        "scope": "repo",
        "evidence_ref_count": 1,
        "planned_effect_count": 1,
        "created_memory_count": 1 if command == "create" else 0,
        "archived_memory_count": 0,
        "utility_observation_count": 1 if update_type else 0,
        "association_effect_count": 0,
        "fact_update_count": 0,
        "created_at": created_at,
    }


def _episode_row(*, episode_id: str, repo_id: str, host_app: str, thread_id: str, started_at: datetime) -> dict[str, object]:
    """Return one episodes row."""

    return {
        "id": episode_id,
        "repo_id": repo_id,
        "host_app": host_app,
        "thread_id": thread_id,
        "title": None,
        "objective": None,
        "status": "completed",
        "started_at": started_at,
        "ended_at": started_at + timedelta(minutes=45),
        "created_at": started_at,
    }


def _event_row(
    *,
    event_id: str,
    episode_id: str,
    seq: int,
    source: str,
    content: str,
    created_at: datetime,
) -> dict[str, object]:
    """Return one episode_events row."""

    return {
        "id": event_id,
        "episode_id": episode_id,
        "seq": seq,
        "host_event_key": event_id,
        "source": source,
        "content": content,
        "created_at": created_at,
    }
