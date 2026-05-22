"""Add auditable concrete memory lifecycle state."""

from __future__ import annotations

from alembic import op


revision = "20260522_0032"
down_revision = "20260522_0031"
branch_labels = None
depends_on = None


_MEMORY_STATUSES = (
    "active",
    "maybe_stale",
    "stale",
    "superseded",
    "wrong",
    "archived",
)
_MEMORY_ACTORS = ("worker", "librarian", "manual", "import")
_TARGET_TYPES_WITH_MEMORY_LIFECYCLE = (
    "memory",
    "fact_update",
    "association_edge",
    "utility_observation",
    "concept_claim",
    "concept_relation",
    "concept_grounding",
    "concept_memory_link",
    "concept_lifecycle_event",
    "memory_lifecycle_event",
)
_TARGET_TYPES_PRE_MEMORY_LIFECYCLE = tuple(
    value
    for value in _TARGET_TYPES_WITH_MEMORY_LIFECYCLE
    if value != "memory_lifecycle_event"
)


def upgrade() -> None:
    """Promote concrete memory archival state into auditable lifecycle state."""

    op.execute(
        f"""
        ALTER TABLE memories
          ADD COLUMN IF NOT EXISTS status TEXT,
          ADD COLUMN IF NOT EXISTS validated_at TIMESTAMPTZ,
          ADD COLUMN IF NOT EXISTS invalidated_at TIMESTAMPTZ,
          ADD COLUMN IF NOT EXISTS superseded_by_id TEXT REFERENCES memories(id) ON DELETE SET NULL,
          ADD COLUMN IF NOT EXISTS updated_by TEXT;

        UPDATE memories
        SET status = CASE WHEN archived THEN 'archived' ELSE 'active' END
        WHERE status IS NULL;

        ALTER TABLE memories
          ALTER COLUMN status SET NOT NULL,
          DROP CONSTRAINT IF EXISTS ck_memories_status,
          DROP CONSTRAINT IF EXISTS ck_memories_updated_by;

        ALTER TABLE memories
          ADD CONSTRAINT ck_memories_status
            CHECK (status IN ({_quoted(_MEMORY_STATUSES)})),
          ADD CONSTRAINT ck_memories_updated_by
            CHECK (updated_by IS NULL OR updated_by IN ({_quoted(_MEMORY_ACTORS)}));

        CREATE TABLE IF NOT EXISTS memory_lifecycle_events (
          id TEXT PRIMARY KEY,
          repo_id TEXT NOT NULL,
          memory_id TEXT NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
          from_status TEXT NOT NULL,
          to_status TEXT NOT NULL,
          rationale TEXT NOT NULL,
          actor TEXT NOT NULL,
          superseded_by_id TEXT REFERENCES memories(id) ON DELETE SET NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          CONSTRAINT ck_memory_lifecycle_events_from_status
            CHECK (from_status IN ({_quoted(_MEMORY_STATUSES)})),
          CONSTRAINT ck_memory_lifecycle_events_to_status
            CHECK (to_status IN ({_quoted(_MEMORY_STATUSES)})),
          CONSTRAINT ck_memory_lifecycle_events_actor
            CHECK (actor IN ({_quoted(_MEMORY_ACTORS)})),
          CONSTRAINT ck_memory_lifecycle_events_rationale
            CHECK (length(btrim(rationale)) > 0)
        );

        CREATE INDEX IF NOT EXISTS idx_memory_lifecycle_events_memory
          ON memory_lifecycle_events(repo_id, memory_id, created_at);

        ALTER TABLE evidence_links
          DROP CONSTRAINT IF EXISTS ck_evidence_links_target_type;

        ALTER TABLE evidence_links
          ADD CONSTRAINT ck_evidence_links_target_type
          CHECK (target_type IN ({_quoted(_TARGET_TYPES_WITH_MEMORY_LIFECYCLE)}));

        DROP VIEW IF EXISTS current_fact_snapshot;

        DROP INDEX IF EXISTS idx_memories_read_visibility;
        CREATE INDEX IF NOT EXISTS idx_memories_read_visibility
          ON memories(repo_id, status, scope, kind, id);

        ALTER TABLE memories
          DROP COLUMN IF EXISTS archived;

        CREATE OR REPLACE VIEW current_fact_snapshot AS
        SELECT m.*
        FROM memories m
        WHERE m.kind = 'fact'
          AND m.status = 'active'
          AND NOT EXISTS (
            SELECT 1 FROM fact_updates fu WHERE fu.old_fact_id = m.id
          );
        """
    )


def downgrade() -> None:
    """Return to the pre-lifecycle memory archive flag shape."""

    op.execute(
        f"""
        DELETE FROM evidence_links
        WHERE target_type = 'memory_lifecycle_event';

        ALTER TABLE evidence_links
          DROP CONSTRAINT IF EXISTS ck_evidence_links_target_type;

        ALTER TABLE evidence_links
          ADD CONSTRAINT ck_evidence_links_target_type
          CHECK (target_type IN ({_quoted(_TARGET_TYPES_PRE_MEMORY_LIFECYCLE)}));

        ALTER TABLE memories
          ADD COLUMN IF NOT EXISTS archived BOOLEAN NOT NULL DEFAULT FALSE;

        UPDATE memories
        SET archived = status IN ('superseded', 'wrong', 'archived');

        DROP VIEW IF EXISTS current_fact_snapshot;

        DROP INDEX IF EXISTS idx_memories_read_visibility;
        CREATE INDEX IF NOT EXISTS idx_memories_read_visibility
          ON memories(repo_id, archived, scope, kind, id);

        DROP TABLE IF EXISTS memory_lifecycle_events;

        ALTER TABLE memories
          DROP CONSTRAINT IF EXISTS ck_memories_status,
          DROP CONSTRAINT IF EXISTS ck_memories_updated_by,
          DROP COLUMN IF EXISTS status,
          DROP COLUMN IF EXISTS validated_at,
          DROP COLUMN IF EXISTS invalidated_at,
          DROP COLUMN IF EXISTS superseded_by_id,
          DROP COLUMN IF EXISTS updated_by;

        CREATE OR REPLACE VIEW current_fact_snapshot AS
        SELECT m.*
        FROM memories m
        WHERE m.kind = 'fact'
          AND m.archived = FALSE
          AND NOT EXISTS (
            SELECT 1 FROM fact_updates fu WHERE fu.old_fact_id = m.id
          );
        """
    )


def _quoted(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)
