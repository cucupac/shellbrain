# Chunk 4 Discovery: Retrieval

Source references read before mutation:
- `architectures/refactor.md`
- `.refactor/baseline/import-map.md`

## Modules to Move or Rename

Use cases:
- `app/core/use_cases/memory_retrieval/__init__.py` -> `app/core/use_cases/retrieval/__init__.py`
- `app/core/use_cases/memory_retrieval/context_pack_pipeline.py` -> `app/core/use_cases/retrieval/context_pack_pipeline.py`
- `app/core/use_cases/memory_retrieval/expansion.py` -> `app/core/use_cases/retrieval/expansion.py`
- `app/core/use_cases/memory_retrieval/read_concepts.py` -> `app/core/use_cases/retrieval/read_concepts.py`
- `app/core/use_cases/memory_retrieval/read_memory.py` -> `app/core/use_cases/retrieval/read.py`
- `app/core/use_cases/memory_retrieval/recall_memory.py` -> `app/core/use_cases/retrieval/recall.py`
- `app/core/use_cases/memory_retrieval/seed_retrieval.py` -> `app/core/use_cases/retrieval/seed_retrieval.py`

Policies:
- `app/core/policies/memory_read_policy/__init__.py` -> `app/core/policies/retrieval/__init__.py`
- `app/core/policies/memory_read_policy/README.md` -> `app/core/policies/retrieval/README.md`
- `app/core/policies/memory_read_policy/bm25.py` -> `app/core/policies/retrieval/bm25.py`
- `app/core/policies/memory_read_policy/context_pack_builder.py` -> `app/core/policies/retrieval/context_pack.py`
- `app/core/policies/memory_read_policy/expansion.py` -> `app/core/policies/retrieval/expansion.py`
- `app/core/policies/memory_read_policy/fusion_rrf.py` -> `app/core/policies/retrieval/fusion_rrf.py`
- `app/core/policies/memory_read_policy/lexical_query.py` -> `app/core/policies/retrieval/lexical_query.py`
- `app/core/policies/memory_read_policy/scoring.py` -> `app/core/policies/retrieval/scoring.py`

Contracts:
- Read/recall request classes currently live in `app/core/contracts/requests.py`.
- Chunk 4 should introduce `app/core/contracts/retrieval.py` and update read/recall imports to use it.

## Current Module Summaries

- `context_pack_pipeline.py`: orchestrates seed retrieval, RRF fusion, expansion, scoring, and context pack assembly.
- `expansion.py`: orchestrates explicit and implicit expansion via read policy repos.
- `read_concepts.py`: appends concept context to read packs based on read expand controls.
- `read_memory.py`: public read use-case entry point returning an `OperationResult` with a pack.
- `recall_memory.py`: public recall use-case entry point implemented as a targeted read wrapper.
- `seed_retrieval.py`: retrieves semantic and keyword seed candidates using thresholds.
- `bm25.py`: pure BM25 scoring and lexical admission helpers.
- `context_pack_builder.py`: pure context-pack assembly, quotas, dedupe, and hard limit logic.
- `expansion.py` policy: pure explicit expansion neighbor selection.
- `fusion_rrf.py`: pure reciprocal-rank fusion.
- `lexical_query.py`: pure lexical normalization and tokenization.
- `scoring.py`: pure scoring of direct, explicit, and implicit buckets.

## Importers and Test References

Raw discovery commands:
- `rg -n "app\\.core\\.use_cases\\.memory_retrieval|core\\.use_cases\\.memory_retrieval|memory_retrieval" . --glob '*.py' --glob '*.md' --glob '!**/__pycache__/**'`
- `rg -n "app\\.core\\.policies\\.memory_read_policy|core\\.policies\\.memory_read_policy|memory_read_policy|context_pack_builder" . --glob '*.py' --glob '*.md' --glob '!**/__pycache__/**'`
- `rg -n "MemoryReadRequest|MemoryRecallRequest|ReadExpandRequest|ReadConceptsExpandRequest" app tests --glob '*.py'`

### `memory_retrieval` Package References

