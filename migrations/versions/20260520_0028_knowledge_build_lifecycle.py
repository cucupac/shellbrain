"""Add lifecycle activation state for forward-only knowledge building."""

from alembic import op


revision = "20260520_0028"
down_revision = "20260519_0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create per-repo lifecycle activation state."""

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS knowledge_build_lifecycle (
          repo_id TEXT PRIMARY KEY,
          activated_at TIMESTAMPTZ NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """
    )


def downgrade() -> None:
    """Drop per-repo lifecycle activation state."""

    op.execute("DROP TABLE IF EXISTS knowledge_build_lifecycle;")
