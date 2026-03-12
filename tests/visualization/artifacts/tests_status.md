# Tests Status

Generated: 2026-03-12 03:26:29 PDT

## Summary

- Total: 121
- Passed: 121
- Failed: 0
- Skipped/Not Run: 0

## create/validation/link_rules

- ✅ solution memories should always include links.problem_id.
- ✅ failed_tactic memories should always include links.problem_id.
- ✅ non-attempt kinds should always reject links.problem_id.
- ✅ create association lists should always reject duplicate target+relation pairs.

## create/validation/reference_checks

- ✅ create should always reject problem references that do not exist.
- ✅ create should always reject problem references outside repo visibility.
- ✅ create should always require links.problem_id to reference a problem memory.
- ✅ create should always reject association targets outside repo visibility.

## create/validation/request_shape

- ✅ create requests should always reject unknown fields.
- ✅ create requests should always enforce unique evidence refs.
- ✅ create requests should always require at least one evidence ref.
- ✅ create requests should always reject op/repo_id at the agent interface.
- ✅ create hydration should always infer configured scope when omitted.
- ✅ create hydration should always preserve explicit scope over configured defaults.

## create/execution/association_records

- ✅ create with associations should always persist association_edge and association_observation rows.

## create/execution/effect_ordering

- ✅ create plans should always preserve deterministic effect ordering by operation type.

## create/execution/embeddings

- ✅ create should always persist a memory_embedding row in PostgreSQL when real embeddings are enabled.
- ✅ create should always persist one memory_embedding row for the new memory.
- ✅ local embedding providers should always return embeddings when sentence-transformers is available.
- ✅ local embedding providers should always fail fast when sentence-transformers is unavailable.

## create/execution/evidence_links

- ✅ create should always attach each evidence ref exactly once in memory_evidence.
- ✅ create with associations should always link evidence refs in association_edge_evidence.

## create/execution/failure_handling

- ✅ validation failures should always write nothing.
- ✅ embedding failures should always write nothing.
- ✅ mid-write side-effect failures should always roll back all prior side effects.

## create/execution/memory_records

- ✅ create(problem) should always persist one memory row and no problem_attempt row.
- ✅ create(solution) should always persist one problem_attempt row with role solution.
- ✅ create(failed_tactic) should always persist one problem_attempt row with role failed_tactic.

## read/validation/unit

- ✅ read hydration should always infer repo_id and default knobs when omitted.
- ✅ read hydration should always preserve explicit payload values over inferred defaults.
- ✅ read hydration should always merge partial expand overrides over config defaults.
- ✅ read requests should always reject unknown fields.
- ✅ read requests should always reject op values other than read.
- ✅ read requests should always require non-empty query text.
- ✅ read requests should always limit kinds filters to ratified memory kinds.
- ✅ read requests should always require unique kinds filters.
- ✅ read requests should always reject config override knobs at the agent interface.

## read/execution/context_pack

- ✅ read context pack config should always define mode-specific limits in read policy yaml.
- ✅ read context pack config should always define direct-heavy quotas by mode in read policy yaml.
- ✅ read context pack config should always load RRF defaults from the read policy yaml.
- ✅ context pack builder should always use targeted mode as eight items by default.
- ✅ context pack builder should always use ambient mode as twelve items by default.
- ✅ read context pack should always return grouped sections under data.pack.
- ✅ read context pack should always order sections as meta, direct, explicit_related, then implicit_related.
- ✅ read context pack should always assign global priority values in displayed order.
- ✅ read context pack should always include kind and text for each returned memory.
- ✅ read context pack should always include why_included for every item.
- ✅ read context pack should always include anchor_memory_id only for non-direct items.
- ✅ read context pack should always include relation_type only for association-link items.
- ✅ read context pack should always omit scenarios in this slice.
- ✅ context pack builder should always fill targeted quotas in direct-first order.
- ✅ context pack builder should always fill ambient quotas with more related context than targeted mode.
- ✅ context pack builder should always deduplicate repeated memories across sections.
- ✅ context pack builder should always let earlier sections win dedupe ties.
- ✅ context pack builder should always shrink a small custom limit in direct-first order.
- ✅ context pack builder should always use spillover when a section underfills.
- ✅ context pack builder should always pick the highest-scoring unselected candidates during spillover.
- ✅ context pack builder should always enforce the hard limit after quotas and spill.

## read/execution/determinism

- ✅ read should always return each memory at most once even if reached by multiple paths.
- ✅ read should always produce deterministic ordering for the same input and snapshot.

## read/execution/expansion

- ✅ read should always include linked problem attempts when problem-link expansion is enabled.
- ✅ read should always include linked fact updates when fact-update expansion is enabled.
- ✅ read should always include linked association neighbors only when enabled and edge strength passes threshold.
- ✅ read should always expand association neighbors only up to max_association_depth.

