"""SQLAlchemy Core tables for the typed concept-context graph substrate."""

from sqlalchemy import CheckConstraint, Column, Float, ForeignKey, Index, String, Table, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP

from app.infrastructure.db.models.metadata import metadata


_CONCEPT_KINDS = "'domain', 'capability', 'process', 'entity', 'rule', 'component'"
_CONCEPT_STATUSES = "'active', 'deprecated', 'archived'"
_LIFECYCLE_STATUSES = "'active', 'maybe_stale', 'stale', 'superseded', 'wrong'"
_RELATION_PREDICATES = "'contains', 'involves', 'precedes', 'constrains', 'depends_on'"
_CLAIM_TYPES = "'definition', 'behavior', 'invariant', 'failure_mode', 'usage_note', 'open_question'"
_ANCHOR_KINDS = (
    "'file', 'symbol', 'line_range', 'api_route', 'db_table', 'schema', 'config_key', "
    "'test', 'metric', 'log', 'doc', 'commit', 'memory'"
)
_ANCHOR_STATUSES = "'active', 'maybe_stale', 'stale', 'deprecated'"
_GROUNDING_ROLES = (
    "'implementation', 'entrypoint', 'storage', 'configuration', 'test', "
    "'observability', 'documentation'"
)
_MEMORY_LINK_ROLES = (
    "'example_of', 'solution_for', 'failed_tactic_for', 'changed', 'validated', "
    "'contradicted', 'warned_about'"
)
_SOURCE_KINDS = "'commit', 'file_hash', 'symbol_hash', 'memory', 'transcript_event', 'manual', 'doc', 'runtime_trace'"
_CREATED_BY_VALUES = "'worker', 'librarian', 'manual', 'import'"
_EVIDENCE_TARGET_TYPES = "'relation', 'claim', 'grounding', 'memory_link'"
_EVIDENCE_KINDS = "'anchor', 'memory', 'commit', 'transcript', 'test', 'manual'"
_PATCH_STATUSES = "'pending', 'applied', 'rejected'"


concepts = Table(
    "concepts",
    metadata,
    Column("id", String, primary_key=True),
    Column("repo_id", String, nullable=False),
    Column("slug", String, nullable=False),
    Column("name", Text, nullable=False),
    Column("kind", String, nullable=False),
    Column("status", String, nullable=False, server_default=text("'active'")),
    Column("scope_note", Text),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()")),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()")),
    CheckConstraint(f"kind IN ({_CONCEPT_KINDS})", name="ck_concepts_kind"),
    CheckConstraint(f"status IN ({_CONCEPT_STATUSES})", name="ck_concepts_status"),
    UniqueConstraint("repo_id", "slug", name="uq_concepts_repo_slug"),
)

concept_aliases = Table(
    "concept_aliases",
    metadata,
    Column("concept_id", String, ForeignKey("concepts.id", ondelete="CASCADE"), primary_key=True),
    Column("normalized_alias", String, primary_key=True),
    Column("repo_id", String, nullable=False),
    Column("alias", Text, nullable=False),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()")),
    UniqueConstraint("concept_id", "normalized_alias", name="uq_concept_aliases_concept_alias"),
)

concept_relations = Table(
    "concept_relations",
    metadata,
    Column("id", String, primary_key=True),
    Column("repo_id", String, nullable=False),
    Column("subject_concept_id", String, ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False),
    Column("predicate", String, nullable=False),
    Column("object_concept_id", String, ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False),
    Column("status", String, nullable=False, server_default=text("'active'")),
    Column("confidence", Float, nullable=False, server_default=text("0.5")),
    Column("observed_at", TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()")),
    Column("validated_at", TIMESTAMP(timezone=True)),
    Column("source_kind", String),
    Column("source_ref", Text),
    Column("superseded_by_id", String, ForeignKey("concept_relations.id", ondelete="SET NULL")),
    Column("created_by", String, nullable=False, server_default=text("'manual'")),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()")),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()")),
    CheckConstraint("subject_concept_id <> object_concept_id", name="ck_concept_relations_no_self_loop"),
    CheckConstraint(f"predicate IN ({_RELATION_PREDICATES})", name="ck_concept_relations_predicate"),
    CheckConstraint(f"status IN ({_LIFECYCLE_STATUSES})", name="ck_concept_relations_status"),
    CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_concept_relations_confidence"),
    CheckConstraint(f"source_kind IS NULL OR source_kind IN ({_SOURCE_KINDS})", name="ck_concept_relations_source_kind"),
    CheckConstraint(f"created_by IN ({_CREATED_BY_VALUES})", name="ck_concept_relations_created_by"),
)

