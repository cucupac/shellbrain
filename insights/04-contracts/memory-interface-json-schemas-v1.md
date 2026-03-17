# Memory Interface JSON Schemas v1

Status: aligned with storage v1, ratified naming locks, and ratified associative-structure integration on 2026-02-25.

This card records the `read` / `create` / `update` interface semantics and exact JSON schemas aligned to:
- `04-contracts/memory-storage-relational-schema-v1.md`
- immutable shellbrain records + link tables (including formal association links)
- contextual utility observations
- no mutable truth score in v1

## Operation Semantics

- `read`: retrieval only.
- `create`: creates immutable shellbrain records and immutable link/evidence records.
- `update`: lifecycle/feedback/linkage updates only (no mutable truth score).
- No separate `association.read` operation exists in v1; association traversal is integrated under `read` policy context-pack assembly.
- "X changed in the codebase and invalidates Y" is represented by immutable creates:
  - create a `change` memory,
  - create a replacement `fact` memory,
  - link them with `update.type = "fact_update_link"`.

## `memory.read.request`

```json
{
  "$id": "memory.read.request",
  "type": "object",
  "required": ["op", "repo_id", "mode", "query"],
  "properties": {
    "op": { "const": "read" },
    "repo_id": { "type": "string", "minLength": 1 },
    "mode": { "enum": ["ambient", "targeted"] },
    "query": { "type": "string", "minLength": 1 },
    "include_global": { "type": "boolean", "default": true },
    "kinds": {
      "type": "array",
      "items": { "enum": ["problem", "solution", "failed_tactic", "fact", "preference", "change"] },
      "uniqueItems": true
    },
    "limit": { "type": "integer", "minimum": 1, "maximum": 100, "default": 20 },
    "expand": {
      "type": "object",
      "properties": {
        "semantic_hops": { "type": "integer", "minimum": 0, "maximum": 3, "default": 2 },
        "include_problem_links": { "type": "boolean", "default": true },
        "include_fact_update_links": { "type": "boolean", "default": true },
        "include_association_links": { "type": "boolean", "default": true },
        "max_association_depth": { "type": "integer", "minimum": 1, "maximum": 4, "default": 2 },
        "min_association_strength": { "type": "number", "minimum": 0, "maximum": 1, "default": 0.25 }
      }
    }
  }
}
```

### `memory.read.request` field meanings

- `op`: must be `read`.
- `repo_id`: repository identifier that selects repo-local shellbrain DB.
- `mode`: `ambient` for startup pack; `targeted` for explicit mid-task lookup.
- `query`: natural-language retrieval query.
- `include_global`: whether global-scope memories are searched with repo memories.
- `kinds`: optional include-filter for shellbrain kinds.
- `limit`: max records returned before final packing.
- `expand.semantic_hops`: max similarity-association hops.
- `expand.include_problem_links`: include linked problem/attempt records.
- `expand.include_fact_update_links`: include linked fact-update chain neighbors.
- `expand.include_association_links`: include formal association-link expansion in explicit-association bucket.
- `expand.max_association_depth`: max traversal depth over formal association links.
- `expand.min_association_strength`: minimum association-link strength eligible for traversal.

## `memory.create.request`

```json
{
  "$id": "memory.create.request",
  "type": "object",
  "required": ["op", "repo_id", "memory"],
  "properties": {
    "op": { "const": "create" },
    "repo_id": { "type": "string", "minLength": 1 },
    "memory": {
      "type": "object",
      "required": ["text", "scope", "kind", "evidence_refs"],
      "properties": {
        "text": { "type": "string", "minLength": 1 },
        "scope": { "enum": ["repo", "global"] },
        "kind": { "enum": ["problem", "solution", "failed_tactic", "fact", "preference", "change"] },
        "rationale": { "type": "string" },
        "links": {
          "type": "object",
          "properties": {
            "problem_id": { "type": "string" },
            "related_memory_ids": { "type": "array", "items": { "type": "string" }, "uniqueItems": true },
            "associations": {
              "type": "array",
              "items": {
                "type": "object",
                "required": ["to_memory_id", "relation_type"],
                "properties": {
                  "to_memory_id": { "type": "string" },
                  "relation_type": { "enum": ["depends_on", "associated_with"] },
                  "confidence": { "type": "number", "minimum": 0, "maximum": 1 },
                  "salience": { "type": "number", "minimum": 0, "maximum": 1 },
                  "rationale": { "type": "string" }
                }
              }
            }
          }
        },
        "evidence_refs": { "type": "array", "minItems": 1, "items": { "type": "string" }, "uniqueItems": true }
      }
    }
  }
}
```

### `memory.create.request` field meanings

- `op`: must be `create`.
- `repo_id`: repository identifier for storage and evidence namespace.
- `memory.text`: immutable shellbrain content.
- `memory.scope`: `repo` or `global`.
- `memory.kind`: shellbrain type written to `memories.kind`.
- `memory.rationale`: optional explanation for why this shellbrain is being created.
- `memory.links.problem_id`: required when `kind` is `solution` or `failed_tactic`.
- `memory.links.related_memory_ids`: optional additional associations.
- `memory.links.associations`: optional explicit formal association links from created shellbrain to existing memories.
- `memory.evidence_refs`: required evidence references (`minItems = 1`) for all create kinds in v1; each value is a stored `episode_events.id`.

## `memory.update.request`

