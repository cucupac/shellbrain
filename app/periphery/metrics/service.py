"""Build repo-scoped metrics snapshots from existing Shellbrain telemetry."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from sqlalchemy.engine import Engine

from app.periphery.metrics.queries import (
    fetch_metrics_repo_ids,
    fetch_daily_events_before_write_rows,
    fetch_daily_followthrough_rows,
    fetch_daily_utility_rows,
    fetch_daily_zero_result_rows,
    fetch_sync_health_summary,
)


_REAL_DATETIME = datetime
_CONFIDENCE_ORDER = {"low": 0, "medium": 1, "high": 2}


def list_metrics_repo_ids(*, engine: Engine) -> list[str]:
    """Return repo ids that have metrics-relevant telemetry in this Shellbrain database."""

    with engine.connect() as conn:
        return fetch_metrics_repo_ids(conn=conn)


def build_metrics_snapshot(*, engine: Engine, repo_id: str, days: int) -> dict[str, Any]:
    """Return one repo-scoped metrics snapshot suitable for artifacts and HTML rendering."""

    if days <= 0:
        raise ValueError("--days must be greater than 0")

    end_at = _REAL_DATETIME.now(timezone.utc)
    current_end_day = end_at.date()
    current_start_day = current_end_day - timedelta(days=days - 1)
    current_start = datetime.combine(current_start_day, time.min, tzinfo=timezone.utc)
    window_span = end_at - current_start
    previous_end = current_start
    previous_start = previous_end - window_span

    with engine.connect() as conn:
        utility_current_rows = fetch_daily_utility_rows(conn=conn, repo_id=repo_id, start_at=current_start, end_at=end_at)
        utility_previous_rows = fetch_daily_utility_rows(conn=conn, repo_id=repo_id, start_at=previous_start, end_at=previous_end)
        followthrough_current_rows = fetch_daily_followthrough_rows(conn=conn, repo_id=repo_id, start_at=current_start, end_at=end_at)
        followthrough_previous_rows = fetch_daily_followthrough_rows(conn=conn, repo_id=repo_id, start_at=previous_start, end_at=previous_end)
        zero_result_current_rows = fetch_daily_zero_result_rows(conn=conn, repo_id=repo_id, start_at=current_start, end_at=end_at)
        zero_result_previous_rows = fetch_daily_zero_result_rows(conn=conn, repo_id=repo_id, start_at=previous_start, end_at=previous_end)
        compliance_current_rows = fetch_daily_events_before_write_rows(conn=conn, repo_id=repo_id, start_at=current_start, end_at=end_at)
        compliance_previous_rows = fetch_daily_events_before_write_rows(conn=conn, repo_id=repo_id, start_at=previous_start, end_at=previous_end)
        sync_summary = fetch_sync_health_summary(conn=conn, repo_id=repo_id, start_at=current_start, end_at=end_at)

    current_days = _window_days(start=current_start_day, end=current_end_day)
    previous_days = _window_days(
        start=previous_start.date(),
        end=(previous_end - timedelta(microseconds=1)).date(),
    )

    utility_metric = _build_ratio_metric(
        name="Utility score trend",
        current_days=current_days,
        previous_days=previous_days,
        current_rows=utility_current_rows,
        previous_rows=utility_previous_rows,
        numerator_key="vote_sum",
        denominator_key="vote_count",
        formatter="score",
        rolling_window=7,
    )
    followthrough_metric = _build_ratio_metric(
        name="Utility follow-through",
        current_days=current_days,
        previous_days=previous_days,
        current_rows=followthrough_current_rows,
        previous_rows=followthrough_previous_rows,
        numerator_key="followthrough_count",
        denominator_key="opportunity_count",
        formatter="percent",
    )
    zero_result_metric = _build_ratio_metric(
        name="Zero-result read rate",
        current_days=current_days,
        previous_days=previous_days,
        current_rows=zero_result_current_rows,
        previous_rows=zero_result_previous_rows,
        numerator_key="zero_result_count",
        denominator_key="read_count",
        formatter="percent",
    )
    compliance_metric = _build_ratio_metric(
        name="Events-before-write compliance",
        current_days=current_days,
        previous_days=previous_days,
        current_rows=compliance_current_rows,
        previous_rows=compliance_previous_rows,
        numerator_key="compliant_count",
        denominator_key="write_count",
        formatter="percent",
    )

    metrics = [
        utility_metric,
        followthrough_metric,
        zero_result_metric,
        compliance_metric,
    ]

    status = _snapshot_status(utility_metric=utility_metric, followthrough_metric=followthrough_metric, zero_result_metric=zero_result_metric)
    alerts = _build_alerts(sync_summary=sync_summary)
    confidence = _overall_confidence(metrics=metrics, alerts=alerts)
    summary_md = _build_summary(
        status=status,
        repo_id=repo_id,
        utility_metric=utility_metric,
        followthrough_metric=followthrough_metric,
        zero_result_metric=zero_result_metric,
        compliance_metric=compliance_metric,
    )

    return {
        "repo_id": repo_id,
        "generated_at": end_at.isoformat(),
        "window_days": days,
        "current_window": {
            "start_at": current_start.isoformat(),
            "end_at": end_at.isoformat(),
        },
        "previous_window": {
            "start_at": previous_start.isoformat(),
            "end_at": previous_end.isoformat(),
        },
        "status": status,
        "confidence": confidence,
        "headline": summary_md.split(". ", 1)[0].strip().rstrip(".") + ".",
        "metrics": metrics,
        "alerts": alerts,
        "summary_md": summary_md,
    }


def _window_days(*, start: date, end: date) -> list[date]:
    """Return a list of inclusive day buckets."""

    days: list[date] = []
    current = start
    while current <= end:
        days.append(current)
        current += timedelta(days=1)
    return days


def _build_ratio_metric(
    *,
    name: str,
    current_days: list[date],
    previous_days: list[date],
    current_rows: Iterable[dict[str, object]],
    previous_rows: Iterable[dict[str, object]],
    numerator_key: str,
    denominator_key: str,
    formatter: str,
    rolling_window: int | None = None,
) -> dict[str, Any]:
    """Build one metric snapshot from grouped daily numerator/denominator rows."""

    current_indexed = _index_rows(rows=current_rows, numerator_key=numerator_key, denominator_key=denominator_key)
    previous_indexed = _index_rows(rows=previous_rows, numerator_key=numerator_key, denominator_key=denominator_key)

    current_totals = _totals_for_days(indexed=current_indexed, days=current_days)
    previous_totals = _totals_for_days(indexed=previous_indexed, days=previous_days)
    current_value = _safe_ratio(current_totals["numerator"], current_totals["denominator"])
    previous_value = _safe_ratio(previous_totals["numerator"], previous_totals["denominator"])
    delta = None if current_value is None or previous_value is None else current_value - previous_value
    confidence = _metric_confidence(name=name, sample_count=int(current_totals["denominator"]))

    series = _build_daily_series(
        days=current_days,
        indexed=current_indexed,
        rolling_window=rolling_window,
    )

    return {
        "name": name,
        "current": current_value,
        "previous": previous_value,
        "delta": delta,
        "sample_count": int(current_totals["denominator"]),
        "confidence": confidence,
        "format": formatter,
        "daily_series": series,
    }


def _index_rows(
    *,
    rows: Iterable[dict[str, object]],
    numerator_key: str,
    denominator_key: str,
) -> dict[date, dict[str, float]]:
    """Index one grouped row stream by UTC day bucket."""

    indexed: dict[date, dict[str, float]] = {}
    for row in rows:
        bucket = _coerce_day(row["day_utc"])
        indexed[bucket] = {
            "numerator": float(row[numerator_key] or 0),
            "denominator": float(row[denominator_key] or 0),
        }
    return indexed


def _build_daily_series(
    *,
    days: list[date],
    indexed: dict[date, dict[str, float]],
    rolling_window: int | None,
) -> list[dict[str, Any]]:
    """Build one current-window daily series with optional weighted rolling averages."""

    series: list[dict[str, Any]] = []
    rolling_values: list[dict[str, float]] = []

    for day in days:
        payload = indexed.get(day, {"numerator": 0.0, "denominator": 0.0})
        numerator = float(payload["numerator"])
        denominator = float(payload["denominator"])
        value = _safe_ratio(numerator, denominator)
        rolling_values.append({"numerator": numerator, "denominator": denominator})
        if rolling_window is not None:
            window = rolling_values[-rolling_window:]
            window_num = sum(item["numerator"] for item in window)
            window_den = sum(item["denominator"] for item in window)
            rolling = _safe_ratio(window_num, window_den)
        else:
            rolling = None
        series.append(
            {
                "date": day.isoformat(),
                "value": value,
                "sample_count": int(denominator),
                "rolling_value": rolling,
            }
        )

    return series


def _totals_for_days(*, indexed: dict[date, dict[str, float]], days: Iterable[date]) -> dict[str, float]:
    """Return numerator and denominator totals for one window."""

    numerator = 0.0
    denominator = 0.0
    for day in days:
        payload = indexed.get(day)
        if payload is None:
            continue
        numerator += float(payload["numerator"])
        denominator += float(payload["denominator"])
    return {"numerator": numerator, "denominator": denominator}


def _safe_ratio(numerator: float, denominator: float) -> float | None:
    """Return one ratio when a denominator exists."""

    if denominator <= 0:
        return None
    return numerator / denominator


def _coerce_day(value: object) -> date:
    """Normalize one SQL day bucket into a date."""

    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    raise TypeError(f"Unsupported day bucket: {value!r}")


def _metric_confidence(*, name: str, sample_count: int) -> str:
    """Return one fixed-confidence label for a metric and current-window sample size."""

    if name == "Utility score trend":
        if sample_count < 10:
            return "low"
        if sample_count < 25:
            return "medium"
        return "high"
    if name == "Utility follow-through":
        if sample_count < 5:
            return "low"
        if sample_count < 15:
            return "medium"
        return "high"
    if sample_count < 20:
        return "low"
    if sample_count < 50:
        return "medium"
    return "high"


def _snapshot_status(
    *,
    utility_metric: dict[str, Any],
    followthrough_metric: dict[str, Any],
    zero_result_metric: dict[str, Any],
) -> str:
    """Return the fixed snapshot status from the plan thresholds."""

    if utility_metric["sample_count"] < 10 or followthrough_metric["sample_count"] < 5:
        return "insufficient_signal"

    if _value_or_none(utility_metric["delta"]) is not None and float(utility_metric["delta"]) <= -0.10:
        return "slipping"
    if _value_or_none(zero_result_metric["delta"]) is not None and float(zero_result_metric["delta"]) >= 0.05:
        return "slipping"
    if _value_or_none(followthrough_metric["delta"]) is not None and float(followthrough_metric["delta"]) <= -0.10:
        return "slipping"
    return "healthy"


def _build_alerts(*, sync_summary: dict[str, object]) -> list[dict[str, Any]]:
    """Return any pipeline/trust alerts for the current snapshot."""

    sync_run_count = int(sync_summary.get("sync_run_count") or 0)
    failed_sync_count = int(sync_summary.get("failed_sync_count") or 0)
    if sync_run_count == 0:
        return []
    failure_rate = failed_sync_count / sync_run_count
    if failure_rate <= 0.05:
        return []
    return [
        {
            "code": "sync_health_warning",
            "severity": "warning",
            "message": f"Sync health is reducing confidence in the snapshot ({failed_sync_count} failed sync runs out of {sync_run_count}).",
            "failure_rate": failure_rate,
            "sync_run_count": sync_run_count,
            "failed_sync_count": failed_sync_count,
        }
    ]


def _overall_confidence(*, metrics: list[dict[str, Any]], alerts: list[dict[str, Any]]) -> str:
    """Return one overall confidence label, degraded by sync alerts when present."""

    current = min(metrics, key=lambda item: _CONFIDENCE_ORDER[str(item["confidence"])])
    confidence = str(current["confidence"])
    if not alerts:
        return confidence
    if confidence == "high":
        return "medium"
    return "low"


def _build_summary(
    *,
    status: str,
    repo_id: str,
    utility_metric: dict[str, Any],
    followthrough_metric: dict[str, Any],
    zero_result_metric: dict[str, Any],
    compliance_metric: dict[str, Any],
) -> str:
    """Return the three-sentence markdown summary required by the plan."""

    utility_votes = int(utility_metric["sample_count"])
    opportunities = int(followthrough_metric["sample_count"])
    sentence_one: str
    if status == "insufficient_signal":
        sentence_one = (
            f"Utility score trend and Utility follow-through do not have enough signal yet for a strong read in {repo_id}, "
            f"with {utility_votes} utility votes and {opportunities} Utility follow-through opportunities in the current window."
        )
    elif status == "slipping":
        sentence_one = (
            f"Utility score trend is slipping for {repo_id}, and Utility follow-through or Zero-result read rate also moved in the wrong direction over the current window."
        )
    else:
        sentence_one = (
            f"Utility score trend is healthy for {repo_id}, and Utility follow-through stayed stable enough to support a positive read on the current window."
        )

    sentence_two = (
        f"Zero-result read rate is {_format_metric_value(zero_result_metric)} and Events-before-write compliance is {_format_metric_value(compliance_metric)} "
        f"when compared with the previous window."
    )
    sentence_three = (
        f"Watch Utility score trend, Utility follow-through, Zero-result read rate, and Events-before-write compliance next to confirm whether the learning loop is strengthening or just noisy."
    )
    return " ".join([sentence_one, sentence_two, sentence_three])


def _format_metric_value(metric: dict[str, Any]) -> str:
    """Return one compact metric comparison string for summaries and cards."""

    current = metric.get("current")
    previous = metric.get("previous")
    if metric["format"] == "score":
        current_text = _format_score(current)
        previous_text = _format_score(previous)
    else:
        current_text = _format_percent(current)
        previous_text = _format_percent(previous)
    return f"{current_text} now versus {previous_text} before"


def _format_score(value: object) -> str:
    """Format one utility score value."""

    if value is None:
        return "no score"
    return f"{float(value):+.2f}"


def _format_percent(value: object) -> str:
    """Format one ratio as a percentage."""

    if value is None:
        return "no rate"
    return f"{float(value) * 100:.1f}%"


def _value_or_none(value: object) -> float | None:
    """Normalize optional numeric values."""

    if value is None:
        return None
    return float(value)
