"""Create instance metadata used for destructive guardrails and backup safety."""

from alembic import op


revision = "20260320_0008"
down_revision = "20260319_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the instance metadata table when missing."""

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS instance_metadata (
          instance_id TEXT PRIMARY KEY,
          instance_mode TEXT NOT NULL,
          created_at TIMESTAMPTZ NOT NULL,
          created_by TEXT NOT NULL,
          notes TEXT NULL
        );
        """
    )


def downgrade() -> None:
    """Drop the instance metadata table for downgrade compatibility."""

    op.execute("DROP TABLE IF EXISTS instance_metadata;")