- `app/core/use_cases/memory_retrieval/recall_memory.py:11` imports `read_memory`.
- `app/core/use_cases/memory_retrieval/read_memory.py:7` imports `context_pack_pipeline`.
- `app/core/use_cases/memory_retrieval/read_memory.py:8` imports `read_concepts`.
- `app/core/use_cases/memory_retrieval/context_pack_pipeline.py:11` imports `expansion`.
- `app/core/use_cases/memory_retrieval/context_pack_pipeline.py:12` imports `seed_retrieval`.
- `app/core/use_cases/agent_operations/retrieval_execution.py:7` imports `recall_memory`.
- `app/core/use_cases/agent_operations/retrieval_execution.py:8` imports `read_memory`.
- `tests/config/test_thresholds_usage.py:3` imports `seed_retrieval.retrieve_seeds`.
- `tests/config/test_thresholds_usage.py:32` monkeypatches `seed_retrieval.get_threshold_settings`.
- `tests/operations/read/execution/keyword/test_read_execution_keyword.py:6` imports `seed_retrieval.retrieve_seeds`.
- `tests/operations/read/execution/scoring/test_read_execution_scoring.py:8` imports `expansion.expand_candidates`.
- `tests/operations/read/execution/scoring/test_read_execution_scoring.py:11` imports `read_memory.execute_read_memory`.
- `tests/operations/read/execution/scoring/test_read_execution_scoring.py:311` monkeypatches `context_pack_pipeline.retrieve_seeds`.
- `tests/operations/read/execution/scoring/test_read_execution_scoring.py:315` monkeypatches `context_pack_pipeline.fuse_with_rrf`.
- `tests/operations/read/execution/scoring/test_read_execution_scoring.py:329` monkeypatches `context_pack_pipeline.expand_candidates`.
- `tests/operations/read/execution/semantic/test_read_execution_semantic_real_repo.py:5` imports `expansion.expand_candidates`.
- `tests/operations/read/execution/semantic/test_read_execution_semantic_wiring.py:9` imports `read_memory.execute_read_memory`.
- `tests/operations/read/execution/semantic/test_read_execution_semantic_wiring.py:146` monkeypatches `read_memory.build_context_pack`.
- `tests/operations/read/execution/semantic/test_read_execution_semantic.py:7` imports `read_memory.execute_read_memory`.
- `tests/operations/read/execution/concepts/test_concept_aware_read.py:12` imports `read_memory.execute_read_memory`.
- `tests/operations/read/execution/concepts/test_concept_aware_read.py:292` monkeypatches `read_memory.build_context_pack`.
- `tests/operations/read/execution/expansion/test_read_execution_expansion.py:5` imports `read_memory.execute_read_memory`.
- `tests/operations/read/execution/determinism/test_read_execution_determinism.py:5` imports `read_memory.execute_read_memory`.
- `tests/operations/read/execution/high_level_behavior/test_read_execution_behavior.py:5` imports `read_memory.execute_read_memory`.
- `tests/operations/read/execution/context_pack/test_context_pack_json_shape.py:8` imports `read_memory.execute_read_memory`.
- `tests/operations/read/execution/context_pack/test_context_pack_json_shape.py:149` monkeypatches `context_pack_pipeline.retrieve_seeds`.
- `tests/operations/read/execution/context_pack/test_context_pack_json_shape.py:153` monkeypatches `context_pack_pipeline.fuse_with_rrf`.
- `tests/operations/read/execution/context_pack/test_context_pack_json_shape.py:166` monkeypatches `context_pack_pipeline.expand_candidates`.
- `tests/operations/read/execution/context_pack/test_context_pack_json_shape.py:192` monkeypatches `context_pack_pipeline.score_candidates`.
- `tests/operations/telemetry/execution/read_summaries/test_read_summary_record_writes.py:221` monkeypatches `context_pack_pipeline.retrieve_seeds`.
- `tests/operations/telemetry/execution/read_summaries/test_read_summary_record_writes.py:225` monkeypatches `context_pack_pipeline.fuse_with_rrf`.
- `tests/operations/telemetry/execution/read_summaries/test_read_summary_record_writes.py:240` monkeypatches `context_pack_pipeline.expand_candidates`.
- `tests/operations/telemetry/execution/read_summaries/test_read_summary_record_writes.py:268` monkeypatches `context_pack_pipeline.score_candidates`.
- `tests/operations/telemetry/execution/operation_invocations/test_operation_invocation_record_writes.py:259` monkeypatches `context_pack_pipeline.retrieve_seeds`.
- `tests/operations/telemetry/execution/operation_invocations/test_operation_invocation_record_writes.py:263` monkeypatches `context_pack_pipeline.fuse_with_rrf`.
- `tests/operations/telemetry/execution/operation_invocations/test_operation_invocation_record_writes.py:278` monkeypatches `context_pack_pipeline.expand_candidates`.
- `tests/operations/telemetry/execution/operation_invocations/test_operation_invocation_record_writes.py:297` monkeypatches `context_pack_pipeline.score_candidates`.
- `tests/operations/telemetry/execution/recall_summaries/test_recall_summary_record_writes.py:221` monkeypatches `recall_memory.execute_read_memory`.

Non-import string references that are not Chunk 4 package references:
- `migrations/versions/20260414_0010_model_usage_telemetry.py:78` mentions SQL view `usage_memory_retrieval`.
- `migrations/versions/20260318_0006_usage_telemetry_schema.py:164` mentions SQL view `usage_memory_retrieval`.
- `app/infrastructure/db/models/views.py:39` creates SQL view `usage_memory_retrieval`.
- `tests/operations/telemetry/execution/derived_views/test_usage_views.py:36`, `:42`, `:46`, `:48` mention SQL view `usage_memory_retrieval`.

