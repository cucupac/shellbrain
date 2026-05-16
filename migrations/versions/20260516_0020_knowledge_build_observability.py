"""Add build_knowledge traces and operation provenance."""

from alembic import op

from app.infrastructure.db.runtime.models.views import (
    USAGE_PROBLEM_RUN_AGENT_TOKENS_SQL,
)

revision = "20260516_0020"
down_revision = "20260515_0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add trace storage, inner-agent tokens, and build_knowledge provenance."""

    op.execute(
        """
        ALTER TABLE knowledge_build_runs
          ADD COLUMN read_trace_json JSONB NOT NULL DEFAULT '{}'::jsonb,
          ADD COLUMN code_trace_json JSONB NOT NULL DEFAULT '{}'::jsonb,
          ADD COLUMN input_tokens BIGINT,
          ADD COLUMN output_tokens BIGINT,
          ADD COLUMN reasoning_output_tokens BIGINT,
          ADD COLUMN cached_input_tokens_total BIGINT,
          ADD COLUMN cache_read_input_tokens BIGINT,
          ADD COLUMN cache_creation_input_tokens BIGINT,
          ADD COLUMN capture_quality TEXT;

        ALTER TABLE knowledge_build_runs
          ADD CONSTRAINT ck_knowledge_build_runs_input_tokens_nonnegative
          CHECK (input_tokens IS NULL OR input_tokens >= 0),
          ADD CONSTRAINT ck_knowledge_build_runs_output_tokens_nonnegative
          CHECK (output_tokens IS NULL OR output_tokens >= 0),
          ADD CONSTRAINT ck_knowledge_build_runs_reasoning_tokens_nonnegative
          CHECK (reasoning_output_tokens IS NULL OR reasoning_output_tokens >= 0),
          ADD CONSTRAINT ck_knowledge_build_runs_cached_tokens_nonnegative
          CHECK (cached_input_tokens_total IS NULL OR cached_input_tokens_total >= 0),
          ADD CONSTRAINT ck_knowledge_build_runs_cache_read_tokens_nonnegative
          CHECK (cache_read_input_tokens IS NULL OR cache_read_input_tokens >= 0),
          ADD CONSTRAINT ck_knowledge_build_runs_cache_creation_tokens_nonnegative
          CHECK (cache_creation_input_tokens IS NULL OR cache_creation_input_tokens >= 0),
          ADD CONSTRAINT ck_knowledge_build_runs_capture_quality
          CHECK (capture_quality IS NULL OR capture_quality IN ('exact', 'estimated'));

        ALTER TABLE inner_agent_invocations
          ADD COLUMN input_tokens BIGINT,
          ADD COLUMN output_tokens BIGINT,
          ADD COLUMN reasoning_output_tokens BIGINT,
          ADD COLUMN cached_input_tokens_total BIGINT,
          ADD COLUMN cache_read_input_tokens BIGINT,
          ADD COLUMN cache_creation_input_tokens BIGINT,
          ADD COLUMN capture_quality TEXT;

        UPDATE inner_agent_invocations
           SET input_tokens = input_token_estimate,
               output_tokens = output_token_estimate,
               capture_quality = CASE
                 WHEN input_token_estimate IS NOT NULL
                   OR output_token_estimate IS NOT NULL
                 THEN 'estimated'
                 ELSE NULL
               END;

        ALTER TABLE inner_agent_invocations
          DROP COLUMN IF EXISTS input_token_estimate,
          DROP COLUMN IF EXISTS output_token_estimate;

        ALTER TABLE inner_agent_invocations
          ADD CONSTRAINT ck_inner_agent_input_tokens_nonnegative
          CHECK (input_tokens IS NULL OR input_tokens >= 0),
          ADD CONSTRAINT ck_inner_agent_output_tokens_nonnegative
          CHECK (output_tokens IS NULL OR output_tokens >= 0),
          ADD CONSTRAINT ck_inner_agent_reasoning_output_tokens_nonnegative
          CHECK (reasoning_output_tokens IS NULL OR reasoning_output_tokens >= 0),
          ADD CONSTRAINT ck_inner_agent_cached_input_tokens_nonnegative
          CHECK (cached_input_tokens_total IS NULL OR cached_input_tokens_total >= 0),
          ADD CONSTRAINT ck_inner_agent_cache_read_tokens_nonnegative
          CHECK (cache_read_input_tokens IS NULL OR cache_read_input_tokens >= 0),
          ADD CONSTRAINT ck_inner_agent_cache_creation_tokens_nonnegative
          CHECK (cache_creation_input_tokens IS NULL OR cache_creation_input_tokens >= 0),
          ADD CONSTRAINT ck_inner_agent_capture_quality
          CHECK (capture_quality IS NULL OR capture_quality IN ('exact', 'estimated'));

        ALTER TABLE operation_invocations
          ADD COLUMN knowledge_build_run_id TEXT;

        ALTER TABLE operation_invocations
          ADD CONSTRAINT fk_operation_invocations_knowledge_build_run
          FOREIGN KEY (knowledge_build_run_id)
          REFERENCES knowledge_build_runs(id)
          ON DELETE SET NULL;

        CREATE INDEX idx_operation_invocations_knowledge_build_run_created_at
          ON operation_invocations(knowledge_build_run_id, created_at)
          WHERE knowledge_build_run_id IS NOT NULL;
        """
    )
    op.execute(USAGE_PROBLEM_RUN_AGENT_TOKENS_SQL)


