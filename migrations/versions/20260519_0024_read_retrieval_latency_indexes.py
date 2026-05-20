"""Add read-path retrieval latency indexes."""

from alembic import op


revision = "20260519_0024"
down_revision = "20260519_0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add covering filters used by read semantic and keyword candidate queries."""

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_memories_read_visibility
          ON memories(repo_id, archived, scope, kind, id);

        CREATE INDEX IF NOT EXISTS idx_memory_embeddings_model_dim_memory
          ON memory_embeddings(model, dim, memory_id);
        """
    )


def downgrade() -> None:
    """Remove read-path retrieval latency indexes."""

    op.execute(
        """
        DROP INDEX IF EXISTS idx_memory_embeddings_model_dim_memory;
        DROP INDEX IF EXISTS idx_memories_read_visibility;
        """
    )
