# Read Policy Context-Pack v1 (RRF + Scenario Lift + Formal Association Links)

Status: ratified direction on 2026-02-21; extended with formal association-link integration on 2026-02-25.

## Intent

Make `read` pack construction concrete without forcing cross-lane raw-score calibration and without unbounded context growth.

## Definitions

- Semantic lane: vector retrieval with threshold `tau_sem`.
- Keyword lane: lexical retrieval with threshold `tau_kw`.
- Rank: 1-based position in a lane's sorted result list for the current query.
- `rank_sem(m)`: semantic-lane rank for memory `m` (missing if not retrieved).
- `rank_kw(m)`: keyword-lane rank for memory `m` (missing if not retrieved).
- Atomic memory set for seed retrieval: `problem`, `solution`, `failed_tactic`, `fact`, `change` (plus `preference` when included by request filter).
- Scenario: derived grouping over linked memories (problem-centered abstraction), not an authoritative write primitive.

## Direct-seed fusion (RRF)

For each memory `m`:

```text
rrf_score(m) =
  (w_sem / (k_rrf + rank_sem(m))) +
  (w_kw  / (k_rrf + rank_kw(m)))
```

- If `m` is missing from a lane, that lane contributes `0`.
- Suggested v1 defaults: `w_sem = 1`, `w_kw = 1`, `k_rrf = 20`.
- This score is used to rank direct seeds and to anchor expansion scoring, not as a universal final truth score.

## How scores are used for context-pack selection

Given `limit = N`:

1. Build candidate seeds:
- Retrieve top `K_sem` semantic items with `semantic_similarity >= tau_sem`.
- Retrieve top `K_kw` keyword items with `keyword_score >= tau_kw`.
- Merge by memory ID and compute `rrf_score`.

2. Select direct seeds:
- Sort merged seeds by `rrf_score DESC`.
- Take top `N_direct` for the direct bucket.

3. Expand associations from direct seeds:
- Explicit associations:
  - problem/attempt links from `problem_attempts`,
  - fact/update links from `fact_updates`,
  - formal relation links from `association_edges` (`depends_on`, `associated_with`).
- Implicit associations:
  - semantic-neighbor hops with decay.

4. Score association candidates:
- Explicit candidate from anchor seed `s` at link-distance `d`:

```text
explicit_score = rrf_score(s) * (explicit_decay ^ d) * link_type_weight * relation_strength * source_weight
```

- For non-relation explicit links (`problem_attempts`, `fact_updates`), set:
  - `relation_strength = 1`,
  - `source_weight = 1`.
- For `association_edges`, use stored edge strength and source/state-aware weighting.
- Suggested ordering behavior:
  - confirmed/agent-sourced association edges outrank tentative/implicit edges at near ties.

- Implicit candidate from anchor seed `s` at hop `h`:

```text
implicit_score = rrf_score(s) * edge_similarity * (implicit_decay ^ h)
```

5. Fill bucket quotas:
- Choose top `N_explicit` by `explicit_score`.
- Choose top `N_implicit` by `implicit_score`.
- Use mode quotas:
  - targeted: direct-heavy,
  - ambient: more association coverage.

6. Dedupe and spill:
- Dedupe by memory ID.
- If a bucket underfills, spill remaining slots to highest-scoring unselected candidates from other buckets.

7. Lift to scenarios:
- Map selected/matched atomic memories to scenarios via `scenario_members`.
- Compute scenario ranking from matched-member evidence:

```text
scenario_score = max(member_score) + scenario_support_weight * ln(1 + matched_member_count)
```

- Select top `N_scenario` scenario cards by `scenario_score`.
- Each selected scenario contributes:
  - one compact scenario summary item,
  - top supporting members not already in pack (bounded by per-scenario member cap).

8. Enforce hard cap:
- Final pack size is always `<= N`.
- Scores are used for:
  - threshold gating,
  - ranking within buckets,
  - spillover selection,
  - scenario ranking and tie-breaks.
- No separate association-read operation is introduced; association traversal is internal to this read-path expansion phase.

## Global utility stance (revised v1 direction)

- `global_utility` may still exist as derived historical metadata, but it is not part of online read ranking in v1.
- The earlier tie-break / near-tie utility-prior idea is removed as over-engineering for the current system.
- Online read ranking should remain driven by:
  - threshold gating,
  - RRF direct-seed ordering,
  - explicit/implicit expansion scoring,
  - bounded context-pack assembly.
- `global_utility` is reserved for possible offline analysis, maintenance heuristics, or future product surfaces rather than retrieval-time ordering.

## Formal association traversal policy (ratified structure)

- Association links are expanded only through existing read-policy flow (no new top-level read op).
- Traversal over `association_edges` is bounded:
  - `max_association_depth` (default suggestion: `2`, tunable),
  - per-anchor fanout cap (`max_association_fanout`, tunable),
  - minimum eligible edge strength (`min_association_strength`, tunable).
- `associated_with` is treated as associative/undirected for traversal.
- `depends_on` is treated as directional for dependency context:
  - dependency expansion follows `from -> to`,
  - dependent expansion may optionally include reverse traversal under a separate budget.

## Update-chain policy (ratified v1 direction)

For `fact_updates` expansion:
- Use bounded depth for context relevance and token control.
- Parameter: `max_update_chain_depth` (default suggestion: `3`, tunable).

## Why this design

- Avoids unstable raw-score mixing (`semantic_similarity` vs lexical score scales).
- Preserves deterministic, bounded context packing.
- Uses scenario abstraction as a higher-level retrieval lens without making scenario an authoritative storage primitive.
- Keeps a small number of tunable knobs.
- Avoids introducing a stale-helpfulness bias into online retrieval ordering.

## Write-policy dependency: scenario constructor (ratified)

- Scenario objects are constructed as a derived projection in the write path.
- On accepted create/update writes, the write path runs `scenario_constructor(affected_ids)` synchronously.
- Constructor upserts derived scenario projections (for example scenario records and scenario-member links) from authoritative memory/link tables.
- Projection failure aborts the write transaction (single commit boundary for authoritative + projection updates).
- Optional async reconciler can exist as backup, not primary v1 path.

## Open points

- Final mode quota numbers (`N_direct`, `N_explicit`, `N_implicit`, `N_scenario` by mode).
- Final default for `max_update_chain_depth` (currently suggested `3`).
- Final defaults for association traversal knobs:
  - `max_association_depth`,
  - `max_association_fanout`,
  - `min_association_strength`.
- Final defaults for relation ranking weights:
  - `relation_type_weight`,
  - `source_weight` (agent/confirmed vs implicit/tentative).
- Final scenario projection schema names/fields and constructor trigger boundaries.
