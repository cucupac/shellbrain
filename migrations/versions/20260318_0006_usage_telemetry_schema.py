"""Create low-overhead usage telemetry storage and analytics views."""

from alembic import op

from app.infrastructure.db.runtime.models.views import (
    USAGE_COMMAND_DAILY_SQL,
    USAGE_MEMORY_RETRIEVAL_SQL,
    USAGE_SESSION_PROTOCOL_SQL,
    USAGE_SYNC_HEALTH_SQL,
    USAGE_WRITE_EFFECTS_SQL,
)

revision = "20260318_0006"
down_revision = "20260313_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create telemetry tables, indexes, and derived analytics views."""

    op.execute(
        """
        CREATE TABLE operation_invocations (
          id TEXT PRIMARY KEY,
          command TEXT NOT NULL CHECK (command IN ('read', 'create', 'update', 'events')),
          repo_id TEXT NOT NULL,
          repo_root TEXT NOT NULL,
          no_sync BOOLEAN NOT NULL DEFAULT FALSE,
          selected_host_app TEXT,
          selected_host_session_key TEXT,
          selected_thread_id TEXT,
          selected_episode_id TEXT,
          matching_candidate_count INTEGER NOT NULL DEFAULT 0 CHECK (matching_candidate_count >= 0),
          selection_ambiguous BOOLEAN NOT NULL DEFAULT FALSE,
          outcome TEXT NOT NULL CHECK (outcome IN ('ok', 'error')),
          error_stage TEXT,
          error_code TEXT,
          error_message TEXT,
          total_latency_ms INTEGER NOT NULL CHECK (total_latency_ms >= 0),
          poller_start_attempted BOOLEAN NOT NULL DEFAULT FALSE,
          poller_started BOOLEAN NOT NULL DEFAULT FALSE,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX idx_operation_invocations_repo_created_at
          ON operation_invocations(repo_id, created_at);
        CREATE INDEX idx_operation_invocations_command_created_at
          ON operation_invocations(command, created_at);
        CREATE INDEX idx_operation_invocations_thread_created_at
          ON operation_invocations(selected_thread_id, created_at)
          WHERE selected_thread_id IS NOT NULL;

        CREATE TABLE read_invocation_summaries (
          invocation_id TEXT PRIMARY KEY REFERENCES operation_invocations(id) ON DELETE CASCADE,
          query_text TEXT NOT NULL,
          mode TEXT NOT NULL,
          requested_limit INTEGER,
          effective_limit INTEGER NOT NULL CHECK (effective_limit >= 0),
          include_global BOOLEAN,
          kinds_filter JSONB,
          direct_count INTEGER NOT NULL CHECK (direct_count >= 0),
          explicit_related_count INTEGER NOT NULL CHECK (explicit_related_count >= 0),
          implicit_related_count INTEGER NOT NULL CHECK (implicit_related_count >= 0),
          total_returned INTEGER NOT NULL CHECK (total_returned >= 0),
          zero_results BOOLEAN NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE TABLE read_result_items (
          invocation_id TEXT NOT NULL REFERENCES operation_invocations(id) ON DELETE CASCADE,
          ordinal INTEGER NOT NULL CHECK (ordinal > 0),
          memory_id TEXT NOT NULL,
          kind TEXT NOT NULL,
          section TEXT NOT NULL,
          priority INTEGER NOT NULL CHECK (priority > 0),
          why_included TEXT NOT NULL,
          anchor_memory_id TEXT,
          relation_type TEXT,
          PRIMARY KEY (invocation_id, ordinal)
        );
        CREATE INDEX idx_read_result_items_memory_invocation
          ON read_result_items(memory_id, invocation_id);

        CREATE TABLE write_invocation_summaries (
          invocation_id TEXT PRIMARY KEY REFERENCES operation_invocations(id) ON DELETE CASCADE,
          operation_command TEXT NOT NULL CHECK (operation_command IN ('create', 'update')),
          target_memory_id TEXT NOT NULL,
          target_kind TEXT,
          update_type TEXT,
          scope TEXT,
          evidence_ref_count INTEGER NOT NULL DEFAULT 0 CHECK (evidence_ref_count >= 0),
          planned_effect_count INTEGER NOT NULL CHECK (planned_effect_count >= 0),
          created_memory_count INTEGER NOT NULL DEFAULT 0 CHECK (created_memory_count >= 0),
          archived_memory_count INTEGER NOT NULL DEFAULT 0 CHECK (archived_memory_count >= 0),
          utility_observation_count INTEGER NOT NULL DEFAULT 0 CHECK (utility_observation_count >= 0),
          association_effect_count INTEGER NOT NULL DEFAULT 0 CHECK (association_effect_count >= 0),
          fact_update_count INTEGER NOT NULL DEFAULT 0 CHECK (fact_update_count >= 0),
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE TABLE write_effect_items (
          invocation_id TEXT NOT NULL REFERENCES operation_invocations(id) ON DELETE CASCADE,
          ordinal INTEGER NOT NULL CHECK (ordinal > 0),
          effect_type TEXT NOT NULL,
          repo_id TEXT NOT NULL,
          primary_memory_id TEXT,
          secondary_memory_id TEXT,
          params_json JSONB NOT NULL DEFAULT '{}'::jsonb,
          PRIMARY KEY (invocation_id, ordinal)
        );
        CREATE INDEX idx_write_effect_items_repo_effect_invocation
          ON write_effect_items(repo_id, effect_type, invocation_id);

        CREATE TABLE episode_sync_runs (
          id TEXT PRIMARY KEY,
          source TEXT NOT NULL CHECK (source IN ('events_inline', 'poller')),
          invocation_id TEXT REFERENCES operation_invocations(id) ON DELETE SET NULL,
          repo_id TEXT NOT NULL,
          host_app TEXT NOT NULL,
          host_session_key TEXT NOT NULL,
          thread_id TEXT NOT NULL,
          episode_id TEXT,
          transcript_path TEXT,
          outcome TEXT NOT NULL CHECK (outcome IN ('ok', 'error')),
          error_stage TEXT,
          error_message TEXT,
          duration_ms INTEGER NOT NULL CHECK (duration_ms >= 0),
          imported_event_count INTEGER NOT NULL DEFAULT 0 CHECK (imported_event_count >= 0),
          total_event_count INTEGER NOT NULL DEFAULT 0 CHECK (total_event_count >= 0),
          user_event_count INTEGER NOT NULL DEFAULT 0 CHECK (user_event_count >= 0),
          assistant_event_count INTEGER NOT NULL DEFAULT 0 CHECK (assistant_event_count >= 0),
          tool_event_count INTEGER NOT NULL DEFAULT 0 CHECK (tool_event_count >= 0),
          system_event_count INTEGER NOT NULL DEFAULT 0 CHECK (system_event_count >= 0),
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX idx_episode_sync_runs_repo_host_created_at
          ON episode_sync_runs(repo_id, host_app, created_at);
        CREATE INDEX idx_episode_sync_runs_thread_created_at
          ON episode_sync_runs(thread_id, created_at);

        CREATE TABLE episode_sync_tool_types (
          sync_run_id TEXT NOT NULL REFERENCES episode_sync_runs(id) ON DELETE CASCADE,
          tool_type TEXT NOT NULL,
          event_count INTEGER NOT NULL CHECK (event_count >= 0),
          PRIMARY KEY (sync_run_id, tool_type)
        );
        """
    )
    op.execute(USAGE_COMMAND_DAILY_SQL)
    op.execute(USAGE_MEMORY_RETRIEVAL_SQL)
    op.execute(USAGE_WRITE_EFFECTS_SQL)
    op.execute(USAGE_SYNC_HEALTH_SQL)
    op.execute(USAGE_SESSION_PROTOCOL_SQL)


def downgrade() -> None:
    """Drop telemetry views, indexes, and tables."""

    op.execute(
        """
        DROP VIEW IF EXISTS usage_session_protocol;
        DROP VIEW IF EXISTS usage_sync_health;
        DROP VIEW IF EXISTS usage_write_effects;
        DROP VIEW IF EXISTS usage_memory_retrieval;
        DROP VIEW IF EXISTS usage_command_daily;

        DROP TABLE IF EXISTS episode_sync_tool_types;
        DROP TABLE IF EXISTS episode_sync_runs;
        DROP TABLE IF EXISTS write_effect_items;
        DROP TABLE IF EXISTS write_invocation_summaries;
        DROP TABLE IF EXISTS read_result_items;
        DROP TABLE IF EXISTS read_invocation_summaries;
        DROP TABLE IF EXISTS operation_invocations;
        """
    )
