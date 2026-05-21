#!/usr/bin/env python3
"""Archive and remove accidental solver historical knowledge-builder writes.

This is a one-off internal cleanup for the May 20, 2026 PDT incident where the
knowledge builder processed historical solver episodes. It defaults to dry-run.
Execute mode requires an explicit confirmation token.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tomllib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row


DEFAULT_REPO_ID = "github.com/relayprotocol/solver"
DEFAULT_START = "2026-05-20 00:00:00 America/Los_Angeles"
DEFAULT_END = "2026-05-21 00:00:00 America/Los_Angeles"
DEFAULT_ARCHIVE_ROOT = "output/cleanup/20260520-solver-backfill"
CONFIRMATION_TOKEN = "2026-05-20-solver-historical-backfill"

EXPECTED_COUNTS = {
    "historical_runs": (677, 0),
    "historical_episodes": (663, 0),
    "doomed_memories": (596, 0),
    "doomed_utility_observations": (249, 40),
    "historical_problem_runs": (167, 0),
    "historical_concepts_created": (92, 10),
    "pure_historical_concepts": (87, 15),
    "mixed_historical_concepts": (5, 10),
}

PREDICATE_SUMMARY = {
    "historical_runs": (
        "knowledge_build_runs.repo_id = target repo, run started during the "
        "incident window, and source episode started before the incident window"
    ),
    "doomed_memories": (
        "write_effect_items.effect_type = 'memory.create' from invocations tied "
        "to historical runs"
    ),
    "doomed_utility_observations": (
        "utility writes from historical-run invocations, plus observations whose "
        "memory_id or problem_id is a doomed memory"
    ),
    "historical_problem_runs": (
        "build_knowledge problem_runs tied to historical episodes, plus problem "
        "runs referencing doomed memories"
    ),
    "pure_historical_concepts": (
        "concepts created near historical concept.add invocations, excluding "
        "concepts later touched by real May 20 evidence or real May 20 memories"
    ),
    "mixed_historical_concepts": (
        "historical concept shells retained because real May 20 evidence touched "
        "them; historical facets and stale embeddings are pruned"
    ),
    "do_not_delete": (
        "knowledge_build_runs, operation_invocations, write_effect_items, episodes, "
        "episode_events, episode_sync_runs, and model-usage rows"
    ),
}


def main() -> int:
    args = _parse_args()
    execute = bool(args.execute)
    if execute and args.confirm != CONFIRMATION_TOKEN:
        raise SystemExit(
            "Execute mode requires --confirm "
            f"{CONFIRMATION_TOKEN!r}. No rows were changed."
        )

    archive_dir = _new_archive_dir(Path(args.archive_root))
    archive_dir.mkdir(parents=True, exist_ok=False)

    dsn = _resolve_dsn(args.dsn)
    manifest: dict[str, Any] = {
        "generated_at": datetime.now(UTC).isoformat(),
        "execute": execute,
        "repo_id": args.repo_id,
        "incident_window": {"start": args.start, "end": args.end},
        "confirmation_required": CONFIRMATION_TOKEN,
        "confirmation_provided": execute,
        "predicate_summary": PREDICATE_SUMMARY,
        "archive_dir": str(archive_dir),
        "git_revision": _maybe_git_revision(),
    }

    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        conn.execute("BEGIN ISOLATION LEVEL REPEATABLE READ")
        try:
            _create_target_tables(
                conn=conn, repo_id=args.repo_id, start=args.start, end=args.end
            )
            counts = _target_counts(conn)
            manifest["target_counts"] = counts
            manifest["count_expectations"] = EXPECTED_COUNTS
            manifest["count_warnings"] = _count_warnings(counts)
            _write_selected_rows(conn=conn, archive_dir=archive_dir, manifest=manifest)
            _write_manifest(archive_dir=archive_dir, manifest=manifest)

            if not execute:
                conn.rollback()
                print(json.dumps({"status": "dry_run", **_result_payload(manifest)}, indent=2))
                return 0

            deleted_counts = _delete_targets(conn)
            manifest["deleted_counts"] = deleted_counts
            verification = _verify_cleanup(conn)
            manifest["verification"] = verification
            _raise_if_verification_failed(verification)
            _write_manifest(archive_dir=archive_dir, manifest=manifest)
            conn.commit()
            print(json.dumps({"status": "executed", **_result_payload(manifest)}, indent=2))
            return 0
        except Exception:
            conn.rollback()
            raise


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Archive and remove May 20 solver historical knowledge-builder backfill artifacts."
    )
    parser.add_argument("--repo-id", default=DEFAULT_REPO_ID)
    parser.add_argument("--start", default=DEFAULT_START)
    parser.add_argument("--end", default=DEFAULT_END)
    parser.add_argument("--archive-root", default=DEFAULT_ARCHIVE_ROOT)
    parser.add_argument(
        "--dsn",
        help=(
            "Postgres DSN. Defaults to SHELLBRAIN_DB_APP_DSN, then "
            "~/.shellbrain/config.toml database.app_dsn."
        ),
    )
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirm")
    return parser.parse_args()


def _resolve_dsn(value: str | None) -> str:
    dsn = value or os.getenv("SHELLBRAIN_DB_APP_DSN")
    if dsn:
        return _normalize_psycopg_dsn(dsn)
    config_path = Path.home() / ".shellbrain" / "config.toml"
    config = tomllib.loads(config_path.read_text())
    return _normalize_psycopg_dsn(str(config["database"]["app_dsn"]))


def _normalize_psycopg_dsn(dsn: str) -> str:
    return dsn.replace("postgresql+psycopg://", "postgresql://", 1)


def _new_archive_dir(root: Path) -> Path:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return root / timestamp


def _create_target_tables(
    *, conn: psycopg.Connection[dict[str, Any]], repo_id: str, start: str, end: str
) -> None:
    params = {"repo_id": repo_id, "start": start, "end": end}
    for statement in _TARGET_TABLE_SQL:
        conn.execute(statement, params)
    conn.execute("ANALYZE cleanup_doomed_memories")
    conn.execute("ANALYZE cleanup_pure_historical_concepts")
    conn.execute("ANALYZE cleanup_doomed_claims")
    conn.execute("ANALYZE cleanup_doomed_groundings")
    conn.execute("ANALYZE cleanup_doomed_relations")
    conn.execute("ANALYZE cleanup_doomed_memory_links")


_TARGET_TABLE_SQL = [
    """
    CREATE TEMP TABLE cleanup_historical_runs ON COMMIT DROP AS
    SELECT kbr.id AS run_id, kbr.episode_id
    FROM knowledge_build_runs kbr
    JOIN episodes e ON e.id = kbr.episode_id
    WHERE kbr.repo_id = %(repo_id)s
      AND kbr.started_at >= %(start)s::timestamptz
      AND kbr.started_at < %(end)s::timestamptz
      AND e.started_at < %(start)s::timestamptz
    """,
    """
    CREATE TEMP TABLE cleanup_today_runs ON COMMIT DROP AS
    SELECT kbr.id AS run_id, kbr.episode_id
    FROM knowledge_build_runs kbr
    JOIN episodes e ON e.id = kbr.episode_id
    WHERE kbr.repo_id = %(repo_id)s
      AND kbr.started_at >= %(start)s::timestamptz
      AND kbr.started_at < %(end)s::timestamptz
      AND e.started_at >= %(start)s::timestamptz
      AND e.started_at < %(end)s::timestamptz
    """,
    """
    CREATE TEMP TABLE cleanup_historical_invocations ON COMMIT DROP AS
    SELECT oi.id, oi.command, oi.created_at
    FROM operation_invocations oi
    JOIN cleanup_historical_runs h ON h.run_id = oi.knowledge_build_run_id
    WHERE oi.repo_id = %(repo_id)s
    """,
    """
    CREATE TEMP TABLE cleanup_today_invocations ON COMMIT DROP AS
    SELECT oi.id, oi.command, oi.created_at
    FROM operation_invocations oi
    JOIN cleanup_today_runs t ON t.run_id = oi.knowledge_build_run_id
    WHERE oi.repo_id = %(repo_id)s
    """,
    """
    CREATE TEMP TABLE cleanup_historical_events ON COMMIT DROP AS
    SELECT ee.id
    FROM episode_events ee
    JOIN cleanup_historical_runs h ON h.episode_id = ee.episode_id
    """,
    """
    CREATE TEMP TABLE cleanup_today_events ON COMMIT DROP AS
    SELECT ee.id
    FROM episode_events ee
    JOIN cleanup_today_runs t ON t.episode_id = ee.episode_id
    """,
    """
    CREATE TEMP TABLE cleanup_doomed_memories ON COMMIT DROP AS
    SELECT DISTINCT wei.primary_memory_id AS memory_id
    FROM write_effect_items wei
    JOIN cleanup_historical_invocations hi ON hi.id = wei.invocation_id
    WHERE wei.effect_type = 'memory.create'
      AND wei.primary_memory_id IS NOT NULL
    """,
    """
    CREATE TEMP TABLE cleanup_today_memories ON COMMIT DROP AS
    SELECT DISTINCT wei.primary_memory_id AS memory_id
    FROM write_effect_items wei
    JOIN cleanup_today_invocations ti ON ti.id = wei.invocation_id
    WHERE wei.effect_type = 'memory.create'
      AND wei.primary_memory_id IS NOT NULL
    """,
    """
    CREATE TEMP TABLE cleanup_concept_ops ON COMMIT DROP AS
    SELECT id, command, created_at, 'historical'::text AS source_class
    FROM cleanup_historical_invocations
    WHERE command IN ('concept.add', 'concept.update')
    UNION ALL
    SELECT id, command, created_at, 'today'::text AS source_class
    FROM cleanup_today_invocations
    WHERE command IN ('concept.add', 'concept.update')
    """,
    """
    CREATE TEMP TABLE cleanup_historical_concepts_created ON COMMIT DROP AS
    SELECT DISTINCT c.id AS concept_id
    FROM concepts c
    JOIN LATERAL (
        SELECT op.created_at
        FROM cleanup_concept_ops op
        WHERE op.source_class = 'historical'
          AND op.command = 'concept.add'
          AND c.created_at >= op.created_at - interval '2.5 seconds'
          AND c.created_at < op.created_at + interval '120 seconds'
        ORDER BY ABS(EXTRACT(EPOCH FROM (c.created_at - op.created_at)))
        LIMIT 1
    ) op ON true
    WHERE c.repo_id = %(repo_id)s
      AND c.created_at >= %(start)s::timestamptz
      AND c.created_at < %(end)s::timestamptz
    """,
    """
    CREATE TEMP TABLE cleanup_today_touched_concepts ON COMMIT DROP AS
    SELECT DISTINCT concept_id
    FROM concept_claims
    WHERE source_ref IN (SELECT id FROM cleanup_today_events)
    UNION
    SELECT DISTINCT concept_id
    FROM concept_groundings
    WHERE source_ref IN (SELECT id FROM cleanup_today_events)
    UNION
    SELECT DISTINCT subject_concept_id
    FROM concept_relations
    WHERE source_ref IN (SELECT id FROM cleanup_today_events)
    UNION
    SELECT DISTINCT object_concept_id
    FROM concept_relations
    WHERE source_ref IN (SELECT id FROM cleanup_today_events)
    UNION
    SELECT DISTINCT concept_id
    FROM concept_memory_links
    WHERE source_ref IN (SELECT id FROM cleanup_today_events)
    UNION
    SELECT DISTINCT concept_id
    FROM concept_memory_links
    WHERE memory_id IN (SELECT memory_id FROM cleanup_today_memories)
    UNION
    SELECT DISTINCT cc.concept_id
    FROM concept_claims cc
    JOIN LATERAL (
        SELECT op.source_class
        FROM cleanup_concept_ops op
        WHERE cc.created_at >= op.created_at - interval '2.5 seconds'
          AND cc.created_at < op.created_at + interval '120 seconds'
        ORDER BY ABS(EXTRACT(EPOCH FROM (cc.created_at - op.created_at)))
        LIMIT 1
    ) op ON true
    WHERE cc.repo_id = %(repo_id)s
      AND op.source_class = 'today'
    UNION
    SELECT DISTINCT cg.concept_id
    FROM concept_groundings cg
    JOIN LATERAL (
        SELECT op.source_class
        FROM cleanup_concept_ops op
        WHERE cg.created_at >= op.created_at - interval '2.5 seconds'
          AND cg.created_at < op.created_at + interval '120 seconds'
        ORDER BY ABS(EXTRACT(EPOCH FROM (cg.created_at - op.created_at)))
        LIMIT 1
    ) op ON true
    WHERE cg.repo_id = %(repo_id)s
      AND op.source_class = 'today'
    UNION
    SELECT DISTINCT cr.subject_concept_id
    FROM concept_relations cr
    JOIN LATERAL (
        SELECT op.source_class
        FROM cleanup_concept_ops op
        WHERE cr.created_at >= op.created_at - interval '2.5 seconds'
          AND cr.created_at < op.created_at + interval '120 seconds'
        ORDER BY ABS(EXTRACT(EPOCH FROM (cr.created_at - op.created_at)))
        LIMIT 1
    ) op ON true
    WHERE cr.repo_id = %(repo_id)s
      AND op.source_class = 'today'
    UNION
    SELECT DISTINCT cr.object_concept_id
    FROM concept_relations cr
    JOIN LATERAL (
        SELECT op.source_class
        FROM cleanup_concept_ops op
        WHERE cr.created_at >= op.created_at - interval '2.5 seconds'
          AND cr.created_at < op.created_at + interval '120 seconds'
        ORDER BY ABS(EXTRACT(EPOCH FROM (cr.created_at - op.created_at)))
        LIMIT 1
    ) op ON true
    WHERE cr.repo_id = %(repo_id)s
      AND op.source_class = 'today'
    UNION
    SELECT DISTINCT ml.concept_id
    FROM concept_memory_links ml
    JOIN LATERAL (
        SELECT op.source_class
        FROM cleanup_concept_ops op
        WHERE ml.created_at >= op.created_at - interval '2.5 seconds'
          AND ml.created_at < op.created_at + interval '120 seconds'
        ORDER BY ABS(EXTRACT(EPOCH FROM (ml.created_at - op.created_at)))
        LIMIT 1
    ) op ON true
    WHERE ml.repo_id = %(repo_id)s
      AND op.source_class = 'today'
    """,
    """
    CREATE TEMP TABLE cleanup_pure_historical_concepts ON COMMIT DROP AS
    SELECT concept_id
    FROM cleanup_historical_concepts_created
    EXCEPT
    SELECT concept_id
    FROM cleanup_today_touched_concepts
    """,
    """
    CREATE TEMP TABLE cleanup_mixed_historical_concepts ON COMMIT DROP AS
    SELECT concept_id
    FROM cleanup_historical_concepts_created
    EXCEPT
    SELECT concept_id
    FROM cleanup_pure_historical_concepts
    """,
    """
    CREATE TEMP TABLE cleanup_claim_source_class ON COMMIT DROP AS
    SELECT cc.id, op.source_class
    FROM concept_claims cc
    JOIN LATERAL (
        SELECT op.source_class
        FROM cleanup_concept_ops op
        WHERE cc.created_at >= op.created_at - interval '2.5 seconds'
          AND cc.created_at < op.created_at + interval '120 seconds'
        ORDER BY ABS(EXTRACT(EPOCH FROM (cc.created_at - op.created_at)))
        LIMIT 1
    ) op ON true
    WHERE cc.repo_id = %(repo_id)s
    """,
    """
    CREATE TEMP TABLE cleanup_grounding_source_class ON COMMIT DROP AS
    SELECT cg.id, op.source_class
    FROM concept_groundings cg
    JOIN LATERAL (
        SELECT op.source_class
        FROM cleanup_concept_ops op
        WHERE cg.created_at >= op.created_at - interval '2.5 seconds'
          AND cg.created_at < op.created_at + interval '120 seconds'
        ORDER BY ABS(EXTRACT(EPOCH FROM (cg.created_at - op.created_at)))
        LIMIT 1
    ) op ON true
    WHERE cg.repo_id = %(repo_id)s
    """,
    """
    CREATE TEMP TABLE cleanup_relation_source_class ON COMMIT DROP AS
    SELECT cr.id, op.source_class
    FROM concept_relations cr
    JOIN LATERAL (
        SELECT op.source_class
        FROM cleanup_concept_ops op
        WHERE cr.created_at >= op.created_at - interval '2.5 seconds'
          AND cr.created_at < op.created_at + interval '120 seconds'
        ORDER BY ABS(EXTRACT(EPOCH FROM (cr.created_at - op.created_at)))
        LIMIT 1
    ) op ON true
    WHERE cr.repo_id = %(repo_id)s
    """,
    """
    CREATE TEMP TABLE cleanup_link_source_class ON COMMIT DROP AS
    SELECT ml.id, op.source_class
    FROM concept_memory_links ml
    JOIN LATERAL (
        SELECT op.source_class
        FROM cleanup_concept_ops op
        WHERE ml.created_at >= op.created_at - interval '2.5 seconds'
          AND ml.created_at < op.created_at + interval '120 seconds'
        ORDER BY ABS(EXTRACT(EPOCH FROM (ml.created_at - op.created_at)))
        LIMIT 1
    ) op ON true
    WHERE ml.repo_id = %(repo_id)s
    """,
    """
    CREATE TEMP TABLE cleanup_doomed_claims ON COMMIT DROP AS
    SELECT id
    FROM concept_claims
    WHERE concept_id IN (SELECT concept_id FROM cleanup_pure_historical_concepts)
    UNION
    SELECT id
    FROM concept_claims
    WHERE source_ref IN (SELECT id FROM cleanup_historical_events)
    UNION
    SELECT cc.id
    FROM concept_claims cc
    JOIN cleanup_claim_source_class sc ON sc.id = cc.id
    WHERE sc.source_class = 'historical'
      AND (cc.source_ref IS NULL OR cc.source_ref NOT IN (SELECT id FROM cleanup_today_events))
    """,
    """
    CREATE TEMP TABLE cleanup_doomed_groundings ON COMMIT DROP AS
    SELECT id
    FROM concept_groundings
    WHERE concept_id IN (SELECT concept_id FROM cleanup_pure_historical_concepts)
    UNION
    SELECT id
    FROM concept_groundings
    WHERE source_ref IN (SELECT id FROM cleanup_historical_events)
    UNION
    SELECT cg.id
    FROM concept_groundings cg
    JOIN cleanup_grounding_source_class sc ON sc.id = cg.id
    WHERE sc.source_class = 'historical'
      AND (cg.source_ref IS NULL OR cg.source_ref NOT IN (SELECT id FROM cleanup_today_events))
    """,
    """
    CREATE TEMP TABLE cleanup_doomed_relations ON COMMIT DROP AS
    SELECT id
    FROM concept_relations
    WHERE subject_concept_id IN (SELECT concept_id FROM cleanup_pure_historical_concepts)
       OR object_concept_id IN (SELECT concept_id FROM cleanup_pure_historical_concepts)
    UNION
    SELECT id
    FROM concept_relations
    WHERE source_ref IN (SELECT id FROM cleanup_historical_events)
    UNION
    SELECT cr.id
    FROM concept_relations cr
    JOIN cleanup_relation_source_class sc ON sc.id = cr.id
    WHERE sc.source_class = 'historical'
      AND (cr.source_ref IS NULL OR cr.source_ref NOT IN (SELECT id FROM cleanup_today_events))
    """,
    """
    CREATE TEMP TABLE cleanup_doomed_memory_links ON COMMIT DROP AS
    SELECT id
    FROM concept_memory_links
    WHERE concept_id IN (SELECT concept_id FROM cleanup_pure_historical_concepts)
       OR memory_id IN (SELECT memory_id FROM cleanup_doomed_memories)
    UNION
    SELECT id
    FROM concept_memory_links
    WHERE source_ref IN (SELECT id FROM cleanup_historical_events)
    UNION
    SELECT ml.id
    FROM concept_memory_links ml
    JOIN cleanup_link_source_class sc ON sc.id = ml.id
    WHERE sc.source_class = 'historical'
      AND (ml.source_ref IS NULL OR ml.source_ref NOT IN (SELECT id FROM cleanup_today_events))
    """,
    """
    CREATE TEMP TABLE cleanup_touched_retained_concepts ON COMMIT DROP AS
    SELECT DISTINCT concept_id
    FROM concept_claims
    WHERE id IN (SELECT id FROM cleanup_doomed_claims)
      AND concept_id NOT IN (SELECT concept_id FROM cleanup_pure_historical_concepts)
    UNION
    SELECT DISTINCT concept_id
    FROM concept_groundings
    WHERE id IN (SELECT id FROM cleanup_doomed_groundings)
      AND concept_id NOT IN (SELECT concept_id FROM cleanup_pure_historical_concepts)
    UNION
    SELECT DISTINCT subject_concept_id
    FROM concept_relations
    WHERE id IN (SELECT id FROM cleanup_doomed_relations)
      AND subject_concept_id NOT IN (SELECT concept_id FROM cleanup_pure_historical_concepts)
    UNION
    SELECT DISTINCT object_concept_id
    FROM concept_relations
    WHERE id IN (SELECT id FROM cleanup_doomed_relations)
      AND object_concept_id NOT IN (SELECT concept_id FROM cleanup_pure_historical_concepts)
    UNION
    SELECT DISTINCT concept_id
    FROM concept_memory_links
    WHERE id IN (SELECT id FROM cleanup_doomed_memory_links)
      AND concept_id NOT IN (SELECT concept_id FROM cleanup_pure_historical_concepts)
    """,
    """
    CREATE TEMP TABLE cleanup_doomed_utility_observations ON COMMIT DROP AS
    SELECT DISTINCT u.id
    FROM utility_observations u
    WHERE u.memory_id IN (SELECT memory_id FROM cleanup_doomed_memories)
       OR u.problem_id IN (SELECT memory_id FROM cleanup_doomed_memories)
    UNION
    SELECT DISTINCT wei.params_json->>'id'
    FROM write_effect_items wei
    JOIN cleanup_historical_invocations hi ON hi.id = wei.invocation_id
    WHERE wei.effect_type = 'utility_observation.append'
      AND wei.params_json ? 'id'
    """,
    """
    CREATE TEMP TABLE cleanup_historical_problem_runs ON COMMIT DROP AS
    SELECT DISTINCT pr.id
    FROM problem_runs pr
    WHERE pr.repo_id = %(repo_id)s
      AND pr.episode_id IN (SELECT episode_id FROM cleanup_historical_runs)
      AND pr.opened_by = 'build_knowledge'
    UNION
    SELECT DISTINCT pr.id
    FROM problem_runs pr
    WHERE pr.problem_memory_id IN (SELECT memory_id FROM cleanup_doomed_memories)
       OR pr.solution_memory_id IN (SELECT memory_id FROM cleanup_doomed_memories)
    """,
    """
    CREATE TEMP TABLE cleanup_doomed_read_result_items ON COMMIT DROP AS
    SELECT rri.invocation_id, rri.ordinal
    FROM read_result_items rri
    WHERE rri.memory_id IN (SELECT memory_id FROM cleanup_doomed_memories)
       OR rri.anchor_memory_id IN (SELECT memory_id FROM cleanup_doomed_memories)
    """,
    """
    CREATE TEMP TABLE cleanup_doomed_association_observations ON COMMIT DROP AS
    SELECT id
    FROM association_observations
    WHERE from_memory_id IN (SELECT memory_id FROM cleanup_doomed_memories)
       OR to_memory_id IN (SELECT memory_id FROM cleanup_doomed_memories)
       OR problem_id IN (SELECT memory_id FROM cleanup_doomed_memories)
    """,
    """
    CREATE TEMP TABLE cleanup_doomed_association_edges ON COMMIT DROP AS
    SELECT id
    FROM association_edges
    WHERE from_memory_id IN (SELECT memory_id FROM cleanup_doomed_memories)
       OR to_memory_id IN (SELECT memory_id FROM cleanup_doomed_memories)
    """,
    """
    CREATE TEMP TABLE cleanup_doomed_concept_evidence ON COMMIT DROP AS
    SELECT id
    FROM concept_evidence
    WHERE (target_type = 'claim' AND target_id IN (SELECT id FROM cleanup_doomed_claims))
       OR (target_type = 'grounding' AND target_id IN (SELECT id FROM cleanup_doomed_groundings))
       OR (target_type = 'relation' AND target_id IN (SELECT id FROM cleanup_doomed_relations))
       OR (target_type = 'memory_link' AND target_id IN (SELECT id FROM cleanup_doomed_memory_links))
       OR memory_id IN (SELECT memory_id FROM cleanup_doomed_memories)
    """,
    """
    CREATE TEMP TABLE cleanup_doomed_anchors ON COMMIT DROP AS
    SELECT DISTINCT a.id
    FROM anchors a
    WHERE a.repo_id = %(repo_id)s
      AND a.created_at >= %(start)s::timestamptz
      AND a.created_at < %(end)s::timestamptz
      AND (
          a.id IN (
              SELECT anchor_id
              FROM concept_groundings
              WHERE id IN (SELECT id FROM cleanup_doomed_groundings)
          )
          OR a.id IN (
              SELECT anchor_id
              FROM concept_evidence
              WHERE id IN (SELECT id FROM cleanup_doomed_concept_evidence)
                AND anchor_id IS NOT NULL
          )
      )
      AND NOT EXISTS (
          SELECT 1
          FROM concept_groundings cg
          WHERE cg.anchor_id = a.id
            AND cg.id NOT IN (SELECT id FROM cleanup_doomed_groundings)
      )
      AND NOT EXISTS (
          SELECT 1
          FROM concept_evidence ce
          WHERE ce.anchor_id = a.id
            AND ce.id NOT IN (SELECT id FROM cleanup_doomed_concept_evidence)
      )
    """,
    """
    CREATE TEMP TABLE cleanup_doomed_evidence_refs ON COMMIT DROP AS
    SELECT DISTINCT er.id
    FROM evidence_refs er
    WHERE er.repo_id = %(repo_id)s
      AND er.created_at >= %(start)s::timestamptz
      AND er.created_at < %(end)s::timestamptz
      AND er.episode_event_id IN (SELECT id FROM cleanup_historical_events)
      AND NOT EXISTS (
          SELECT 1
          FROM memory_evidence me
          WHERE me.evidence_id = er.id
            AND me.memory_id NOT IN (SELECT memory_id FROM cleanup_doomed_memories)
      )
      AND NOT EXISTS (
          SELECT 1
          FROM association_edge_evidence aee
          WHERE aee.evidence_id = er.id
            AND aee.edge_id NOT IN (SELECT id FROM cleanup_doomed_association_edges)
      )
      AND NOT EXISTS (
          SELECT 1
          FROM utility_observation_evidence uoe
          WHERE uoe.evidence_id = er.id
            AND uoe.observation_id NOT IN (SELECT id FROM cleanup_doomed_utility_observations)
      )
    """,
]


def _target_counts(conn: psycopg.Connection[dict[str, Any]]) -> dict[str, int]:
    count_queries = {
        "historical_runs": "SELECT COUNT(*) FROM cleanup_historical_runs",
        "historical_episodes": "SELECT COUNT(DISTINCT episode_id) FROM cleanup_historical_runs",
        "historical_invocations": "SELECT COUNT(*) FROM cleanup_historical_invocations",
        "doomed_memories": "SELECT COUNT(*) FROM cleanup_doomed_memories",
        "today_memories_to_keep": "SELECT COUNT(*) FROM cleanup_today_memories",
        "doomed_utility_observations": "SELECT COUNT(*) FROM cleanup_doomed_utility_observations",
        "historical_problem_runs": "SELECT COUNT(*) FROM cleanup_historical_problem_runs",
        "historical_concepts_created": "SELECT COUNT(*) FROM cleanup_historical_concepts_created",
        "pure_historical_concepts": "SELECT COUNT(*) FROM cleanup_pure_historical_concepts",
        "mixed_historical_concepts": "SELECT COUNT(*) FROM cleanup_mixed_historical_concepts",
        "touched_retained_concepts": "SELECT COUNT(*) FROM cleanup_touched_retained_concepts",
        "doomed_claims": "SELECT COUNT(*) FROM cleanup_doomed_claims",
        "doomed_groundings": "SELECT COUNT(*) FROM cleanup_doomed_groundings",
        "doomed_relations": "SELECT COUNT(*) FROM cleanup_doomed_relations",
        "doomed_memory_links": "SELECT COUNT(*) FROM cleanup_doomed_memory_links",
        "doomed_read_result_items": "SELECT COUNT(*) FROM cleanup_doomed_read_result_items",
        "doomed_association_observations": "SELECT COUNT(*) FROM cleanup_doomed_association_observations",
        "doomed_association_edges": "SELECT COUNT(*) FROM cleanup_doomed_association_edges",
        "doomed_concept_evidence": "SELECT COUNT(*) FROM cleanup_doomed_concept_evidence",
        "doomed_anchors": "SELECT COUNT(*) FROM cleanup_doomed_anchors",
        "doomed_evidence_refs": "SELECT COUNT(*) FROM cleanup_doomed_evidence_refs",
    }
    return {
        name: int(conn.execute(query).fetchone()["count"])
        for name, query in count_queries.items()
    }


def _count_warnings(counts: dict[str, int]) -> list[str]:
    warnings: list[str] = []
    for key, expectation in EXPECTED_COUNTS.items():
        expected, tolerance = expectation
        observed = counts.get(key)
        if observed is None:
            continue
        if abs(observed - expected) > tolerance:
            warnings.append(
                f"{key}: observed {observed}, expected about {expected} "
                f"(tolerance {tolerance})"
            )
    return warnings


def _write_selected_rows(
    *,
    conn: psycopg.Connection[dict[str, Any]],
    archive_dir: Path,
    manifest: dict[str, Any],
) -> None:
    exports: dict[str, dict[str, Any]] = {}
    for name, query in _EXPORT_QUERIES.items():
        path = archive_dir / f"{name}.jsonl"
        row_count = _write_jsonl(conn=conn, query=query, path=path)
        exports[name] = {
            "row_count": row_count,
            "path": str(path),
            "sha256": _sha256(path),
        }
    manifest["exports"] = exports


_EXPORT_QUERIES = {
    "knowledge_build_runs_watermarks_retained": """
        SELECT kbr.*
        FROM knowledge_build_runs kbr
        JOIN cleanup_historical_runs h ON h.run_id = kbr.id
        ORDER BY kbr.started_at, kbr.id
    """,
    "operation_invocations_retained": """
        SELECT oi.*
        FROM operation_invocations oi
        JOIN cleanup_historical_invocations hi ON hi.id = oi.id
        ORDER BY oi.created_at, oi.id
    """,
    "write_effect_items_retained": """
        SELECT wei.*
        FROM write_effect_items wei
        JOIN cleanup_historical_invocations hi ON hi.id = wei.invocation_id
        ORDER BY wei.invocation_id, wei.ordinal
    """,
    "memories": """
        SELECT m.*
        FROM memories m
        JOIN cleanup_doomed_memories d ON d.memory_id = m.id
        ORDER BY m.created_at, m.id
    """,
    "memory_embeddings": """
        SELECT me.*
        FROM memory_embeddings me
        JOIN cleanup_doomed_memories d ON d.memory_id = me.memory_id
        ORDER BY me.memory_id
    """,
    "memory_evidence": """
        SELECT me.*
        FROM memory_evidence me
        JOIN cleanup_doomed_memories d ON d.memory_id = me.memory_id
        ORDER BY me.memory_id, me.evidence_id
    """,
    "evidence_refs": """
        SELECT er.*
        FROM evidence_refs er
        JOIN cleanup_doomed_evidence_refs d ON d.id = er.id
        ORDER BY er.created_at, er.id
    """,
    "read_result_items": """
        SELECT rri.*
        FROM read_result_items rri
        JOIN cleanup_doomed_read_result_items d
          ON d.invocation_id = rri.invocation_id AND d.ordinal = rri.ordinal
        ORDER BY rri.invocation_id, rri.ordinal
    """,
    "utility_observations": """
        SELECT u.*
        FROM utility_observations u
        JOIN cleanup_doomed_utility_observations d ON d.id = u.id
        ORDER BY u.created_at, u.id
    """,
    "utility_observation_evidence": """
        SELECT uoe.*
        FROM utility_observation_evidence uoe
        JOIN cleanup_doomed_utility_observations d ON d.id = uoe.observation_id
        ORDER BY uoe.observation_id, uoe.evidence_id
    """,
    "problem_runs": """
        SELECT pr.*
        FROM problem_runs pr
        JOIN cleanup_historical_problem_runs d ON d.id = pr.id
        ORDER BY pr.opened_at, pr.id
    """,
    "association_observations": """
        SELECT ao.*
        FROM association_observations ao
        JOIN cleanup_doomed_association_observations d ON d.id = ao.id
        ORDER BY ao.created_at, ao.id
    """,
    "association_edges": """
        SELECT ae.*
        FROM association_edges ae
        JOIN cleanup_doomed_association_edges d ON d.id = ae.id
        ORDER BY ae.created_at, ae.id
    """,
    "association_edge_evidence": """
        SELECT aee.*
        FROM association_edge_evidence aee
        JOIN cleanup_doomed_association_edges d ON d.id = aee.edge_id
        ORDER BY aee.edge_id, aee.evidence_id
    """,
    "concepts": """
        SELECT c.*
        FROM concepts c
        JOIN cleanup_pure_historical_concepts d ON d.concept_id = c.id
        ORDER BY c.created_at, c.id
    """,
    "concept_aliases": """
        SELECT ca.*
        FROM concept_aliases ca
        JOIN cleanup_pure_historical_concepts d ON d.concept_id = ca.concept_id
        ORDER BY ca.concept_id, ca.normalized_alias
    """,
    "concept_embeddings": """
        SELECT ce.*
        FROM concept_embeddings ce
        WHERE ce.concept_id IN (SELECT concept_id FROM cleanup_pure_historical_concepts)
           OR ce.concept_id IN (SELECT concept_id FROM cleanup_touched_retained_concepts)
        ORDER BY ce.concept_id
    """,
    "concept_claims": """
        SELECT cc.*
        FROM concept_claims cc
        JOIN cleanup_doomed_claims d ON d.id = cc.id
        ORDER BY cc.created_at, cc.id
    """,
    "concept_groundings": """
        SELECT cg.*
        FROM concept_groundings cg
        JOIN cleanup_doomed_groundings d ON d.id = cg.id
        ORDER BY cg.created_at, cg.id
    """,
    "concept_relations": """
        SELECT cr.*
        FROM concept_relations cr
        JOIN cleanup_doomed_relations d ON d.id = cr.id
        ORDER BY cr.created_at, cr.id
    """,
    "concept_memory_links": """
        SELECT ml.*
        FROM concept_memory_links ml
        JOIN cleanup_doomed_memory_links d ON d.id = ml.id
        ORDER BY ml.created_at, ml.id
    """,
    "concept_evidence": """
        SELECT ce.*
        FROM concept_evidence ce
        JOIN cleanup_doomed_concept_evidence d ON d.id = ce.id
        ORDER BY ce.created_at, ce.id
    """,
    "anchors": """
        SELECT a.*
        FROM anchors a
        JOIN cleanup_doomed_anchors d ON d.id = a.id
        ORDER BY a.created_at, a.id
    """,
}


def _write_jsonl(
    *, conn: psycopg.Connection[dict[str, Any]], query: str, path: Path
) -> int:
    count = 0
    with path.open("w", encoding="utf-8") as handle:
        for row in conn.execute(query):
            handle.write(json.dumps(row, default=str, sort_keys=True))
            handle.write("\n")
            count += 1
    return count


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_manifest(*, archive_dir: Path, manifest: dict[str, Any]) -> None:
    path = archive_dir / "manifest.json"
    manifest_without_self_hash = dict(manifest)
    manifest_without_self_hash.pop("manifest_sha256", None)
    path.write_text(
        json.dumps(manifest_without_self_hash, indent=2, sort_keys=True, default=str)
        + "\n",
        encoding="utf-8",
    )
    manifest["manifest_sha256"] = _sha256(path)
    path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )


def _delete_targets(conn: psycopg.Connection[dict[str, Any]]) -> dict[str, int]:
    delete_statements = [
        (
            "read_result_items",
            """
            DELETE FROM read_result_items rri
            USING cleanup_doomed_read_result_items d
            WHERE rri.invocation_id = d.invocation_id
              AND rri.ordinal = d.ordinal
            """,
        ),
        (
            "utility_observation_evidence",
            """
            DELETE FROM utility_observation_evidence uoe
            USING cleanup_doomed_utility_observations d
            WHERE uoe.observation_id = d.id
            """,
        ),
        (
            "utility_observations",
            """
            DELETE FROM utility_observations u
            USING cleanup_doomed_utility_observations d
            WHERE u.id = d.id
            """,
        ),
        (
            "problem_runs",
            """
            DELETE FROM problem_runs pr
            USING cleanup_historical_problem_runs d
            WHERE pr.id = d.id
            """,
        ),
        (
            "association_edge_evidence",
            """
            DELETE FROM association_edge_evidence aee
            USING cleanup_doomed_association_edges d
            WHERE aee.edge_id = d.id
            """,
        ),
        (
            "association_observations",
            """
            DELETE FROM association_observations ao
            USING cleanup_doomed_association_observations d
            WHERE ao.id = d.id
            """,
        ),
        (
            "association_edges",
            """
            DELETE FROM association_edges ae
            USING cleanup_doomed_association_edges d
            WHERE ae.id = d.id
            """,
        ),
        (
            "concept_evidence",
            """
            DELETE FROM concept_evidence ce
            USING cleanup_doomed_concept_evidence d
            WHERE ce.id = d.id
            """,
        ),
        (
            "concept_memory_links",
            """
            DELETE FROM concept_memory_links ml
            USING cleanup_doomed_memory_links d
            WHERE ml.id = d.id
            """,
        ),
        (
            "concept_relations",
            """
            DELETE FROM concept_relations cr
            USING cleanup_doomed_relations d
            WHERE cr.id = d.id
            """,
        ),
        (
            "concept_groundings",
            """
            DELETE FROM concept_groundings cg
            USING cleanup_doomed_groundings d
            WHERE cg.id = d.id
            """,
        ),
        (
            "concept_claims",
            """
            DELETE FROM concept_claims cc
            USING cleanup_doomed_claims d
            WHERE cc.id = d.id
            """,
        ),
        (
            "concept_aliases",
            """
            DELETE FROM concept_aliases ca
            USING cleanup_pure_historical_concepts d
            WHERE ca.concept_id = d.concept_id
            """,
        ),
        (
            "concept_embeddings",
            """
            DELETE FROM concept_embeddings ce
            WHERE ce.concept_id IN (
                SELECT concept_id FROM cleanup_pure_historical_concepts
                UNION
                SELECT concept_id FROM cleanup_touched_retained_concepts
            )
            """,
        ),
        (
            "concepts",
            """
            DELETE FROM concepts c
            USING cleanup_pure_historical_concepts d
            WHERE c.id = d.concept_id
            """,
        ),
        (
            "memory_evidence",
            """
            DELETE FROM memory_evidence me
            USING cleanup_doomed_memories d
            WHERE me.memory_id = d.memory_id
            """,
        ),
        (
            "memory_embeddings",
            """
            DELETE FROM memory_embeddings me
            USING cleanup_doomed_memories d
            WHERE me.memory_id = d.memory_id
            """,
        ),
        (
            "memories",
            """
            DELETE FROM memories m
            USING cleanup_doomed_memories d
            WHERE m.id = d.memory_id
            """,
        ),
        (
            "evidence_refs",
            """
            DELETE FROM evidence_refs er
            USING cleanup_doomed_evidence_refs d
            WHERE er.id = d.id
              AND NOT EXISTS (
                  SELECT 1 FROM memory_evidence me WHERE me.evidence_id = er.id
              )
              AND NOT EXISTS (
                  SELECT 1 FROM association_edge_evidence aee WHERE aee.evidence_id = er.id
              )
              AND NOT EXISTS (
                  SELECT 1 FROM utility_observation_evidence uoe WHERE uoe.evidence_id = er.id
              )
            """,
        ),
        (
            "anchors",
            """
            DELETE FROM anchors a
            USING cleanup_doomed_anchors d
            WHERE a.id = d.id
              AND NOT EXISTS (
                  SELECT 1 FROM concept_groundings cg WHERE cg.anchor_id = a.id
              )
              AND NOT EXISTS (
                  SELECT 1 FROM concept_evidence ce WHERE ce.anchor_id = a.id
              )
            """,
        ),
    ]
    deleted: dict[str, int] = {}
    for name, statement in delete_statements:
        cursor = conn.execute(statement)
        deleted[name] = int(cursor.rowcount)
    return deleted


def _verify_cleanup(conn: psycopg.Connection[dict[str, Any]]) -> dict[str, int]:
    verification_queries = {
        "remaining_doomed_memories": """
            SELECT COUNT(*)
            FROM memories m
            JOIN cleanup_doomed_memories d ON d.memory_id = m.id
        """,
        "remaining_doomed_memory_embeddings": """
            SELECT COUNT(*)
            FROM memory_embeddings me
            JOIN cleanup_doomed_memories d ON d.memory_id = me.memory_id
        """,
        "remaining_doomed_memory_evidence": """
            SELECT COUNT(*)
            FROM memory_evidence me
            JOIN cleanup_doomed_memories d ON d.memory_id = me.memory_id
        """,
        "remaining_doomed_read_result_items": """
            SELECT COUNT(*)
            FROM read_result_items rri
            WHERE rri.memory_id IN (SELECT memory_id FROM cleanup_doomed_memories)
               OR rri.anchor_memory_id IN (SELECT memory_id FROM cleanup_doomed_memories)
        """,
        "remaining_doomed_utility_observations": """
            SELECT COUNT(*)
            FROM utility_observations u
            WHERE u.id IN (SELECT id FROM cleanup_doomed_utility_observations)
               OR u.memory_id IN (SELECT memory_id FROM cleanup_doomed_memories)
               OR u.problem_id IN (SELECT memory_id FROM cleanup_doomed_memories)
        """,
        "remaining_doomed_association_observations": """
            SELECT COUNT(*)
            FROM association_observations ao
            WHERE ao.from_memory_id IN (SELECT memory_id FROM cleanup_doomed_memories)
               OR ao.to_memory_id IN (SELECT memory_id FROM cleanup_doomed_memories)
               OR ao.problem_id IN (SELECT memory_id FROM cleanup_doomed_memories)
        """,
        "remaining_doomed_association_edges": """
            SELECT COUNT(*)
            FROM association_edges ae
            WHERE ae.from_memory_id IN (SELECT memory_id FROM cleanup_doomed_memories)
               OR ae.to_memory_id IN (SELECT memory_id FROM cleanup_doomed_memories)
        """,
        "remaining_doomed_concept_memory_links": """
            SELECT COUNT(*)
            FROM concept_memory_links ml
            WHERE ml.memory_id IN (SELECT memory_id FROM cleanup_doomed_memories)
               OR ml.id IN (SELECT id FROM cleanup_doomed_memory_links)
        """,
        "remaining_doomed_concepts": """
            SELECT COUNT(*)
            FROM concepts c
            JOIN cleanup_pure_historical_concepts d ON d.concept_id = c.id
        """,
        "remaining_today_memories_to_keep": """
            SELECT COUNT(*)
            FROM memories m
            JOIN cleanup_today_memories t ON t.memory_id = m.id
        """,
        "historical_runs_retained": """
            SELECT COUNT(*)
            FROM knowledge_build_runs kbr
            JOIN cleanup_historical_runs h ON h.run_id = kbr.id
        """,
    }
    return {
        name: int(conn.execute(query).fetchone()["count"])
        for name, query in verification_queries.items()
    }


def _raise_if_verification_failed(verification: dict[str, int]) -> None:
    allowed_nonzero = {
        "remaining_today_memories_to_keep",
        "historical_runs_retained",
    }
    failures = {
        name: count
        for name, count in verification.items()
        if count != 0 and name not in allowed_nonzero
    }
    if failures:
        raise RuntimeError(f"Cleanup verification failed: {failures}")
    if verification.get("remaining_today_memories_to_keep", 0) <= 0:
        raise RuntimeError("Cleanup verification failed: no today memories remained.")
    if verification.get("historical_runs_retained", 0) <= 0:
        raise RuntimeError("Cleanup verification failed: historical run watermarks missing.")


def _result_payload(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "archive_dir": manifest["archive_dir"],
        "target_counts": manifest["target_counts"],
        "count_warnings": manifest["count_warnings"],
        "manifest_sha256": manifest.get("manifest_sha256"),
        "deleted_counts": manifest.get("deleted_counts"),
        "verification": manifest.get("verification"),
    }


def _maybe_git_revision() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception:
        return None
    return result.stdout.strip() or None


if __name__ == "__main__":
    try:
        exit_code = main()
    except Exception as exc:
        print(f"cleanup failed: {exc}", file=sys.stderr)
        raise
    raise SystemExit(exit_code)
