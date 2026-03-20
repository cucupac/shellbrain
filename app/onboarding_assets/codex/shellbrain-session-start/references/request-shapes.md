# Shellbrain Request Shapes

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

## Read

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

## Events

Use `events` before any create or evidence-bearing update:

```bash
shellbrain events --json '{"limit":10}'
```

Read returned ids from `data.events[].id`.

`events` inspects normalized episodic evidence. Those ids are the canonical grounding for durable writes.

When caller identity is trusted, `events` reads from the exact caller thread instead of guessing from the repo alone.
`shellbrain init` normally installs Claude integration through the global Shellbrain SessionStart hook in `~/.claude/settings.json`. Use `shellbrain admin install-claude-hook --repo-root ...` only when you intentionally need the repo-local override path.

## Create

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

## Update

### Archive State

Archive or unarchive an existing memory:

```bash
shellbrain update --json '{"memory_id":"mem-123","update":{"type":"archive_state","archived":true}}'
```

### Utility Vote

Record whether something helped solve a problem:

```bash
shellbrain update --json '{"memory_id":"mem-123","update":{"type":"utility_vote","problem_id":"mem-problem","vote":1.0,"evidence_refs":["evt-123"]}}'
```

Use `utility_vote` after solving a problem to judge whether a retrieved memory was actually useful or misleading in that specific context.

Batch utility votes are also supported:

```bash
shellbrain update --json '{"updates":[{"memory_id":"mem-123","update":{"type":"utility_vote","problem_id":"mem-problem","vote":1.0,"evidence_refs":["evt-123"]}},{"memory_id":"mem-456","update":{"type":"utility_vote","problem_id":"mem-problem","vote":-0.25,"evidence_refs":["evt-123"]}}]}'
```

Vote semantics:

- `-1.0` to `< 0`:
  unhelpful or misleading
- `0.0`:
  neutral, mixed, or unclear
- `> 0` to `1.0`:
  helpful

### Fact Update Link

Link an older fact to a newer fact through a change memory:

```bash
shellbrain update --json '{"memory_id":"mem-change","update":{"type":"fact_update_link","old_fact_id":"mem-old-fact","new_fact_id":"mem-new-fact","evidence_refs":["evt-123"]}}'
```

Use this when ground truth changed:

1. create a `change` memory
2. create the replacement `fact`
3. connect the old and new facts through `fact_update_link`

### Association Link

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
- `utility_vote.vote` is a `-1.0` to `1.0` scale where negative votes mean unhelpful and positive votes mean helpful.
