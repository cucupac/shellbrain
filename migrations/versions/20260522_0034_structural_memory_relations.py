"""Add constrained structural memory relations."""

from __future__ import annotations

from alembic import op


revision = "20260522_0034"
down_revision = "20260522_0033"
branch_labels = None
depends_on = None


_PREDICATES = (
    "solved_by",
    "failed_with",
    "superseded_by",
    "explained_by_change",
)
_MEMORY_STATUSES = (
    "active",
    "maybe_stale",
    "stale",
    "superseded",
    "wrong",
    "archived",
)
_MEMORY_ACTORS = ("worker", "librarian", "manual", "import")
_TARGET_TYPES_WITH_STRUCTURAL_RELATIONS = (
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
_TARGET_TYPES_PRE_STRUCTURAL_RELATIONS = tuple(
    value
    for value in _TARGET_TYPES_WITH_STRUCTURAL_RELATIONS
    if value != "structural_memory_relation"
)


def upgrade() -> None:
    """Create structural memory relations and backfill compatibility rows."""

    _create_schema()
    _backfill_relations()
    _backfill_fact_update_evidence()
    _assert_backfill_parity()


def downgrade() -> None:
    """Drop structural relation storage while preserving compatibility tables."""

    op.execute(
        f"""
        DELETE FROM evidence_links
        WHERE target_type = 'structural_memory_relation';

        ALTER TABLE evidence_links
          DROP CONSTRAINT IF EXISTS ck_evidence_links_target_type;

        ALTER TABLE evidence_links
          ADD CONSTRAINT ck_evidence_links_target_type
          CHECK (target_type IN ({_quoted(_TARGET_TYPES_PRE_STRUCTURAL_RELATIONS)}));

        DROP TABLE IF EXISTS structural_memory_relations;
        """
    )


def _create_schema() -> None:
    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS structural_memory_relations (
          id TEXT PRIMARY KEY,
          repo_id TEXT NOT NULL,
          subject_memory_id TEXT NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
          predicate TEXT NOT NULL,
          object_memory_id TEXT NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
          status TEXT NOT NULL DEFAULT 'active',
          confidence DOUBLE PRECISION,
          observed_at TIMESTAMPTZ,
          validated_at TIMESTAMPTZ,
          invalidated_at TIMESTAMPTZ,
          superseded_by_id TEXT REFERENCES structural_memory_relations(id) ON DELETE SET NULL,
          created_by TEXT NOT NULL DEFAULT 'worker',
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          CONSTRAINT ck_structural_memory_relations_predicate
            CHECK (predicate IN ({_quoted(_PREDICATES)})),
          CONSTRAINT ck_structural_memory_relations_status
            CHECK (status IN ({_quoted(_MEMORY_STATUSES)})),
          CONSTRAINT ck_structural_memory_relations_confidence
            CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
          CONSTRAINT ck_structural_memory_relations_distinct_memories
            CHECK (subject_memory_id <> object_memory_id),
          CONSTRAINT ck_structural_memory_relations_created_by
            CHECK (created_by IN ({_quoted(_MEMORY_ACTORS)})),
          CONSTRAINT uq_structural_memory_relations_natural
            UNIQUE (repo_id, subject_memory_id, predicate, object_memory_id)
        );

        CREATE INDEX IF NOT EXISTS idx_structural_memory_relations_subject
          ON structural_memory_relations(repo_id, subject_memory_id, predicate);

        CREATE INDEX IF NOT EXISTS idx_structural_memory_relations_object
          ON structural_memory_relations(repo_id, object_memory_id, predicate);

        ALTER TABLE evidence_links
          DROP CONSTRAINT IF EXISTS ck_evidence_links_target_type;

        ALTER TABLE evidence_links
          ADD CONSTRAINT ck_evidence_links_target_type
          CHECK (target_type IN ({_quoted(_TARGET_TYPES_WITH_STRUCTURAL_RELATIONS)}));
        """
    )


def _backfill_relations() -> None:
    op.execute(
        """
        DROP TABLE IF EXISTS _phase6_structural_counts;
        CREATE TEMP TABLE _phase6_structural_counts ON COMMIT DROP AS
        SELECT
          (SELECT count(*) FROM problem_attempts) AS problem_attempt_count,
          (SELECT count(*) FROM fact_updates) AS fact_update_count;

        DO $$
        DECLARE
          invalid_problem_attempts BIGINT;
          invalid_fact_updates BIGINT;
        BEGIN
          SELECT count(*) INTO invalid_problem_attempts
          FROM problem_attempts pa
          JOIN memories problem ON problem.id = pa.problem_id
          JOIN memories attempt ON attempt.id = pa.attempt_id
          WHERE pa.role NOT IN ('solution', 'failed_tactic')
             OR problem.repo_id <> attempt.repo_id
             OR problem.kind <> 'problem'
             OR (pa.role = 'solution' AND attempt.kind <> 'solution')
             OR (pa.role = 'failed_tactic' AND attempt.kind <> 'failed_tactic');

          IF invalid_problem_attempts <> 0 THEN
            RAISE EXCEPTION
              'Phase 6 structural backfill found % invalid problem_attempt row(s).',
              invalid_problem_attempts;
          END IF;

          SELECT count(*) INTO invalid_fact_updates
          FROM fact_updates fu
          JOIN memories old_memory ON old_memory.id = fu.old_fact_id
          JOIN memories change_memory ON change_memory.id = fu.change_id
          JOIN memories new_memory ON new_memory.id = fu.new_fact_id
          WHERE old_memory.repo_id <> change_memory.repo_id
             OR old_memory.repo_id <> new_memory.repo_id
             OR old_memory.kind NOT IN ('fact', 'preference', 'change')
             OR new_memory.kind NOT IN ('fact', 'preference', 'change')
             OR change_memory.kind <> 'change';

          IF invalid_fact_updates <> 0 THEN
            RAISE EXCEPTION
              'Phase 6 structural backfill found % invalid fact_update row(s).',
              invalid_fact_updates;
          END IF;
        END $$;

        DROP TABLE IF EXISTS _phase6_structural_expected;
        CREATE TEMP TABLE _phase6_structural_expected ON COMMIT DROP AS
        SELECT
          'struct-pa-' || md5(pa.problem_id || ':' || pa.role || ':' || pa.attempt_id) AS id,
          problem.repo_id AS repo_id,
          pa.problem_id AS subject_memory_id,
          CASE pa.role
            WHEN 'solution' THEN 'solved_by'
            WHEN 'failed_tactic' THEN 'failed_with'
          END AS predicate,
          pa.attempt_id AS object_memory_id,
          pa.created_at AS created_at,
          NULL::TEXT AS source_fact_update_id
        FROM problem_attempts pa
        JOIN memories problem ON problem.id = pa.problem_id
        UNION ALL
        SELECT
          'struct-fu-sup-' || md5(fu.id) AS id,
          old_memory.repo_id AS repo_id,
          fu.old_fact_id AS subject_memory_id,
          'superseded_by' AS predicate,
          fu.new_fact_id AS object_memory_id,
          fu.created_at AS created_at,
          fu.id AS source_fact_update_id
        FROM fact_updates fu
        JOIN memories old_memory ON old_memory.id = fu.old_fact_id
        UNION ALL
        SELECT
          'struct-fu-old-change-' || md5(fu.id) AS id,
          old_memory.repo_id AS repo_id,
          fu.old_fact_id AS subject_memory_id,
          'explained_by_change' AS predicate,
          fu.change_id AS object_memory_id,
          fu.created_at AS created_at,
          fu.id AS source_fact_update_id
        FROM fact_updates fu
        JOIN memories old_memory ON old_memory.id = fu.old_fact_id
        UNION ALL
        SELECT
          'struct-fu-new-change-' || md5(fu.id) AS id,
          new_memory.repo_id AS repo_id,
          fu.new_fact_id AS subject_memory_id,
          'explained_by_change' AS predicate,
          fu.change_id AS object_memory_id,
          fu.created_at AS created_at,
          fu.id AS source_fact_update_id
        FROM fact_updates fu
        JOIN memories new_memory ON new_memory.id = fu.new_fact_id;

        DO $$
        DECLARE
          collision_count BIGINT;
        BEGIN
          SELECT count(*) INTO collision_count
          FROM (
            SELECT repo_id, subject_memory_id, predicate, object_memory_id
            FROM _phase6_structural_expected
            GROUP BY repo_id, subject_memory_id, predicate, object_memory_id
            HAVING count(*) > 1
          ) collisions;

          IF collision_count <> 0 THEN
            RAISE EXCEPTION
              'Phase 6 structural backfill would create % natural-key collision(s).',
              collision_count;
          END IF;
        END $$;

        INSERT INTO structural_memory_relations (
          id,
          repo_id,
          subject_memory_id,
          predicate,
          object_memory_id,
          status,
          confidence,
          observed_at,
          validated_at,
          invalidated_at,
          superseded_by_id,
          created_by,
          created_at,
          updated_at
        )
        SELECT
          id,
          repo_id,
          subject_memory_id,
          predicate,
          object_memory_id,
          'active',
          NULL::DOUBLE PRECISION,
          NULL::TIMESTAMPTZ,
          NULL::TIMESTAMPTZ,
          NULL::TIMESTAMPTZ,
          NULL::TEXT,
          'import',
          created_at,
          created_at
        FROM _phase6_structural_expected
        ON CONFLICT (repo_id, subject_memory_id, predicate, object_memory_id)
        DO NOTHING;
        """
    )


def _backfill_fact_update_evidence() -> None:
    op.execute(
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
          'struct-rel-evidence-' || md5(el.id || ':' || expected.id),
          el.repo_id,
          'structural_memory_relation',
          expected.id,
          el.evidence_id,
          el.evidence_role,
          el.created_at
        FROM evidence_links el
        JOIN _phase6_structural_expected expected
          ON expected.source_fact_update_id = el.target_id
        WHERE el.target_type = 'fact_update'
        ON CONFLICT (repo_id, target_type, target_id, evidence_id, evidence_role)
        DO NOTHING;
        """
    )


