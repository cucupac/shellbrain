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

`shellbrain init` is first-time bootstrap and repair. It is not a per-session ritual.

1. If Shellbrain has never been bootstrapped on this machine, the current repo has never been registered, or the user says Shellbrain setup is broken, run `shellbrain init`.
2. Otherwise, do not rerun `init` just because a new agent session started. Start with focused `read` queries right away.
3. If readiness is unclear, inspect with `shellbrain admin doctor` instead of rerunning `init` by reflex.
4. If `doctor` reports `repair_needed`, rerun `shellbrain init` instead of trying to repair Shellbrain manually.
5. In Claude Code, if direct `shellbrain` calls fail in the current session, retry through a login shell that sources the user's login profile:
   `zsh -lc 'source ~/.zprofile >/dev/null 2>&1; shellbrain --help'`
   If the host shell is bash instead of zsh, use:
   `bash -lc 'source ~/.bash_profile >/dev/null 2>&1; shellbrain --help'`
6. If the wrapped login-shell check still cannot find `shellbrain`, inspect Python's user script directory:
   `python3 -c "import sysconfig; print(sysconfig.get_path('scripts', 'posix_user'))"`
   If `shellbrain` exists there, call it directly or add that directory to the login profile PATH and retry. If it does not, reinstall the Shellbrain CLI.
7. Only drop to the advanced/operator recovery notes if `doctor` says the managed runtime is blocked.
8. Resolve the target repo:
   - Use the current working directory when already inside the repo.
   - Pass `--repo-root /absolute/path/to/repo` when working from somewhere else.
   - Treat repo path as operational context; Shellbrain should normally derive durable repo identity from normalized git remote, not from `basename(repo_root)`.
   - Shellbrain prefers `origin`, then a single remaining remote. If multiple remotes exist and none is `origin`, pass `--repo-id`.
   - If there is no usable remote, Shellbrain falls back to a weak-local identity tied to the current path.
9. Start with focused `read` queries about the concrete problem, subsystem, decision, or constraint you are working on. Do not start with vague prompts like "what should I know about this repo?"
10. Use a startup read bundle:
   - prior attempts:
     `shellbrain read --json '{"query":"Have we seen this failure mode before?","kinds":["problem","solution","failed_tactic"]}'`
   - constraints and preferences:
     `shellbrain read --json '{"query":"What repo constraints or user preferences matter for this task?","kinds":["fact","preference","change"]}'`
   - area-specific facts:
     `shellbrain read --json '{"query":"What facts or changes matter in this subsystem?","kinds":["fact","change","problem","solution"]}'`
11. When the `shellbrain` command is not on PATH in the current shell, wrap invocations:
   `zsh -lc "source ~/.zprofile >/dev/null 2>&1; shellbrain read --json '{\"query\":\"Have we seen this failure mode before?\",\"kinds\":[\"problem\",\"solution\",\"failed_tactic\"]}'"`
12. Inspect the returned context pack:
   - `direct` = direct matches
   - `explicit_related` = linked memories, including authored associations and problem/fact chains
   - `implicit_related` = semantic neighbors and bounded associative hops
13. Re-run `read` liberally during the task whenever the search shifts, you hit a new subproblem, or you suspect the right memory will only become relevant mid-journey.
14. Before `create` or any evidence-bearing `update`, run `shellbrain events --json '{"limit":10}'`.
15. Reuse returned `data.events[].id` values verbatim as `evidence_refs`.
16. At session end, normalize the episode into durable memories:
   - store the `problem`
   - store each `failed_tactic`
   - store the `solution`
   - store any durable `fact`, `preference`, or `change`
   - record `utility_vote` updates for memories that helped or misled
17. Use the exact payload shapes documented below.

Trusted session note:

- `events` now syncs the exact trusted caller thread instead of mixing same-repo agent threads.
- Claude trusted identity normally comes from the global Shellbrain SessionStart hook in `~/.claude/settings.json`. Repo-local `.claude/settings.local.json` is only the explicit override or repair path.
- Successful responses may include `data.guidance`; treat that as an internal Shellbrain nudge about pending utility votes or workflow reminders.

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
- `shellbrain init` is the normal first-time bootstrap and repair path, not the default way to start every agent session.
- `shellbrain admin doctor` is the inspect path when readiness is unclear.
- Background episodic capture runs automatically. `events` still performs an inline sync before it returns fresh transcript evidence.
- Use `read` again before writing when you need to check whether a memory already exists or whether an `update` is more appropriate than a new `create`.

---

## Session Workflow

### Mental Model

Shellbrain is not an LLM chat endpoint. It is a retrieval and write system for structured long-term memory.

Think in four layers:

