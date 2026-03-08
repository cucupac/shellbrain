# Tests Status

Generated: 2026-03-08 03:01:27 PDT

## Summary

- Total: 84
- Passed: 84
- Failed: 0
- Skipped/Not Run: 0

## read/validation

- ✅ read hydration should always infer repo_id and default knobs when omitted.
- ✅ read hydration should always preserve explicit payload values over inferred defaults.
- ✅ read requests should always reject unknown fields.
- ✅ read requests should always reject op values other than read.
- ✅ read requests should always require non-empty query text.
- ✅ read requests should always limit kinds filters to ratified memory kinds.
- ✅ read requests should always require unique kinds filters.
- ✅ read requests should always enforce limit and expansion knob bounds.

## read/execution

- ✅ read should always be retrieval-only and never mutate database state.
- ✅ read should always enforce repo visibility and include_global scope rules.
- ✅ read should always apply kinds as include-only filters.
- ✅ read should always enforce a hard output cap equal to limit.
- ✅ read should always return an empty pack when nothing passes retrieval gates.
- ✅ read should always include linked problem attempts when problem-link expansion is enabled.
- ✅ read should always include linked fact updates when fact-update expansion is enabled.
- ✅ read should always include linked association neighbors only when enabled and edge strength passes threshold.
- ✅ keyword retrieval should always admit high-coverage partial matches while rejecting low-coverage generic partial matches.
- ✅ keyword retrieval should always be stricter for ambient reads than for targeted reads.
- ✅ keyword retrieval should always rank denser shorter matches ahead of verbose matches.
- ✅ keyword retrieval should always gate the visible lexical corpus before scoring.
- ✅ keyword retrieval should always break equal-score ties by memory identifier.
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
- ✅ read should always return each memory at most once even if reached by multiple paths.
- ✅ read should always produce deterministic ordering for the same input and snapshot.

## update/validation

- ✅ update requests should always require memory_id to reference a visible memory.
- ✅ utility_vote updates should always require problem_id to reference a visible problem memory.
- ✅ fact_update_link updates should always require visible fact endpoints and memory_id to reference a visible change memory.
- ✅ association_link updates should always require to_memory_id to reference a visible memory.
- ✅ rejected update requests should always write nothing.
- ✅ update hydration should always infer repo_id and default commit mode when omitted.
- ✅ update hydration should always preserve explicit repo_id and mode over inferred defaults.
- ✅ association_link updates should always reject self-links.
- ✅ fact_update_link updates should always require distinct fact endpoints and reserve memory_id for the change memory.

## update/execution

- ✅ preview-only updates should always describe the writes they would make and then make no writes.
- ✅ archiving a memory should always change only its archived flag.
- ✅ non-archiving updates should always leave the original memory row unchanged.
- ✅ each update type should always write only its own kind of related record.
- ✅ failed update execution should always roll back every partial write.

## write/validation

- ✅ create should always reject problem references that do not exist.
- ✅ create should always reject problem references outside repo visibility.
- ✅ create should always require links.problem_id to reference a problem memory.
- ✅ create should always reject association targets outside repo visibility.
- ✅ validation failures should always write nothing.
- ✅ embedding failures should always write nothing.
- ✅ utility_vote updates should always require a visible problem reference.
- ✅ utility_vote updates should always require problem_id to reference a problem memory.
- ✅ fact_update_link updates should always require fact endpoints and a change-memory target.
- ✅ association_link updates should always reject targets outside repo visibility.
- ✅ create requests should always reject unknown fields.
- ✅ update requests should always reject unrecognized update.type values.
- ✅ update requests should always reject op values other than update.
- ✅ create requests should always enforce confidence bounds and unique evidence refs.
- ✅ create requests should always require at least one evidence ref.
- ✅ solution memories should always include links.problem_id.
- ✅ failed_tactic memories should always include links.problem_id.
- ✅ non-attempt kinds should always reject links.problem_id.
- ✅ create association lists should always reject duplicate target+relation pairs.
- ✅ association_link updates should always reject self-links.
- ✅ fact_update_link updates should always require different old_fact_id and new_fact_id.

## write/execution

- ✅ create(problem) should always persist one memory row and no problem_attempt row.
- ✅ create(solution) should always persist one problem_attempt row with role solution.
- ✅ create(failed_tactic) should always persist one problem_attempt row with role failed_tactic.
- ✅ create should always persist one memory_embedding row for the new memory.
- ✅ create should always attach each evidence ref exactly once in memory_evidence.
- ✅ create with associations should always persist association_edge and association_observation rows.
- ✅ create with associations should always link evidence refs in association_edge_evidence.
- ✅ mid-write side-effect failures should always roll back all prior side effects.
- ✅ update(archive_state) commit should always change archived state and preserve other memory fields.
- ✅ update(utility_vote) commit should always append one utility_observation with the provided payload.
- ✅ update(fact_update_link) commit should always append one fact_update with change_id equal to memory_id.
- ✅ update(association_link) commit should always persist edge, observation, and edge evidence links.
- ✅ update(dry_run) should always return planned_side_effects and write nothing.
- ✅ write plans should always preserve deterministic effect ordering by operation type.
