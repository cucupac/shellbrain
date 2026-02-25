# Memory Interface JSON Schemas v1

Status: aligned with storage v1 and ratified naming locks on 2026-02-25.

This card records the `read` / `create` / `update` interface semantics and exact JSON schemas aligned to:
- `04-contracts/memory-storage-relational-schema-v1.md`
- immutable memory records + link tables
- contextual utility observations
- no mutable truth score in v1

## Operation Semantics

- `read`: retrieval only.
- `create`: creates immutable memory records and immutable link/evidence records.
- `update`: lifecycle and feedback updates only (no mutable truth score).
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
        "include_fact_update_links": { "type": "boolean", "default": true }
      }
    }
  }
}
```

### `memory.read.request` field meanings

- `op`: must be `read`.
- `repo_id`: repository identifier that selects repo-local memory DB.
- `mode`: `ambient` for startup pack; `targeted` for explicit mid-task lookup.
- `query`: natural-language retrieval query.
- `include_global`: whether global-scope memories are searched with repo memories.
- `kinds`: optional include-filter for memory kinds.
- `limit`: max records returned before final packing.
- `expand.semantic_hops`: max similarity-association hops.
- `expand.include_problem_links`: include linked problem/attempt records.
- `expand.include_fact_update_links`: include linked fact-update chain neighbors.

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
      "required": ["text", "scope", "kind", "confidence", "evidence_refs"],
      "properties": {
        "text": { "type": "string", "minLength": 1 },
        "scope": { "enum": ["repo", "global"] },
        "kind": { "enum": ["problem", "solution", "failed_tactic", "fact", "preference", "change"] },
        "confidence": { "type": "number", "minimum": 0, "maximum": 1 },
        "rationale": { "type": "string" },
        "links": {
          "type": "object",
          "properties": {
            "problem_id": { "type": "string" },
            "related_memory_ids": { "type": "array", "items": { "type": "string" }, "uniqueItems": true }
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
- `memory.text`: immutable memory content.
- `memory.scope`: `repo` or `global`.
- `memory.kind`: memory type written to `memories.kind`.
- `memory.confidence`: create-time confidence for audit and debugging (stored as `memories.create_confidence`).
- `memory.rationale`: optional explanation for why this memory is being created.
- `memory.links.problem_id`: required when `kind` is `solution` or `failed_tactic`.
- `memory.links.related_memory_ids`: optional additional associations.
- `memory.evidence_refs`: required evidence references (`minItems = 1`) for all create kinds in v1.

## `memory.update.request`

```json
{
  "$id": "memory.update.request",
  "type": "object",
  "required": ["op", "repo_id", "memory_id", "mode", "update"],
  "properties": {
    "op": { "const": "update" },
    "repo_id": { "type": "string", "minLength": 1 },
    "memory_id": { "type": "string" },
    "mode": { "enum": ["dry_run", "commit"] },
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
- `mode`: `dry_run` validates and previews; `commit` persists.
- `update.type`:
  - `archive_state`: toggles `memories.archived`.
  - `utility_vote`: appends contextual utility observation for `(memory_id, problem_id)`.
  - `fact_update_link`: creates a `fact_updates` chain row.
- `update.archived`: archive flag for lifecycle control.
- `update.problem_id`: problem context for utility feedback.
- `update.vote`: utility signal in `[-1, 1]` as aligned to `utility_observations.vote`.
- `update.old_fact_id`: prior fact in a fact-update chain.
- `update.new_fact_id`: replacement fact in a fact-update chain.
- `memory_id` with `fact_update_link`: this is the `change_id`.
- `update.rationale`: optional reason string.
- `update.evidence_refs`: optional evidence pointers (recommended, not always required).

## Simpler v1 profile (recommended)

To reduce interface complexity without losing core behavior:
- Keep all three ops, but use `update` only for:
  - `archive_state`
  - `utility_vote`
  - `fact_update_link`
- Represent truth change only via immutable creates + immutable linking:
  - create `change`,
  - create replacement `fact`,
  - link via `fact_update_link`.
- Treat all ranking/selection weighting as retrieval-engine internals, not interface payload parameters.

## Validation Placement

A validation layer sits directly under the interface and performs:
- Schema validation: shape, types, enums, required fields.
- Semantic validation: domain constraints from storage card (for example:
  - `problem_id` kind checks,
  - fact-update link-kind checks,
  - evidence requirements by kind/rule).
