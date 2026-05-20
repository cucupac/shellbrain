"""Allow explicit teach knowledge runs."""

from alembic import op


revision = "20260519_0023"
down_revision = "20260519_0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Widen build_knowledge trigger values for immediate teach runs."""

    op.execute(
        """
        ALTER TABLE knowledge_build_runs
          DROP CONSTRAINT IF EXISTS ck_knowledge_build_runs_trigger;

        ALTER TABLE knowledge_build_runs
          ADD CONSTRAINT ck_knowledge_build_runs_trigger
          CHECK (trigger IN (
            'session_replaced',
            'idle_stable',
            'watermark_stable',
            'explicit_teach'
          ));
        """
    )


def downgrade() -> None:
    """Restore the pre-teach trigger constraint."""

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
