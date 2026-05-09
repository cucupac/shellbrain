"""Add model-usage telemetry storage and derived views."""

from alembic import op

from app.infrastructure.db.runtime.models.views import (
    USAGE_COMMAND_DAILY_SQL,
    USAGE_MEMORY_RETRIEVAL_SQL,
    USAGE_PROBLEM_TOKENS_SQL,
    USAGE_SESSION_PROTOCOL_SQL,
    USAGE_SESSION_TOKENS_SQL,
    USAGE_SYNC_HEALTH_SQL,
    USAGE_TOKEN_CAPTURE_HEALTH_SQL,
    USAGE_WRITE_EFFECTS_SQL,
)

revision = "20260414_0010"
down_revision = "20260410_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create model-usage telemetry storage and derived views."""

    op.execute(
        """
        CREATE TABLE model_usage (
          id TEXT PRIMARY KEY,
          repo_id TEXT NOT NULL,
          thread_id TEXT,
          episode_id TEXT,
          host_app TEXT NOT NULL,
          host_session_key TEXT NOT NULL,
          host_usage_key TEXT NOT NULL,
          source_kind TEXT NOT NULL,
          occurred_at TIMESTAMPTZ NOT NULL,
          agent_role TEXT NOT NULL DEFAULT 'foreground',
          provider TEXT,
          model_id TEXT,
          input_tokens BIGINT,
          output_tokens BIGINT,
          reasoning_output_tokens BIGINT,
          cached_input_tokens_total BIGINT,
          cache_read_input_tokens BIGINT,
          cache_creation_input_tokens BIGINT,
          capture_quality TEXT NOT NULL DEFAULT 'exact',
          raw_usage_json JSONB NOT NULL DEFAULT '{}'::jsonb,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          CONSTRAINT uq_model_usage_host_session_usage UNIQUE (host_app, host_session_key, host_usage_key)
        );
        CREATE INDEX idx_model_usage_repo_thread_occurred_at
          ON model_usage(repo_id, thread_id, occurred_at);
        CREATE INDEX idx_model_usage_repo_host_session_occurred_at
          ON model_usage(repo_id, host_app, host_session_key, occurred_at);
        """
    )
    op.execute(USAGE_COMMAND_DAILY_SQL)
    op.execute(USAGE_MEMORY_RETRIEVAL_SQL)
    op.execute(USAGE_WRITE_EFFECTS_SQL)
    op.execute(USAGE_SYNC_HEALTH_SQL)
    op.execute(USAGE_SESSION_PROTOCOL_SQL)
    op.execute(USAGE_SESSION_TOKENS_SQL)
    op.execute(USAGE_PROBLEM_TOKENS_SQL)
    op.execute(USAGE_TOKEN_CAPTURE_HEALTH_SQL)


def downgrade() -> None:
    """Drop model-usage telemetry views and table."""

    op.execute(
        """
        DROP VIEW IF EXISTS usage_token_capture_health;
        DROP VIEW IF EXISTS usage_problem_tokens;
        DROP VIEW IF EXISTS usage_session_tokens;
        DROP VIEW IF EXISTS usage_session_protocol;
        DROP VIEW IF EXISTS usage_sync_health;
        DROP VIEW IF EXISTS usage_write_effects;
        DROP VIEW IF EXISTS usage_memory_retrieval;
        DROP VIEW IF EXISTS usage_command_daily;

        DROP TABLE IF EXISTS model_usage;
        """
    )
