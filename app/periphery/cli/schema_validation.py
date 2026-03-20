"""CLI schema-validation helpers for strict request contracts."""

from typing import Any, Literal

from pydantic import Field, ValidationError, field_validator

from app.core.contracts.errors import ErrorCode, ErrorDetail
from app.core.contracts.requests import (
    BatchUtilityVoteItem,
    EpisodeEventsRequest,
    MemoryBatchUpdateRequest,
    MemoryCreateLinks,
    MemoryCreateRequest,
    MemoryReadRequest,
    MemoryUpdateRequest,
    StrictBaseModel,
    UpdatePayload,
    UtilityVoteUpdate,
)


class AgentReadRequest(StrictBaseModel):
    """Agent-facing read payload with config-only retrieval knobs removed."""

    op: Literal["read"] = "read"
    repo_id: str | None = None
    mode: Literal["ambient", "targeted"] | None = None
    query: str = Field(min_length=1)
    include_global: bool | None = None
    kinds: (
        list[Literal["problem", "solution", "failed_tactic", "fact", "preference", "change"]] | None
    ) = None
    limit: int | None = Field(default=None, ge=1, le=100)

    @field_validator("kinds")
    @classmethod
    def _validate_kinds_unique(
        cls,
        value: list[Literal["problem", "solution", "failed_tactic", "fact", "preference", "change"]] | None,
    ) -> list[Literal["problem", "solution", "failed_tactic", "fact", "preference", "change"]] | None:
        """This validator enforces unique kinds filters for agent read requests."""

        if value is None:
            return value
        if len(value) != len(set(value)):
            raise ValueError("kinds must be unique")
        return value


class AgentCreateBody(StrictBaseModel):
    """Agent-facing create payload with transport fields removed."""

    text: str
    scope: Literal["repo", "global"] | None = None
    kind: Literal["problem", "solution", "failed_tactic", "fact", "preference", "change"]
    rationale: str | None = None
    links: MemoryCreateLinks = Field(default_factory=MemoryCreateLinks)
    evidence_refs: list[str] = Field(min_length=1)

    @field_validator("evidence_refs")
    @classmethod
    def _validate_evidence_unique(cls, value: list[str]) -> list[str]:
        """This validator enforces unique evidence references for agent create requests."""

        if len(value) != len(set(value)):
            raise ValueError("evidence_refs must be unique")
        return value


class AgentCreateRequest(StrictBaseModel):
    """Agent-facing create payload with repo/op transport details removed."""

    memory: AgentCreateBody


class AgentEventsRequest(StrictBaseModel):
    """Agent-facing events payload with transport fields removed."""

    limit: int | None = Field(default=None, ge=1, le=100)


class AgentUpdateRequest(StrictBaseModel):
    """Agent-facing update payload with repo/op transport details removed."""

    memory_id: str
    update: UpdatePayload


class AgentBatchUpdateItem(StrictBaseModel):
    """Agent-facing batch utility item with transport fields removed."""

    memory_id: str
    update: UtilityVoteUpdate


class AgentBatchUpdateRequest(StrictBaseModel):
    """Agent-facing batch utility update payload."""

    updates: list[AgentBatchUpdateItem] = Field(min_length=1)


def _format_validation_errors(exc: ValidationError) -> list[ErrorDetail]:
    """Convert Pydantic validation errors into contract error details."""

    details: list[ErrorDetail] = []
    for item in exc.errors():
        path = ".".join(str(segment) for segment in item.get("loc", ()))
        message = item.get("msg", "Schema validation failed")
        if path in {"memory.evidence_refs", "update.evidence_refs"} and item.get("type") in {
            "too_short",
            "missing",
        }:
            message = "evidence_refs must include at least one stored episode event id; query events first"
        details.append(
            ErrorDetail(
                code=ErrorCode.SCHEMA_ERROR,
                message=message,
                field=path or None,
            )
        )
    return details


def validate_create_schema(payload: dict[str, Any]) -> tuple[AgentCreateRequest | None, list[ErrorDetail]]:
    """Validate and parse agent create payloads into the simplified create contract."""

    try:
        return AgentCreateRequest.model_validate(payload), []
    except ValidationError as exc:
        return None, _format_validation_errors(exc)


def validate_read_schema(payload: dict[str, Any]) -> tuple[AgentReadRequest | None, list[ErrorDetail]]:
    """Validate and parse agent read payloads into the simplified read contract."""

    try:
        return AgentReadRequest.model_validate(payload), []
    except ValidationError as exc:
        return None, _format_validation_errors(exc)


def validate_events_schema(payload: dict[str, Any]) -> tuple[AgentEventsRequest | None, list[ErrorDetail]]:
    """Validate and parse agent events payloads into the simplified events contract."""

    try:
        return AgentEventsRequest.model_validate(payload), []
    except ValidationError as exc:
        return None, _format_validation_errors(exc)


def validate_internal_read_contract(payload: dict[str, Any]) -> tuple[MemoryReadRequest | None, list[ErrorDetail]]:
    """Validate one hydrated read payload against the full internal read contract."""

    try:
        return MemoryReadRequest.model_validate(payload), []
    except ValidationError as exc:
        return None, _format_validation_errors(exc)


def validate_internal_events_contract(
    payload: dict[str, Any],
) -> tuple[EpisodeEventsRequest | None, list[ErrorDetail]]:
    """Validate one hydrated events payload against the full internal events contract."""

    try:
        return EpisodeEventsRequest.model_validate(payload), []
    except ValidationError as exc:
        return None, _format_validation_errors(exc)


def validate_internal_create_contract(payload: dict[str, Any]) -> tuple[MemoryCreateRequest | None, list[ErrorDetail]]:
    """Validate one hydrated create payload against the full internal create contract."""

    try:
        return MemoryCreateRequest.model_validate(payload), []
    except ValidationError as exc:
        return None, _format_validation_errors(exc)


def validate_update_schema(payload: dict[str, Any]) -> tuple[AgentUpdateRequest | None, list[ErrorDetail]]:
    """Validate and parse agent update payloads into the simplified update contract."""

    try:
        if "updates" in payload:
            return AgentBatchUpdateRequest.model_validate(payload), []
        return AgentUpdateRequest.model_validate(payload), []
    except ValidationError as exc:
        return None, _format_validation_errors(exc)


def validate_internal_update_contract(
    payload: dict[str, Any],
) -> tuple[MemoryUpdateRequest | MemoryBatchUpdateRequest | None, list[ErrorDetail]]:
    """Validate one hydrated update payload against the full internal update contract."""

    try:
        if "updates" in payload:
            return MemoryBatchUpdateRequest.model_validate(payload), []
        return MemoryUpdateRequest.model_validate(payload), []
    except ValidationError as exc:
        return None, _format_validation_errors(exc)
