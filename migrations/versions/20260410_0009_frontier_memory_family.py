"""Add frontier memory kind and matures_into association relation constraints."""

from alembic import op


revision = "20260410_0009"
down_revision = "20260320_0008"
branch_labels = None
depends_on = None


def _drop_check_constraint(table_name: str, required_snippets: list[str]) -> None:
    """Drop one unnamed CHECK constraint by matching its rendered definition."""

    like_clauses = " AND ".join(
        f"pg_get_constraintdef(con.oid) LIKE '%{snippet}%'" for snippet in required_snippets
    )
    op.execute(
        f"""
        DO $$
        DECLARE constraint_name TEXT;
        BEGIN
          SELECT con.conname
          INTO constraint_name
          FROM pg_constraint con
          JOIN pg_class rel ON rel.oid = con.conrelid
          JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
          WHERE nsp.nspname = current_schema()
            AND rel.relname = '{table_name}'
            AND con.contype = 'c'
            AND {like_clauses}
          LIMIT 1;

          IF constraint_name IS NOT NULL THEN
            EXECUTE format('ALTER TABLE {table_name} DROP CONSTRAINT %I', constraint_name);
          END IF;
        END $$;
        """
    )


def upgrade() -> None:
    """Widen durable-memory and association relation constraints for frontier support."""

    _drop_check_constraint("memories", ["kind", "problem", "change"])
    _drop_check_constraint("association_edges", ["relation_type", "depends_on", "associated_with"])
    _drop_check_constraint("association_observations", ["relation_type", "depends_on", "associated_with"])

    op.execute(
        """
        ALTER TABLE memories
        ADD CONSTRAINT ck_memories_kind_ratified
        CHECK (kind IN ('problem', 'solution', 'failed_tactic', 'fact', 'preference', 'change', 'frontier'));

        ALTER TABLE association_edges
        ADD CONSTRAINT ck_association_edges_relation_type
        CHECK (relation_type IN ('depends_on', 'associated_with', 'matures_into'));

        ALTER TABLE association_observations
        ADD CONSTRAINT ck_association_observations_relation_type
        CHECK (relation_type IN ('depends_on', 'associated_with', 'matures_into'));
        """
    )


def downgrade() -> None:
    """Restore the prior durable-memory and association relation constraint set."""

    op.execute(
        """
        ALTER TABLE association_observations
        DROP CONSTRAINT IF EXISTS ck_association_observations_relation_type;

        ALTER TABLE association_edges
        DROP CONSTRAINT IF EXISTS ck_association_edges_relation_type;

        ALTER TABLE memories
        DROP CONSTRAINT IF EXISTS ck_memories_kind_ratified;
        """
    )

    op.execute(
        """
        ALTER TABLE memories
        ADD CONSTRAINT ck_memories_kind_ratified
        CHECK (kind IN ('problem', 'solution', 'failed_tactic', 'fact', 'preference', 'change'));

        ALTER TABLE association_edges
        ADD CONSTRAINT ck_association_edges_relation_type
        CHECK (relation_type IN ('depends_on', 'associated_with'));

        ALTER TABLE association_observations
        ADD CONSTRAINT ck_association_observations_relation_type
        CHECK (relation_type IN ('depends_on', 'associated_with'));
        """
    )
