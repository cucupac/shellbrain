"""Internal telemetry records used to persist low-overhead usage analytics."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class OperationInvocationRecord:
    """Append-only parent row for one operational command invocation."""

    id: str
    command: str
    repo_id: str
    repo_root: str
    no_sync: bool
    knowledge_build_run_id: str | None
    caller_id: str | None
    caller_trust_level: str | None
    identity_failure_code: str | None
    selected_host_app: str | None
    selected_host_session_key: str | None
    selected_thread_id: str | None
    selected_episode_id: str | None
    matching_candidate_count: int
    selection_ambiguous: bool
    outcome: str
    error_stage: str | None
    error_code: str | None
    error_message: str | None
    total_latency_ms: int
    poller_start_attempted: bool
    poller_started: bool
    created_at: datetime
    guidance_codes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ReadSummaryRecord:
    """One summary row describing a successful read invocation."""

    invocation_id: str
    query_text: str
    mode: str
    requested_limit: int | None
    effective_limit: int
    include_global: bool | None
    kinds_filter: list[str] | None
    direct_count: int
    explicit_related_count: int
    implicit_related_count: int
    total_returned: int
    zero_results: bool
    pack_char_count: int | None
    pack_token_estimate: int | None
    pack_token_estimate_method: str | None
    direct_token_estimate: int | None
    explicit_related_token_estimate: int | None
    implicit_related_token_estimate: int | None
    concept_count: int | None
    concept_token_estimate: int | None
    concept_refs_returned: list[str] | None
    concept_facets_returned: list[str] | None
    created_at: datetime


@dataclass(frozen=True)
class ReadResultItemRecord:
    """One displayed read result item in stable pack order."""

    invocation_id: str
    ordinal: int
    memory_id: str
    kind: str
    section: str
    priority: int
    why_included: str
    anchor_memory_id: str | None
    relation_type: str | None


@dataclass(frozen=True)
class RecallSummaryRecord:
    """One summary row describing a successful recall invocation."""

    invocation_id: str
    query_text: str
    candidate_token_estimate: int
    brief_token_estimate: int
    fallback_reason: str | None
    provider: str | None
    model: str | None
    reasoning: str | None
    private_read_count: int
    concept_expansion_count: int
    created_at: datetime


@dataclass(frozen=True)
class RecallSourceItemRecord:
    """One recall candidate source item in stable candidate order."""

    invocation_id: str
    ordinal: int
    source_kind: str
    source_id: str
    input_section: str
    output_section: str | None


@dataclass(frozen=True)
class InnerAgentInvocationRecord:
    """One provider-backed inner-agent run or fallback decision."""

    id: str
    operation_invocation_id: str
    agent_name: str
    provider: str | None
    model: str | None
    reasoning: str | None
    status: str
    fallback_used: bool
    timeout_seconds: int | None
    duration_ms: int
    input_tokens: int | None
    output_tokens: int | None
    reasoning_output_tokens: int | None
    cached_input_tokens_total: int | None
    cache_read_input_tokens: int | None
    cache_creation_input_tokens: int | None
    capture_quality: str | None
    private_read_count: int
    concept_expansion_count: int
    error_code: str | None
    error_message: str | None
    created_at: datetime


@dataclass(frozen=True)
class WriteSummaryRecord:
    """One summary row describing a successful create or update invocation."""

    invocation_id: str
    operation_command: str
    target_memory_id: str
    target_kind: str | None
    update_type: str | None
    scope: str | None
    evidence_ref_count: int
    planned_effect_count: int
    created_memory_count: int
    archived_memory_count: int
    utility_observation_count: int
    association_effect_count: int
    fact_update_count: int
    created_at: datetime


@dataclass(frozen=True)
class WriteEffectItemRecord:
    """One compact side-effect row attached to a write invocation."""

    invocation_id: str
    ordinal: int
    effect_type: str
    repo_id: str
    primary_memory_id: str | None
    secondary_memory_id: str | None
    params_json: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EpisodeSyncRunRecord:
    """One inline or poller sync attempt."""

    id: str
    source: str
    invocation_id: str | None
    repo_id: str
    host_app: str
    host_session_key: str
    thread_id: str
    episode_id: str | None
    transcript_path: str | None
    outcome: str
    error_stage: str | None
    error_message: str | None
    duration_ms: int
    imported_event_count: int
    total_event_count: int
    user_event_count: int
    assistant_event_count: int
    tool_event_count: int
    system_event_count: int
    created_at: datetime


@dataclass(frozen=True)
class EpisodeSyncToolTypeRecord:
    """Aggregated per-tool counts for one sync run."""

    sync_run_id: str
    tool_type: str
    event_count: int


@dataclass(frozen=True)
class ModelUsageRecord:
    """One normalized host model-usage event tied to a repo session."""

    id: str
    repo_id: str
    thread_id: str | None
    episode_id: str | None
    host_app: str
    host_session_key: str
    host_usage_key: str
    source_kind: str
    occurred_at: datetime
    agent_role: str
    provider: str | None
    model_id: str | None
    input_tokens: int | None
    output_tokens: int | None
    reasoning_output_tokens: int | None
    cached_input_tokens_total: int | None
    cache_read_input_tokens: int | None
    cache_creation_input_tokens: int | None
    capture_quality: str
    raw_usage_json: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None