- procedural / experiential memory:
  - `problem`
  - `solution`
  - `failed_tactic`
- semantic memory:
  - `fact`
  - `preference`
  - `change`
- associative memory:
  - explicit durable links between memories
  - implicit semantic-neighbor expansion during `read`
- episodic memory:
  - transcript-derived `episode_events` captured from the active host session

The point is case-based reasoning: query for similar prior problems, plans, constraints, and facts; use current repo state as ground truth; and then write back durable lessons from the finished episode.

### Bootstrap

Treat `shellbrain init` as first-time bootstrap plus repair, not as a routine start-of-session command.

Normal session rhythm:

- if Shellbrain already works in this repo, go straight to `read`
- if readiness is unclear, run `shellbrain admin doctor`
- if Shellbrain has never been bootstrapped on this machine, this repo has never been registered, or `doctor` says `repair_needed`, run `shellbrain init`

Bootstrap and repair path:

```bash
shellbrain init
shellbrain admin doctor
```

Use Shellbrain normally after `doctor` shows the machine bootstrap is `ready` and the current repo is registered.

If `doctor` reports `repair_needed`, rerun `shellbrain init` instead of trying to patch Shellbrain manually.

In Claude Code, if direct `shellbrain` calls fail in the current session, retry through a login shell that sources the user's login profile:

```bash
zsh -lc 'source ~/.zprofile >/dev/null 2>&1; shellbrain --help'
```

If the host shell is bash instead of zsh, use:

```bash
bash -lc 'source ~/.bash_profile >/dev/null 2>&1; shellbrain --help'
```

If the wrapped login-shell check still cannot find `shellbrain`, inspect Python's user script directory:

```bash
python3 -c "import sysconfig; print(sysconfig.get_path('scripts', 'posix_user'))"
```

If that directory contains `shellbrain`, call it directly or add that directory to the login profile PATH and retry. If it does not, reinstall the Shellbrain CLI.

Assume Shellbrain comes from a one-time machine install. Do not rerun `init` just because a new agent starts. If direct calls fail in the current Claude Code session, keep using the login-shell wrapper for Shellbrain invocations before declaring Shellbrain blocked. Only if the wrapped check fails should you inspect the user script directory or ask the operator to restore the machine-level install.

Drop into the advanced/operator path only when `doctor` says the managed runtime is blocked.

### Repo Targeting

- Default to the current working directory when it is the repo you are working in.
- Use `--repo-root /absolute/path/to/repo` when your shell is elsewhere.
- Treat path as operational context, not durable identity.
- Shellbrain should normally derive durable repo identity from normalized git remote.
- It prefers `origin`, then a single remaining remote.
- If multiple remotes exist and none is `origin`, `init` stops and asks for `--repo-id`.
- If no usable remote exists, Shellbrain falls back to a weak-local identity tied to the current path.

### Query Playbook

`read` uses lexical retrieval plus embedding similarity, then expands through explicit links and implicit semantic neighbors. Query it like a search and retrieval system, not like an open-ended chat model.

Good query families:

1. Prior attempts for the current problem:

```bash
shellbrain read --json '{"query":"Have we seen this migration lock timeout before?","kinds":["problem","solution","failed_tactic"]}'
```

2. Constraints and preferences for the current task:

```bash
shellbrain read --json '{"query":"What repo constraints or user preferences matter for this auth refactor?","kinds":["fact","preference","change"]}'
```

3. Facts and changes for the subsystem you are entering:

```bash
shellbrain read --json '{"query":"What facts or recent changes matter around the payments retry worker?","kinds":["fact","change","problem","solution"]}'
```

Avoid generic prompts like:

- "what should I know about this repo?"
- "what should I know before I start?"

Those are too vague for the actual retrieval model.

### How To Read The Pack

`read` returns a bounded context pack:

- `direct`:
  direct matches to the current query
- `explicit_related`:
  memories reached through explicit link structure such as problem-attempt relations, fact-update chains, and authored associations
- `implicit_related`:
  semantic neighbors and bounded associative hops

Use `why_included` and `anchor_memory_id` to understand why a related item appeared.

### Session Cadence

#### Start of session

1. Resolve the target repo.
2. Run one or more focused `read` queries tied to the actual problem.
3. Process the context pack and extract candidate prior cases, facts, and preferences.

#### During the task

Re-run `read` whenever:

- the search shifts to a new subproblem
- you hit a blocker and want similar prior failures or tactics
- you move into a new subsystem
- you suspect a fact, preference, or change memory may matter halfway through the journey

Do not treat Shellbrain as startup-only. Query liberally while solving.

#### Before any write

Inspect fresh evidence:

```bash
shellbrain events --json '{"limit":10}'
```

