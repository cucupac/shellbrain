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
- Explicit expansion bucket now includes formal association links (`association_edges`) in addition to `problem_attempts` and `fact_updates`.
- Scenario lift is included:
  - derive scenarios from matched members,
  - rank scenarios from matched-member evidence,
  - include bounded summaries/members.
- Fact update-chain expansion is bounded (parameterized depth).
- Association-link traversal is bounded and integrated under read-policy expansion (no separate read operation).
- If read request omits expansion knobs, runtime uses policy-config defaults before pack assembly.

Source:
- `insights/03-refinements/read-policy-context-pack-v1.md`

## Not yet locked

- Final per-mode quotas:
  - `N_direct`, `N_explicit`, `N_implicit`, `N_scenario`.
- Final default `max_update_chain_depth`.
- Final defaults for association traversal and ranking knobs.
- Final scenario projection schema and constructor trigger boundaries.
