"""Remove legacy knowledge-builder trigger constraint."""

from alembic import op


revision = "20260519_0026"
down_revision = "20260519_0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Keep one canonical trigger constraint with all supported values."""

    op.execute(
        """
        ALTER TABLE knowledge_build_runs
          DROP CONSTRAINT IF EXISTS knowledge_build_runs_trigger_check;

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
    """Restore the previous named trigger constraint."""

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
