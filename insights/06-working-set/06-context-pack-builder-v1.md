# Context Pack Builder v1

Status: current v1 slice is locked around atomic-shellbrain pack assembly; scenario lift is deferred.

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
- Current v1 pack output is limited to atomic-shellbrain sections:
  - `meta`
  - `direct`
  - `explicit_related`
  - `implicit_related`
- Scenario lift is intentionally not part of the current v1 output surface.
- Fact update-chain expansion is bounded (parameterized depth).
- Association-link traversal is bounded and integrated under read-policy expansion (no separate read operation).
- If read request omits expansion knobs, runtime uses policy-config defaults before pack assembly.

Source:
- `insights/03-refinements/read-policy-context-pack-v1.md`

## Not yet locked

- Final per-mode quotas:
  - `N_direct`, `N_explicit`, `N_implicit`.
- Final default `max_update_chain_depth`.
- Final defaults for association traversal and ranking knobs.
- Future scenario projection schema, constructor trigger boundaries, and any later `N_scenario` defaults if scenario lift is reintroduced.
