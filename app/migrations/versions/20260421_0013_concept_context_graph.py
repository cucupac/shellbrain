"""Add typed concept-context graph substrate."""

from alembic import op

revision = "20260421_0013"
down_revision = "20260415_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create Phase 1 concept graph tables, constraints, and indexes."""

    op.execute(
        """
        CREATE TABLE concepts (
          id TEXT PRIMARY KEY,
          repo_id TEXT NOT NULL,
          slug TEXT NOT NULL,
          name TEXT NOT NULL,
          kind TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'active',
          scope_note TEXT,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          CONSTRAINT ck_concepts_kind CHECK (kind IN ('domain', 'capability', 'process', 'entity', 'rule', 'component')),
          CONSTRAINT ck_concepts_status CHECK (status IN ('active', 'deprecated', 'archived')),
          CONSTRAINT uq_concepts_repo_slug UNIQUE (repo_id, slug)
        );

        CREATE TABLE concept_aliases (
          concept_id TEXT NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
          normalized_alias TEXT NOT NULL,
          repo_id TEXT NOT NULL,
          alias TEXT NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (concept_id, normalized_alias),
          CONSTRAINT uq_concept_aliases_concept_alias UNIQUE (concept_id, normalized_alias)
        );

        CREATE TABLE concept_relations (
          id TEXT PRIMARY KEY,
          repo_id TEXT NOT NULL,
          subject_concept_id TEXT NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
          predicate TEXT NOT NULL,
          object_concept_id TEXT NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
          status TEXT NOT NULL DEFAULT 'active',
          confidence DOUBLE PRECISION NOT NULL DEFAULT 0.5,
          observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          validated_at TIMESTAMPTZ,
          source_kind TEXT,
          source_ref TEXT,
          superseded_by_id TEXT REFERENCES concept_relations(id) ON DELETE SET NULL,
          created_by TEXT NOT NULL DEFAULT 'manual',
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          CONSTRAINT ck_concept_relations_no_self_loop CHECK (subject_concept_id <> object_concept_id),
          CONSTRAINT ck_concept_relations_predicate CHECK (predicate IN ('contains', 'involves', 'precedes', 'constrains', 'depends_on')),
          CONSTRAINT ck_concept_relations_status CHECK (status IN ('active', 'maybe_stale', 'stale', 'superseded', 'wrong')),
          CONSTRAINT ck_concept_relations_confidence CHECK (confidence >= 0 AND confidence <= 1),
          CONSTRAINT ck_concept_relations_source_kind CHECK (source_kind IS NULL OR source_kind IN ('commit', 'file_hash', 'symbol_hash', 'memory', 'transcript_event', 'manual', 'doc', 'runtime_trace')),
          CONSTRAINT ck_concept_relations_created_by CHECK (created_by IN ('worker', 'librarian', 'manual', 'import'))
        );

        CREATE UNIQUE INDEX uq_concept_relations_active_natural
          ON concept_relations(repo_id, subject_concept_id, predicate, object_concept_id)
          WHERE status = 'active';
        CREATE INDEX idx_concept_relations_subject
          ON concept_relations(repo_id, subject_concept_id, status);
        CREATE INDEX idx_concept_relations_object
          ON concept_relations(repo_id, object_concept_id, status);

        CREATE TABLE concept_claims (
          id TEXT PRIMARY KEY,
          repo_id TEXT NOT NULL,
          concept_id TEXT NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
          claim_type TEXT NOT NULL,
          text TEXT NOT NULL,
          normalized_text TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'active',
          confidence DOUBLE PRECISION NOT NULL DEFAULT 0.5,
          observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          validated_at TIMESTAMPTZ,
          source_kind TEXT,
          source_ref TEXT,
          superseded_by_id TEXT REFERENCES concept_claims(id) ON DELETE SET NULL,
          created_by TEXT NOT NULL DEFAULT 'manual',
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          CONSTRAINT ck_concept_claims_claim_type CHECK (claim_type IN ('definition', 'behavior', 'invariant', 'failure_mode', 'usage_note', 'open_question')),
          CONSTRAINT ck_concept_claims_status CHECK (status IN ('active', 'maybe_stale', 'stale', 'superseded', 'wrong')),
          CONSTRAINT ck_concept_claims_confidence CHECK (confidence >= 0 AND confidence <= 1),
          CONSTRAINT ck_concept_claims_source_kind CHECK (source_kind IS NULL OR source_kind IN ('commit', 'file_hash', 'symbol_hash', 'memory', 'transcript_event', 'manual', 'doc', 'runtime_trace')),
          CONSTRAINT ck_concept_claims_created_by CHECK (created_by IN ('worker', 'librarian', 'manual', 'import')),
          CONSTRAINT uq_concept_claims_natural UNIQUE (repo_id, concept_id, claim_type, normalized_text)
        );
        CREATE INDEX idx_concept_claims_concept
          ON concept_claims(repo_id, concept_id, status);

        CREATE TABLE anchors (
          id TEXT PRIMARY KEY,
          repo_id TEXT NOT NULL,
          kind TEXT NOT NULL,
          locator_json JSONB NOT NULL DEFAULT '{}'::jsonb,
          canonical_locator_hash TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'active',
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          CONSTRAINT ck_anchors_kind CHECK (kind IN ('file', 'symbol', 'line_range', 'api_route', 'db_table', 'schema', 'config_key', 'test', 'metric', 'log', 'doc', 'commit', 'memory')),
          CONSTRAINT ck_anchors_status CHECK (status IN ('active', 'maybe_stale', 'stale', 'deprecated')),
          CONSTRAINT uq_anchors_repo_kind_locator_hash UNIQUE (repo_id, kind, canonical_locator_hash)
        );

        CREATE TABLE concept_groundings (
          id TEXT PRIMARY KEY,
          repo_id TEXT NOT NULL,
          concept_id TEXT NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
          role TEXT NOT NULL,
          anchor_id TEXT NOT NULL REFERENCES anchors(id) ON DELETE CASCADE,
          status TEXT NOT NULL DEFAULT 'active',
          confidence DOUBLE PRECISION NOT NULL DEFAULT 0.5,
          observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          validated_at TIMESTAMPTZ,
          source_kind TEXT,
          source_ref TEXT,
          superseded_by_id TEXT REFERENCES concept_groundings(id) ON DELETE SET NULL,
          created_by TEXT NOT NULL DEFAULT 'manual',
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          CONSTRAINT ck_concept_groundings_role CHECK (role IN ('implementation', 'entrypoint', 'storage', 'configuration', 'test', 'observability', 'documentation')),
          CONSTRAINT ck_concept_groundings_status CHECK (status IN ('active', 'maybe_stale', 'stale', 'superseded', 'wrong')),
          CONSTRAINT ck_concept_groundings_confidence CHECK (confidence >= 0 AND confidence <= 1),
          CONSTRAINT ck_concept_groundings_source_kind CHECK (source_kind IS NULL OR source_kind IN ('commit', 'file_hash', 'symbol_hash', 'memory', 'transcript_event', 'manual', 'doc', 'runtime_trace')),
          CONSTRAINT ck_concept_groundings_created_by CHECK (created_by IN ('worker', 'librarian', 'manual', 'import'))
        );
        CREATE UNIQUE INDEX uq_concept_groundings_active_natural
          ON concept_groundings(repo_id, concept_id, role, anchor_id)
          WHERE status = 'active';
        CREATE INDEX idx_concept_groundings_concept
          ON concept_groundings(repo_id, concept_id, status);

        CREATE TABLE concept_memory_links (
          id TEXT PRIMARY KEY,
          repo_id TEXT NOT NULL,
          concept_id TEXT NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
          role TEXT NOT NULL,
          memory_id TEXT NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
          status TEXT NOT NULL DEFAULT 'active',
          confidence DOUBLE PRECISION NOT NULL DEFAULT 0.5,
          observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          validated_at TIMESTAMPTZ,
          source_kind TEXT,
          source_ref TEXT,
          superseded_by_id TEXT REFERENCES concept_memory_links(id) ON DELETE SET NULL,
          created_by TEXT NOT NULL DEFAULT 'manual',
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          CONSTRAINT ck_concept_memory_links_role CHECK (role IN ('example_of', 'solution_for', 'failed_tactic_for', 'changed', 'validated', 'contradicted', 'warned_about')),
          CONSTRAINT ck_concept_memory_links_status CHECK (status IN ('active', 'maybe_stale', 'stale', 'superseded', 'wrong')),
          CONSTRAINT ck_concept_memory_links_confidence CHECK (confidence >= 0 AND confidence <= 1),
          CONSTRAINT ck_concept_memory_links_source_kind CHECK (source_kind IS NULL OR source_kind IN ('commit', 'file_hash', 'symbol_hash', 'memory', 'transcript_event', 'manual', 'doc', 'runtime_trace')),
          CONSTRAINT ck_concept_memory_links_created_by CHECK (created_by IN ('worker', 'librarian', 'manual', 'import'))
        );
        CREATE UNIQUE INDEX uq_concept_memory_links_active_natural
          ON concept_memory_links(repo_id, concept_id, role, memory_id)
          WHERE status = 'active';
        CREATE INDEX idx_concept_memory_links_memory
          ON concept_memory_links(repo_id, memory_id, status);

        CREATE TABLE concept_evidence (
          id TEXT PRIMARY KEY,
          repo_id TEXT NOT NULL,
          target_type TEXT NOT NULL,
          target_id TEXT NOT NULL,
          evidence_kind TEXT NOT NULL,
          anchor_id TEXT REFERENCES anchors(id) ON DELETE SET NULL,
          memory_id TEXT REFERENCES memories(id) ON DELETE SET NULL,
          commit_ref TEXT,
          transcript_ref TEXT,
          note TEXT,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          CONSTRAINT ck_concept_evidence_target_type CHECK (target_type IN ('relation', 'claim', 'grounding', 'memory_link')),
          CONSTRAINT ck_concept_evidence_kind CHECK (evidence_kind IN ('anchor', 'memory', 'commit', 'transcript', 'test', 'manual'))
        );
        CREATE INDEX idx_concept_evidence_target
          ON concept_evidence(repo_id, target_type, target_id);

        CREATE TABLE graph_patches (
          id TEXT PRIMARY KEY,
          repo_id TEXT NOT NULL,
          schema_version TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'pending',
          proposed_by TEXT NOT NULL DEFAULT 'manual',
          operations_json JSONB NOT NULL DEFAULT '[]'::jsonb,
          evidence_summary TEXT,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          applied_at TIMESTAMPTZ,
          CONSTRAINT ck_graph_patches_status CHECK (status IN ('pending', 'applied', 'rejected')),
          CONSTRAINT ck_graph_patches_proposed_by CHECK (proposed_by IN ('worker', 'librarian', 'manual', 'import'))
        );
        """
    )


def downgrade() -> None:
    """Drop Phase 1 concept graph tables."""

    op.execute(
        """
        DROP TABLE IF EXISTS graph_patches;
        DROP TABLE IF EXISTS concept_evidence;
        DROP TABLE IF EXISTS concept_memory_links;
        DROP TABLE IF EXISTS concept_groundings;
        DROP TABLE IF EXISTS anchors;
        DROP TABLE IF EXISTS concept_claims;
        DROP TABLE IF EXISTS concept_relations;
        DROP TABLE IF EXISTS concept_aliases;
        DROP TABLE IF EXISTS concepts;
        """
    )
