"""Preserve evidence on utility and fact update writes."""

from alembic import op


revision = "20260519_0022"
down_revision = "20260519_0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add evidence link tables for update write records."""

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

        CREATE TABLE utility_observation_evidence (
          observation_id TEXT NOT NULL REFERENCES utility_observations(id) ON DELETE CASCADE,
          evidence_id TEXT NOT NULL REFERENCES evidence_refs(id) ON DELETE CASCADE,
          PRIMARY KEY (observation_id, evidence_id)
        );

        CREATE TABLE fact_update_evidence (
          fact_update_id TEXT NOT NULL REFERENCES fact_updates(id) ON DELETE CASCADE,
          evidence_id TEXT NOT NULL REFERENCES evidence_refs(id) ON DELETE CASCADE,
          PRIMARY KEY (fact_update_id, evidence_id)
        );
        """
    )


def downgrade() -> None:
    """Drop evidence link tables for update write records."""

    op.execute(
        """
        DROP TABLE IF EXISTS fact_update_evidence;
        DROP TABLE IF EXISTS utility_observation_evidence;

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
            'concept_orientation'
          ));
        """
    )
