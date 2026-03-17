# Shellbrain Request Shapes

The public CLI expects agent-facing payloads. It hydrates `op` and `repo_id` automatically.

## Read

Use `read` to pull prior repo context before acting:

```bash
shellbrain read --json '{"query":"what should I know about this repo before I start?"}'
```

Optional `kinds` filter:

```bash
shellbrain read --json '{"query":"what deploy issues matter here?","kinds":["problem","fact","change"]}'
```

Allowed kinds:

- `problem`
- `solution`
- `failed_tactic`
- `fact`
- `preference`
- `change`

## Events

Use `events` before any create or evidence-bearing update:

```bash
shellbrain events --json '{"limit":10}'
```

Read returned ids from `data.events[].id`.

## Create

Minimal create:

```bash
shellbrain create --json '{"memory":{"text":"Deploy failed because APP_ENV was unset","kind":"problem","evidence_refs":["evt-123"]}}'
```

Notes:

- `scope` is optional and defaults to repo scope.
- `kind` must be one of the six allowed kinds listed above.
- `evidence_refs` must contain stored `episode_event` ids returned by `events`.

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

### Fact Update Link

Link an older fact to a newer fact through a change memory:

```bash
shellbrain update --json '{"memory_id":"mem-change","update":{"type":"fact_update_link","old_fact_id":"mem-old-fact","new_fact_id":"mem-new-fact","evidence_refs":["evt-123"]}}'
```

### Association Link

Link two memories explicitly:

```bash
shellbrain update --json '{"memory_id":"mem-123","update":{"type":"association_link","to_memory_id":"mem-456","relation_type":"associated_with","evidence_refs":["evt-123"]}}'
```

Allowed update types:

- `archive_state`
- `utility_vote`
- `fact_update_link`
- `association_link`

Important nuance:

- `archive_state` does not carry `evidence_refs`.
- The evidence-bearing update types carry `evidence_refs` inside the `update` object, not at the top level.
