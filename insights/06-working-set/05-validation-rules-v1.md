# Validation Rules v1

Status: partially concrete; matrix card still to be published.

## Locked so far

- Validation has three layers:
  1. schema validation
  2. semantic validation
  3. DB integrity validation
- Create evidence is strict:
  - `memory.evidence_refs` is required with `minItems >= 1`.
- Ergonomic adapter hydration checks:
  - inferred fields are applied before strict schema validation,
  - explicit agent-provided fields override inferred defaults,
  - auto-evidence attachment is permitted only with unambiguous provenance.
- Semantic kind checks are required for relational links:
  - `problem_attempts`: problem/attempt kind-role consistency
  - `fact_updates`: fact/fact/change consistency
  - `association_edges`: relation-type validity + no self-loop + source-mode validity
  - `association_link` updates: from/to existence and scope visibility checks
  - `utility_observations.problem_id`: should be kind `problem`
  - `session_transfers` event/session consistency

Sources:
- `insights/04-contracts/memory-interface-json-schemas-v1.md`
- `insights/04-contracts/memory-storage-relational-schema-v1.md`
- `insights/discovery.md` (2026-02-25 matrix refinement entry)

## Ratified pre-lock constraints

- Do not hard-enforce `global` scope restriction to `preference` yet.
- Do not hard-enforce one-successor-only fact chains in v1.
- Keep DB triggers minimal in v1 (hard invariants only).
- Final matrix must include explicit idempotency/duplicate handling.
- Final matrix must include explicit validation-stage error contract.

## Not yet locked

- Full per-op/per-kind semantic validation matrix publication.
- Error response schema and code contract (`schema_error`, `semantic_error`, `integrity_error`, `not_found`, `conflict`, etc.).
- Final trigger and promotion/demotion thresholds for implicit association edges.
