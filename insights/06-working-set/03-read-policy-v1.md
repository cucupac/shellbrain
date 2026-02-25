# Read Policy v1

Status: locked structure, open numeric defaults.

## Locked

- Dual-lane retrieval:
  - semantic lane + keyword lane.
- Seed fusion via RRF.
- Score use is bounded to pack assembly behavior:
  - gating,
  - ranking,
  - spillover ordering,
  - scenario ranking/tie-break.
- Expansion types:
  - explicit link expansion (`problem_attempts`, `fact_updates`)
  - implicit semantic-neighbor expansion.
- Global utility prior is weak and late-stage only:
  - never threshold gate,
  - never rescue irrelevant memories,
  - near-tie/tie-break nudger only.

Source:
- `insights/03-refinements/read-policy-context-pack-v1.md`

## Not yet locked

- Final defaults for `lambda_utility`, near-tie band width, final `alpha_utility`.
- Whether near-tie policy is shared or mode-specific (`ambient` vs `targeted`).
