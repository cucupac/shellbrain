"""Drop create_confidence from memories after removing it from the write contract."""

from alembic import op

from app.periphery.db.models.views import CURRENT_FACT_SNAPSHOT_SQL


revision = "20260312_0003"
down_revision = "20260312_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Remove the obsolete create_confidence column from memories."""

    op.execute(
        """
        DROP VIEW IF EXISTS current_fact_snapshot;

        ALTER TABLE memories
        DROP COLUMN IF EXISTS create_confidence;
        """
    )
    op.execute(CURRENT_FACT_SNAPSHOT_SQL)


def downgrade() -> None:
    """Restore the removed create_confidence column for downgrade compatibility."""

    op.execute(
        """
        DROP VIEW IF EXISTS current_fact_snapshot;

        ALTER TABLE memories
        ADD COLUMN IF NOT EXISTS create_confidence DOUBLE PRECISION
        CHECK (create_confidence >= 0 AND create_confidence <= 1);
        """
    )
    op.execute(CURRENT_FACT_SNAPSHOT_SQL)
