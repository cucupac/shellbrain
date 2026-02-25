# Context Pack Builder v1

Status: structure locked, quota/default tuning still open.

## Locked

- Candidate seeds come from semantic + keyword lanes with threshold gates.
- RRF ranks merged direct seeds.
- Bucketed selection flow:
  - direct bucket,
  - explicit expansion bucket,
  - implicit expansion bucket,
  - dedupe + spill,
  - hard final cap.
- Scenario lift is included:
  - derive scenarios from matched members,
  - rank scenarios from matched-member evidence,
  - include bounded summaries/members.
- Fact update-chain expansion is bounded (parameterized depth).
- Global utility is weak late-stage tie-break signal only.

Source:
- `insights/03-refinements/read-policy-context-pack-v1.md`

## Not yet locked

- Final per-mode quotas:
  - `N_direct`, `N_explicit`, `N_implicit`, `N_scenario`.
- Final default `max_update_chain_depth`.
- Final scenario projection schema and constructor trigger boundaries.
