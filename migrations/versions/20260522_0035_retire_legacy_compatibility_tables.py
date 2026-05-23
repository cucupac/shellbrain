"""Retire legacy evidence and memory-relation compatibility tables."""

from __future__ import annotations

from alembic import op
from sqlalchemy import text

from migrations._usage_view_sql import (
    CURRENT_FACT_SNAPSHOT_SQL,
    USAGE_PROBLEM_READ_ROI_SQL,
    USAGE_PROBLEM_TOKENS_SQL,
    USAGE_READ_BEFORE_SOLVE_ROI_SQL,
)


revision = "20260522_0035"
down_revision = "20260522_0034"
branch_labels = None
depends_on = None


_TARGET_TYPES_WITHOUT_FACT_UPDATE = (
    "memory",
    "association_edge",
    "utility_observation",
    "concept_claim",
    "concept_relation",
    "concept_grounding",
    "concept_memory_link",
    "concept_lifecycle_event",
    "memory_lifecycle_event",
    "structural_memory_relation",
)
_TARGET_TYPES_WITH_FACT_UPDATE = (
    "memory",
    "fact_update",
    "association_edge",
    "utility_observation",
    "concept_claim",
    "concept_relation",
    "concept_grounding",
    "concept_memory_link",
    "concept_lifecycle_event",
    "memory_lifecycle_event",
    "structural_memory_relation",
)


def upgrade() -> None:
    """Translate remaining compatibility evidence and drop retired tables."""

    bind = op.get_bind()
    _drop_dependent_views()
    _assert_fact_update_evidence_targets_exist(bind)
    _retarget_fact_update_evidence(bind)
    _remove_fact_update_evidence_targets(bind)
    _shrink_evidence_target_constraint()
    _drop_legacy_tables()
    _create_canonical_views()


def downgrade() -> None:
    """Recreate empty compatibility tables for downgrade shape compatibility."""

    _drop_dependent_views()
    _widen_evidence_target_constraint()
    _create_legacy_tables()
    _create_canonical_views()


def _drop_dependent_views() -> None:
    op.execute(
        """
        DROP VIEW IF EXISTS usage_read_before_solve_roi;
        DROP VIEW IF EXISTS usage_problem_read_roi;
        DROP VIEW IF EXISTS usage_problem_tokens;
        DROP VIEW IF EXISTS usage_read_before_solve_roi_legacy;
        DROP VIEW IF EXISTS usage_problem_read_roi_legacy;
        DROP VIEW IF EXISTS usage_problem_tokens_legacy;
        DROP VIEW IF EXISTS current_fact_snapshot;
        """
    )


def _assert_fact_update_evidence_targets_exist(bind) -> None:
    """Reject malformed fact-update evidence links before destructive cleanup."""

    missing_rows = bind.execute(
        text(
            """
            SELECT el.id, el.repo_id, el.target_id
            FROM evidence_links el
            LEFT JOIN fact_updates fu ON fu.id = el.target_id
            WHERE el.target_type = 'fact_update'
              AND fu.id IS NULL
            ORDER BY el.repo_id, el.target_id, el.id
            LIMIT 5;
            """
        )
    ).mappings().all()
    if not missing_rows:
        return

    sample = ", ".join(
        f"id={row['id']} repo_id={row['repo_id']} target_id={row['target_id']}"
        for row in missing_rows
    )
    raise RuntimeError(
        "Cannot retire fact_update evidence target: evidence_links reference "
        f"missing fact_updates rows. Sample: {sample}"
    )