Then reuse returned `data.events[].id` values verbatim as `evidence_refs`.

#### Session end

Normalize the episode into durable memory:

1. Store the `problem`.
2. Store each `failed_tactic`.
3. Store the `solution`.
4. Store any durable `fact`, `preference`, or `change` discovered while working.
5. Record `utility_vote` updates for memories that helped or misled.

This is where Shellbrain compounds: future agents can ask, with high fidelity, whether they have seen anything like the current problem before.

### Memory Kinds and Scope

Link invariant:

- `solution` and `failed_tactic` require `links.problem_id`
- the other kinds do not accept `links.problem_id`

Scope guidance:

- default to `scope: "repo"`
- use `scope: "global"` for cross-repo user preferences, coding style preferences, architectural preferences, or project facts that are not repo-specific

### Links and Utility

- explicit associations:
  memories you deliberately link because they are similar or one depends on the other
- implicit associations:
  semantic-neighbor expansion during `read`
- `utility_vote`:
  problem-scoped feedback about whether a retrieved memory helped solve the current `problem`
  on a `-1.0` to `1.0` scale:
  negative = unhelpful or misleading
  `0.0` = neutral or unclear
  positive = helpful
- `fact_update_link`:
  how you represent truth evolution when a `change` supersedes one fact with another

Important modeling pattern for changed truth:

1. create a `change` memory
2. create the new `fact`
3. connect old and new facts through `fact_update_link`

### Evidence Model

- `events` syncs the exact trusted caller thread when Shellbrain can identify the host session cleanly.
- Supported hosts are Claude Code and Codex.
- Claude trusted identity normally comes from the global Shellbrain SessionStart hook in `~/.claude/settings.json`.
- Successful Shellbrain commands keep background episodic capture warm automatically.
- `events` also performs an inline sync before returning recent stored events.
- The transcript log is evidence, not the memory itself. Do not store raw transcript chunks as durable memories.
- Successful responses may include `data.guidance`; treat it as an internal nudge from Shellbrain about pending utility votes or workflow reminders.

### Recovery

- New agent session, but Shellbrain was already set up
  Do not rerun `init`. Start with `read`. Use `doctor` only if readiness is unclear.

- `shellbrain: command not found`
  Retry through `zsh -lc 'source ~/.zprofile >/dev/null 2>&1; shellbrain --help'` first. Only if that still fails should you ask the operator to restore the one-time machine install.

- `shellbrain init` fails or `doctor` shows `repair_needed`
  Rerun `shellbrain init`. That is the normal repair path.

- `doctor` says the managed runtime is blocked
  Escalate to the operator path only after `doctor` gives a specific failure. That path may still involve manual DSN, migration, or Docker repair.

- No active host session found
  Verify that the user is working in Claude Code, that transcript files exist, and that `repo_root` matches the repo used in that session.

- Claude integration missing or untrusted
  Rerun `shellbrain init` or `shellbrain admin install-host-assets --host claude` to restore the global Claude integration. Use `shellbrain admin install-claude-hook --repo-root ...` only when you intentionally need the repo-local override path. Do not hand-edit Claude hook config in the normal path.

- `init` asks for `--repo-id`
  That means multiple remotes exist and none is `origin`. Pick the durable identity you want and rerun with an explicit repo id.

- Evidence ref rejected or event not visible
  Rerun `shellbrain events` and use the returned ids verbatim. Do not reuse stale ids from memory.

---

## Request Shapes

The public CLI expects agent-facing payloads. It hydrates `op` and `repo_id` automatically.

Assume the normal product bootstrap has already happened:

- `shellbrain init` has succeeded for the machine
- the current repo has been registered
- `shellbrain admin doctor` reports Shellbrain as ready

Do not rerun `shellbrain init` at the start of an ordinary agent session. If readiness is unclear, inspect with `shellbrain admin doctor` before debugging individual request payloads.

Shellbrain should normally infer durable repo identity from normalized git remote. Use `--repo-root` when your shell is elsewhere; reserve explicit repo-id overrides for rare advanced cases.

More precisely:

- Shellbrain prefers the normalized `origin` fetch URL.
- If `origin` is absent but exactly one remote exists, it uses that remote.
- If multiple remotes exist and none is `origin`, rerun `init` with `--repo-id`.
- If no usable remote exists, Shellbrain falls back to a weak-local identity tied to the current path.

### Read

Use `read` to retrieve durable memories related to the current problem or subproblem.

Shellbrain `read` is retrieval, not chat. Query it with concrete failure modes, subsystem names, decisions, or constraints. Avoid vague prompts like "what should I know about this repo?"

Prior attempts:

```bash
shellbrain read --json '{"query":"Have we seen this migration lock timeout before?","kinds":["problem","solution","failed_tactic"]}'
```

