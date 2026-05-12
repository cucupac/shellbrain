"""Prepare raw CLI concept payloads for typed core use cases."""

from __future__ import annotations

from app.core.use_cases.concepts.add.request import ConceptAddRequest
from app.core.use_cases.concepts.show.request import ConceptShowRequest
from app.core.use_cases.concepts.update.request import ConceptUpdateRequest
from app.entrypoints.cli.request_parsing.hydration import (
    hydrate_concept_add_payload,
    hydrate_concept_show_payload,
    hydrate_concept_update_payload,
)
from app.entrypoints.cli.request_parsing.payload_validation import (
    validate_concept_add_schema,
    validate_concept_show_schema,
    validate_concept_update_schema,
)
from app.entrypoints.cli.request_parsing.prepared import PreparedOperationRequest


def prepare_concept_add_request(
    payload: dict,
    *,
    inferred_repo_id: str,
) -> PreparedOperationRequest[ConceptAddRequest]:
    """Validate and hydrate one raw concept-add payload."""

    hydrated = hydrate_concept_add_payload(payload, inferred_repo_id=inferred_repo_id)
    request, errors = validate_concept_add_schema(hydrated)
    return PreparedOperationRequest(
        request=request,
        errors=errors,
        error_stage="schema_validation" if errors else "schema_validation",
    )


def prepare_concept_update_request(
    payload: dict,
    *,
    inferred_repo_id: str,
) -> PreparedOperationRequest[ConceptUpdateRequest]:
    """Validate and hydrate one raw concept-update payload."""

    hydrated = hydrate_concept_update_payload(
        payload, inferred_repo_id=inferred_repo_id
    )
    request, errors = validate_concept_update_schema(hydrated)
    return PreparedOperationRequest(
        request=request,
        errors=errors,
        error_stage="schema_validation" if errors else "schema_validation",
    )


def prepare_concept_show_request(
    payload: dict,
    *,
    inferred_repo_id: str,
) -> PreparedOperationRequest[ConceptShowRequest]:
    """Validate and hydrate one raw concept-show payload."""

    hydrated = hydrate_concept_show_payload(payload, inferred_repo_id=inferred_repo_id)
    request, errors = validate_concept_show_schema(hydrated)
    return PreparedOperationRequest(
        request=request,
        errors=errors,
        error_stage="schema_validation" if errors else "schema_validation",
    )
