"""Prompt rendering for provider-backed build_context synthesis."""

from __future__ import annotations

import json

from app.core.ports.host_apps.inner_agents import InnerAgentRunRequest


def render_build_context_prompt(request: InnerAgentRunRequest) -> str:
    """Render the bounded JSON-first prompt sent to an inner-agent provider."""

    payload = {
        "query": request.query,
        "current_problem": request.current_problem,
        "candidate_context": request.candidate_context,
        "expansion_handles": request.expansion_handles,
        "output_contract": {
            "brief": {
                "summary": "string",
                "constraints": ["string"],
                "known_traps": ["string"],
                "prior_cases": ["string"],
                "concept_orientation": ["string"],
                "anchors": ["string"],
                "gaps": ["string"],
            }
        },
        "expansion_request_contract": {
            "requested_expansions": [
                {
                    "read_payload": {
                        "query": "string",
                        "expand": {
                            "concepts": {
                                "mode": "explicit",
                                "refs": ["concept-slug"],
                                "facets": ["claims"],
                            }
                        },
                    }
                }
            ]
        },
    }
    return (
        "You are Shellbrain build_context, a read-only recall synthesis agent.\n"
        "Use only the provided candidate_context and expansion_handles. If one "
        "or two listed expansion_handles are necessary, return only JSON matching "
        "the expansion_request_contract; Shellbrain will perform approved reads. "
        "Otherwise return only JSON matching the output_contract. Do not run "
        "commands, mutate state, create memories, update concepts, or infer facts "
        "not supported by the context. If the context is not relevant, say so in "
        "the brief gaps.\n\n"
        f"{json.dumps(payload, sort_keys=True, separators=(',', ':'))}"
    )
