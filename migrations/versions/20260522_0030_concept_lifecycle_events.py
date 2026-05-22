"""Add auditable lifecycle updates for concept truth records."""

from alembic import op


revision = "20260522_0030"
down_revision = "20260522_0029"
branch_labels = None
depends_on = None


_TRUTH_TABLES = (
    "concept_relations",
    "concept_claims",
    "concept_groundings",
    "concept_memory_links",
)


def upgrade() -> None:
    """Add lifecycle event storage and expand lifecycle metadata."""

    for table_name in _TRUTH_TABLES:
        op.execute(
            f"""
            ALTER TABLE {table_name}
              ADD COLUMN IF NOT EXISTS invalidated_at TIMESTAMPTZ,
              ADD COLUMN IF NOT EXISTS updated_by TEXT;

            ALTER TABLE {table_name}
              DROP CONSTRAINT IF EXISTS ck_{table_name}_status,
              DROP CONSTRAINT IF EXISTS ck_{table_name}_updated_by;

            ALTER TABLE {table_name}
              ADD CONSTRAINT ck_{table_name}_status
              CHECK (status IN ('active', 'maybe_stale', 'stale', 'superseded', 'wrong', 'archived')),
              ADD CONSTRAINT ck_{table_name}_updated_by
              CHECK (updated_by IS NULL OR updated_by IN ('worker', 'librarian', 'manual', 'import'));
            """
        )

    op.execute(
        """
        ALTER TABLE concept_evidence
          DROP CONSTRAINT IF EXISTS ck_concept_evidence_target_type;

        ALTER TABLE concept_evidence
          ADD CONSTRAINT ck_concept_evidence_target_type
          CHECK (target_type IN ('relation', 'claim', 'grounding', 'memory_link', 'lifecycle_event'));

        CREATE TABLE IF NOT EXISTS concept_lifecycle_events (
          id TEXT PRIMARY KEY,
          repo_id TEXT NOT NULL,
          target_type TEXT NOT NULL,
          target_id TEXT NOT NULL,
          from_status TEXT NOT NULL,
          to_status TEXT NOT NULL,
          rationale TEXT NOT NULL,
          actor TEXT NOT NULL,
          superseded_by_id TEXT,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          CONSTRAINT ck_concept_lifecycle_events_target_type
            CHECK (target_type IN ('relation', 'claim', 'grounding', 'memory_link')),
          CONSTRAINT ck_concept_lifecycle_events_from_status
            CHECK (from_status IN ('active', 'maybe_stale', 'stale', 'superseded', 'wrong', 'archived')),
          CONSTRAINT ck_concept_lifecycle_events_to_status
            CHECK (to_status IN ('active', 'maybe_stale', 'stale', 'superseded', 'wrong', 'archived')),
          CONSTRAINT ck_concept_lifecycle_events_actor
            CHECK (actor IN ('worker', 'librarian', 'manual', 'import')),
          CONSTRAINT ck_concept_lifecycle_events_rationale
            CHECK (btrim(rationale) <> '')
        );

        CREATE INDEX IF NOT EXISTS idx_concept_lifecycle_events_target
          ON concept_lifecycle_events(repo_id, target_type, target_id, created_at);
        """
    )


def downgrade() -> None:
    """Remove lifecycle event storage and restore previous lifecycle constraints."""

    op.execute(
        """
        DELETE FROM concept_evidence WHERE target_type = 'lifecycle_event';
        DROP TABLE IF EXISTS concept_lifecycle_events;

        ALTER TABLE concept_evidence
          DROP CONSTRAINT IF EXISTS ck_concept_evidence_target_type;

        ALTER TABLE concept_evidence
          ADD CONSTRAINT ck_concept_evidence_target_type
          CHECK (target_type IN ('relation', 'claim', 'grounding', 'memory_link'));
        """
    )

    for table_name in _TRUTH_TABLES:
        op.execute(
            f"""
            UPDATE {table_name}
            SET status = 'stale'
            WHERE status = 'archived';

            ALTER TABLE {table_name}
              DROP CONSTRAINT IF EXISTS ck_{table_name}_status,
              DROP CONSTRAINT IF EXISTS ck_{table_name}_updated_by;

            ALTER TABLE {table_name}
              ADD CONSTRAINT ck_{table_name}_status
              CHECK (status IN ('active', 'maybe_stale', 'stale', 'superseded', 'wrong'));

            ALTER TABLE {table_name}
              DROP COLUMN IF EXISTS invalidated_at,
              DROP COLUMN IF EXISTS updated_by;
            """
        )
