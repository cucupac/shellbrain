"""Allow stable-watermark knowledge-builder runs."""

from alembic import op

revision = "20260519_0021"
down_revision = "20260516_0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Widen build_knowledge trigger values for stable watermark builds."""

    op.execute(
        """
        ALTER TABLE knowledge_build_runs
          DROP CONSTRAINT IF EXISTS ck_knowledge_build_runs_trigger;

        ALTER TABLE knowledge_build_runs
          ADD CONSTRAINT ck_knowledge_build_runs_trigger
          CHECK (trigger IN (
            'session_replaced',
            'idle_stable',
            'watermark_stable'
          ));
        """
    )


def downgrade() -> None:
    """Restore the pre-watermark trigger constraint."""

    op.execute(
        """
        ALTER TABLE knowledge_build_runs
          DROP CONSTRAINT IF EXISTS ck_knowledge_build_runs_trigger;

        ALTER TABLE knowledge_build_runs
          ADD CONSTRAINT ck_knowledge_build_runs_trigger
          CHECK (trigger IN ('session_replaced', 'idle_stable'));
        """
    )
