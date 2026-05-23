"""Tighten concept-memory link role semantics."""

from __future__ import annotations

from alembic import op


revision = "20260522_0033"
down_revision = "20260522_0032"
branch_labels = None
depends_on = None


_NEW_ROLES = (
    "example_of",
    "solution_for",
    "failed_tactic_for",
    "warns_about",
    "change_relevant_to",
)
_PREVIOUS_ROLES = (
    "example_of",
    "solution_for",
    "failed_tactic_for",
    "changed",
    "validated",
    "contradicted",
    "warned_about",
)


def upgrade() -> None:
    """Rewrite legacy bridge roles, then shrink the role constraint."""

    op.execute(
        f"""
        DROP TABLE IF EXISTS _concept_memory_links_role_cleanup_before;
        CREATE TEMP TABLE _concept_memory_links_role_cleanup_before ON COMMIT DROP AS
        SELECT
          id,
          repo_id,
          concept_id,
          memory_id,
          status,
          confidence,
          observed_at,
          validated_at,
          invalidated_at,
          source_kind,
          source_ref,
          superseded_by_id,
          created_by,
          updated_by,
          created_at,
          updated_at
        FROM concept_memory_links;

        DO $$
        DECLARE
          collision_count BIGINT;
        BEGIN
          WITH mapped AS (
            SELECT
              repo_id,
              concept_id,
              memory_id,
              CASE role
                WHEN 'warned_about' THEN 'warns_about'
                WHEN 'changed' THEN 'change_relevant_to'
                WHEN 'validated' THEN 'example_of'
                WHEN 'contradicted' THEN 'warns_about'
                ELSE role
              END AS mapped_role
            FROM concept_memory_links
            WHERE status = 'active'
          ),
          collisions AS (
            SELECT repo_id, concept_id, mapped_role, memory_id
            FROM mapped
            GROUP BY repo_id, concept_id, mapped_role, memory_id
            HAVING count(*) > 1
          )
          SELECT count(*) INTO collision_count FROM collisions;

          IF collision_count > 0 THEN
            RAISE EXCEPTION
              'Concept-memory role cleanup would create % active natural-key collision(s).',
              collision_count;
          END IF;
        END $$;

        ALTER TABLE concept_memory_links
          DROP CONSTRAINT IF EXISTS ck_concept_memory_links_role;

        UPDATE concept_memory_links
        SET role = CASE role
          WHEN 'warned_about' THEN 'warns_about'
          WHEN 'changed' THEN 'change_relevant_to'
          WHEN 'validated' THEN 'example_of'
          WHEN 'contradicted' THEN 'warns_about'
          ELSE role
        END
        WHERE role IN ('warned_about', 'changed', 'validated', 'contradicted');

        ALTER TABLE concept_memory_links
          ADD CONSTRAINT ck_concept_memory_links_role
          CHECK (role IN ({_quoted(_NEW_ROLES)}));

        DO $$
        DECLARE
          before_count BIGINT;
          after_count BIGINT;
          legacy_count BIGINT;
          invalid_count BIGINT;
          unchanged_non_role_count BIGINT;
        BEGIN
          SELECT count(*) INTO before_count
          FROM _concept_memory_links_role_cleanup_before;

          SELECT count(*) INTO after_count
          FROM concept_memory_links;

          IF before_count <> after_count THEN
            RAISE EXCEPTION
              'Concept-memory role cleanup changed row count from % to %.',
              before_count,
              after_count;
          END IF;

          SELECT count(*) INTO legacy_count
          FROM concept_memory_links
          WHERE role IN ('changed', 'validated', 'contradicted', 'warned_about');

          IF legacy_count <> 0 THEN
            RAISE EXCEPTION
              'Concept-memory role cleanup left % legacy role row(s).',
              legacy_count;
          END IF;

          SELECT count(*) INTO invalid_count
          FROM concept_memory_links
          WHERE role NOT IN ({_quoted(_NEW_ROLES)});

          IF invalid_count <> 0 THEN
            RAISE EXCEPTION
              'Concept-memory role cleanup produced % invalid role row(s).',
              invalid_count;
          END IF;

          SELECT count(*) INTO unchanged_non_role_count
          FROM _concept_memory_links_role_cleanup_before before_rows
          FULL JOIN concept_memory_links after_rows USING (id)
          WHERE before_rows.id IS NULL
             OR after_rows.id IS NULL
             OR before_rows.repo_id IS DISTINCT FROM after_rows.repo_id
             OR before_rows.concept_id IS DISTINCT FROM after_rows.concept_id
             OR before_rows.memory_id IS DISTINCT FROM after_rows.memory_id
             OR before_rows.status IS DISTINCT FROM after_rows.status
             OR before_rows.confidence IS DISTINCT FROM after_rows.confidence
             OR before_rows.observed_at IS DISTINCT FROM after_rows.observed_at
             OR before_rows.validated_at IS DISTINCT FROM after_rows.validated_at
             OR before_rows.invalidated_at IS DISTINCT FROM after_rows.invalidated_at
             OR before_rows.source_kind IS DISTINCT FROM after_rows.source_kind
             OR before_rows.source_ref IS DISTINCT FROM after_rows.source_ref
             OR before_rows.superseded_by_id IS DISTINCT FROM after_rows.superseded_by_id
             OR before_rows.created_by IS DISTINCT FROM after_rows.created_by
             OR before_rows.updated_by IS DISTINCT FROM after_rows.updated_by
             OR before_rows.created_at IS DISTINCT FROM after_rows.created_at
             OR before_rows.updated_at IS DISTINCT FROM after_rows.updated_at;

          IF unchanged_non_role_count <> 0 THEN
            RAISE EXCEPTION
              'Concept-memory role cleanup changed % non-role row value(s).',
              unchanged_non_role_count;
          END IF;
        END $$;
        """
    )


def downgrade() -> None:
    """Recreate the previous role constraint for Alembic downgrade only."""

    op.execute(
        f"""
        ALTER TABLE concept_memory_links
          DROP CONSTRAINT IF EXISTS ck_concept_memory_links_role;

        UPDATE concept_memory_links
        SET role = CASE role
          WHEN 'warns_about' THEN 'warned_about'
          WHEN 'change_relevant_to' THEN 'changed'
          ELSE role
        END
        WHERE role IN ('warns_about', 'change_relevant_to');

        ALTER TABLE concept_memory_links
          ADD CONSTRAINT ck_concept_memory_links_role
          CHECK (role IN ({_quoted(_PREVIOUS_ROLES)}));
        """
    )


def _quoted(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)
