"""Add minimal recall telemetry tables."""

from alembic import op

revision = "20260508_0016"
down_revision = "20260422_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create recall telemetry tables and allow recall command rows when constrained."""

    op.execute(
        """
        DO $$
        DECLARE
          command_constraint_name TEXT;
        BEGIN
          SELECT con.conname
            INTO command_constraint_name
            FROM pg_constraint con
            JOIN pg_class rel ON rel.oid = con.conrelid
            JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
           WHERE nsp.nspname = current_schema()
             AND rel.relname = 'operation_invocations'
             AND con.contype = 'c'
             AND pg_get_constraintdef(con.oid) LIKE '%command%'
             AND pg_get_constraintdef(con.oid) LIKE '%read%'
             AND pg_get_constraintdef(con.oid) LIKE '%events%'
           LIMIT 1;

          IF command_constraint_name IS NOT NULL THEN
            EXECUTE format('ALTER TABLE operation_invocations DROP CONSTRAINT %I', command_constraint_name);
            ALTER TABLE operation_invocations
              ADD CONSTRAINT ck_operation_invocations_command
              CHECK (command IN ('read', 'create', 'update', 'events', 'concept', 'recall'));
          END IF;
        END $$;

        CREATE TABLE recall_invocation_summaries (
          invocation_id TEXT PRIMARY KEY REFERENCES operation_invocations(id) ON DELETE CASCADE,
          query_text TEXT NOT NULL,
          candidate_token_estimate INTEGER NOT NULL CHECK (candidate_token_estimate >= 0),
          brief_token_estimate INTEGER NOT NULL CHECK (brief_token_estimate >= 0),
          fallback_reason TEXT CHECK (fallback_reason IS NULL OR fallback_reason = 'no_candidates'),
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE TABLE recall_source_items (
          invocation_id TEXT NOT NULL REFERENCES operation_invocations(id) ON DELETE CASCADE,
          ordinal INTEGER NOT NULL CHECK (ordinal > 0),
          source_kind TEXT NOT NULL CHECK (source_kind IN ('memory', 'concept')),
          source_id TEXT NOT NULL,
          input_section TEXT NOT NULL CHECK (
            input_section IN ('direct', 'explicit_related', 'implicit_related', 'concept_orientation')
          ),
          output_section TEXT CHECK (output_section IS NULL OR output_section IN ('summary', 'sources')),
          PRIMARY KEY (invocation_id, ordinal)
        );

        CREATE INDEX idx_recall_source_items_source_invocation
          ON recall_source_items(source_kind, source_id, invocation_id);
        """
    )


def downgrade() -> None:
    """Drop recall telemetry tables and remove recall from the named command check if present."""

    op.execute(
        """
        DROP INDEX IF EXISTS idx_recall_source_items_source_invocation;
        DROP TABLE IF EXISTS recall_source_items;
        DROP TABLE IF EXISTS recall_invocation_summaries;

        DO $$
        BEGIN
          IF EXISTS (
            SELECT 1
              FROM pg_constraint con
              JOIN pg_class rel ON rel.oid = con.conrelid
              JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
             WHERE nsp.nspname = current_schema()
               AND rel.relname = 'operation_invocations'
               AND con.contype = 'c'
               AND con.conname = 'ck_operation_invocations_command'
          ) THEN
            ALTER TABLE operation_invocations DROP CONSTRAINT ck_operation_invocations_command;
            ALTER TABLE operation_invocations
              ADD CONSTRAINT ck_operation_invocations_command
              CHECK (command IN ('read', 'create', 'update', 'events', 'concept'));
          END IF;
        END $$;
        """
    )
