"""Allow recall telemetry to record explicit synthesis failures."""

from alembic import op

revision = "20260922_0040"
down_revision = "20260901_0039"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Preserve recall telemetry when synthesis falls back to retrieved memories."""
    op.execute("""
        ALTER TABLE recall_invocation_summaries
          DROP CONSTRAINT recall_invocation_summaries_fallback_reason_check;
        ALTER TABLE recall_invocation_summaries
          ADD CONSTRAINT ck_recall_fallback_reason CHECK (
            fallback_reason IS NULL OR fallback_reason IN (
              'no_candidates', 'no_context', 'provider_unavailable',
              'timeout', 'invalid_output', 'error'
            )
          );
    """)


def downgrade() -> None:
    """Refuse to discard failure reasons recorded by the newer schema."""
    op.execute("""
        ALTER TABLE recall_invocation_summaries DROP CONSTRAINT ck_recall_fallback_reason;
        ALTER TABLE recall_invocation_summaries
          ADD CONSTRAINT recall_invocation_summaries_fallback_reason_check
          CHECK (fallback_reason IS NULL OR fallback_reason = 'no_candidates');
    """)