def _retarget_fact_update_evidence(bind) -> None:
    """Copy fact-update evidence links onto canonical structural relations."""

    unretargetable_count = bind.execute(
        text(
            """
            SELECT count(*)
            FROM evidence_links el
            JOIN fact_updates fu ON fu.id = el.target_id
            LEFT JOIN structural_memory_relations smr
              ON smr.repo_id = el.repo_id
             AND (
               (
                 smr.subject_memory_id = fu.old_fact_id
                 AND smr.predicate = 'superseded_by'
                 AND smr.object_memory_id = fu.new_fact_id
               ) OR (
                 smr.subject_memory_id = fu.old_fact_id
                 AND smr.predicate = 'explained_by_change'
                 AND smr.object_memory_id = fu.change_id
               ) OR (
                 smr.subject_memory_id = fu.new_fact_id
                 AND smr.predicate = 'explained_by_change'
                 AND smr.object_memory_id = fu.change_id
               )
             )
            WHERE el.target_type = 'fact_update'
              AND smr.id IS NULL;
            """
        )
    ).scalar()
    if unretargetable_count:
        raise RuntimeError(
            "Cannot retire fact_updates: "
            f"{unretargetable_count} fact_update evidence links have no structural relation."
        )

    bind.execute(
        text(
            """
            INSERT INTO evidence_links (
              id,
              repo_id,
              target_type,
              target_id,
              evidence_id,
              evidence_role,
              created_at
            )
            SELECT
              'retarget-fu-' || md5(el.id || ':' || smr.id || ':' || el.evidence_role),
              el.repo_id,
              'structural_memory_relation',
              smr.id,
              el.evidence_id,
              el.evidence_role,
              el.created_at
            FROM evidence_links el
            JOIN fact_updates fu ON fu.id = el.target_id
            JOIN structural_memory_relations smr
              ON smr.repo_id = el.repo_id
             AND (
               (
                 smr.subject_memory_id = fu.old_fact_id
                 AND smr.predicate = 'superseded_by'
                 AND smr.object_memory_id = fu.new_fact_id
               ) OR (
                 smr.subject_memory_id = fu.old_fact_id
                 AND smr.predicate = 'explained_by_change'
                 AND smr.object_memory_id = fu.change_id
               ) OR (
                 smr.subject_memory_id = fu.new_fact_id
                 AND smr.predicate = 'explained_by_change'
                 AND smr.object_memory_id = fu.change_id
               )
             )
            WHERE el.target_type = 'fact_update'
            ON CONFLICT (repo_id, target_type, target_id, evidence_id, evidence_role)
            DO NOTHING;
            """
        )
    )


def _remove_fact_update_evidence_targets(bind) -> None:
    bind.execute(text("DELETE FROM evidence_links WHERE target_type = 'fact_update';"))
    remaining = bind.execute(
        text("SELECT count(*) FROM evidence_links WHERE target_type = 'fact_update';")
    ).scalar()
    if remaining:
        raise RuntimeError(
            f"Cannot retire fact_update evidence target: {remaining} links remain."
        )


def _shrink_evidence_target_constraint() -> None:
    op.execute(
        f"""
        ALTER TABLE evidence_links
          DROP CONSTRAINT IF EXISTS ck_evidence_links_target_type;

        ALTER TABLE evidence_links
          ADD CONSTRAINT ck_evidence_links_target_type
          CHECK (target_type IN ({_quoted(_TARGET_TYPES_WITHOUT_FACT_UPDATE)}));
        """
    )


def _widen_evidence_target_constraint() -> None:
    op.execute(
        f"""
        ALTER TABLE evidence_links
          DROP CONSTRAINT IF EXISTS ck_evidence_links_target_type;

        ALTER TABLE evidence_links
          ADD CONSTRAINT ck_evidence_links_target_type
          CHECK (target_type IN ({_quoted(_TARGET_TYPES_WITH_FACT_UPDATE)}));
        """
    )


def _drop_legacy_tables() -> None:
    op.execute(
        """
        DROP TABLE IF EXISTS concept_evidence;
        DROP TABLE IF EXISTS utility_observation_evidence;
        DROP TABLE IF EXISTS association_edge_evidence;
        DROP TABLE IF EXISTS memory_evidence;
        DROP TABLE IF EXISTS fact_update_evidence;
        DROP TABLE IF EXISTS problem_attempts;
        DROP TABLE IF EXISTS fact_updates;
        """
    )


