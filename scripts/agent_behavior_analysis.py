#!/usr/bin/env python3
"""Print one pre/post attention-programming behavior report as JSON."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import sys

from app.startup.admin_db import get_optional_admin_db_dsn
from app.startup.db import get_optional_db_dsn
from app.core.use_cases.metrics.agent_behavior_analysis import build_agent_behavior_report
from app.infrastructure.db.engine import get_engine


def main(argv: list[str] | None = None) -> int:
    """Parse args, load telemetry, and print one JSON report."""

    parser = argparse.ArgumentParser(description="Compare Shellbrain behavior before and after a rollout cutoff.")
    parser.add_argument("--cutoff", required=True, help="Rollout cutoff in ISO-8601 form. Date-only values are allowed.")
    parser.add_argument("--days", type=int, default=14, help="Days to analyze on each side of the cutoff. Defaults to 14.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print the JSON output.")
    args = parser.parse_args(argv)

    dsn = get_optional_db_dsn() or get_optional_admin_db_dsn()
    if not dsn:
        print("No configured database DSN found. Run this from a bootstrapped Shellbrain environment.", file=sys.stderr)
        return 2
    cutoff_at = _parse_cutoff(args.cutoff)
    engine = get_engine(dsn)
    try:
        report = build_agent_behavior_report(engine=engine, cutoff_at=cutoff_at, window_days=args.days)
    finally:
        engine.dispose()
    json_text = json.dumps(report, indent=2 if args.pretty else None, sort_keys=True)
    print(json_text)
    return 0


def _parse_cutoff(raw: str) -> datetime:
    """Parse one cutoff string as an aware UTC datetime."""

    parsed = datetime.fromisoformat(raw)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


if __name__ == "__main__":
    raise SystemExit(main())
