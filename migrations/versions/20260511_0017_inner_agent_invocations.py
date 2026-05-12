"""Add inner-agent telemetry tables and recall provider fields."""

from alembic import op

revision = "20260511_0017"
down_revision = "20260508_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create inner-agent telemetry and extend recall summaries."""

    op.execute(
        """
        ALTER TABLE recall_invocation_summaries
          ADD COLUMN provider TEXT,
          ADD COLUMN model TEXT,
          ADD COLUMN reasoning TEXT,
          ADD COLUMN private_read_count INTEGER NOT NULL DEFAULT 0,
          ADD COLUMN concept_expansion_count INTEGER NOT NULL DEFAULT 0,
          ADD CONSTRAINT ck_recall_private_read_count_nonnegative
            CHECK (private_read_count >= 0),
          ADD CONSTRAINT ck_recall_concept_expansion_count_nonnegative
            CHECK (concept_expansion_count >= 0);

        CREATE TABLE inner_agent_invocations (
          id TEXT PRIMARY KEY,
          operation_invocation_id TEXT NOT NULL REFERENCES operation_invocations(id) ON DELETE CASCADE,
          agent_name TEXT NOT NULL CHECK (agent_name IN ('build_context', 'build_knowledge')),
          provider TEXT,
          model TEXT,
          reasoning TEXT,
          status TEXT NOT NULL CHECK (
            status IN (
              'ok',
              'no_context',
              'provider_unavailable',
              'timeout',
              'invalid_output',
              'error',
              'disabled'
            )
          ),
          fallback_used BOOLEAN NOT NULL DEFAULT FALSE,
          timeout_seconds INTEGER,
          duration_ms INTEGER NOT NULL DEFAULT 0 CHECK (duration_ms >= 0),
          input_token_estimate INTEGER CHECK (
            input_token_estimate IS NULL OR input_token_estimate >= 0
          ),
          output_token_estimate INTEGER CHECK (
            output_token_estimate IS NULL OR output_token_estimate >= 0
          ),
          private_read_count INTEGER NOT NULL DEFAULT 0 CHECK (private_read_count >= 0),
          concept_expansion_count INTEGER NOT NULL DEFAULT 0 CHECK (concept_expansion_count >= 0),
          error_code TEXT,
          error_message TEXT,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE INDEX idx_inner_agent_invocations_operation
          ON inner_agent_invocations(operation_invocation_id);

        CREATE INDEX idx_inner_agent_invocations_agent_status_created_at
          ON inner_agent_invocations(agent_name, status, created_at);
        """
    )


def downgrade() -> None:
    """Drop inner-agent telemetry and recall provider fields."""

    op.execute(
        """
        DROP INDEX IF EXISTS idx_inner_agent_invocations_agent_status_created_at;
        DROP INDEX IF EXISTS idx_inner_agent_invocations_operation;
        DROP TABLE IF EXISTS inner_agent_invocations;

        ALTER TABLE recall_invocation_summaries
          DROP CONSTRAINT IF EXISTS ck_recall_concept_expansion_count_nonnegative,
          DROP CONSTRAINT IF EXISTS ck_recall_private_read_count_nonnegative,
          DROP COLUMN IF EXISTS concept_expansion_count,
          DROP COLUMN IF EXISTS private_read_count,
          DROP COLUMN IF EXISTS reasoning,
          DROP COLUMN IF EXISTS model,
          DROP COLUMN IF EXISTS provider;
        """
    )