### `memory_read_policy` Package References

- `app/core/use_cases/memory_retrieval/context_pack_pipeline.py:8` imports `context_pack_builder.assemble_context_pack`.
- `app/core/use_cases/memory_retrieval/context_pack_pipeline.py:9` imports `fusion_rrf.fuse_with_rrf`.
- `app/core/use_cases/memory_retrieval/context_pack_pipeline.py:10` imports `scoring.score_candidates`.
- `app/core/use_cases/memory_retrieval/expansion.py:7` imports policy expansion selectors.
- `app/core/use_cases/memory_retrieval/seed_retrieval.py:8` imports `bm25`.
- `app/core/use_cases/memory_retrieval/seed_retrieval.py:9` imports `lexical_query`.
- `app/core/policies/memory_read_policy/README.md:24` documents `memory_retrieval/seed_retrieval.py`.
- `tests/operations/read/execution/scoring/test_read_execution_scoring.py:9` imports `fusion_rrf.fuse_with_rrf`.
- `tests/operations/read/execution/scoring/test_read_execution_scoring.py:10` imports `scoring.score_candidates`.
- `tests/operations/read/execution/context_pack/test_context_pack_config_defaults.py:5` imports `context_pack_builder.assemble_context_pack`.
- `tests/operations/read/execution/context_pack/test_context_pack_rules.py:3` imports `context_pack_builder.assemble_context_pack`.
- `tests/config/test_architecture_boundaries.py:259` forbids DB adapters importing `memory_read_policy.bm25`.
- `tests/config/test_architecture_boundaries.py:260` forbids DB adapters importing `memory_read_policy.lexical_query`.
- `tests/config/test_architecture_boundaries.py:261` forbids DB adapters importing `memory_read_policy.scoring`.

### Read and Recall Contract References

- `app/core/contracts/requests.py:21` defines `ReadConceptsExpandRequest`.
- `app/core/contracts/requests.py:58` defines `ReadExpandRequest`.
- `app/core/contracts/requests.py:70` defines `MemoryReadRequest`.
- `app/core/contracts/requests.py:97` defines `MemoryRecallRequest`.
- `app/startup/agent_operations.py:13` imports `MemoryReadRequest`.
- `app/startup/agent_operations.py:14` imports `MemoryRecallRequest`.
- `app/core/use_cases/agent_operations/retrieval/read.py:9` imports `MemoryReadRequest`.
- `app/core/use_cases/agent_operations/retrieval/recall.py:9` imports `MemoryRecallRequest`.
- `app/core/use_cases/memory_retrieval/read_concepts.py:7` imports `MemoryReadRequest` and `ReadConceptsExpandRequest`.
- `app/core/use_cases/memory_retrieval/read_memory.py:3` imports `MemoryReadRequest`.
- `app/core/use_cases/memory_retrieval/recall_memory.py:7` imports `MemoryReadRequest` and `MemoryRecallRequest`.
- `app/core/observability/telemetry/operation_records.py:27` imports `MemoryReadRequest`.
- `app/core/observability/telemetry/operation_records.py:28` imports `MemoryRecallRequest`.
- `app/entrypoints/cli/protocol/operation_requests.py:14` imports `MemoryReadRequest`.
- `app/entrypoints/cli/protocol/operation_requests.py:15` imports `MemoryRecallRequest`.
- `app/entrypoints/cli/protocol/payload_validation.py:15` imports `MemoryRecallRequest`.
- `app/entrypoints/cli/protocol/payload_validation.py:16` imports `MemoryReadRequest`.
- `app/entrypoints/cli/protocol/payload_validation.py:17` imports `ReadConceptsExpandRequest`.
- `tests/operations/read/_execution_helpers.py:3` imports `MemoryReadRequest`.
- `tests/operations/read/execution/scoring/test_read_execution_scoring.py:7` imports `MemoryReadRequest`.
- `tests/operations/read/execution/context_pack/test_context_pack_json_shape.py:7` imports `MemoryReadRequest`.
- `tests/operations/read/execution/semantic/test_read_execution_semantic.py:5` imports `MemoryReadRequest`.

## Focused Tests to Update or Run

- `tests/operations/read`
- `tests/operations/recall`
- `tests/operations/telemetry/execution/read_summaries/test_read_summary_record_writes.py`
- `tests/operations/telemetry/execution/recall_summaries/test_recall_summary_record_writes.py`
- `tests/operations/telemetry/execution/operation_invocations/test_operation_invocation_record_writes.py`
- `tests/config/test_thresholds_usage.py`
- `tests/config/test_architecture_boundaries.py`

