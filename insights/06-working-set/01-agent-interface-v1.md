# Agent Interface v1

Status: mostly locked.

## Locked

- External interface verbs are `create`, `read`, `update`.
- `create` writes immutable memory records and evidence/link records.
- `read` is retrieval only.
- `update` is lifecycle/feedback only (`archive_state`, `utility_vote`, `fact_update_link`).
- Naming lock is `create` (not `write`) and `episodes` (not `work_sessions`).

## Current request schemas

- `memory.read.request`
- `memory.create.request`
- `memory.update.request`

Source:
- `insights/04-contracts/memory-interface-json-schemas-v1.md`

## Not yet locked

- Response/error schemas for each operation.
- Backward compatibility behavior for legacy payloads that used `op: "write"`.
