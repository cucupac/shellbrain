# Write Policy v1

Status: locked at high level; final semantic matrix details still pending.

## Locked

- Routing:
  - `create` -> Write Policy
  - `update` -> Write Policy
- Ordered gates:
  1. schema validity
  2. semantic validity
  3. DB integrity validity
- Atomicity:
  - accepted write-path requests commit in one transaction or fully abort.
- Strict create evidence:
  - `evidence_refs >= 1` for all create kinds.
- Deterministic side effects:
  - `create(problem|fact|preference|change)` -> `memories` (+ evidence links)
  - `create(solution|failed_tactic)` -> `memories` + `problem_attempts` (+ evidence links)
  - `update(archive_state)` -> `memories.archived`
  - `update(utility_vote)` -> `utility_observations`
  - `update(fact_update_link)` -> `fact_updates`

Sources:
- `insights/discovery.md` (2026-02-19, 2026-02-25 entries)
- `insights/04-contracts/memory-interface-json-schemas-v1.md`
- `insights/04-contracts/memory-storage-relational-schema-v1.md`

## Not yet locked

- Final published per-kind semantic validation matrix.
- Idempotency/duplicate behavior policy.
- Compatibility rules for legacy naming (`write` payloads).
