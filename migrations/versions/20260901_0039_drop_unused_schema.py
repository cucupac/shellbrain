"""Drop tables and columns no code path reads or writes."""

from __future__ import annotations

from alembic import op


revision = "20260901_0039"
down_revision = "20260815_0038"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Drop the unused session-transfer and graph-patch tables and four never-written columns."""

    op.execute(
        """
        DROP TABLE IF EXISTS session_transfers;
        DROP TABLE IF EXISTS graph_patches;
        ALTER TABLE episodes DROP COLUMN IF EXISTS title;
        ALTER TABLE episodes DROP COLUMN IF EXISTS objective;
        ALTER TABLE association_edges DROP COLUMN IF EXISTS last_used_at;
        ALTER TABLE recall_source_items DROP COLUMN IF EXISTS output_section;
        """
    )


def downgrade() -> None:
    """Recreate the dropped tables and columns, empty."""

    op.execute(
        """
        ALTER TABLE recall_source_items
          ADD COLUMN output_section TEXT
          CHECK (output_section IS NULL OR output_section IN ('summary', 'sources'));
        ALTER TABLE association_edges ADD COLUMN last_used_at TIMESTAMPTZ;
        ALTER TABLE episodes ADD COLUMN objective TEXT;
        ALTER TABLE episodes ADD COLUMN title TEXT;

        CREATE TABLE graph_patches (
          id TEXT PRIMARY KEY,
          repo_id TEXT NOT NULL,
          schema_version TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'pending',
          proposed_by TEXT NOT NULL DEFAULT 'manual',
          operations_json JSONB NOT NULL DEFAULT '[]'::jsonb,
          evidence_summary TEXT,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          applied_at TIMESTAMPTZ,
          CONSTRAINT ck_graph_patches_status CHECK (status IN ('pending', 'applied', 'rejected')),
          CONSTRAINT ck_graph_patches_proposed_by CHECK (proposed_by IN ('worker', 'librarian', 'manual', 'import'))
        );

        CREATE TABLE session_transfers (
          id TEXT PRIMARY KEY,
          repo_id TEXT NOT NULL,
          from_episode_id TEXT NOT NULL REFERENCES episodes(id) ON DELETE CASCADE,
          to_episode_id TEXT NOT NULL REFERENCES episodes(id) ON DELETE CASCADE,
          event_id TEXT NOT NULL REFERENCES episode_events(id) ON DELETE CASCADE,
          transfer_kind TEXT NOT NULL CHECK (transfer_kind IN ('message_handoff', 'context_summary', 'task_split', 'task_merge')),
          rationale TEXT,
          transferred_by TEXT,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          UNIQUE (from_episode_id, to_episode_id, event_id, transfer_kind),
          CONSTRAINT ck_session_transfers_distinct_episodes CHECK (from_episode_id <> to_episode_id)
        );
        CREATE INDEX idx_session_transfers_from ON session_transfers(from_episode_id, created_at);
        CREATE INDEX idx_session_transfers_to ON session_transfers(to_episode_id, created_at);
        CREATE INDEX idx_session_transfers_event ON session_transfers(event_id);
        """
    )
