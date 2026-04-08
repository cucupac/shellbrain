"""Read-only pre/post behavior analysis for the attention-programming rollout."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
import json
import re
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine


_MID_SESSION_MINUTES = 15
_STARTUP_WINDOW_MINUTES = 10
_CHECKPOINT_TO_READ_WINDOW_MINUTES = 10
_UTILITY_VOTE_UPDATE_TYPES = {"utility_vote", "utility_vote_batch"}
_SB_READ_RE = re.compile(r"^SB:\s*read\s*\|\s*(.+)$")
_SB_SKIP_RE = re.compile(r"^SB:\s*skip\s*\|\s*(.+)$")


def build_agent_behavior_report(
    *,
    engine: Engine,
    cutoff_at: datetime,
    window_days: int,
) -> dict[str, Any]:
    """Return one pre/post behavior report around a rollout cutoff."""

    if window_days <= 0:
        raise ValueError("window_days must be greater than 0")
    cutoff_at = _coerce_utc(cutoff_at)
    pre_start_at = cutoff_at - timedelta(days=window_days)
    post_end_at = cutoff_at + timedelta(days=window_days)
    with engine.connect() as conn:
        operation_rows = _fetch_operation_rows(conn=conn, start_at=pre_start_at, end_at=post_end_at)
        read_rows = _fetch_read_rows(conn=conn, start_at=pre_start_at, end_at=post_end_at)
        write_rows = _fetch_write_rows(conn=conn, start_at=pre_start_at, end_at=post_end_at)
        checkpoint_rows = _fetch_checkpoint_rows(conn=conn, start_at=pre_start_at, end_at=post_end_at)

    pre_report = _build_window_report(
        operation_rows=[row for row in operation_rows if _coerce_utc(row["created_at"]) < cutoff_at],
        read_rows=[row for row in read_rows if _coerce_utc(row["created_at"]) < cutoff_at],
        write_rows=[row for row in write_rows if _coerce_utc(row["created_at"]) < cutoff_at],
        checkpoint_rows=[row for row in checkpoint_rows if _coerce_utc(row["created_at"]) < cutoff_at],
    )
    post_report = _build_window_report(
        operation_rows=[row for row in operation_rows if _coerce_utc(row["created_at"]) >= cutoff_at],
        read_rows=[row for row in read_rows if _coerce_utc(row["created_at"]) >= cutoff_at],
        write_rows=[row for row in write_rows if _coerce_utc(row["created_at"]) >= cutoff_at],
        checkpoint_rows=[row for row in checkpoint_rows if _coerce_utc(row["created_at"]) >= cutoff_at],
    )
    return {
        "window": {
            "cutoff_at": cutoff_at.isoformat(),
            "window_days": window_days,
            "pre_start_at": pre_start_at.isoformat(),
            "post_end_at": post_end_at.isoformat(),
            "mid_session_minutes": _MID_SESSION_MINUTES,
            "startup_window_minutes": _STARTUP_WINDOW_MINUTES,
            "checkpoint_to_read_window_minutes": _CHECKPOINT_TO_READ_WINDOW_MINUTES,
        },
        "pre": pre_report,
        "post": post_report,
        "delta": _build_delta(pre_report["overall"], post_report["overall"]),
        "notes": [
            "This report uses proxy metrics from existing telemetry and transcript events.",
            "It does not infer true semantic subproblem shifts beyond visible SB checkpoints.",
            "Token-overhead metrics are intentionally omitted in v1 because host token usage is not stored.",
        ],
    }


def _fetch_operation_rows(*, conn: Connection, start_at: datetime, end_at: datetime) -> list[dict[str, object]]:
    """Return operation invocations for the requested window."""

    rows = conn.execute(
        text(
            """
            SELECT
              id,
              command,
              repo_id,
              COALESCE(selected_host_app, 'unknown') AS host_app,
              selected_thread_id AS thread_id,
              guidance_codes,
              total_latency_ms,
              created_at
            FROM operation_invocations
            WHERE created_at >= :start_at
              AND created_at < :end_at
              AND selected_thread_id IS NOT NULL
            ORDER BY created_at ASC, id ASC;
            """
        ),
        {"start_at": start_at, "end_at": end_at},
    ).mappings()
    return [dict(row) for row in rows]


def _fetch_read_rows(*, conn: Connection, start_at: datetime, end_at: datetime) -> list[dict[str, object]]:
    """Return read summaries for the requested window."""

    rows = conn.execute(
        text(
            """
            SELECT
              oi.id AS invocation_id,
              oi.repo_id,
              COALESCE(oi.selected_host_app, 'unknown') AS host_app,
              oi.selected_thread_id AS thread_id,
              oi.total_latency_ms,
              oi.created_at,
              ris.query_text,
              ris.zero_results
            FROM read_invocation_summaries ris
            JOIN operation_invocations oi ON oi.id = ris.invocation_id
            WHERE oi.created_at >= :start_at
              AND oi.created_at < :end_at
              AND oi.selected_thread_id IS NOT NULL
            ORDER BY oi.created_at ASC, oi.id ASC;
            """
        ),
        {"start_at": start_at, "end_at": end_at},
    ).mappings()
    return [dict(row) for row in rows]


def _fetch_write_rows(*, conn: Connection, start_at: datetime, end_at: datetime) -> list[dict[str, object]]:
    """Return successful writes for the requested window."""

    rows = conn.execute(
        text(
            """
            SELECT
              oi.id AS invocation_id,
              oi.command,
              oi.repo_id,
              COALESCE(oi.selected_host_app, 'unknown') AS host_app,
              oi.selected_thread_id AS thread_id,
              oi.total_latency_ms,
              oi.created_at,
              wis.update_type
            FROM write_invocation_summaries wis
            JOIN operation_invocations oi ON oi.id = wis.invocation_id
            WHERE oi.created_at >= :start_at
              AND oi.created_at < :end_at
              AND oi.selected_thread_id IS NOT NULL
            ORDER BY oi.created_at ASC, oi.id ASC;
            """
        ),
        {"start_at": start_at, "end_at": end_at},
    ).mappings()
    return [dict(row) for row in rows]


def _fetch_checkpoint_rows(*, conn: Connection, start_at: datetime, end_at: datetime) -> list[dict[str, object]]:
    """Return parsed SB checkpoints from transcript events in the requested window."""

    rows = conn.execute(
        text(
            """
            SELECT
              e.repo_id,
              COALESCE(e.host_app, 'unknown') AS host_app,
              e.thread_id,
              ee.source,
              ee.content,
              ee.created_at
            FROM episode_events ee
            JOIN episodes e ON e.id = ee.episode_id
            WHERE ee.created_at >= :start_at
              AND ee.created_at < :end_at
              AND e.thread_id IS NOT NULL
            ORDER BY ee.created_at ASC, ee.id ASC;
            """
        ),
        {"start_at": start_at, "end_at": end_at},
    ).mappings()

    checkpoints: list[dict[str, object]] = []
    for row in rows:
        for checkpoint in _parse_checkpoint_lines(
            repo_id=str(row["repo_id"]),
            host_app=str(row["host_app"]),
            thread_id=str(row["thread_id"]),
            source=str(row["source"]),
            content=str(row["content"]),
            created_at=_coerce_utc(row["created_at"]),
        ):
            checkpoints.append(checkpoint)
    return checkpoints


def _parse_checkpoint_lines(
    *,
    repo_id: str,
    host_app: str,
    thread_id: str,
    source: str,
    content: str,
    created_at: datetime,
) -> list[dict[str, object]]:
    """Parse SB checkpoints from one episode event body."""

    checkpoints: list[dict[str, object]] = []
    for line in content.splitlines():
        stripped = line.strip()
        read_match = _SB_READ_RE.match(stripped)
        if read_match:
            payload = [part.strip() for part in read_match.group(1).split("|")]
            signature = " | ".join(payload)
            checkpoints.append(
                {
                    "repo_id": repo_id,
                    "host_app": host_app,
                    "thread_id": thread_id,
                    "source": source,
                    "action": "read",
                    "signature": signature,
                    "reason": None,
                    "raw_line": stripped,
                    "created_at": created_at,
                }
            )
            continue
        skip_match = _SB_SKIP_RE.match(stripped)
        if skip_match:
            payload = [part.strip() for part in skip_match.group(1).split("|")]
            checkpoints.append(
                {
                    "repo_id": repo_id,
                    "host_app": host_app,
                    "thread_id": thread_id,
                    "source": source,
                    "action": "skip",
                    "signature": None,
                    "reason": " | ".join(payload),
                    "raw_line": stripped,
                    "created_at": created_at,
                }
            )
    return checkpoints


def _build_window_report(
    *,
    operation_rows: list[dict[str, object]],
    read_rows: list[dict[str, object]],
    write_rows: list[dict[str, object]],
    checkpoint_rows: list[dict[str, object]],
) -> dict[str, Any]:
    """Return overall and segmented metrics for one analysis window."""

    repo_ids = sorted({str(row["repo_id"]) for row in operation_rows})
    host_apps = sorted({str(row["host_app"]) for row in operation_rows})
    repo_host_pairs = sorted({(str(row["repo_id"]), str(row["host_app"])) for row in operation_rows})
    return {
        "overall": _compute_metrics(
            operation_rows=operation_rows,
            read_rows=read_rows,
            write_rows=write_rows,
            checkpoint_rows=checkpoint_rows,
        ),
        "by_repo": {
            repo_id: _compute_metrics(
                operation_rows=[row for row in operation_rows if str(row["repo_id"]) == repo_id],
                read_rows=[row for row in read_rows if str(row["repo_id"]) == repo_id],
                write_rows=[row for row in write_rows if str(row["repo_id"]) == repo_id],
                checkpoint_rows=[row for row in checkpoint_rows if str(row["repo_id"]) == repo_id],
            )
            for repo_id in repo_ids
        },
        "by_host": {
            host_app: _compute_metrics(
                operation_rows=[row for row in operation_rows if str(row["host_app"]) == host_app],
                read_rows=[row for row in read_rows if str(row["host_app"]) == host_app],
                write_rows=[row for row in write_rows if str(row["host_app"]) == host_app],
                checkpoint_rows=[row for row in checkpoint_rows if str(row["host_app"]) == host_app],
            )
            for host_app in host_apps
        },
        "by_repo_host": [
            {
                "repo_id": repo_id,
                "host_app": host_app,
                "metrics": _compute_metrics(
                    operation_rows=[
                        row
                        for row in operation_rows
                        if str(row["repo_id"]) == repo_id and str(row["host_app"]) == host_app
                    ],
                    read_rows=[
                        row for row in read_rows if str(row["repo_id"]) == repo_id and str(row["host_app"]) == host_app
                    ],
                    write_rows=[
                        row for row in write_rows if str(row["repo_id"]) == repo_id and str(row["host_app"]) == host_app
                    ],
                    checkpoint_rows=[
                        row
                        for row in checkpoint_rows
                        if str(row["repo_id"]) == repo_id and str(row["host_app"]) == host_app
                    ],
                ),
            }
            for repo_id, host_app in repo_host_pairs
        ],
    }


def _compute_metrics(
    *,
    operation_rows: list[dict[str, object]],
    read_rows: list[dict[str, object]],
    write_rows: list[dict[str, object]],
    checkpoint_rows: list[dict[str, object]],
) -> dict[str, Any]:
    """Compute the behavior metrics for one filtered slice."""

    thread_ops = _group_by_thread(operation_rows)
    thread_reads = _group_by_thread(read_rows)
    thread_writes = _group_by_thread(write_rows)
    thread_checkpoints = _group_by_thread(checkpoint_rows)
    read_threads = list(thread_reads.keys())
    total_reads = len(read_rows)
    total_checkpoints = len(checkpoint_rows)
    total_writes = len(write_rows)
    threads_with_rereads = 0
    mid_session_reread_threads = 0
    read_after_other_action_threads = 0
    startup_window_read_count = 0
    reread_then_write_threads = 0

    for thread_key, reads in thread_reads.items():
        reads = sorted(reads, key=_thread_row_time)
        ops = sorted(thread_ops.get(thread_key, []), key=_thread_row_time)
        writes = sorted(thread_writes.get(thread_key, []), key=_thread_row_time)
        first_op_time = _thread_row_time(ops[0]) if ops else _thread_row_time(reads[0])
        startup_window_end = first_op_time + timedelta(minutes=_STARTUP_WINDOW_MINUTES)
        startup_window_read_count += sum(1 for row in reads if _thread_row_time(row) <= startup_window_end)
        if len(reads) >= 2:
            threads_with_rereads += 1
            reread_time = _thread_row_time(reads[1])
            if reread_time >= first_op_time + timedelta(minutes=_MID_SESSION_MINUTES):
                mid_session_reread_threads += 1
            if any(_thread_row_time(write_row) > reread_time for write_row in writes):
                reread_then_write_threads += 1
        if any(
            any(_thread_row_time(op_row) < _thread_row_time(read_row) and str(op_row["command"]) != "read" for op_row in ops)
            for read_row in reads
        ):
            read_after_other_action_threads += 1

    write_preceded_by_events = 0
    for thread_key, writes in thread_writes.items():
        event_times = [
            _thread_row_time(row)
            for row in thread_ops.get(thread_key, [])
            if str(row["command"]) == "events"
        ]
        for write_row in writes:
            if any(event_time < _thread_row_time(write_row) for event_time in event_times):
                write_preceded_by_events += 1

    guidance_threads: dict[tuple[str, str, str], datetime] = {}
    for row in operation_rows:
        guidance_codes = row.get("guidance_codes")
        if not _guidance_contains_pending_utility_votes(guidance_codes):
            continue
        thread_key = _thread_key(row)
        created_at = _thread_row_time(row)
        current = guidance_threads.get(thread_key)
        if current is None or created_at < current:
            guidance_threads[thread_key] = created_at
    utility_followthrough = 0
    for thread_key, first_guidance_at in guidance_threads.items():
        writes = thread_writes.get(thread_key, [])
        if any(
            _thread_row_time(write_row) > first_guidance_at and str(write_row.get("update_type")) in _UTILITY_VOTE_UPDATE_TYPES
            for write_row in writes
        ):
            utility_followthrough += 1

    read_checkpoint_count = 0
    skip_checkpoint_count = 0
    repeated_read_checkpoint_count = 0
    same_signature_read_checkpoint_count = 0
    checkpoint_to_read_count = 0

    for thread_key, checkpoints in thread_checkpoints.items():
        checkpoints = sorted(checkpoints, key=_thread_row_time)
        reads = sorted(thread_reads.get(thread_key, []), key=_thread_row_time)
        previous_read_signature: str | None = None
        for index, checkpoint in enumerate(checkpoints):
            action = str(checkpoint["action"])
            if action == "skip":
                skip_checkpoint_count += 1
                continue
            read_checkpoint_count += 1
            signature = str(checkpoint["signature"])
            if previous_read_signature is not None:
                repeated_read_checkpoint_count += 1
                if signature == previous_read_signature:
                    same_signature_read_checkpoint_count += 1
            previous_read_signature = signature
            next_checkpoint_at = None
            if index + 1 < len(checkpoints):
                next_checkpoint_at = _thread_row_time(checkpoints[index + 1])
            checkpoint_deadline = _thread_row_time(checkpoint) + timedelta(minutes=_CHECKPOINT_TO_READ_WINDOW_MINUTES)
            if next_checkpoint_at is not None and next_checkpoint_at < checkpoint_deadline:
                checkpoint_deadline = next_checkpoint_at
            if any(
                _thread_row_time(read_row) >= _thread_row_time(checkpoint)
                and _thread_row_time(read_row) < checkpoint_deadline
                for read_row in reads
            ):
                checkpoint_to_read_count += 1

    avg_invocation_latency_ms = _average([int(row["total_latency_ms"]) for row in operation_rows])
    avg_read_latency_ms = _average([int(row["total_latency_ms"]) for row in read_rows])

    return {
        "thread_count": len(thread_ops),
        "read_thread_count": len(read_threads),
        "read_count": total_reads,
        "write_count": total_writes,
        "checkpoint_count": total_checkpoints,
        "mid_session_reread_rate": _safe_rate(mid_session_reread_threads, len(read_threads)),
        "mid_session_reread_thread_count": mid_session_reread_threads,
        "multi_read_thread_rate": _safe_rate(threads_with_rereads, len(read_threads)),
        "multi_read_thread_count": threads_with_rereads,
        "read_after_other_action_rate": _safe_rate(read_after_other_action_threads, len(read_threads)),
        "read_after_other_action_thread_count": read_after_other_action_threads,
        "startup_window_read_concentration": _safe_rate(startup_window_read_count, total_reads),
        "zero_result_read_rate": _safe_rate(sum(1 for row in read_rows if bool(row.get("zero_results"))), total_reads),
        "events_before_write_compliance": _safe_rate(write_preceded_by_events, total_writes),
        "writes_preceded_by_events": write_preceded_by_events,
        "utility_vote_followthrough": _safe_rate(utility_followthrough, len(guidance_threads)),
        "utility_vote_opportunity_count": len(guidance_threads),
        "same_signature_reread_rate": _safe_rate(same_signature_read_checkpoint_count, repeated_read_checkpoint_count),
        "same_signature_reread_count": same_signature_read_checkpoint_count,
        "checkpoint_to_read_rate": _safe_rate(checkpoint_to_read_count, read_checkpoint_count),
        "checkpoint_to_read_count": checkpoint_to_read_count,
        "checkpoint_skip_rate": _safe_rate(skip_checkpoint_count, total_checkpoints),
        "checkpoint_skip_count": skip_checkpoint_count,
        "read_to_useful_write_rate": _safe_rate(reread_then_write_threads, threads_with_rereads),
        "read_to_useful_write_thread_count": reread_then_write_threads,
        "avg_invocation_latency_ms": avg_invocation_latency_ms,
        "avg_read_latency_ms": avg_read_latency_ms,
    }


def _group_by_thread(rows: list[dict[str, object]]) -> dict[tuple[str, str, str], list[dict[str, object]]]:
    """Group rows by repo, host, and thread."""

    grouped: dict[tuple[str, str, str], list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[_thread_key(row)].append(row)
    return grouped


def _thread_key(row: dict[str, object]) -> tuple[str, str, str]:
    """Return the canonical repo/host/thread key for one row."""

    return (str(row["repo_id"]), str(row["host_app"]), str(row["thread_id"]))


def _thread_row_time(row: dict[str, object]) -> datetime:
    """Return one row timestamp as a UTC datetime."""

    return _coerce_utc(row["created_at"])


def _coerce_utc(value: object) -> datetime:
    """Return one datetime normalized to UTC."""

    if not isinstance(value, datetime):
        raise TypeError(f"Expected datetime, got {type(value).__name__}")
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _average(values: list[int]) -> float | None:
    """Return the rounded arithmetic mean for one numeric list."""

    if not values:
        return None
    return round(sum(values) / len(values), 2)


def _safe_rate(numerator: int, denominator: int) -> float | None:
    """Return one rounded rate or None when the denominator is empty."""

    if denominator <= 0:
        return None
    return round(numerator / denominator, 4)


def _guidance_contains_pending_utility_votes(guidance_codes: object) -> bool:
    """Return whether one guidance payload includes pending utility-vote reminders."""

    if isinstance(guidance_codes, list):
        return "pending_utility_votes" in {str(item) for item in guidance_codes}
    if isinstance(guidance_codes, str):
        if "pending_utility_votes" in guidance_codes:
            return True
        try:
            parsed = json.loads(guidance_codes)
        except json.JSONDecodeError:
            return False
        return isinstance(parsed, list) and "pending_utility_votes" in {str(item) for item in parsed}
    return False


def _build_delta(pre_metrics: dict[str, Any], post_metrics: dict[str, Any]) -> dict[str, float | None]:
    """Return simple post-minus-pre deltas for numeric overall metrics."""

    delta: dict[str, float | None] = {}
    for key, post_value in post_metrics.items():
        pre_value = pre_metrics.get(key)
        if isinstance(pre_value, (int, float)) and isinstance(post_value, (int, float)):
            delta[key] = round(float(post_value) - float(pre_value), 4)
            continue
        delta[key] = None
    return delta
