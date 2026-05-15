"""Prepare raw CLI scenario payloads for typed core use cases."""

from __future__ import annotations

from app.core.use_cases.scenarios.record.request import ScenarioRecordRequest
from app.entrypoints.cli.request_parsing.hydration import (
    hydrate_scenario_record_payload,
)
from app.entrypoints.cli.request_parsing.payload_validation import (
    validate_internal_scenario_record_contract,
    validate_scenario_record_schema,
)
from app.entrypoints.cli.request_parsing.prepared import PreparedOperationRequest


def prepare_scenario_record_request(
    payload: dict,
    *,
    inferred_repo_id: str,
) -> PreparedOperationRequest[ScenarioRecordRequest]:
    """Validate and hydrate one raw scenario-record payload."""

    agent_request, errors = validate_scenario_record_schema(payload)
    if errors:
        return PreparedOperationRequest(
            request=None, errors=errors, error_stage="schema_validation"
        )
    assert agent_request is not None
    hydrated = hydrate_scenario_record_payload(
        agent_request.model_dump(mode="python", exclude_none=True),
        inferred_repo_id=inferred_repo_id,
    )
    request, contract_errors = validate_internal_scenario_record_contract(hydrated)
    return PreparedOperationRequest(
        request=request,
        errors=contract_errors,
        error_stage="contract_validation" if contract_errors else "schema_validation",
    )
