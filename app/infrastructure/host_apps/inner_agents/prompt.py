"""Prompt rendering for Codex-backed build_context synthesis."""

from __future__ import annotations

import json

from app.core.ports.host_apps.inner_agents import InnerAgentRunRequest


_BUILD_CONTEXT_PROMPT_TEMPLATE = """\
# ROLE
You are Shellbrain build_context. You are a synchronous, read-only recall and
synthesis agent serving another coding agent.

# INPUT
Use the provided query, current_problem, repo_root, and budgets. The working
agent will only see your final JSON.

# ALLOWED COMMANDS
You may run only read-only Shellbrain commands listed in the payload. If command
syntax is unclear, run one of the help commands listed in the payload.

# FORBIDDEN COMMANDS
Do not call recursive recall. Do not create or update memories, concepts,
utility votes, problem runs, admin state, files, or settings.

# REQUIRED WORKFLOW
1. Run `shellbrain events --json '{"limit":10}'` first.
2. Run at least one targeted `shellbrain read` using both the query and current_problem
   to form the search text.
3. If read results include concept refs that may affect the answer, inspect
   those refs with `shellbrain concept show` or explicit `shellbrain read`
   concept expansion before relying on the concept.
4. Run additional reads only when events or concept details reveal a sharper
   query. Stay within max_private_reads.

# READINESS TO SYNTHESIZE
Synthesize only when you have enough relevant memories, events, or concept
details to answer the working agent directly, or when you have completed the
required events/read/concept checks and found no relevant Shellbrain context. If
nothing relevant exists, say that plainly.

# OUTPUT JSON
Return only valid JSON matching output_contract. Include a compact brief and a
best-effort read_trace with commands used, source ids, concept refs, and
no_context_reason when applicable.
"""


def render_build_context_prompt(request: InnerAgentRunRequest) -> str:
    """Render the JSON-first prompt sent to an autonomous read-only provider."""

    payload = {
        "query": request.query,
        "current_problem": request.current_problem,
        "repo_root": request.repo_root,
        "budgets": {
            "max_private_reads": request.max_private_reads,
            "max_candidate_tokens": request.max_candidate_tokens,
            "max_brief_tokens": request.max_brief_tokens,
        },
        "help_commands": [
            "shellbrain --help",
            "shellbrain events --help",
            "shellbrain read --help",
            "shellbrain concept show --help",
        ],
        "allowed_shellbrain_commands": [
            "shellbrain events --json '{\"limit\":10}'",
            "shellbrain read --json '{\"query\":\"...\"}'",
            "shellbrain read --json '{\"query\":\"...\",\"expand\":{\"concepts\":{\"mode\":\"explicit\",\"refs\":[\"concept-ref\"],\"facets\":[\"claims\",\"relations\",\"groundings\",\"memory_links\"]}}}'",
            "shellbrain concept show --json '{\"schema_version\":\"concept.v1\",\"concept\":\"concept-ref\",\"include\":[\"claims\",\"relations\",\"groundings\",\"memory_links\"]}'",
        ],
        "forbidden_shellbrain_commands": [
            "shellbrain recall",
            "shellbrain memory add",
            "shellbrain memory update",
            "shellbrain concept add",
            "shellbrain concept update",
            "any admin, init, upgrade, metrics, or durable write command",
        ],
        "output_contract": {
            "brief": {
                "summary": "string",
                "constraints": ["string"],
                "known_traps": ["string"],
                "prior_cases": ["string"],
                "concept_orientation": ["string"],
                "anchors": ["string"],
                "gaps": ["string"],
                "sources": [
                    {
                        "kind": "memory|concept|episode_event",
                        "id": "source id or concept ref",
                        "section": "read_trace",
                    }
                ],
            },
            "read_trace": {
                "commands": [
                    {
                        "command": "shellbrain ...",
                        "purpose": "string",
                        "source_ids": ["memory or episode ids used"],
                        "concept_refs": ["concept refs inspected"],
                    }
                ],
                "source_ids": ["memory or episode ids used"],
                "concept_refs": ["concept refs inspected"],
                "no_context_reason": "string when no relevant context exists",
            },
        },
    }
    payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return f"{_BUILD_CONTEXT_PROMPT_TEMPLATE}\n{payload_json}"
