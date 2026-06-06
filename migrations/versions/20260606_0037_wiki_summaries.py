"""Add generated wiki summaries."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260606_0037"
down_revision = "20260526_0036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the generated wiki summary cache table."""

    op.create_table(
        "wiki_summaries",
        sa.Column("repo_id", sa.String(), primary_key=True),
        sa.Column("target_type", sa.String(), primary_key=True),
        sa.Column("target_id", sa.String(), primary_key=True),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("input_hash", sa.String(), nullable=True),
        sa.Column(
            "source_refs_json",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "generated_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=True,
        ),
        sa.Column("generation_status", sa.String(), nullable=False),
        sa.Column("model", sa.String(), nullable=True),
        sa.Column("prompt_version", sa.String(), nullable=True),
        sa.Column("last_error_code", sa.String(), nullable=True),
        sa.Column("last_error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.CheckConstraint(
            "target_type IN ('repo', 'concept')",
            name="ck_wiki_summaries_target_type",
        ),
        sa.CheckConstraint(
            "generation_status IN ('pending', 'ok', 'failed')",
            name="ck_wiki_summaries_generation_status",
        ),
        sa.CheckConstraint(
            "generation_status <> 'ok' OR body IS NOT NULL",
            name="ck_wiki_summaries_ok_body",
        ),
        sa.CheckConstraint(
            "generation_status <> 'ok' OR input_hash IS NOT NULL",
            name="ck_wiki_summaries_ok_input_hash",
        ),
    )
    op.create_index(
        "idx_wiki_summaries_repo_status_updated",
        "wiki_summaries",
        ["repo_id", "generation_status", "updated_at"],
    )


def downgrade() -> None:
    """Drop the generated wiki summary cache table."""

    op.drop_index(
        "idx_wiki_summaries_repo_status_updated",
        table_name="wiki_summaries",
    )
    op.drop_table("wiki_summaries")