def downgrade() -> None:
    """Remove build_knowledge trace storage, token columns, and provenance link."""

    op.execute(
        """
        DROP VIEW IF EXISTS usage_problem_run_agent_tokens;

        DROP INDEX IF EXISTS idx_operation_invocations_knowledge_build_run_created_at;

        ALTER TABLE operation_invocations
          DROP CONSTRAINT IF EXISTS fk_operation_invocations_knowledge_build_run,
          DROP COLUMN IF EXISTS knowledge_build_run_id;

        ALTER TABLE inner_agent_invocations
          ADD COLUMN input_token_estimate INTEGER,
          ADD COLUMN output_token_estimate INTEGER;

        UPDATE inner_agent_invocations
           SET input_token_estimate = input_tokens::INTEGER,
               output_token_estimate = output_tokens::INTEGER;

        ALTER TABLE inner_agent_invocations
          DROP CONSTRAINT IF EXISTS ck_inner_agent_capture_quality,
          DROP CONSTRAINT IF EXISTS ck_inner_agent_cache_creation_tokens_nonnegative,
          DROP CONSTRAINT IF EXISTS ck_inner_agent_cache_read_tokens_nonnegative,
          DROP CONSTRAINT IF EXISTS ck_inner_agent_cached_input_tokens_nonnegative,
          DROP CONSTRAINT IF EXISTS ck_inner_agent_reasoning_output_tokens_nonnegative,
          DROP CONSTRAINT IF EXISTS ck_inner_agent_output_tokens_nonnegative,
          DROP CONSTRAINT IF EXISTS ck_inner_agent_input_tokens_nonnegative,
          DROP COLUMN IF EXISTS capture_quality,
          DROP COLUMN IF EXISTS cache_creation_input_tokens,
          DROP COLUMN IF EXISTS cache_read_input_tokens,
          DROP COLUMN IF EXISTS cached_input_tokens_total,
          DROP COLUMN IF EXISTS reasoning_output_tokens,
          DROP COLUMN IF EXISTS output_tokens,
          DROP COLUMN IF EXISTS input_tokens;

        ALTER TABLE inner_agent_invocations
          ADD CONSTRAINT ck_inner_agent_input_tokens_nonnegative
          CHECK (input_token_estimate IS NULL OR input_token_estimate >= 0),
          ADD CONSTRAINT ck_inner_agent_output_tokens_nonnegative
          CHECK (output_token_estimate IS NULL OR output_token_estimate >= 0);

        ALTER TABLE knowledge_build_runs
          DROP CONSTRAINT IF EXISTS ck_knowledge_build_runs_capture_quality,
          DROP CONSTRAINT IF EXISTS ck_knowledge_build_runs_cache_creation_tokens_nonnegative,
          DROP CONSTRAINT IF EXISTS ck_knowledge_build_runs_cache_read_tokens_nonnegative,
          DROP CONSTRAINT IF EXISTS ck_knowledge_build_runs_cached_tokens_nonnegative,
          DROP CONSTRAINT IF EXISTS ck_knowledge_build_runs_reasoning_tokens_nonnegative,
          DROP CONSTRAINT IF EXISTS ck_knowledge_build_runs_output_tokens_nonnegative,
          DROP CONSTRAINT IF EXISTS ck_knowledge_build_runs_input_tokens_nonnegative,
          DROP COLUMN IF EXISTS capture_quality,
          DROP COLUMN IF EXISTS cache_creation_input_tokens,
          DROP COLUMN IF EXISTS cache_read_input_tokens,
          DROP COLUMN IF EXISTS cached_input_tokens_total,
          DROP COLUMN IF EXISTS reasoning_output_tokens,
          DROP COLUMN IF EXISTS output_tokens,
          DROP COLUMN IF EXISTS input_tokens;

        ALTER TABLE knowledge_build_runs
          DROP COLUMN IF EXISTS code_trace_json,
          DROP COLUMN IF EXISTS read_trace_json;
        """
    )
