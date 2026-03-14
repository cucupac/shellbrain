# DB Schema v1

Status: locked schema card with a few open policy-level details.

## Locked

- Relational PostgreSQL 16 v1 (+ pgvector + PostgreSQL FTS).
- Core immutable tables:
  - `memories`
  - `problem_attempts`
  - `fact_updates`
  - `association_edges`
  - `association_observations`
  - `utility_observations`
  - `episodes`
  - `episode_events`
  - `session_transfers`
  - `evidence_refs`
- `memory_evidence`
- `association_edge_evidence`
- Derived views:
  - `current_fact_snapshot`
  - `global_utility`
  - direct dependency/dependent count views
- No mutable truth score in v1.
- `evidence_refs.episode_event_id` stores the canonical FK-backed event pointer; `ref` remains as a compatibility mirror.

Source:
- `insights/04-contracts/memory-storage-relational-schema-v1.md`

## Not yet locked

- Canonical `episode_events.content` payload shape (data contract, not table existence).
- Canonical compatibility policy for `evidence_refs.ref` once all writers are event-backed.
- Final defaults for association strength update function parameters.
- Final compatibility/migration policy for legacy naming if needed.
