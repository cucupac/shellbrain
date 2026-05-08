"""Add concept-aware read telemetry columns."""

from alembic import op

revision = "20260422_0014"
down_revision = "20260421_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add forward-only concept read telemetry fields."""

    op.execute(
        """
        ALTER TABLE read_invocation_summaries
          ADD COLUMN concept_count INTEGER,
          ADD COLUMN concept_token_estimate INTEGER,
          ADD COLUMN concept_refs_returned JSONB,
          ADD COLUMN concept_facets_returned JSONB;
        """
    )


def downgrade() -> None:
    """Drop concept read telemetry fields."""

    op.execute(
        """
        ALTER TABLE read_invocation_summaries
          DROP COLUMN IF EXISTS concept_facets_returned,
          DROP COLUMN IF EXISTS concept_refs_returned,
          DROP COLUMN IF EXISTS concept_token_estimate,
          DROP COLUMN IF EXISTS concept_count;
        """
    )
