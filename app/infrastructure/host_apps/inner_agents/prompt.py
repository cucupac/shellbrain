"""Prompt rendering for Codex-backed build_context synthesis."""

from __future__ import annotations

import json

from app.core.ports.host_apps.inner_agents import (
    BuildKnowledgeAgentRequest,
    InnerAgentRunRequest,
)


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

# OPERATING PRINCIPLES
- Be maximally useful to the working agent: surface specific files, functions,
  constraints, traps, prior attempts, and high-leverage next context that can
  reduce solving time and token spend.
- Prefer newer evidence when comparable sources conflict. For memories, recency
  means created_at. For concepts, consider status, observed_at, validated_at,
  and updated_at.
- Separate sourced facts from inference. Do not present an inference as stored
  Shellbrain knowledge.
- If a material contradiction could change the worker guidance, mention the
  chosen source in the brief and explain the conflict compactly in `brief.gaps`.

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
best-effort read_trace with commands used, source ids, concept refs,
and no_context_reason when applicable.
"""


_BUILD_KNOWLEDGE_PROMPT_TEMPLATE = """\
# ROLE
You are Shellbrain build_knowledge, the internal knowledge builder.

# GOAL
Build the best future recall substrate for this repo by writing durable,
evidence-backed memories and concept graph updates.

# ALLOWED SHELLBRAIN COMMANDS
You may run `shellbrain events`, `shellbrain read`, `shellbrain concept show`,
`shellbrain memory add`, `shellbrain memory update`, `shellbrain concept add`,
and `shellbrain concept update`.

# ALLOWED CODE ACTIONS
Read and search files. Inspect git history and diffs. Identify files, functions,
tests, configs, routes, tables, and invariants that should ground future recall.

# FORBIDDEN ACTIONS
Do not edit code or config files. Do not run write-producing formatters. Do not
commit, push, call `shellbrain recall`, run admin/init/upgrade/metrics, or write
directly to the database. Your only writes are Shellbrain memory/concept write
commands allowed above.

# REQUIRED WORKFLOW
1. Inspect exact episode events first with the provided episode_id.
2. Read existing memories and concepts before writing so you avoid duplicates.
3. Inspect code read-only before creating anchors, groundings, or file/function
   claims.
4. Write only evidence-backed knowledge using event ids from the exact episode
   whenever possible.
5. Look for problem, failed-tactic, solution, fact, preference, and change
   boundaries.
6. Update concept graph records, links, claims, relations, anchors, groundings,
   and memory links when the episode provides durable evidence.
7. Treat idle-stable episodes as partial sessions. Consolidate only to the
   provided event_watermark.

# READINESS
Stop when new session evidence up to event_watermark has been consolidated, or
when you can explain why no durable memory or concept write is justified.

# HELP
Use `shellbrain --help` and command-specific `--help` for exact JSON payload
syntax. Useful commands include:
- `shellbrain events --help`
- `shellbrain read --help`
- `shellbrain concept show --help`
- `shellbrain memory add --help`
- `shellbrain memory update --help`
- `shellbrain concept add --help`
- `shellbrain concept update --help`

# OUTPUT JSON
Return only valid JSON matching output_contract.
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


def render_build_knowledge_prompt(request: BuildKnowledgeAgentRequest) -> str:
    """Render the prompt sent to the autonomous knowledge-builder provider."""

    payload = {
        "repo_id": request.repo_id,
        "repo_root": request.repo_root,
        "episode_id": request.episode_id,
        "trigger": request.trigger,
        "event_watermark": request.event_watermark,
        "previous_event_watermark": request.previous_event_watermark,
        "budgets": {
            "max_shellbrain_reads": request.max_shellbrain_reads,
            "max_code_files": request.max_code_files,
            "max_write_commands": request.max_write_commands,
            "timeout_seconds": request.timeout_seconds,
        },
        "first_command": (
            "shellbrain events --json "
            f"'{{\"episode_id\":\"{request.episode_id}\","
            f"\"after_seq\":{request.previous_event_watermark or 0},"
            f"\"up_to_seq\":{request.event_watermark}}}'"
        ),
        "help_commands": [
            "shellbrain --help",
            "shellbrain events --help",
            "shellbrain read --help",
            "shellbrain concept show --help",
            "shellbrain memory add --help",
            "shellbrain memory update --help",
            "shellbrain concept add --help",
            "shellbrain concept update --help",
        ],
        "output_contract": {
            "status": "ok|skipped",
            "run_summary": "string explaining what was consolidated or why no write was justified",
            "write_count": "integer count of shellbrain memory/concept write commands executed",
            "skipped_items": [
                {
                    "summary": "unclear, duplicate, unsupported, or low-confidence item",
                    "reason": "why it was not written",
                    "evidence_event_ids": ["episode event ids when available"],
                }
            ],
            "read_trace": {
                "commands": [
                    {
                        "command": "shellbrain ...",
                        "purpose": "string",
                        "source_ids": ["memory or episode ids used"],
                        "concept_refs": ["concept refs inspected"],
                    }
                ]
            },
            "code_trace": {
                "files": [
                    {
                        "path": "repo-relative path",
                        "symbols": ["function/class/config/table names"],
                        "purpose": "why it matters for the written knowledge",
                    }
                ]
            },
        },
    }
    payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return f"{_BUILD_KNOWLEDGE_PROMPT_TEMPLATE}\n{payload_json}"
