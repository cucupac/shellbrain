"""Cross-repo usage analytics report for reviewer agents."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
import math
import re
from typing import Any

from app.core.use_cases.admin.analytics_diagnostics import (
    classify_operation_failure,
    classify_sync_failure,
)


_MAX_STRENGTHS = 3
_MAX_FAILURES = 6
_MAX_CAPABILITY_GAPS = 3
_MAX_EVIDENCE = 3
_PRIORITY_LIMIT = 3
_REAL_DATETIME = datetime

_SEVERITY_WEIGHT = {"high": 3, "medium": 2, "low": 1}


def build_analytics_report(
    *,
    days: int,
    end_at: datetime | None = None,
    operation_rows: list[dict[str, object]],
    read_rows: list[dict[str, object]],
    write_rows: list[dict[str, object]],
    sync_rows: list[dict[str, object]],
    pending_threads: list[dict[str, object]],
    utility_vote_rows: list[dict[str, object]],
    event_rows: list[dict[str, object]],
) -> dict[str, Any]:
    """Return one cross-repo telemetry report from fetched rows."""

    if days <= 0:
        raise ValueError("--days must be greater than 0")
    if end_at is None:
        end_at = _REAL_DATETIME.now(timezone.utc)
    start_at = end_at - timedelta(days=days)

    strengths = _build_strengths(
        operation_rows=operation_rows,
        write_rows=write_rows,
        sync_rows=sync_rows,
        event_rows=event_rows,
    )
    failures = _build_failures(
        operation_rows=operation_rows, read_rows=read_rows, sync_rows=sync_rows
    )
    capability_gaps = _build_capability_gaps(
        operation_rows=operation_rows,
        write_rows=write_rows,
        pending_threads=pending_threads,
        utility_vote_rows=utility_vote_rows,
        event_rows=event_rows,
    )
    priorities = _build_priorities(failures=failures, capability_gaps=capability_gaps)
    repo_rollups = _build_repo_rollups(
        operation_rows=operation_rows,
        sync_rows=sync_rows,
        strengths=strengths,
        failures=failures,
        capability_gaps=capability_gaps,
    )

    repo_ids = set()
    repo_ids.update(
        str(row["repo_id"]) for row in operation_rows if row.get("repo_id") is not None
    )
    repo_ids.update(
        str(row["repo_id"]) for row in sync_rows if row.get("repo_id") is not None
    )
    top_strength = strengths[0] if strengths else None
    top_failure = failures[0] if failures else None
    top_gap = capability_gaps[0] if capability_gaps else None

    return {
        "window": {
            "days": days,
            "start_at": start_at.isoformat(),
            "end_at": end_at.isoformat(),
        },
        "summary": {
            "overall_health": _overall_health(
                failures=failures, capability_gaps=capability_gaps
            ),
            "top_strength": None
            if top_strength is None
            else _summary_ref(top_strength),
            "top_failure": None if top_failure is None else _summary_ref(top_failure),
            "top_capability_gap": None if top_gap is None else _summary_ref(top_gap),
            "repo_count": len(repo_ids),
            "invocation_count": len(operation_rows),
            "failure_count": sum(
                1 for row in operation_rows if row.get("outcome") == "error"
            )
            + sum(1 for row in sync_rows if row.get("outcome") == "error"),
        },
        "strengths": strengths,
        "failures": failures,
        "capability_gaps": capability_gaps,
        "priorities": priorities,
        "repo_rollups": repo_rollups,
    }


def _build_strengths(
    *,
    operation_rows: list[dict[str, object]],
    write_rows: list[dict[str, object]],
    sync_rows: list[dict[str, object]],
    event_rows: list[dict[str, object]],
) -> list[dict[str, Any]]:
    """Return ranked positive findings from the telemetry window."""

    findings: list[tuple[float, dict[str, Any]]] = []

    command_groups: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for row in operation_rows:
        command_groups[(str(row["repo_id"]), str(row["command"]))].append(row)
    for (repo_id, command), rows in command_groups.items():
        failures = [row for row in rows if row.get("outcome") == "error"]
        if len(rows) < 10 or failures:
            continue
        avg_latency_ms = sum(int(row["total_latency_ms"]) for row in rows) / len(rows)
        finding = _finding(
            finding_type="strength",
            category="command_success",
            severity=_positive_severity(len(rows)),
            title=f"{repo_id} is executing {command} reliably.",
            where={"repo_id": repo_id, "command": command},
            why_it_matters=f"Agents are successfully using {command} in this repo without visible failures in the report window.",
            metrics={
                "invocation_count": len(rows),
                "failure_count": 0,
                "avg_latency_ms": round(avg_latency_ms, 2),
            },
            diagnosis={
                "category": "healthy_command_usage",
                "summary": "This command is being used successfully at meaningful volume.",
            },
            evidence=_operation_evidence(rows),
            recommended_action="Keep this flow stable and treat it as the reference behavior for nearby product surfaces.",
        )
        findings.append((len(rows), finding))

    sync_groups: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for row in sync_rows:
        sync_groups[(str(row["repo_id"]), str(row["host_app"]))].append(row)
    for (repo_id, host_app), rows in sync_groups.items():
        if len(rows) < 100:
            continue
        failed = [row for row in rows if row.get("outcome") == "error"]
        failure_rate = len(failed) / len(rows)
        if failure_rate >= 0.05:
            continue
        finding = _finding(
            finding_type="strength",
            category="sync_stability",
            severity=_positive_severity(len(rows)),
            title=f"{repo_id} has stable {host_app} sync health.",
            where={"repo_id": repo_id, "host_app": host_app},
            why_it_matters="Reliable transcript sync is required before agents can use evidence-backed writes safely.",
            metrics={
                "sync_run_count": len(rows),
                "failure_rate": round(failure_rate, 4),
                "imported_event_count": sum(
                    int(row["imported_event_count"]) for row in rows
                ),
            },
            diagnosis={
                "category": "healthy_sync_usage",
                "summary": "Sync is succeeding consistently at nontrivial volume.",
            },
            evidence=_sync_evidence(rows),
            recommended_action="Use this host/repo combination as a reference point when debugging weaker sync paths.",
        )
        findings.append((len(rows), finding))

    event_times = _thread_times(rows=event_rows)
    write_groups: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in write_rows:
        write_groups[str(row["repo_id"])].append(row)
    for repo_id, rows in write_groups.items():
        if len(rows) < 5:
            continue
        preceded = 0
        for row in rows:
            thread_id = row.get("selected_thread_id")
            if not isinstance(thread_id, str):
                continue
            if _has_prior_time(
                times=event_times[(repo_id, thread_id)], created_at=_row_time(row)
            ):
                preceded += 1
        compliance = preceded / len(rows)
        if compliance < 0.9:
            continue
        finding = _finding(
            finding_type="strength",
            category="events_before_write",
            severity=_positive_severity(len(rows)),
            title=f"{repo_id} is following the events-before-write protocol.",
            where={"repo_id": repo_id},
            why_it_matters="When writes are consistently preceded by events, evidence-backed memory updates are more trustworthy.",
            metrics={
                "write_count": len(rows),
                "writes_preceded_by_events": preceded,
                "compliance_rate": round(compliance, 4),
            },
            diagnosis={
                "category": "healthy_protocol_usage",
                "summary": "Agents in this repo are using the write protocol correctly most of the time.",
            },
            evidence=_write_evidence(rows),
            recommended_action="Preserve this protocol ergonomics as the expected baseline.",
        )
        findings.append((compliance * len(rows), finding))

    findings.sort(
        key=lambda item: (
            _SEVERITY_WEIGHT[item[1]["severity"]],
            item[0],
            item[1]["title"],
        ),
        reverse=True,
    )
    return [item[1] for item in findings[:_MAX_STRENGTHS]]


def _build_failures(
    *,
    operation_rows: list[dict[str, object]],
    read_rows: list[dict[str, object]],
    sync_rows: list[dict[str, object]],
) -> list[dict[str, Any]]:
    """Return ranked failure findings from the telemetry window."""

    findings: list[tuple[float, dict[str, Any]]] = []

    op_groups: dict[tuple[str, str, str, str, str], list[dict[str, object]]] = (
        defaultdict(list)
    )
    for row in operation_rows:
        if row.get("outcome") != "error":
            continue
        diagnosis = classify_operation_failure(
            command=str(row["command"]),
            error_stage=_optional_str(row.get("error_stage")),
            error_code=_optional_str(row.get("error_code")),
            error_message=_optional_str(row.get("error_message")),
        )
        key = (
            str(row["repo_id"]),
            str(row["command"]),
            _optional_str(row.get("error_stage")) or "",
            _optional_str(row.get("error_code")) or "",
            diagnosis["category"],
        )
        normalized = dict(row)
        normalized["_diagnosis"] = diagnosis
        op_groups[key].append(normalized)
    for (
        repo_id,
        command,
        error_stage,
        error_code,
        _category,
    ), rows in op_groups.items():
        diagnosis = rows[0]["_diagnosis"]
        rate = len(rows) / max(
            1,
            sum(
                1
                for item in operation_rows
                if item.get("repo_id") == repo_id and item.get("command") == command
            ),
        )
        finding = _finding(
            finding_type="failure",
            category=str(diagnosis["category"]),
            severity=_failure_severity(count=len(rows), rate=rate),
            title=f"{repo_id} is failing on {command}.",
            where={"repo_id": repo_id, "command": command},
            why_it_matters=f"Agents cannot rely on {command} in this repo until this failure mode is addressed.",
            metrics={
                "failure_count": len(rows),
                "failure_rate_for_command": round(rate, 4),
                "error_stage": error_stage or None,
                "error_code": error_code or None,
            },
            diagnosis={
                "category": str(diagnosis["category"]),
                "summary": str(diagnosis["summary"]),
            },
            evidence=_operation_evidence(rows),
            recommended_action=str(diagnosis["recommended_action"]),
        )
        findings.append((len(rows) + rate, finding))

    sync_group_totals: dict[tuple[str, str], int] = defaultdict(int)
    sync_failure_groups: dict[tuple[str, str, str, str], list[dict[str, object]]] = (
        defaultdict(list)
    )
    for row in sync_rows:
        key = (str(row["repo_id"]), str(row["host_app"]))
        sync_group_totals[key] += 1
        if row.get("outcome") != "error":
            continue
        diagnosis = classify_sync_failure(
            error_stage=_optional_str(row.get("error_stage")),
            error_message=_optional_str(row.get("error_message")),
        )
        failure_key = (
            str(row["repo_id"]),
            str(row["host_app"]),
            _optional_str(row.get("error_stage")) or "",
            diagnosis["category"],
        )
        normalized = dict(row)
        normalized["_diagnosis"] = diagnosis
        sync_failure_groups[failure_key].append(normalized)
    for (
        repo_id,
        host_app,
        error_stage,
        _category,
    ), rows in sync_failure_groups.items():
        diagnosis = rows[0]["_diagnosis"]
        total = sync_group_totals[(repo_id, host_app)]
        rate = len(rows) / max(1, total)
        finding = _finding(
            finding_type="failure",
            category=str(diagnosis["category"]),
            severity=_failure_severity(count=len(rows), rate=rate),
            title=f"{repo_id} has unstable {host_app} sync.",
            where={"repo_id": repo_id, "host_app": host_app},
            why_it_matters="When sync is unstable, evidence-backed workflows and exact thread grounding degrade quickly.",
            metrics={
                "failure_count": len(rows),
                "sync_run_count": total,
                "failure_rate": round(rate, 4),
                "error_stage": error_stage or None,
            },
            diagnosis={
                "category": str(diagnosis["category"]),
                "summary": str(diagnosis["summary"]),
            },
            evidence=_sync_evidence(rows),
            recommended_action=str(diagnosis["recommended_action"]),
        )
        findings.append((len(rows) + rate, finding))

    read_groups: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in read_rows:
        read_groups[str(row["repo_id"])].append(row)
    for repo_id, rows in read_groups.items():
        if len(rows) < 5:
            continue
        zero_rows = [row for row in rows if bool(row.get("zero_results"))]
        zero_rate = len(zero_rows) / len(rows)
        if zero_rate < 0.2:
            continue
        finding = _finding(
            finding_type="failure",
            category="zero_result_reads",
            severity=_gap_severity(rate=zero_rate),
            title=f"{repo_id} is producing too many zero-result reads.",
            where={"repo_id": repo_id},
            why_it_matters="When reads return nothing at a high rate, agents are not getting useful memory recall when they ask for it.",
            metrics={
                "read_count": len(rows),
                "zero_result_read_count": len(zero_rows),
                "zero_result_rate": round(zero_rate, 4),
            },
            diagnosis={
                "category": "zero_result_reads",
                "summary": "Read requests are often returning no memory pack at all.",
            },
            evidence=_read_evidence(zero_rows or rows),
            recommended_action="Investigate query ergonomics and retrieval thresholds for the affected repos.",
        )
        findings.append((len(zero_rows) + zero_rate, finding))

    ambiguity_groups: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in operation_rows:
        ambiguity_groups[str(row["repo_id"])].append(row)
    for repo_id, rows in ambiguity_groups.items():
        ambiguous_rows = [row for row in rows if bool(row.get("selection_ambiguous"))]
        if len(ambiguous_rows) < 3 and (len(ambiguous_rows) / max(1, len(rows))) < 0.1:
            continue
        ambiguity_rate = len(ambiguous_rows) / len(rows)
        finding = _finding(
            finding_type="failure",
            category="ambiguous_session_selection",
            severity=_gap_severity(rate=ambiguity_rate),
            title=f"{repo_id} is hitting ambiguous session selection.",
            where={"repo_id": repo_id},
            why_it_matters="Ambiguous thread selection weakens exact grounding for events and any workflow that depends on caller/thread identity.",
            metrics={
                "invocation_count": len(rows),
                "ambiguous_selection_count": len(ambiguous_rows),
                "ambiguity_rate": round(ambiguity_rate, 4),
            },
            diagnosis={
                "category": "ambiguous_session_selection",
                "summary": "Shellbrain is seeing multiple plausible sessions for the same repo usage context.",
            },
            evidence=_operation_evidence(ambiguous_rows),
            recommended_action="Tighten trusted session selection so events and guidance resolve to one exact thread more reliably.",
        )
        findings.append((len(ambiguous_rows) + ambiguity_rate, finding))

    findings.sort(
        key=lambda item: (
            _SEVERITY_WEIGHT[item[1]["severity"]],
            item[0],
            item[1]["title"],
        ),
        reverse=True,
    )
    return [item[1] for item in findings[:_MAX_FAILURES]]


def _build_capability_gaps(
    *,
    operation_rows: list[dict[str, object]],
    write_rows: list[dict[str, object]],
    pending_threads: list[dict[str, object]],
    utility_vote_rows: list[dict[str, object]],
    event_rows: list[dict[str, object]],
) -> list[dict[str, Any]]:
    """Return ranked workflow-gap findings from the telemetry window."""

    findings: list[tuple[float, dict[str, Any]]] = []

    utility_vote_times: dict[tuple[str, str], list[datetime]] = defaultdict(list)
    for row in utility_vote_rows:
        thread_id = row.get("selected_thread_id")
        if not isinstance(thread_id, str):
            continue
        utility_vote_times[(str(row["repo_id"]), thread_id)].append(_row_time(row))
    gaps_by_repo: dict[str, list[dict[str, object]]] = defaultdict(list)
    opportunities_by_repo: dict[str, int] = defaultdict(int)
    for row in pending_threads:
        repo_id = str(row["repo_id"])
        thread_id = row.get("selected_thread_id")
        if not isinstance(thread_id, str):
            continue
        opportunities_by_repo[repo_id] += 1
        first_guidance_at = _row_time(row, field="first_guidance_at")
        if _has_prior_time(
            times=utility_vote_times[(repo_id, thread_id)],
            created_at=first_guidance_at,
            inclusive=False,
            direction="after",
        ):
            continue
        gaps_by_repo[repo_id].append(row)
    for repo_id, rows in gaps_by_repo.items():
        rate = len(rows) / max(1, opportunities_by_repo[repo_id])
        finding = _finding(
            finding_type="capability_gap",
            category="utility_vote_followthrough",
            severity=_gap_severity(rate=rate),
            title=f"{repo_id} is not following through on pending utility votes.",
            where={"repo_id": repo_id},
            why_it_matters="If retrieved memories are not rated after use, Shellbrain cannot learn which recall results actually helped agents.",
            metrics={
                "opportunity_count": opportunities_by_repo[repo_id],
                "gap_count": len(rows),
                "gap_rate": round(rate, 4),
            },
            diagnosis={
                "category": "utility_vote_followthrough",
                "summary": "Threads are receiving pending utility-vote nudges without a later utility_vote write.",
            },
            evidence=_guidance_evidence(rows),
            recommended_action="Make the closeout path for utility votes more obvious and easier to complete in one shot.",
        )
        findings.append((len(rows) + rate, finding))

    event_times = _thread_times(rows=event_rows)
    write_gaps_by_repo: dict[str, list[dict[str, object]]] = defaultdict(list)
    writes_by_repo: dict[str, int] = defaultdict(int)
    for row in write_rows:
        repo_id = str(row["repo_id"])
        writes_by_repo[repo_id] += 1
        thread_id = row.get("selected_thread_id")
        if not isinstance(thread_id, str):
            write_gaps_by_repo[repo_id].append(row)
            continue
        if _has_prior_time(
            times=event_times[(repo_id, thread_id)], created_at=_row_time(row)
        ):
            continue
        write_gaps_by_repo[repo_id].append(row)
    for repo_id, rows in write_gaps_by_repo.items():
        rate = len(rows) / max(1, writes_by_repo[repo_id])
        finding = _finding(
            finding_type="capability_gap",
            category="events_before_write",
            severity=_gap_severity(rate=rate),
            title=f"{repo_id} is skipping events before writes.",
            where={"repo_id": repo_id},
            why_it_matters="Writes without earlier events weaken evidence grounding and make later review less trustworthy.",
            metrics={
                "write_count": writes_by_repo[repo_id],
                "gap_count": len(rows),
                "gap_rate": round(rate, 4),
            },
            diagnosis={
                "category": "events_before_write",
                "summary": "Writes are occurring without an earlier events call in the same thread.",
            },
            evidence=_write_evidence(rows),
            recommended_action="Tighten the write workflow so events is the obvious and easiest precursor to create or update.",
        )
        findings.append((len(rows) + rate, finding))

    findings.sort(
        key=lambda item: (
            _SEVERITY_WEIGHT[item[1]["severity"]],
            item[0],
            item[1]["title"],
        ),
        reverse=True,
    )
    return [item[1] for item in findings[:_MAX_CAPABILITY_GAPS]]


def _build_priorities(
    *, failures: list[dict[str, Any]], capability_gaps: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Return top product priorities derived from failure and gap findings."""

    grouped: dict[str, dict[str, Any]] = {}
    for finding in [*failures, *capability_gaps]:
        category = str(finding["category"])
        entry = grouped.setdefault(
            category,
            {
                "category": category,
                "finding_ids": [],
                "repo_ids": set(),
                "score": 0.0,
                "title": str(finding["title"]),
                "severity": str(finding["severity"]),
                "type": str(finding["type"]),
            },
        )
        entry["finding_ids"].append(finding["id"])
        where = finding.get("where", {})
        if isinstance(where, dict) and isinstance(where.get("repo_id"), str):
            entry["repo_ids"].add(where["repo_id"])
        metric_score = _impact_score(finding.get("metrics", {}))
        entry["score"] += _SEVERITY_WEIGHT[str(finding["severity"])] + metric_score
        if (
            _SEVERITY_WEIGHT[str(finding["severity"])]
            > _SEVERITY_WEIGHT[str(entry["severity"])]
        ):
            entry["severity"] = finding["severity"]
            entry["title"] = finding["title"]
            entry["type"] = finding["type"]
    priorities = sorted(
        grouped.values(),
        key=lambda item: (item["score"], len(item["repo_ids"])),
        reverse=True,
    )
    return [
        {
            "category": item["category"],
            "title": item["title"],
            "severity": item["severity"],
            "type": item["type"],
            "affected_repo_count": len(item["repo_ids"]),
            "affected_repos": sorted(item["repo_ids"]),
            "finding_ids": item["finding_ids"],
        }
        for item in priorities[:_PRIORITY_LIMIT]
    ]