Constraints and preferences:

```bash
shellbrain read --json '{"query":"What repo constraints or user preferences matter for this auth refactor?","kinds":["fact","preference","change"]}'
```

Area-specific facts and changes:

```bash
shellbrain read --json '{"query":"What facts or recent changes matter around the payments retry worker?","kinds":["fact","change","problem","solution"]}'
```

Allowed kinds:

- `problem`
- `solution`
- `failed_tactic`
- `fact`
- `preference`
- `change`

Read returns a context pack with:

- `direct`
- `explicit_related`
- `implicit_related`

Use `why_included` and `anchor_memory_id` to understand why related memories appeared.

### Events

Use `events` before any create or evidence-bearing update:

```bash
shellbrain events --json '{"limit":10}'
```

Read returned ids from `data.events[].id`.

`events` inspects normalized episodic evidence. Those ids are the canonical grounding for durable writes.

When caller identity is trusted, `events` reads from the exact caller thread instead of guessing from the repo alone.
`shellbrain init` normally installs Claude integration through the global Shellbrain SessionStart hook in `~/.claude/settings.json`. Use `shellbrain admin install-claude-hook --repo-root ...` only when you intentionally need the repo-local override path.

### Create

Minimal create:

```bash
shellbrain create --json '{"memory":{"text":"Deploy failed because APP_ENV was unset","kind":"problem","evidence_refs":["evt-123"]}}'
```

Notes:

- `scope` is optional and defaults to repo scope.
- `kind` must be one of the six allowed kinds listed above.
- `solution` and `failed_tactic` require `links.problem_id`.
- `problem`, `fact`, `preference`, and `change` do not accept `links.problem_id`.
- `evidence_refs` must contain stored `episode_event` ids returned by `events`.

When to use each create kind:

- `problem`:
  the obstacle or failure mode
- `solution`:
  what worked for a specific problem
- `failed_tactic`:
  what did not work for a specific problem
- `fact`:
  durable truth about the repo or workflow
- `preference`:
  durable user or repo convention
- `change`:
  something that invalidates or revises prior truth

### Update

#### Archive State

Archive or unarchive an existing memory:

```bash
shellbrain update --json '{"memory_id":"mem-123","update":{"type":"archive_state","archived":true}}'
```

#### Utility Vote

Record whether something helped solve a problem:

```bash
shellbrain update --json '{"memory_id":"mem-123","update":{"type":"utility_vote","problem_id":"mem-problem","vote":1.0,"evidence_refs":["evt-123"]}}'
```

Batch utility votes are also supported:

```bash
shellbrain update --json '{"updates":[{"memory_id":"mem-123","update":{"type":"utility_vote","problem_id":"mem-problem","vote":1.0,"evidence_refs":["evt-123"]}},{"memory_id":"mem-456","update":{"type":"utility_vote","problem_id":"mem-problem","vote":-0.25,"evidence_refs":["evt-123"]}}]}'
```

Use `utility_vote` after solving a problem to judge whether a retrieved memory was actually useful or misleading in that specific context.

Vote semantics:

- `-1.0` to `< 0`:
  unhelpful or misleading
- `0.0`:
  neutral, mixed, or unclear
- `> 0` to `1.0`:
  helpful

#### Fact Update Link

Link an older fact to a newer fact through a change memory:

```bash
shellbrain update --json '{"memory_id":"mem-change","update":{"type":"fact_update_link","old_fact_id":"mem-old-fact","new_fact_id":"mem-new-fact","evidence_refs":["evt-123"]}}'
```

Use this when ground truth changed:

1. create a `change` memory
2. create the replacement `fact`
3. connect the old and new facts through `fact_update_link`

#### Association Link

Link two memories explicitly:

```bash
shellbrain update --json '{"memory_id":"mem-123","update":{"type":"association_link","to_memory_id":"mem-456","relation_type":"associated_with","evidence_refs":["evt-123"]}}'
```

Use `association_link` when two memories are similar or one depends on the other in a way you want future retrieval to preserve explicitly. This is the explicit side of associative memory; semantic-neighbor expansion remains the implicit side.

Allowed update types:

- `archive_state`
- `utility_vote`
- `fact_update_link`
- `association_link`

Important nuance:

- `archive_state` does not carry `evidence_refs`.
- The evidence-bearing update types carry `evidence_refs` inside the `update` object, not at the top level.
- `utility_vote` is about usefulness for a specific problem, not about changing truth.

## Resources

- If you get stuck or need to understand how shellbrain works at a deeper level, read the docs at https://shellbrain.ai/agents — the sitemap there links to pages on memory types, recall, and the full system.