def _create_legacy_tables() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS problem_attempts (
          problem_id TEXT NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
          attempt_id TEXT NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
          role TEXT NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (problem_id, attempt_id),
          CONSTRAINT ck_problem_attempts_distinct_memories
            CHECK (problem_id <> attempt_id)
        );

        CREATE TABLE IF NOT EXISTS fact_updates (
          id TEXT PRIMARY KEY,
          old_fact_id TEXT NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
          change_id TEXT NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
          new_fact_id TEXT NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          CONSTRAINT ck_fact_updates_distinct_fact_endpoints
            CHECK (old_fact_id <> new_fact_id),
          CONSTRAINT ck_fact_updates_change_id_distinct
            CHECK (change_id <> old_fact_id AND change_id <> new_fact_id),
          CONSTRAINT uq_fact_updates_chain
            UNIQUE (old_fact_id, change_id, new_fact_id)
        );

        CREATE INDEX IF NOT EXISTS idx_problem_attempts_problem
          ON problem_attempts(problem_id);
        CREATE INDEX IF NOT EXISTS idx_problem_attempts_attempt
          ON problem_attempts(attempt_id);
        CREATE INDEX IF NOT EXISTS idx_fact_updates_old_fact
          ON fact_updates(old_fact_id);
        CREATE INDEX IF NOT EXISTS idx_fact_updates_new_fact
          ON fact_updates(new_fact_id);

        CREATE TABLE IF NOT EXISTS memory_evidence (
          memory_id TEXT NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
          evidence_id TEXT NOT NULL REFERENCES evidence_refs(id) ON DELETE CASCADE,
          PRIMARY KEY (memory_id, evidence_id),
          CONSTRAINT uq_memory_evidence_pair UNIQUE (memory_id, evidence_id)
        );

        CREATE TABLE IF NOT EXISTS association_edge_evidence (
          edge_id TEXT NOT NULL REFERENCES association_edges(id) ON DELETE CASCADE,
          evidence_id TEXT NOT NULL REFERENCES evidence_refs(id) ON DELETE CASCADE,
          PRIMARY KEY (edge_id, evidence_id)
        );

        CREATE TABLE IF NOT EXISTS utility_observation_evidence (
          observation_id TEXT NOT NULL REFERENCES utility_observations(id) ON DELETE CASCADE,
          evidence_id TEXT NOT NULL REFERENCES evidence_refs(id) ON DELETE CASCADE,
          PRIMARY KEY (observation_id, evidence_id)
        );

        CREATE TABLE IF NOT EXISTS fact_update_evidence (
          fact_update_id TEXT NOT NULL REFERENCES fact_updates(id) ON DELETE CASCADE,
          evidence_id TEXT NOT NULL REFERENCES evidence_refs(id) ON DELETE CASCADE,
          PRIMARY KEY (fact_update_id, evidence_id)
        );

        CREATE TABLE IF NOT EXISTS concept_evidence (
          id TEXT PRIMARY KEY,
          repo_id TEXT NOT NULL,
          target_type TEXT NOT NULL,
          target_id TEXT NOT NULL,
          evidence_kind TEXT NOT NULL,
          anchor_id TEXT REFERENCES anchors(id) ON DELETE SET NULL,
          memory_id TEXT REFERENCES memories(id) ON DELETE SET NULL,
          commit_ref TEXT,
          transcript_ref TEXT,
          note TEXT,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          CONSTRAINT ck_concept_evidence_target_type
            CHECK (target_type IN ('relation', 'claim', 'grounding', 'memory_link', 'lifecycle_event')),
          CONSTRAINT ck_concept_evidence_kind
            CHECK (evidence_kind IN ('anchor', 'memory', 'commit', 'transcript', 'test', 'manual'))
        );

        CREATE INDEX IF NOT EXISTS idx_memory_evidence_evidence
          ON memory_evidence(evidence_id);
        CREATE INDEX IF NOT EXISTS idx_assoc_edge_evidence_evidence
          ON association_edge_evidence(evidence_id);
        CREATE INDEX IF NOT EXISTS idx_concept_evidence_target
          ON concept_evidence(repo_id, target_type, target_id);
        """
    )


def _create_canonical_views() -> None:
    op.execute(CURRENT_FACT_SNAPSHOT_SQL)
    op.execute(USAGE_PROBLEM_TOKENS_SQL)
    op.execute(USAGE_PROBLEM_READ_ROI_SQL)
    op.execute(USAGE_READ_BEFORE_SOLVE_ROI_SQL)


def _quoted(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)
