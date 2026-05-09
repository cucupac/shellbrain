# Chunk 3 Discovery

Scope: memory domain refactor only. This note records importers and direct tests for every module this chunk mutates, before any source moves or import updates.

## `app/core/entities/memory.py`

Summary:
- Defines `MemoryKind`, mature-kind helpers, `MemoryScope`, and the immutable `Memory` record.
- Imported by core repo interfaces, memory planning/execution, validation, retrieval/concept reads, settings, DB repository, and memory-oriented tests.
- Will be renamed to `app/core/entities/memories.py`; importers must update in the same chunk.

Importers:
- `app/core/entities/settings.py:9`
- `app/core/interfaces/repos.py:21`
- `app/core/policies/memory_create_policy/plan.py:16`
- `app/core/use_cases/concepts/apply_concept_changes.py:43`
- `app/core/use_cases/memory_retrieval/read_concepts.py:9`
- `app/core/use_cases/plan_execution.py:11`
- `app/core/validation/memory_integrity.py:12`
- `app/core/validation/memory_semantic.py:11`
- `app/infrastructure/db/repos/relational/memories_repo.py:9`
- `tests/operations/_shared/integration_db_fixtures.py:19`
- `tests/operations/concepts/execution/test_concept_use_case.py:6`
- `tests/operations/create/execution/association_records/test_create_association_records.py:6`
- `tests/operations/create/execution/evidence_links/test_create_evidence_links.py:8`
- `tests/operations/create/execution/memory_records/test_create_memory_records.py:6`
- `tests/operations/create/validation/reference_checks/test_create_reference_checks.py:5`
- `tests/operations/read/execution/concepts/test_concept_aware_read.py:10`
- `tests/operations/read/execution/conftest.py:13`
- `tests/operations/telemetry/execution/operation_invocations/test_operation_invocation_record_writes.py:10`
- `tests/operations/telemetry/execution/write_summaries/test_write_summary_record_writes.py:7`
- `tests/operations/update/execution/failure_handling/test_update_failure_handling.py:7`
- `tests/operations/update/execution/high_level_behavior/test_update_high_level_behavior.py:5`
- `tests/operations/update/execution/record_writes/test_update_record_writes.py:5`
- `tests/operations/update/validation/failure_handling/test_update_validation_failure_handling.py:5`
- `tests/operations/update/validation/reference_checks/test_update_reference_checks.py:6`

Direct tests:
- Same test importers above directly reference `Memory`, `MemoryKind`, or `MemoryScope`.
- No dedicated entity-only test file exists before this chunk.

## `app/core/validation/memory_semantic.py`

Summary:
- Defines pure create/update semantic checks for problem links, duplicate association pairs, self-links, fact endpoint distinctness, and batch utility-vote problem consistency.
- Depends only on contracts and `MemoryKind`; no repository access.
- Will move to `app/core/policies/memories/link_rules.py`.

Importers:
- `app/core/use_cases/agent_operations/validation.py:8`
- `tests/operations/create/validation/link_rules/test_create_link_rules.py:4`
- `tests/operations/update/validation/link_rules/test_update_link_rules.py:4`

Direct tests:
- `tests/operations/create/validation/link_rules/test_create_link_rules.py`
- `tests/operations/update/validation/link_rules/test_update_link_rules.py`

## `app/core/validation/memory_integrity.py`

Summary:
- Defines repository-backed reference checks for visible memories, problem/fact/change kind requirements, evidence event visibility, and `matures_into` constraints.
- Depends on `IUnitOfWork`, memory entities, and request contracts.
- Will move to `app/core/use_cases/memories/reference_checks.py`.

Importers:
- `app/core/use_cases/agent_operations/validation.py:7`
- `tests/operations/update/validation/reference_checks/test_update_reference_checks.py:8`

Direct tests:
- `tests/operations/create/validation/reference_checks/test_create_reference_checks.py` exercises create reference checks through `handle_create`.
- `tests/operations/update/validation/reference_checks/test_update_reference_checks.py` imports `validate_update_integrity` directly.

## `app/core/use_cases/memories/create_memory.py`

Summary:
- Orchestrates an already-validated memory create request over unit of work, embedding provider, and ID generator.
- Allocates plan IDs, calls the pure create plan, executes side effects, and returns an `OperationResult`.
- Will be renamed to `app/core/use_cases/memories/add.py`.

Importers:
- `app/core/use_cases/agent_operations/memories/add.py:21`
- `tests/operations/create/execution/association_records/test_create_association_records.py:8`
- `tests/operations/create/execution/embeddings/test_create_embedding_persistence.py:13`
- `tests/operations/create/execution/embeddings/test_create_embedding_records.py:7`
- `tests/operations/create/execution/evidence_links/test_create_evidence_links.py:10`
- `tests/operations/create/execution/failure_handling/test_create_failure_handling.py:9`
- `tests/operations/create/execution/memory_records/test_create_memory_records.py:8`

Direct tests:
- All create execution test importers listed above.

## `app/core/use_cases/memories/update_memory.py`

Summary:
- Orchestrates already-validated single and batch memory updates over unit of work and ID generator.
- Allocates plan IDs, calls the pure update plan, executes side effects, and returns an `OperationResult`.
- Will be renamed to `app/core/use_cases/memories/update.py`.

Importers:
- `app/core/use_cases/agent_operations/memories/update.py:24`
- `tests/operations/update/execution/failure_handling/test_update_failure_handling.py:8`
- `tests/operations/update/execution/high_level_behavior/test_update_high_level_behavior.py:6`
- `tests/operations/update/execution/record_writes/test_update_record_writes.py:6`

Direct tests:
- All update execution test importers listed above.

## `app/core/policies/memory_create_policy/plan.py`

Summary:
- Builds deterministic typed side-effect plans for memory create.
- Pure policy code that consumes already-validated payload dictionaries and preallocated IDs.
- Will move to `app/core/policies/memories/add_plan.py`.

Importers:
- `app/core/use_cases/memories/create_memory.py:11`
- `tests/operations/create/execution/effect_ordering/test_create_effect_ordering.py:4`

Direct tests:
- `tests/operations/create/execution/effect_ordering/test_create_effect_ordering.py`

## `app/core/policies/memory_update_policy/plan.py`

Summary:
- Builds deterministic typed side-effect plans for memory update.
- Pure policy code that consumes already-validated payload dictionaries and preallocated IDs.
- Will move to `app/core/policies/memories/update_plan.py`.

Importers:
- `app/core/use_cases/memories/update_memory.py:10`

Direct tests:
- `tests/operations/update/execution/record_writes/test_update_record_writes.py`
- `tests/operations/update/execution/failure_handling/test_update_failure_handling.py`
- `tests/operations/update/execution/high_level_behavior/test_update_high_level_behavior.py`

## Package paths removed by this chunk

- `app/core/policies/memory_create_policy/__init__.py`
- `app/core/policies/memory_update_policy/__init__.py`
- `app/core/validation/__init__.py`

These package initializers have no direct importers in `rg` output. They will be removed because the chunk forbids the old policy paths and all `app.core.validation` imports.
