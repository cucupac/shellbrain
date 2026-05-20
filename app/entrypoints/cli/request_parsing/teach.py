"""Prepare raw CLI teach payloads for the core use case."""

from __future__ import annotations

from app.core.use_cases.knowledge_builder.teach_knowledge import TeachKnowledgeRequest
from app.entrypoints.cli.request_parsing.payload_validation import (
    validate_teach_schema,
)
from app.entrypoints.cli.request_parsing.prepared import PreparedOperationRequest


def prepare_teach_request(
    payload: dict,
    *,
    inferred_repo_id: str,
    repo_root: str,
) -> PreparedOperationRequest[TeachKnowledgeRequest]:
    """Validate and hydrate one raw teach payload."""

    agent_request, errors = validate_teach_schema(payload)
    if errors:
        return PreparedOperationRequest(
            request=None, errors=errors, error_stage="schema_validation"
        )
    assert agent_request is not None
    request = TeachKnowledgeRequest(
        repo_id=inferred_repo_id,
        repo_root=repo_root,
        text=agent_request.text,
        current_problem=agent_request.current_problem,
    )
    return PreparedOperationRequest(request=request, errors=[])
