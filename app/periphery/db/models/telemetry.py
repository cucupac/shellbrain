"""SQLAlchemy Core tables for low-overhead usage telemetry storage."""

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    and_,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP

from app.periphery.db.models.metadata import metadata


operation_invocations = Table(
    "operation_invocations",
    metadata,
    Column("id", String, primary_key=True),
    Column("command", String, nullable=False),
    Column("repo_id", String, nullable=False),
    Column("repo_root", Text, nullable=False),
    Column("no_sync", Boolean, nullable=False, server_default=text("FALSE")),
    Column("caller_id", String),
    Column("caller_trust_level", String),
    Column("identity_failure_code", String),
    Column("selected_host_app", String),
    Column("selected_host_session_key", String),
    Column("selected_thread_id", String),
    Column("selected_episode_id", String),
    Column("matching_candidate_count", Integer, nullable=False, server_default=text("0")),
    Column("selection_ambiguous", Boolean, nullable=False, server_default=text("FALSE")),
    Column("outcome", String, nullable=False),
    Column("error_stage", String),
    Column("error_code", String),
    Column("error_message", Text),
    Column("total_latency_ms", Integer, nullable=False),
    Column("poller_start_attempted", Boolean, nullable=False, server_default=text("FALSE")),
    Column("poller_started", Boolean, nullable=False, server_default=text("FALSE")),
    Column("guidance_codes", JSONB, nullable=False, server_default=text("'[]'::jsonb")),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()")),
)

