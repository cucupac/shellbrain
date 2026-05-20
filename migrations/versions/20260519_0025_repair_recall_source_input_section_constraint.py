"""Repair recall source input section constraint drift."""

from alembic import op


revision = "20260519_0025"
down_revision = "20260519_0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Allow provider-backed recall provenance rows from inner-agent read traces."""

    op.execute(
        """
        ALTER TABLE recall_source_items
          DROP CONSTRAINT IF EXISTS ck_recall_source_items_input_section;

        ALTER TABLE recall_source_items
          DROP CONSTRAINT IF EXISTS recall_source_items_input_section_check;

        ALTER TABLE recall_source_items
          ADD CONSTRAINT ck_recall_source_items_input_section
          CHECK (input_section IN (
            'direct',
            'explicit_related',
            'implicit_related',
            'concept_orientation',
            'inner_agent.read_trace'
          ));
        """
    )


def downgrade() -> None:
    """Keep the normalized 0022-era constraint when downgrading past the repair."""

    op.execute(
        """
        ALTER TABLE recall_source_items
          DROP CONSTRAINT IF EXISTS ck_recall_source_items_input_section;

        ALTER TABLE recall_source_items
          ADD CONSTRAINT ck_recall_source_items_input_section
          CHECK (input_section IN (
            'direct',
            'explicit_related',
            'implicit_related',
            'concept_orientation',
            'inner_agent.read_trace'
          ));
        """
    )
