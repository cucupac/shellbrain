# Shellbrain Session Workflow

## Mental Model

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

## Bootstrap

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

In Codex desktop and similar tool shells, if direct `shellbrain` calls fail in the current session, retry through a login shell that sources `~/.zprofile`:

```bash
zsh -lc 'source ~/.zprofile >/dev/null 2>&1; shellbrain --help'
```

Assume Shellbrain comes from a one-time machine install. Do not rerun `init` just because a new agent starts. If direct calls fail in the current Codex session, keep using the `zsh -lc 'source ~/.zprofile ...'` wrapper for Shellbrain invocations before declaring Shellbrain blocked. Only if the wrapped check fails should you ask the operator to restore the machine-level install.

Drop into the advanced/operator path only when `doctor` says the managed runtime is blocked.

## Repo Targeting

- Default to the current working directory when it is the repo you are working in.
- Use `--repo-root /absolute/path/to/repo` when your shell is elsewhere.
- Treat path as operational context, not durable identity.
- Shellbrain should normally derive durable repo identity from normalized git remote.
- It prefers `origin`, then a single remaining remote.
- If multiple remotes exist and none is `origin`, `init` stops and asks for `--repo-id`.
- If no usable remote exists, Shellbrain falls back to a weak-local identity tied to the current path.

## Query Playbook

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

## How To Read The Pack

`read` returns a bounded context pack:

- `direct`:
  direct matches to the current query
- `explicit_related`:
  memories reached through explicit link structure such as problem-attempt relations, fact-update chains, and authored associations
- `implicit_related`:
  semantic neighbors and bounded associative hops

Use `why_included` and `anchor_memory_id` to understand why a related item appeared.

## Session Cadence

### Start of session

1. Resolve the target repo.
2. Run one or more focused `read` queries tied to the actual problem.
3. Process the context pack and extract candidate prior cases, facts, and preferences.

### During the task

Re-run `read` whenever:

- the search shifts to a new subproblem
- you hit a blocker and want similar prior failures or tactics
- you move into a new subsystem
- you suspect a fact, preference, or change memory may matter halfway through the journey

Do not treat Shellbrain as startup-only. Query liberally while solving.

### Before any write

Inspect fresh evidence:

```bash
shellbrain events --json '{"limit":10}'
```

Then reuse returned `data.events[].id` values verbatim as `evidence_refs`.

### Session end

Normalize the episode into durable memory:

1. Store the `problem`.
2. Store each `failed_tactic`.
3. Store the `solution`.
4. Store any durable `fact`, `preference`, or `change` discovered while working.
5. Record `utility_vote` updates for memories that helped or misled.

This is where Shellbrain compounds: future agents can ask, with high fidelity, whether they have seen anything like the current problem before.

## Memory Kinds and Scope

- `problem`:
  the obstacle or failure mode
- `solution`:
  what worked for that problem
- `failed_tactic`:
  what did not work for that problem
- `fact`:
  durable truth about the repo, environment, architecture, or workflow
- `preference`:
  user or repo convention about how work should be done
- `change`:
  something that invalidated or revised prior truth

Link invariant:

- `solution` and `failed_tactic` require `links.problem_id`
- the other kinds do not accept `links.problem_id`

Scope guidance:

- default to `scope: "repo"`
- use `scope: "global"` for cross-repo user preferences, coding style preferences, architectural preferences, or project facts that are not repo-specific

## Links and Utility

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

## Evidence Model

- `events` syncs the exact trusted caller thread when Shellbrain can identify the host session cleanly.
- Supported hosts are Codex and Claude Code.
- Codex caller identity is automatic.
- Claude trusted identity normally comes from the global Shellbrain SessionStart hook in `~/.claude/settings.json`.
- Successful Shellbrain commands keep background episodic capture warm automatically.
- `events` also performs an inline sync before returning recent stored events.
- The transcript log is evidence, not the memory itself. Do not store raw transcript chunks as durable memories.
- Successful responses may include `data.guidance`; treat it as an internal nudge from Shellbrain about pending utility votes or workflow reminders.

## Recovery

- New agent session, but Shellbrain was already set up
  Do not rerun `init`. Start with `read`. Use `doctor` only if readiness is unclear.

- `shellbrain: command not found`
  Retry through `zsh -lc 'source ~/.zprofile >/dev/null 2>&1; shellbrain --help'` first. Only if that still fails should you ask the operator to restore the one-time machine install.

- `shellbrain init` fails or `doctor` shows `repair_needed`
  Rerun `shellbrain init`. That is the normal repair path.

- `doctor` says the managed runtime is blocked
  Escalate to the operator path only after `doctor` gives a specific failure. That path may still involve manual DSN, migration, or Docker repair.

- No active host session found
  Verify that the user is working in Codex or Claude Code, that transcript files exist, and that `repo_root` matches the repo used in that session.

- Claude integration missing or untrusted
  Rerun `shellbrain init` or `shellbrain admin install-host-assets --host claude` to restore the global Claude integration. Use `shellbrain admin install-claude-hook --repo-root ...` only when you intentionally need the repo-local override path. Do not hand-edit Claude hook config in the normal path.

- `init` asks for `--repo-id`
  That means multiple remotes exist and none is `origin`. Pick the durable identity you want and rerun with an explicit repo id.

- Evidence ref rejected or event not visible
  Rerun `shellbrain events` and use the returned ids verbatim. Do not reuse stale ids from memory.