concept_claims = Table(
    "concept_claims",
    metadata,
    Column("id", String, primary_key=True),
    Column("repo_id", String, nullable=False),
    Column("concept_id", String, ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False),
    Column("claim_type", String, nullable=False),
    Column("text", Text, nullable=False),
    Column("normalized_text", Text, nullable=False),
    Column("status", String, nullable=False, server_default=text("'active'")),
    Column("confidence", Float, nullable=False, server_default=text("0.5")),
    Column("observed_at", TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()")),
    Column("validated_at", TIMESTAMP(timezone=True)),
    Column("source_kind", String),
    Column("source_ref", Text),
    Column("superseded_by_id", String, ForeignKey("concept_claims.id", ondelete="SET NULL")),
    Column("created_by", String, nullable=False, server_default=text("'manual'")),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()")),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()")),
    CheckConstraint(f"claim_type IN ({_CLAIM_TYPES})", name="ck_concept_claims_claim_type"),
    CheckConstraint(f"status IN ({_LIFECYCLE_STATUSES})", name="ck_concept_claims_status"),
    CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_concept_claims_confidence"),
    CheckConstraint(f"source_kind IS NULL OR source_kind IN ({_SOURCE_KINDS})", name="ck_concept_claims_source_kind"),
    CheckConstraint(f"created_by IN ({_CREATED_BY_VALUES})", name="ck_concept_claims_created_by"),
    UniqueConstraint("repo_id", "concept_id", "claim_type", "normalized_text", name="uq_concept_claims_natural"),
)

anchors = Table(
    "anchors",
    metadata,
    Column("id", String, primary_key=True),
    Column("repo_id", String, nullable=False),
    Column("kind", String, nullable=False),
    Column("locator_json", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("canonical_locator_hash", String, nullable=False),
    Column("status", String, nullable=False, server_default=text("'active'")),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()")),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()")),
    CheckConstraint(f"kind IN ({_ANCHOR_KINDS})", name="ck_anchors_kind"),
    CheckConstraint(f"status IN ({_ANCHOR_STATUSES})", name="ck_anchors_status"),
    UniqueConstraint("repo_id", "kind", "canonical_locator_hash", name="uq_anchors_repo_kind_locator_hash"),
)

concept_groundings = Table(
    "concept_groundings",
    metadata,
    Column("id", String, primary_key=True),
    Column("repo_id", String, nullable=False),
    Column("concept_id", String, ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False),
    Column("role", String, nullable=False),
    Column("anchor_id", String, ForeignKey("anchors.id", ondelete="CASCADE"), nullable=False),
    Column("status", String, nullable=False, server_default=text("'active'")),
    Column("confidence", Float, nullable=False, server_default=text("0.5")),
    Column("observed_at", TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()")),
    Column("validated_at", TIMESTAMP(timezone=True)),
    Column("source_kind", String),
    Column("source_ref", Text),
    Column("superseded_by_id", String, ForeignKey("concept_groundings.id", ondelete="SET NULL")),
    Column("created_by", String, nullable=False, server_default=text("'manual'")),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()")),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()")),
    CheckConstraint(f"role IN ({_GROUNDING_ROLES})", name="ck_concept_groundings_role"),
    CheckConstraint(f"status IN ({_LIFECYCLE_STATUSES})", name="ck_concept_groundings_status"),
    CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_concept_groundings_confidence"),
    CheckConstraint(f"source_kind IS NULL OR source_kind IN ({_SOURCE_KINDS})", name="ck_concept_groundings_source_kind"),
    CheckConstraint(f"created_by IN ({_CREATED_BY_VALUES})", name="ck_concept_groundings_created_by"),
)

