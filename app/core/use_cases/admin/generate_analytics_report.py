"""Measurements and source records for reviewer-owned analytics."""

from collections import defaultdict
from datetime import datetime, timedelta
from statistics import mean
from typing import Any


def build_analytics_report(
    *,
    days: int,
    operation_rows: list[dict[str, object]],
    read_rows: list[dict[str, object]],
    sync_rows: list[dict[str, object]],
    end_at: datetime,
) -> dict[str, Any]:
    """Summarize usage without assigning health or product priorities."""
    if days <= 0:
        raise ValueError("--days must be greater than 0")
    start_at = end_at - timedelta(days=days)
    operations = [r for r in operation_rows if start_at <= r["created_at"] < end_at]
    reads = [r for r in read_rows if start_at <= r["created_at"] < end_at]
    syncs = [r for r in sync_rows if start_at <= r["created_at"] < end_at]
    repo_ids = sorted({str(r["repo_id"]) for r in [*operations, *syncs]})
    commands = defaultdict(list)
    for row in operations:
        commands[(str(row["repo_id"]), str(row["command"]))].append(row)
    empty_by_repo = defaultdict(list)
    for row in reads:
        empty_by_repo[str(row["repo_id"])].append(row)
    sync_by_host = defaultdict(list)
    for row in syncs:
        sync_by_host[(str(row["repo_id"]), str(row["host_app"]))].append(row)
    failure_groups = defaultdict(list)
    for source, rows in (("operation", operations), ("sync", syncs)):
        for row in rows:
            if row["outcome"] == "error":
                key = (
                    source,
                    str(row["repo_id"]),
                    str(row.get("command") or row.get("host_app")),
                    row.get("error_stage"),
                    row.get("error_code"),
                    row.get("error_message"),
                )
                failure_groups[key].append(row)
    return {
        "window": {
            "days": days,
            "start_at": start_at.isoformat(),
            "end_at": end_at.isoformat(),
        },
        "summary": {
            "repo_count": len(repo_ids),
            "invocation_count": len(operations),
            "failure_count": sum(len(rows) for rows in failure_groups.values()),
            "sync_run_count": len(syncs),
        },
        "commands": [
            {
                "repo_id": repo,
                "command": command,
                "invocation_count": len(rows),
                "failure_count": sum(r["outcome"] == "error" for r in rows),
                "avg_latency_ms": round(
                    mean(int(r["total_latency_ms"]) for r in rows), 2
                ),
                "max_latency_ms": max(int(r["total_latency_ms"]) for r in rows),
                "sample_invocation_ids": [str(r["id"]) for r in rows[-5:]],
            }
            for (repo, command), rows in sorted(commands.items())
        ],
        "retrieval": [
            {
                "repo_id": repo,
                "request_count": len(rows),
                "zero_result_count": sum(bool(r["zero_results"]) for r in rows),
                "sample_empty_invocation_ids": [
                    str(r["invocation_id"]) for r in rows if r["zero_results"]
                ][-5:],
            }
            for repo, rows in sorted(empty_by_repo.items())
        ],
        "sync": [
            {
                "repo_id": repo,
                "host_app": host,
                "run_count": len(rows),
                "failure_count": sum(r["outcome"] == "error" for r in rows),
                "imported_event_count": sum(
                    int(r["imported_event_count"]) for r in rows
                ),
            }
            for (repo, host), rows in sorted(sync_by_host.items())
        ],
        "failures": [
            {
                "source": source,
                "repo_id": repo,
                "command_or_host": operation,
                "error_stage": stage,
                "error_code": code,
                "error_message": message,
                "count": len(rows),
                "sample_record_ids": [str(r["id"]) for r in rows[-5:]],
            }
            for (
                source,
                repo,
                operation,
                stage,
                code,
                message,
            ), rows in failure_groups.items()
        ],
    }
