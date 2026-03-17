---
name: shellbrain-session-start
description: Use when Codex should get up to speed in any repo with the installed shellbrain CLI, retrieve prior repo context, inspect recent transcript evidence, and write back durable Shellbrain entries. Trigger when the user asks to use shellbrain, wants prior repo recall, wants to preserve durable learnings, or starts a session that should reuse long-term repo context.
---

# Shellbrain Session Start

## Overview

Use Shellbrain as a case-based reasoning system for long-running agent work.

Shellbrain has two layers:

- durable memories:
  - `problem`
  - `solution`
  - `failed_tactic`
  - `fact`
  - `preference`
  - `change`
- episodic evidence:
  - transcript-derived `episode_events` that justify writes

`read` recalls durable abstractions. `events` inspects the episodic evidence stream. `create` and `update` let the agent turn what happened in a session into reusable long-term memory.

Treat current repo state as ground truth. Treat Shellbrain as advisory long-term memory that helps answer: "Have I seen anything like this before, and what was useful?"

## Quick Start

1. Check that Shellbrain is available with `shellbrain --help`.
2. Assume Shellbrain is already available from a one-time global install. If the CLI is missing, ask the operator to restore that machine-level install instead of reinstalling per repo. The operator should also have `SHELLBRAIN_DB_DSN` set and `shellbrain admin migrate` already applied.
3. Resolve the target repo:
   - Use the current working directory when already inside the repo.
   - Pass `--repo-root /absolute/path/to/repo` when working from somewhere else.
   - Pass `--repo-id` only when `basename(repo_root)` is not the right repo identifier.
4. Start with focused `read` queries about the concrete problem, subsystem, decision, or constraint you are working on. Do not start with vague prompts like "what should I know about this repo?"
5. Use a startup read bundle:
   - prior attempts:
     `shellbrain read --json '{"query":"Have we seen this failure mode before?","kinds":["problem","solution","failed_tactic"]}'`
   - constraints and preferences:
     `shellbrain read --json '{"query":"What repo constraints or user preferences matter for this task?","kinds":["fact","preference","change"]}'`
   - area-specific facts:
     `shellbrain read --json '{"query":"What facts or changes matter in this subsystem?","kinds":["fact","change","problem","solution"]}'`
6. Inspect the returned context pack:
   - `direct` = direct matches
   - `explicit_related` = linked memories, including authored associations and problem/fact chains
   - `implicit_related` = semantic neighbors and bounded associative hops
7. Re-run `read` liberally during the task whenever the search shifts, you hit a new subproblem, or you suspect the right memory will only become relevant mid-journey.
8. Before `create` or any evidence-bearing `update`, run `shellbrain events --json '{"limit":10}'`.
9. Reuse returned `data.events[].id` values verbatim as `evidence_refs`.
10. At session end, normalize the episode into durable memories:
   - store the `problem`
   - store each `failed_tactic`
   - store the `solution`
   - store any durable `fact`, `preference`, or `change`
   - record `utility_vote` updates for memories that helped or misled
11. Use the exact payload shapes in [references/request-shapes.md](references/request-shapes.md).

## Memory Kinds

- `problem`:
  the obstacle, failure mode, or recurring issue that future agents may face again
- `solution`:
  what worked for a specific `problem`
- `failed_tactic`:
  what was tried and did not work for a specific `problem`
- `fact`:
  durable truth about the repo, architecture, workflow, or environment
- `preference`:
  durable user or repo convention about how work should be done
- `change`:
  something that invalidated or revised prior truth

Invariant:

- `solution` and `failed_tactic` require `links.problem_id`
- `problem`, `fact`, `preference`, and `change` do not accept `links.problem_id`

## Updates and Links

- `utility_vote`:
  score whether a memory helped solve a specific `problem`
  on a `-1.0` to `1.0` scale:
  negative = unhelpful or misleading
  `0.0` = neutral or unclear
  positive = helpful
- `fact_update_link`:
  connect an older fact to a newer fact through a `change` memory
- `association_link`:
  add an explicit durable relation between two memories
- `archive_state`:
  hide or restore an existing memory without rewriting history

Use explicit associations when two memories are similar or one depends on the other in a way you want future retrieval to honor. Shellbrain also has implicit associations via semantic neighbors; those show up in `implicit_related` during `read`, but only explicit authored links become durable graph structure.

## Operating Rules

- Never invent `evidence_refs`.
- Skip the write if `events` returns nothing useful or the evidence is ambiguous.
- Prefer `scope: "repo"` unless the knowledge is intentionally cross-repo. Use `scope: "global"` for cross-repo user preferences, coding conventions, or project-wide facts.
- Store durable, reusable knowledge. Do not store transient chatter, raw logs, or short-lived status.
- Background episodic capture runs automatically. `events` still performs an inline sync before it returns fresh transcript evidence.
- Use `read` again before writing when you need to check whether a memory already exists or whether an `update` is more appropriate than a new `create`.

## Resources

- Read [references/session-workflow.md](references/session-workflow.md) for the full session cadence, query playbook, and evidence model.
- Read [references/request-shapes.md](references/request-shapes.md) for valid JSON payloads, response-shape notes, and command examples.