```json
{
  "$id": "memory.update.request",
  "type": "object",
  "required": ["op", "repo_id", "memory_id", "update"],
  "properties": {
    "op": { "const": "update" },
    "repo_id": { "type": "string", "minLength": 1 },
    "memory_id": { "type": "string" },
    "update": {
      "type": "object",
      "oneOf": [
        {
          "required": ["type", "archived"],
          "properties": {
            "type": { "const": "archive_state" },
            "archived": { "type": "boolean" },
            "rationale": { "type": "string" }
          }
        },
        {
          "required": ["type", "problem_id", "vote"],
          "properties": {
            "type": { "const": "utility_vote" },
            "problem_id": { "type": "string" },
            "vote": { "type": "number", "minimum": -1, "maximum": 1 },
            "rationale": { "type": "string" },
            "evidence_refs": { "type": "array", "items": { "type": "string" }, "uniqueItems": true }
          }
        },
        {
          "required": ["type", "old_fact_id", "new_fact_id"],
          "properties": {
            "type": { "const": "fact_update_link" },
            "old_fact_id": { "type": "string" },
            "new_fact_id": { "type": "string" },
            "rationale": { "type": "string" },
            "evidence_refs": { "type": "array", "items": { "type": "string" }, "uniqueItems": true }
          }
        },
        {
          "required": ["type", "to_memory_id", "relation_type", "evidence_refs"],
          "properties": {
            "type": { "const": "association_link" },
            "to_memory_id": { "type": "string" },
            "relation_type": { "enum": ["depends_on", "associated_with"] },
            "confidence": { "type": "number", "minimum": 0, "maximum": 1 },
            "salience": { "type": "number", "minimum": 0, "maximum": 1 },
            "rationale": { "type": "string" },
            "evidence_refs": { "type": "array", "minItems": 1, "items": { "type": "string" }, "uniqueItems": true }
          }
        }
      ]
    }
  }
}
```

### `memory.update.request` field meanings

- `op`: must be `update`.
- `repo_id`: repository identifier for the operation.
- `memory_id`: target memory.
- `update.type`:
  - `archive_state`: toggles `memories.archived`.
  - `utility_vote`: appends contextual utility observation for `(memory_id, problem_id)`.
  - `fact_update_link`: creates a `fact_updates` chain row.
  - `association_link`: upserts a formal association link from `memory_id` (from) to `update.to_memory_id` (to).
- `update.archived`: archive flag for lifecycle control.
- `update.problem_id`: problem context for utility feedback.
- `update.vote`: utility signal in `[-1, 1]` as aligned to `utility_observations.vote`.
- `update.old_fact_id`: prior fact in a fact-update chain.
- `update.new_fact_id`: replacement fact in a fact-update chain.
- `memory_id` with `fact_update_link`: this is the `change_id`.
- `update.to_memory_id`: association-link destination shellbrain ID.
- `update.relation_type`: association-link relation type (`depends_on` or `associated_with`).
- `update.rationale`: optional reason string.
- `update.evidence_refs`: required for `association_link`; optional (recommended) for other update types. When provided, each value is a stored `episode_events.id`.

## Simpler v1 profile (recommended)

To reduce interface complexity without losing core behavior:
- Keep all three ops, but use `update` only for:
  - `archive_state`
  - `utility_vote`
  - `fact_update_link`
  - `association_link`
- Represent truth change only via immutable creates + immutable linking:
  - create `change`,
  - create replacement `fact`,
  - link via `fact_update_link`.
- Treat all ranking/selection weighting as retrieval-engine internals, not interface payload parameters.

## Agent Ergonomic Profile (CLI Adapter, Ratified)

Purpose:
- Keep strict internal schemas deterministic.
- Reduce agent burden by inferring contextual fields in CLI/runtime adapter before strict validation.

Rules:
- Internal validation/store layer still receives full strict payloads.
- Agent-facing CLI can accept compact payloads and hydrate missing contextual fields.
- Explicitly provided agent fields always override inferred defaults.

Hydration rules by operation:

- `read`:
  - required from agent: `query` (optional `kinds`).
  - inferred by adapter:
    - `repo_id` from cwd/repo resolver,
    - `mode = "targeted"` for explicit CLI calls,
    - `include_global = true`,
    - `limit` default from policy config,
    - `expand.*` defaults from policy config.

- `events`:
  - required from agent: nothing.
  - optional from agent:
    - `limit` for recent-event count.
  - inferred by adapter:
    - `repo_id` from cwd/repo resolver,
    - newest repo-matching supported host session.

- `create`:
  - required from agent: `memory.kind`, `memory.text`, `memory.evidence_refs` (and `links.problem_id` when `kind` is `solution` or `failed_tactic`).
  - inferred by adapter:
    - `repo_id` from cwd/repo resolver,
    - `memory.scope = "repo"` unless explicitly set.
  - association link preference:
    - use typed `memory.links.associations[]` when explicitly linking memories.
    - untyped `memory.links.related_memory_ids` remains available but is not the preferred primary linking path for agent-authored explicit relations.

- `update`:
  - required from agent: `memory_id`, `update.type`, and type-specific required fields.
  - inferred by adapter:
    - `repo_id` from cwd/repo resolver.

## Validation Placement

A validation layer sits directly under the interface and performs:
- Schema validation: shape, types, enums, required fields.
- Semantic validation: domain constraints from storage card (for example:
  - `problem_id` kind checks,
  - fact-update link-kind checks,
  - association-link existence/scope/self-loop checks,
  - evidence requirements by kind/rule).