## read/execution/high_level_behavior

- ✅ read should always be retrieval-only and never mutate database state.
- ✅ read should always enforce repo visibility and include_global scope rules.
- ✅ read should always apply kinds as include-only filters.
- ✅ read should always enforce a hard output cap equal to limit.
- ✅ read should always return an empty pack when nothing passes retrieval gates.

## read/execution/keyword

- ✅ keyword retrieval should always admit high-coverage partial matches while rejecting low-coverage generic partial matches.
- ✅ keyword retrieval should always be stricter for ambient reads than for targeted reads.
- ✅ keyword retrieval should always rank denser shorter matches ahead of verbose matches.
- ✅ keyword retrieval should always gate the visible lexical corpus before scoring.
- ✅ keyword retrieval should always break equal-score ties by memory identifier.

## read/execution/scoring

- ✅ read scoring should always preserve RRF ordering for fused direct seeds.
- ✅ read scoring should always rank a dual-lane hit above single-lane hits.
- ✅ read scoring should always break equal RRF scores by memory identifier.
- ✅ read scoring should always rank shallower explicit candidates above deeper ones.
- ✅ read scoring should always rank stronger association edges above weaker ones.
- ✅ read scoring should always ignore relation strength for non-association explicit links.
- ✅ read scoring should always rank higher-similarity implicit candidates above lower ones.
- ✅ read scoring should always rank lower-hop implicit candidates above higher-hop ones.
- ✅ read scoring should always return raw explicit metadata for downstream scoring.
- ✅ read scoring should always return raw implicit metadata for downstream scoring.
- ✅ read scoring should always order competing expanded candidates via the scoring stage.

## read/execution/semantic

- ✅ read should always return semantic seed matches when lexical retrieval misses.
- ✅ read should always apply repo visibility, include_global, and kinds filters before admitting semantic matches.
- ✅ read should always fuse semantic and keyword direct hits without duplicating shared memories.
- ✅ read should always expand implicit semantic neighbors only up to semantic_hops depth.
- ✅ read should always keep semantic ordering deterministic for the same input and snapshot.
- ✅ read should always exclude archived memories from direct retrieval and all expansion paths.
- ✅ read should always return visible semantic matches through the real semantic lane when lexical retrieval misses.
- ✅ read should always apply archived, repo visibility, include_global, and kinds filters in the real semantic lane.
- ✅ read should always expand semantic neighbors through the real semantic lane only up to semantic_hops depth.
- ✅ read should always return semantic direct matches through the live query-embedding seam when lexical retrieval misses.
- ✅ read should always fuse live semantic seeds with keyword direct hits without duplicates.
- ✅ read should always surface query-embedding failure as a structured read error rather than silently dropping the semantic lane.

## update/validation/failure_handling

- ✅ rejected update requests should always write nothing.

## update/validation/hydration

- ✅ update hydration should always infer repo_id when omitted.
- ✅ update hydration should always preserve explicit repo_id over inferred defaults.

## update/validation/link_rules

- ✅ association_link updates should always reject self-links.
- ✅ fact_update_link updates should always require distinct fact endpoints and reserve memory_id for the change memory.

## update/validation/reference_checks

- ✅ update requests should always require memory_id to reference a visible memory.
- ✅ utility_vote updates should always require problem_id to reference a visible problem memory.
- ✅ fact_update_link updates should always require visible fact endpoints and memory_id to reference a visible change memory.
- ✅ fact_update_link updates should always require fact endpoints and a change-memory target.
- ✅ association_link updates should always require to_memory_id to reference a visible memory.

## update/validation/request_shape

- ✅ update requests should always reject unrecognized update.type values.
- ✅ update requests should always reject op/repo_id at the agent interface.

## update/execution/failure_handling

- ✅ problem_attempt rows should always reject identical problem_id and attempt_id values.
- ✅ fact_update rows should always reject identical old_fact_id and new_fact_id values.
- ✅ fact_update rows should always reject change_id values that equal old_fact_id or new_fact_id.
- ✅ episode rows should always reject ended_at values earlier than started_at.
- ✅ session_transfer rows should always reject identical from_episode_id and to_episode_id values.
- ✅ failed update execution should always roll back every partial write.

## update/execution/high_level_behavior

- ✅ archiving a memory should always change only its archived flag.
- ✅ non-archiving updates should always leave the original memory row unchanged.

## update/execution/record_writes

- ✅ update(utility_vote) commit should always append one utility_observation with the provided payload.
- ✅ update(fact_update_link) commit should always append one fact_update with change_id equal to memory_id.
- ✅ update(association_link) commit should always persist edge, observation, and edge evidence links.
- ✅ each update type should always write only its own kind of related record.
