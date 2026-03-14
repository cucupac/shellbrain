"""Attach evidence references directly to stored episode events."""

from alembic import op


revision = "20260313_0005"
down_revision = "20260313_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add episode_event-backed evidence references while preserving legacy ref strings."""

    op.execute(
        """
        ALTER TABLE evidence_refs
        ADD COLUMN episode_event_id TEXT REFERENCES episode_events(id);

        UPDATE evidence_refs AS er
        SET episode_event_id = er.ref
        FROM episode_events AS ee
        JOIN episodes AS ep ON ep.id = ee.episode_id
        WHERE er.episode_event_id IS NULL
          AND er.ref = ee.id
          AND er.repo_id = ep.repo_id;

        ALTER TABLE evidence_refs
        ADD CONSTRAINT uq_evidence_repo_episode_event UNIQUE (repo_id, episode_event_id);
        """
    )


def downgrade() -> None:
    """Remove episode-event-backed evidence reference storage."""

    op.execute(
        """
        ALTER TABLE evidence_refs
        DROP CONSTRAINT IF EXISTS uq_evidence_repo_episode_event;

        ALTER TABLE evidence_refs
        DROP COLUMN IF EXISTS episode_event_id;
        """
    )
