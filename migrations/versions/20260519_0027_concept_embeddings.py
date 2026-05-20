"""Add aggregate concept embeddings for concept retrieval."""

from alembic import op


revision = "20260519_0027"
down_revision = "20260519_0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create one-current-embedding rows for active concept retrieval."""

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS concept_embeddings (
          concept_id TEXT PRIMARY KEY REFERENCES concepts(id) ON DELETE CASCADE,
          repo_id TEXT NOT NULL,
          model TEXT NOT NULL,
          dim INTEGER NOT NULL CHECK (dim > 0),
          vector VECTOR NOT NULL,
          source_hash TEXT NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE INDEX IF NOT EXISTS idx_concept_embeddings_repo_model_dim_concept
          ON concept_embeddings(repo_id, model, dim, concept_id);
        """
    )


def downgrade() -> None:
    """Remove aggregate concept embeddings."""

    op.execute(
        """
        DROP INDEX IF EXISTS idx_concept_embeddings_repo_model_dim_concept;
        DROP TABLE IF EXISTS concept_embeddings;
        """
    )
