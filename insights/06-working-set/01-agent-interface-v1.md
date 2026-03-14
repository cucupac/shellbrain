# Agent Interface v1

Status: mostly locked.

## Locked

- External interface verbs are `create`, `read`, `update`, `events`.
- `create` writes immutable memory records and evidence/link records.
- `read` is retrieval only.
- `update` covers lifecycle/feedback/linkage (`archive_state`, `utility_vote`, `fact_update_link`, `association_link`).
- No separate `association.read` operation exists; formal association traversal is integrated into read-policy context-pack expansion.
- Naming lock is `create` (not `write`) and `episodes` (not `work_sessions`).
- Two-layer interface is ratified:
  - strict internal contract (full payload, deterministic validation),
  - ergonomic CLI adapter (contextual field hydration before strict validation).

## Agent required vs inferred fields (ergonomic adapter)

- `read`:
  - agent supplies: `query` (optional `kinds` filter).
  - adapter infers: `repo_id`, `mode`, `include_global`, `limit`, `expand` defaults.

- `events`:
  - agent supplies: optional `limit`.
  - adapter infers: `repo_id` and the newest repo-matching supported host session.

- `create`:
  - agent supplies: `memory.kind`, `memory.text`, `memory.evidence_refs` (plus `links.problem_id` when required by kind).
  - adapter infers: `repo_id`, default `scope`.

- `update`:
  - agent supplies: `memory_id`, `update.type`, and type-specific required fields, including explicit `update.evidence_refs` where required.
  - adapter infers: `repo_id`.

- explicit override rule:
  - agent-provided values take precedence over inferred defaults.

## Current request schemas

- `memory.read.request`
- `memory.events.request`
- `memory.create.request`
- `memory.update.request`

Source:
- `insights/04-contracts/memory-interface-json-schemas-v1.md`

## Not yet locked

- Response/error schemas for each operation.
- Final defaults for new read expansion knobs related to formal associations.
- Future alias policy if interface operation names ever change.
