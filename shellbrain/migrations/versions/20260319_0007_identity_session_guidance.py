"""Extend telemetry storage with caller identity and guidance metadata."""

from alembic import op


revision = "20260319_0007"
down_revision = "20260318_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add identity and guidance columns to operation telemetry."""

    op.execute(
        """
        ALTER TABLE operation_invocations
          ADD COLUMN IF NOT EXISTS caller_id TEXT;

        ALTER TABLE operation_invocations
          ADD COLUMN IF NOT EXISTS caller_trust_level TEXT;

        ALTER TABLE operation_invocations
          ADD COLUMN IF NOT EXISTS identity_failure_code TEXT;

        ALTER TABLE operation_invocations
          ADD COLUMN IF NOT EXISTS guidance_codes JSONB NOT NULL DEFAULT '[]'::jsonb;
        """
    )


def downgrade() -> None:
    """Drop identity and guidance columns from operation telemetry."""

    op.execute(
        """
        ALTER TABLE operation_invocations
          DROP COLUMN IF EXISTS guidance_codes;

        ALTER TABLE operation_invocations
          DROP COLUMN IF EXISTS identity_failure_code;

        ALTER TABLE operation_invocations
          DROP COLUMN IF EXISTS caller_trust_level;

        ALTER TABLE operation_invocations
          DROP COLUMN IF EXISTS caller_id;
        """
    )
