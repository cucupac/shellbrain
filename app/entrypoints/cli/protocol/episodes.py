"""Prepare raw CLI episode payloads for typed core use cases."""

from __future__ import annotations

from app.core.contracts.requests import EpisodeEventsRequest
from app.entrypoints.cli.protocol.hydration import hydrate_events_payload
from app.entrypoints.cli.protocol.payload_validation import (
    validate_events_schema,
    validate_internal_events_contract,
)
from app.entrypoints.cli.protocol.prepared import PreparedOperationRequest


def prepare_events_request(
    payload: dict,
    *,
    inferred_repo_id: str,
) -> PreparedOperationRequest[EpisodeEventsRequest]:
    """Validate and hydrate one raw events payload."""

    agent_request, errors = validate_events_schema(payload)
    if errors:
        return PreparedOperationRequest(
            request=None, errors=errors, error_stage="schema_validation"
        )
    assert agent_request is not None
    hydrated = hydrate_events_payload(
        agent_request.model_dump(mode="python", exclude_none=True),
        inferred_repo_id=inferred_repo_id,
    )
    request, contract_errors = validate_internal_events_contract(hydrated)
    return PreparedOperationRequest(
        request=request,
        errors=contract_errors,
        error_stage="contract_validation" if contract_errors else "schema_validation",
    )
