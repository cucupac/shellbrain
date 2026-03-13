"""Add explicit host session metadata and upstream event dedupe for episodes."""

from alembic import op


revision = "20260313_0004"
down_revision = "20260312_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add host-app identity and upstream event keys for episodic sync."""

    op.execute(
        """
        ALTER TABLE episodes
        ADD COLUMN host_app TEXT;

        UPDATE episodes
        SET host_app = CASE
          WHEN thread_id LIKE 'codex:%' THEN 'codex'
          WHEN thread_id LIKE 'claude_code:%' THEN 'claude_code'
          ELSE 'unknown'
        END
        WHERE host_app IS NULL;

        ALTER TABLE episodes
        ALTER COLUMN host_app SET NOT NULL;

        ALTER TABLE episode_events
        ADD COLUMN host_event_key TEXT;

        UPDATE episode_events
        SET host_event_key = 'legacy:' || id
        WHERE host_event_key IS NULL;

        ALTER TABLE episode_events
        ALTER COLUMN host_event_key SET NOT NULL;

        DROP INDEX IF EXISTS idx_episodes_repo_thread;

        ALTER TABLE episodes
        ADD CONSTRAINT uq_episodes_repo_thread UNIQUE (repo_id, thread_id);

        ALTER TABLE episode_events
        ADD CONSTRAINT uq_episode_events_host_event_key UNIQUE (episode_id, host_event_key);
        """
    )


def downgrade() -> None:
    """Remove episode sync hardening columns and constraints."""

    op.execute(
        """
        ALTER TABLE episode_events
        DROP CONSTRAINT IF EXISTS uq_episode_events_host_event_key;

        ALTER TABLE episodes
        DROP CONSTRAINT IF EXISTS uq_episodes_repo_thread;

        CREATE INDEX IF NOT EXISTS idx_episodes_repo_thread ON episodes(repo_id, thread_id);

        ALTER TABLE episode_events
        DROP COLUMN IF EXISTS host_event_key;

        ALTER TABLE episodes
        DROP COLUMN IF EXISTS host_app;
        """
    )