read_invocation_summaries = Table(
    "read_invocation_summaries",
    metadata,
    Column(
        "invocation_id",
        String,
        ForeignKey("operation_invocations.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("query_text", Text, nullable=False),
    Column("mode", String, nullable=False),
    Column("requested_limit", Integer),
    Column("effective_limit", Integer, nullable=False),
    Column("include_global", Boolean),
    Column("kinds_filter", JSONB),
    Column("direct_count", Integer, nullable=False),
    Column("explicit_related_count", Integer, nullable=False),
    Column("implicit_related_count", Integer, nullable=False),
    Column("total_returned", Integer, nullable=False),
    Column("zero_results", Boolean, nullable=False),
    Column("pack_char_count", Integer),
    Column("pack_token_estimate", Integer),
    Column("pack_token_estimate_method", String),
    Column("direct_token_estimate", Integer),
    Column("explicit_related_token_estimate", Integer),
    Column("implicit_related_token_estimate", Integer),
    Column("concept_count", Integer),
    Column("concept_token_estimate", Integer),
    Column("concept_refs_returned", JSONB),
    Column("concept_facets_returned", JSONB),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()")),
)

read_result_items = Table(
    "read_result_items",
    metadata,
    Column(
        "invocation_id",
        String,
        ForeignKey("operation_invocations.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("ordinal", Integer, primary_key=True),
    Column("memory_id", String, nullable=False),
    Column("kind", String, nullable=False),
    Column("section", String, nullable=False),
    Column("priority", Integer, nullable=False),
    Column("why_included", String, nullable=False),
    Column("anchor_memory_id", String),
    Column("relation_type", String),
)

recall_invocation_summaries = Table(
    "recall_invocation_summaries",
    metadata,
    Column(
        "invocation_id",
        String,
        ForeignKey("operation_invocations.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("query_text", Text, nullable=False),
    Column("candidate_token_estimate", Integer, nullable=False),
    Column("brief_token_estimate", Integer, nullable=False),
    Column("fallback_reason", String),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()")),
    CheckConstraint("candidate_token_estimate >= 0", name="ck_recall_candidate_token_estimate_nonnegative"),
    CheckConstraint("brief_token_estimate >= 0", name="ck_recall_brief_token_estimate_nonnegative"),
    CheckConstraint(
        "fallback_reason IS NULL OR fallback_reason = 'no_candidates'",
        name="ck_recall_fallback_reason",
    ),
)

recall_source_items = Table(
    "recall_source_items",
    metadata,
    Column(
        "invocation_id",
        String,
        ForeignKey("operation_invocations.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("ordinal", Integer, primary_key=True),
    Column("source_kind", String, nullable=False),
    Column("source_id", String, nullable=False),
    Column("input_section", String, nullable=False),
    Column("output_section", String),
    CheckConstraint("ordinal > 0", name="ck_recall_source_items_ordinal_positive"),
    CheckConstraint("source_kind IN ('memory', 'concept')", name="ck_recall_source_items_source_kind"),
    CheckConstraint(
        "input_section IN ('direct', 'explicit_related', 'implicit_related', 'concept_orientation')",
        name="ck_recall_source_items_input_section",
    ),
    CheckConstraint(
        "output_section IS NULL OR output_section IN ('summary', 'sources')",
        name="ck_recall_source_items_output_section",
    ),
)

write_invocation_summaries = Table(
    "write_invocation_summaries",
    metadata,
    Column(
        "invocation_id",
        String,
        ForeignKey("operation_invocations.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("operation_command", String, nullable=False),
    Column("target_memory_id", String, nullable=False),
    Column("target_kind", String),
    Column("update_type", String),
    Column("scope", String),
    Column("evidence_ref_count", Integer, nullable=False, server_default=text("0")),
    Column("planned_effect_count", Integer, nullable=False),
    Column("created_memory_count", Integer, nullable=False, server_default=text("0")),
    Column("archived_memory_count", Integer, nullable=False, server_default=text("0")),
    Column("utility_observation_count", Integer, nullable=False, server_default=text("0")),
    Column("association_effect_count", Integer, nullable=False, server_default=text("0")),
    Column("fact_update_count", Integer, nullable=False, server_default=text("0")),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()")),
)

write_effect_items = Table(
    "write_effect_items",
    metadata,
    Column(
        "invocation_id",
        String,
        ForeignKey("operation_invocations.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("ordinal", Integer, primary_key=True),
    Column("effect_type", String, nullable=False),
    Column("repo_id", String, nullable=False),
    Column("primary_memory_id", String),
    Column("secondary_memory_id", String),
    Column("params_json", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
)

episode_sync_runs = Table(
    "episode_sync_runs",
    metadata,
    Column("id", String, primary_key=True),
    Column("source", String, nullable=False),
    Column("invocation_id", String, ForeignKey("operation_invocations.id", ondelete="SET NULL")),
    Column("repo_id", String, nullable=False),
    Column("host_app", String, nullable=False),
    Column("host_session_key", String, nullable=False),
    Column("thread_id", String, nullable=False),
    Column("episode_id", String),
    Column("transcript_path", Text),
    Column("outcome", String, nullable=False),
    Column("error_stage", String),
    Column("error_message", Text),
    Column("duration_ms", Integer, nullable=False),
    Column("imported_event_count", Integer, nullable=False, server_default=text("0")),
    Column("total_event_count", Integer, nullable=False, server_default=text("0")),
    Column("user_event_count", Integer, nullable=False, server_default=text("0")),
    Column("assistant_event_count", Integer, nullable=False, server_default=text("0")),
    Column("tool_event_count", Integer, nullable=False, server_default=text("0")),
    Column("system_event_count", Integer, nullable=False, server_default=text("0")),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()")),
)

episode_sync_tool_types = Table(
    "episode_sync_tool_types",
    metadata,
    Column(
        "sync_run_id",
        String,
        ForeignKey("episode_sync_runs.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("tool_type", String, primary_key=True),
    Column("event_count", Integer, nullable=False),
)

model_usage = Table(
    "model_usage",
    metadata,
    Column("id", String, primary_key=True),
    Column("repo_id", String, nullable=False),
    Column("thread_id", String),
    Column("episode_id", String),
    Column("host_app", String, nullable=False),
    Column("host_session_key", String, nullable=False),
    Column("host_usage_key", String, nullable=False),
    Column("source_kind", String, nullable=False),
    Column("occurred_at", TIMESTAMP(timezone=True), nullable=False),
    Column("agent_role", String, nullable=False, server_default=text("'foreground'")),
    Column("provider", String),
    Column("model_id", String),
    Column("input_tokens", BigInteger),
    Column("output_tokens", BigInteger),
    Column("reasoning_output_tokens", BigInteger),
    Column("cached_input_tokens_total", BigInteger),
    Column("cache_read_input_tokens", BigInteger),
    Column("cache_creation_input_tokens", BigInteger),
    Column("capture_quality", String, nullable=False, server_default=text("'exact'")),
    Column("raw_usage_json", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()")),
    UniqueConstraint("host_app", "host_session_key", "host_usage_key", name="uq_model_usage_host_session_usage"),
)

Index("idx_operation_invocations_repo_created_at", operation_invocations.c.repo_id, operation_invocations.c.created_at)
Index("idx_operation_invocations_command_created_at", operation_invocations.c.command, operation_invocations.c.created_at)
Index(
    "idx_operation_invocations_thread_created_at",
    operation_invocations.c.selected_thread_id,
    operation_invocations.c.created_at,
    postgresql_where=operation_invocations.c.selected_thread_id.is_not(None),
)
Index(
    "idx_operation_invocations_successful_read_thread_created_at",
    operation_invocations.c.repo_id,
    operation_invocations.c.selected_thread_id,
    operation_invocations.c.created_at,
    postgresql_where=and_(
        operation_invocations.c.command == "read",
        operation_invocations.c.outcome == "ok",
        operation_invocations.c.selected_thread_id.is_not(None),
    ),
)
Index("idx_read_result_items_memory_invocation", read_result_items.c.memory_id, read_result_items.c.invocation_id)
Index(
    "idx_recall_source_items_source_invocation",
    recall_source_items.c.source_kind,
    recall_source_items.c.source_id,
    recall_source_items.c.invocation_id,
)
Index(
    "idx_write_effect_items_repo_effect_invocation",
    write_effect_items.c.repo_id,
    write_effect_items.c.effect_type,
    write_effect_items.c.invocation_id,
)
Index("idx_episode_sync_runs_repo_host_created_at", episode_sync_runs.c.repo_id, episode_sync_runs.c.host_app, episode_sync_runs.c.created_at)
Index("idx_episode_sync_runs_thread_created_at", episode_sync_runs.c.thread_id, episode_sync_runs.c.created_at)
Index("idx_model_usage_repo_thread_occurred_at", model_usage.c.repo_id, model_usage.c.thread_id, model_usage.c.occurred_at)
Index(
    "idx_model_usage_repo_host_session_occurred_at",
    model_usage.c.repo_id,
    model_usage.c.host_app,
    model_usage.c.host_session_key,
    model_usage.c.occurred_at,
)
