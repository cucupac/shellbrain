"""Add hard schema invariants for episodes, problem attempts, and fact updates."""

from alembic import op


revision = "20260312_0002"
down_revision = "20260226_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply additional DB-level constraints that encode obvious write invariants."""

    op.execute(
        """
        ALTER TABLE episodes
        ADD CONSTRAINT ck_episodes_ended_after_started
        CHECK (ended_at IS NULL OR ended_at >= started_at);

        ALTER TABLE session_transfers
        ADD CONSTRAINT ck_session_transfers_distinct_episodes
        CHECK (from_episode_id <> to_episode_id);

        ALTER TABLE problem_attempts
        ADD CONSTRAINT ck_problem_attempts_distinct_memories
        CHECK (problem_id <> attempt_id);

        ALTER TABLE fact_updates
        ADD CONSTRAINT ck_fact_updates_distinct_fact_endpoints
        CHECK (old_fact_id <> new_fact_id);

        ALTER TABLE fact_updates
        ADD CONSTRAINT ck_fact_updates_change_id_distinct
        CHECK (change_id <> old_fact_id AND change_id <> new_fact_id);
        """
    )


def downgrade() -> None:
    """Remove the added DB-level invariant constraints."""

    op.execute(
        """
        ALTER TABLE fact_updates
        DROP CONSTRAINT IF EXISTS ck_fact_updates_change_id_distinct;

        ALTER TABLE fact_updates
        DROP CONSTRAINT IF EXISTS ck_fact_updates_distinct_fact_endpoints;

        ALTER TABLE problem_attempts
        DROP CONSTRAINT IF EXISTS ck_problem_attempts_distinct_memories;

        ALTER TABLE session_transfers
        DROP CONSTRAINT IF EXISTS ck_session_transfers_distinct_episodes;

        ALTER TABLE episodes
        DROP CONSTRAINT IF EXISTS ck_episodes_ended_after_started;
        """
    )