concept_memory_links = Table(
    "concept_memory_links",
    metadata,
    Column("id", String, primary_key=True),
    Column("repo_id", String, nullable=False),
    Column("concept_id", String, ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False),
    Column("role", String, nullable=False),
    Column("memory_id", String, ForeignKey("memories.id", ondelete="CASCADE"), nullable=False),
    Column("status", String, nullable=False, server_default=text("'active'")),
    Column("confidence", Float, nullable=False, server_default=text("0.5")),
    Column("observed_at", TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()")),
    Column("validated_at", TIMESTAMP(timezone=True)),
    Column("source_kind", String),
    Column("source_ref", Text),
    Column("superseded_by_id", String, ForeignKey("concept_memory_links.id", ondelete="SET NULL")),
    Column("created_by", String, nullable=False, server_default=text("'manual'")),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()")),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()")),
    CheckConstraint(f"role IN ({_MEMORY_LINK_ROLES})", name="ck_concept_memory_links_role"),
    CheckConstraint(f"status IN ({_LIFECYCLE_STATUSES})", name="ck_concept_memory_links_status"),
    CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_concept_memory_links_confidence"),
    CheckConstraint(f"source_kind IS NULL OR source_kind IN ({_SOURCE_KINDS})", name="ck_concept_memory_links_source_kind"),
    CheckConstraint(f"created_by IN ({_CREATED_BY_VALUES})", name="ck_concept_memory_links_created_by"),
)

concept_evidence = Table(
    "concept_evidence",
    metadata,
    Column("id", String, primary_key=True),
    Column("repo_id", String, nullable=False),
    Column("target_type", String, nullable=False),
    Column("target_id", String, nullable=False),
    Column("evidence_kind", String, nullable=False),
    Column("anchor_id", String, ForeignKey("anchors.id", ondelete="SET NULL")),
    Column("memory_id", String, ForeignKey("memories.id", ondelete="SET NULL")),
    Column("commit_ref", Text),
    Column("transcript_ref", Text),
    Column("note", Text),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()")),
    CheckConstraint(f"target_type IN ({_EVIDENCE_TARGET_TYPES})", name="ck_concept_evidence_target_type"),
    CheckConstraint(f"evidence_kind IN ({_EVIDENCE_KINDS})", name="ck_concept_evidence_kind"),
)

graph_patches = Table(
    "graph_patches",
    metadata,
    Column("id", String, primary_key=True),
    Column("repo_id", String, nullable=False),
    Column("schema_version", String, nullable=False),
    Column("status", String, nullable=False, server_default=text("'pending'")),
    Column("proposed_by", String, nullable=False, server_default=text("'manual'")),
    Column("operations_json", JSONB, nullable=False, server_default=text("'[]'::jsonb")),
    Column("evidence_summary", Text),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()")),
    Column("applied_at", TIMESTAMP(timezone=True)),
    CheckConstraint(f"status IN ({_PATCH_STATUSES})", name="ck_graph_patches_status"),
    CheckConstraint(f"proposed_by IN ({_CREATED_BY_VALUES})", name="ck_graph_patches_proposed_by"),
)

Index(
    "uq_concept_relations_active_natural",
    concept_relations.c.repo_id,
    concept_relations.c.subject_concept_id,
    concept_relations.c.predicate,
    concept_relations.c.object_concept_id,
    unique=True,
    postgresql_where=concept_relations.c.status == "active",
)
Index(
    "uq_concept_groundings_active_natural",
    concept_groundings.c.repo_id,
    concept_groundings.c.concept_id,
    concept_groundings.c.role,
    concept_groundings.c.anchor_id,
    unique=True,
    postgresql_where=concept_groundings.c.status == "active",
)
Index(
    "uq_concept_memory_links_active_natural",
    concept_memory_links.c.repo_id,
    concept_memory_links.c.concept_id,
    concept_memory_links.c.role,
    concept_memory_links.c.memory_id,
    unique=True,
    postgresql_where=concept_memory_links.c.status == "active",
)
Index("idx_concept_relations_subject", concept_relations.c.repo_id, concept_relations.c.subject_concept_id, concept_relations.c.status)
Index("idx_concept_relations_object", concept_relations.c.repo_id, concept_relations.c.object_concept_id, concept_relations.c.status)
Index("idx_concept_claims_concept", concept_claims.c.repo_id, concept_claims.c.concept_id, concept_claims.c.status)
Index("idx_concept_groundings_concept", concept_groundings.c.repo_id, concept_groundings.c.concept_id, concept_groundings.c.status)
Index("idx_concept_memory_links_memory", concept_memory_links.c.repo_id, concept_memory_links.c.memory_id, concept_memory_links.c.status)
Index("idx_concept_evidence_target", concept_evidence.c.repo_id, concept_evidence.c.target_type, concept_evidence.c.target_id)
