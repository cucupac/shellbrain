"""Add knowledge-builder build run tracking."""

from alembic import op

revision = "20260513_0018"
down_revision = "20260511_0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create build_knowledge run records."""

    op.execute(
        """
        CREATE TABLE knowledge_build_runs (
          id TEXT PRIMARY KEY,
          repo_id TEXT NOT NULL,
          episode_id TEXT NOT NULL REFERENCES episodes(id) ON DELETE CASCADE,
          trigger TEXT NOT NULL CHECK (
            trigger IN ('session_replaced', 'idle_stable')
          ),
          status TEXT NOT NULL CHECK (
            status IN (
              'running',
              'ok',
              'skipped',
              'provider_unavailable',
              'timeout',
              'invalid_output',
              'error'
            )
          ),
          event_watermark INTEGER NOT NULL CHECK (event_watermark >= 0),
          previous_event_watermark INTEGER CHECK (
            previous_event_watermark IS NULL OR previous_event_watermark >= 0
          ),
          provider TEXT NOT NULL,
          model TEXT NOT NULL,
          reasoning TEXT NOT NULL,
          write_count INTEGER NOT NULL DEFAULT 0 CHECK (write_count >= 0),
          skipped_item_count INTEGER NOT NULL DEFAULT 0
            CHECK (skipped_item_count >= 0),
          run_summary TEXT,
          error_code TEXT,
          error_message TEXT,
          started_at TIMESTAMPTZ NOT NULL,
          finished_at TIMESTAMPTZ,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE INDEX idx_knowledge_build_runs_episode_status_created_at
          ON knowledge_build_runs(repo_id, episode_id, status, created_at);
        """
    )


def downgrade() -> None:
    """Drop build_knowledge run records."""

    op.execute(
        """
        DROP INDEX IF EXISTS idx_knowledge_build_runs_episode_status_created_at;
        DROP TABLE IF EXISTS knowledge_build_runs;
        """
    )