def _build_repo_rollups(
    *,
    operation_rows: list[dict[str, object]],
    sync_rows: list[dict[str, object]],
    strengths: list[dict[str, Any]],
    failures: list[dict[str, Any]],
    capability_gaps: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return repo-scoped secondary rollups for the report."""

    repos = sorted(
        {
            *(
                str(row["repo_id"])
                for row in operation_rows
                if row.get("repo_id") is not None
            ),
            *(
                str(row["repo_id"])
                for row in sync_rows
                if row.get("repo_id") is not None
            ),
        }
    )
    failure_refs = _finding_refs_by_repo(failures)
    strength_refs = _finding_refs_by_repo(strengths)
    gap_refs = _finding_refs_by_repo(capability_gaps)
    rollups: list[dict[str, Any]] = []
    for repo_id in repos:
        repo_ops = [row for row in operation_rows if row.get("repo_id") == repo_id]
        repo_syncs = [row for row in sync_rows if row.get("repo_id") == repo_id]
        rollups.append(
            {
                "repo_id": repo_id,
                "invocation_count": len(repo_ops),
                "failure_count": sum(
                    1 for row in repo_ops if row.get("outcome") == "error"
                )
                + sum(1 for row in repo_syncs if row.get("outcome") == "error"),
                "sync_run_count": len(repo_syncs),
                "sync_failure_count": sum(
                    1 for row in repo_syncs if row.get("outcome") == "error"
                ),
                "strength_ids": strength_refs.get(repo_id, []),
                "failure_ids": failure_refs.get(repo_id, []),
                "capability_gap_ids": gap_refs.get(repo_id, []),
            }
        )
    return rollups


def _finding_refs_by_repo(findings: list[dict[str, Any]]) -> dict[str, list[str]]:
    """Return finding ids grouped by repo."""

    grouped: dict[str, list[str]] = defaultdict(list)
    for finding in findings:
        where = finding.get("where")
        if not isinstance(where, dict):
            continue
        repo_id = where.get("repo_id")
        if isinstance(repo_id, str):
            grouped[repo_id].append(str(finding["id"]))
    return grouped


def _impact_score(metrics: object) -> float:
    """Return one compact numeric score from a metrics object."""

    if not isinstance(metrics, dict):
        return 0.0
    for key in (
        "failure_count",
        "gap_count",
        "zero_result_read_count",
        "ambiguous_selection_count",
        "sync_run_count",
        "invocation_count",
        "write_count",
        "opportunity_count",
    ):
        value = metrics.get(key)
        if isinstance(value, int):
            return math.log1p(value)
    return 0.0


def _finding(
    *,
    finding_type: str,
    category: str,
    severity: str,
    title: str,
    where: dict[str, object],
    why_it_matters: str,
    metrics: dict[str, object],
    diagnosis: dict[str, object],
    evidence: list[dict[str, object]],
    recommended_action: str,
) -> dict[str, Any]:
    """Build one report finding."""

    return {
        "id": _finding_id(finding_type=finding_type, category=category, where=where),
        "type": finding_type,
        "category": category,
        "severity": severity,
        "title": title,
        "where": where,
        "why_it_matters": why_it_matters,
        "metrics": metrics,
        "diagnosis": diagnosis,
        "evidence": evidence[:_MAX_EVIDENCE],
        "recommended_action": recommended_action,
    }


def _finding_id(*, finding_type: str, category: str, where: dict[str, object]) -> str:
    """Return one stable finding id."""

    parts = [finding_type, category]
    for key in ("repo_id", "command", "host_app"):
        value = where.get(key)
        if isinstance(value, str):
            parts.append(value)
    raw = "-".join(parts)
    return re.sub(r"[^a-z0-9]+", "-", raw.lower()).strip("-")


def _summary_ref(finding: dict[str, Any]) -> dict[str, str]:
    """Return one compact summary reference to a finding."""

    return {
        "id": str(finding["id"]),
        "title": str(finding["title"]),
        "severity": str(finding["severity"]),
    }


def _overall_health(
    *, failures: list[dict[str, Any]], capability_gaps: list[dict[str, Any]]
) -> str:
    """Return one compact overall health label."""

    high_count = sum(
        1 for item in [*failures, *capability_gaps] if item["severity"] == "high"
    )
    if not failures and not capability_gaps:
        return "healthy"
    if high_count >= 2 or failures:
        return "needs_attention"
    return "mixed"


def _operation_evidence(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    """Return compact evidence records for operation rows."""

    evidence = []
    for row in rows[:_MAX_EVIDENCE]:
        evidence.append(
            {
                "invocation_id": row.get("id") or row.get("invocation_id"),
                "thread_id": row.get("selected_thread_id"),
                "created_at": _row_time(row).isoformat(),
                "error_message": _truncate(_optional_str(row.get("error_message"))),
            }
        )
    return evidence


def _sync_evidence(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    """Return compact evidence records for sync rows."""

    evidence = []
    for row in rows[:_MAX_EVIDENCE]:
        evidence.append(
            {
                "sync_run_id": row.get("id"),
                "thread_id": row.get("thread_id"),
                "created_at": _row_time(row).isoformat(),
                "error_message": _truncate(_optional_str(row.get("error_message"))),
            }
        )
    return evidence


def _read_evidence(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    """Return compact evidence records for read rows."""

    evidence = []
    for row in rows[:_MAX_EVIDENCE]:
        evidence.append(
            {
                "invocation_id": row.get("invocation_id"),
                "thread_id": row.get("selected_thread_id"),
                "created_at": _row_time(row).isoformat(),
                "zero_results": bool(row.get("zero_results")),
            }
        )
    return evidence


def _write_evidence(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    """Return compact evidence records for write rows."""

    evidence = []
    for row in rows[:_MAX_EVIDENCE]:
        evidence.append(
            {
                "invocation_id": row.get("invocation_id"),
                "thread_id": row.get("selected_thread_id"),
                "created_at": _row_time(row).isoformat(),
                "command": row.get("command"),
                "update_type": row.get("update_type"),
            }
        )
    return evidence


def _guidance_evidence(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    """Return compact evidence records for guidance rows."""

    evidence = []
    for row in rows[:_MAX_EVIDENCE]:
        evidence.append(
            {
                "thread_id": row.get("selected_thread_id"),
                "first_guidance_at": _row_time(
                    row, field="first_guidance_at"
                ).isoformat(),
                "reminder_count": int(row.get("reminder_count") or 0),
            }
        )
    return evidence


def _thread_times(
    *, rows: list[dict[str, object]]
) -> dict[tuple[str, str], list[datetime]]:
    """Return created_at timestamps grouped by repo/thread."""

    grouped: dict[tuple[str, str], list[datetime]] = defaultdict(list)
    for row in rows:
        thread_id = row.get("selected_thread_id")
        if not isinstance(thread_id, str):
            continue
        grouped[(str(row["repo_id"]), thread_id)].append(_row_time(row))
    for times in grouped.values():
        times.sort()
    return grouped


def _has_prior_time(
    *,
    times: list[datetime],
    created_at: datetime,
    inclusive: bool = False,
    direction: str = "before",
) -> bool:
    """Return whether one sorted list contains a time before or after the target."""

    if direction == "after":
        for item in times:
            if inclusive and item >= created_at:
                return True
            if not inclusive and item > created_at:
                return True
        return False
    for item in times:
        if inclusive and item <= created_at:
            return True
        if not inclusive and item < created_at:
            return True
    return False


def _row_time(row: dict[str, object], *, field: str = "created_at") -> datetime:
    """Return a timezone-aware datetime from one row mapping."""

    value = row.get(field)
    if isinstance(value, _REAL_DATETIME):
        return (
            value.astimezone(timezone.utc)
            if value.tzinfo is not None
            else value.replace(tzinfo=timezone.utc)
        )
    if isinstance(value, str):
        parsed = _REAL_DATETIME.fromisoformat(value.replace("Z", "+00:00"))
        return (
            parsed.astimezone(timezone.utc)
            if parsed.tzinfo is not None
            else parsed.replace(tzinfo=timezone.utc)
        )
    raise TypeError(f"Expected datetime field {field!r}, got {value!r}")


def _truncate(value: str | None, *, limit: int = 240) -> str | None:
    """Return a short printable error message."""

    if value is None:
        return None
    compact = " ".join(value.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1] + "…"


def _optional_str(value: object) -> str | None:
    """Return a string when present."""

    return value if isinstance(value, str) else None


def _failure_severity(*, count: int, rate: float) -> str:
    """Return one severity label for a failure cluster."""

    if count >= 5 or rate >= 0.2:
        return "high"
    if count >= 2 or rate >= 0.05:
        return "medium"
    return "low"


def _gap_severity(*, rate: float) -> str:
    """Return one severity label for a workflow-gap cluster."""

    if rate >= 0.5:
        return "high"
    if rate >= 0.2:
        return "medium"
    return "low"


def _positive_severity(volume: int) -> str:
    """Return one severity-like label for a strength, based on its volume."""

    if volume >= 100:
        return "high"
    if volume >= 25:
        return "medium"
    return "low"