def _assert_backfill_parity() -> None:
    op.execute(
        """
        DO $$
        DECLARE
          before_problem_attempt_count BIGINT;
          before_fact_update_count BIGINT;
          after_problem_attempt_count BIGINT;
          after_fact_update_count BIGINT;
          expected_relation_count BIGINT;
          actual_relation_count BIGINT;
          expected_evidence_count BIGINT;
          actual_evidence_count BIGINT;
        BEGIN
          SELECT problem_attempt_count, fact_update_count
            INTO before_problem_attempt_count, before_fact_update_count
          FROM _phase6_structural_counts;

          SELECT count(*) INTO after_problem_attempt_count FROM problem_attempts;
          SELECT count(*) INTO after_fact_update_count FROM fact_updates;

          IF before_problem_attempt_count <> after_problem_attempt_count THEN
            RAISE EXCEPTION
              'Phase 6 changed problem_attempt row count from % to %.',
              before_problem_attempt_count,
              after_problem_attempt_count;
          END IF;

          IF before_fact_update_count <> after_fact_update_count THEN
            RAISE EXCEPTION
              'Phase 6 changed fact_update row count from % to %.',
              before_fact_update_count,
              after_fact_update_count;
          END IF;

          SELECT count(*) INTO expected_relation_count
          FROM _phase6_structural_expected;

          SELECT count(*) INTO actual_relation_count
          FROM _phase6_structural_expected expected
          JOIN structural_memory_relations relation
            ON relation.repo_id = expected.repo_id
           AND relation.subject_memory_id = expected.subject_memory_id
           AND relation.predicate = expected.predicate
           AND relation.object_memory_id = expected.object_memory_id;

          IF expected_relation_count <> actual_relation_count THEN
            RAISE EXCEPTION
              'Phase 6 expected % structural relation(s), found %.',
              expected_relation_count,
              actual_relation_count;
          END IF;

          SELECT count(*) INTO expected_evidence_count
          FROM evidence_links el
          JOIN _phase6_structural_expected expected
            ON expected.source_fact_update_id = el.target_id
          WHERE el.target_type = 'fact_update';

          SELECT count(*) INTO actual_evidence_count
          FROM evidence_links el
          JOIN _phase6_structural_expected expected
            ON expected.id = el.target_id
          WHERE el.target_type = 'structural_memory_relation';

          IF expected_evidence_count <> actual_evidence_count THEN
            RAISE EXCEPTION
              'Phase 6 expected % structural evidence link(s), found %.',
              expected_evidence_count,
              actual_evidence_count;
          END IF;
        END $$;
        """
    )


def _quoted(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)
