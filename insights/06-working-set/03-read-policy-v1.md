# Read Policy v1

Status: locked structure, open numeric defaults.

## Locked

- Dual-lane retrieval:
  - semantic lane + keyword lane.
- Seed fusion via RRF.
- Score use is bounded to pack assembly behavior:
  - gating,
  - ranking,
  - spillover ordering.
- `global_utility` is not used in online read ranking in v1; the earlier tie-break idea was dropped as over-engineering.
- Expansion types:
  - explicit link expansion (`problem_attempts`, `fact_updates`)
  - explicit formal association-link expansion (`association_edges`)
  - implicit semantic-neighbor expansion.

Source:
- `insights/03-refinements/read-policy-context-pack-v1.md`

## Not yet locked

- Final defaults for association traversal knobs (`max_association_depth`, `max_association_fanout`, `min_association_strength`).
- Final defaults for relation/source weighting in explicit bucket ranking.
