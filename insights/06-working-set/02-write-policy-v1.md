# Create and Update Policy v1

Status: locked at high level; final semantic matrix details still pending.

## Locked

- Routing:
  - `create` -> Create Policy
  - `update` -> Update Policy
- Ordered gates:
  1. schema validity
  2. semantic validity
  3. DB integrity validity
- Atomicity:
  - accepted create/update requests commit in one transaction or fully abort.
- Strict create evidence:
  - `evidence_refs >= 1` for all create kinds.
- Explicit evidence workflow:
  - agents query `events` to inspect the current active episode,
  - agents choose one or more stored `episode_events.id` values as `evidence_refs`,
  - adapter does not auto-attach evidence in v1.
- Deterministic side effects:
  - `create(problem|fact|preference|change)` -> `memories` (+ evidence links)
  - `create(solution|failed_tactic)` -> `memories` + `problem_attempts` (+ evidence links)
  - `create(... with links.associations[])` -> association-edge upserts + edge-evidence links (+ immutable association observations)
  - `update(archive_state)` -> `memories.archived`
  - `update(utility_vote)` -> `utility_observations`
  - `update(fact_update_link)` -> `fact_updates`
  - `update(association_link)` -> association-edge upsert + immutable association observation (+ edge-evidence links)
- Association write channels:
  - explicit agent links via interface (`create.links.associations[]` and `update.association_link`),
  - implicit reinforcement via session-end co-activation consolidator (internal channel).
- Association source discipline in v1:
  - implicit channel creates/reinforces only `associated_with`,
  - typed dependency links (`depends_on`) are agent-authored.

Sources:
- `insights/discovery.md` (2026-02-19, 2026-02-25 entries)
- `insights/04-contracts/memory-interface-json-schemas-v1.md`
- `insights/04-contracts/memory-storage-relational-schema-v1.md`

## Not yet locked

- Final published per-kind semantic validation matrix.
- Idempotency/duplicate behavior policy.
- Final trigger cadence for implicit association consolidation (session-end only vs additional periodic runs).
- Future alias policy if interface operation names ever change.
