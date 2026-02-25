# DB Schema v1

Status: locked schema card with a few open policy-level details.

## Locked

- Relational SQLite v1.
- Core immutable tables:
  - `memories`
  - `problem_attempts`
  - `fact_updates`
  - `utility_observations`
  - `episodes`
  - `episode_events`
  - `session_transfers`
  - `evidence_refs`
  - `memory_evidence`
- `memories` uses `create_confidence`.
- Derived views:
  - `current_fact_snapshot`
  - `global_utility`
- No mutable truth score in v1.

Source:
- `insights/04-contracts/memory-storage-relational-schema-v1.md`

## Not yet locked

- Canonical `episode_events.content` payload shape (data contract, not table existence).
- Canonical `evidence_refs.ref` pointer string format.
- Final compatibility/migration policy for legacy naming if needed.
