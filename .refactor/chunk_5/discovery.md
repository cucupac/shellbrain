## Chunk 5 Discovery

Date: 2026-05-08

Scope: concepts contracts, concept core use cases, concept relation policy, concept CLI preparation/endpoints, concept operation wrappers, and concept tests. This note was written before source mutation.

## Source Modules To Mutate

### `app/core/contracts/concepts.py`

Summary:
- Defines concept action payloads and the mode-based `ConceptCommandRequest`.
- Owns concept schema literals and inline evidence validation.
- Must become distinct add/update/show contracts with no `mode="apply"` command.

Importers and references:
- `app/startup/agent_operations.py:7` imports `ConceptCommandRequest`.
- `app/startup/agent_operations.py:108` annotates `handle_concept`.
- `app/entrypoints/cli/protocol/operation_requests.py:8` imports `ConceptCommandRequest`.
- `app/entrypoints/cli/protocol/operation_requests.py:194` returns `PreparedOperationRequest[ConceptCommandRequest]`.
- `app/entrypoints/cli/protocol/payload_validation.py:7` imports `ConceptCommandRequest`.
- `app/entrypoints/cli/protocol/payload_validation.py:237` validates `ConceptCommandRequest`.
- `app/core/use_cases/concepts/apply_concept_changes.py:11` imports concept actions and `ConceptCommandRequest`.
- `app/core/use_cases/agent_operations/concepts/apply.py:8` imports `ConceptCommandRequest`.

Test references:
- `tests/operations/concepts/validation/test_concept_contracts.py:3` validates concept schema.
- `tests/operations/concepts/execution/test_concept_use_case.py:5` imports `ConceptCommandRequest`.
- `tests/operations/concepts/execution/test_concept_use_case.py:50,104,132,133` constructs mode-based command requests.
- `tests/operations/read/execution/concepts/test_concept_aware_read.py:8,191,243` constructs mode-based command requests.

### `app/core/use_cases/concepts/apply_concept_changes.py`

Summary:
- Dispatches `mode="apply"` and `mode="show"`.
- Mixes concept creation/update, repo-backed reference checks, pure relation rules, containment traversal, serialization views, and direct `uuid4()` generation.
- Must be deleted and split into add/update/show/reference/containment/views modules.

Importers and references:
- `app/core/use_cases/agent_operations/concepts/apply.py:15` imports `execute_concept_command`.
- `tests/operations/concepts/execution/test_concept_use_case.py:7` imports `execute_concept_command`.
- `tests/operations/read/execution/concepts/test_concept_aware_read.py:11` imports `execute_concept_command`.

Test references:
- `tests/operations/concepts/execution/test_concept_use_case.py:36,49,86,88,125` calls `execute_concept_command`.
- `tests/operations/read/execution/concepts/test_concept_aware_read.py:190,242` calls `execute_concept_command`.

### `app/core/policies/concepts/relation_rules.py` (new)

Summary:
- New pure policy module for relation shape and contains-cycle decisions over already-loaded concepts/edges.
- No current importers before mutation.

Planned importers:
- `app/core/use_cases/concepts/update.py`
- `app/core/use_cases/concepts/containment_checks.py`

### `app/core/interfaces/repos.py`

Summary:
- Defines `IConceptsRepo`, currently with `upsert_concept`.
- Concept add/update need explicit create/update operations to avoid upsert semantics in core use cases.
- Retrieval also imports `IConceptsRepo`, so non-concept methods must remain stable.

Importers and references:
- `app/core/interfaces/unit_of_work.py:6,8,28` imports and exposes `IConceptsRepo`.
- `app/infrastructure/db/repos/relational/concepts_repo.py:36,50` implements `IConceptsRepo`.
- `app/core/use_cases/retrieval/read_concepts.py:10,24,83,135,164,311` uses `IConceptsRepo`.
- Other repo interfaces in this file are imported by DB adapters and retrieval modules but are not part of Chunk 5.

Concept method references:
- `app/core/use_cases/concepts/apply_concept_changes.py:78` calls `uow.concepts.upsert_concept`.
- `app/core/use_cases/concepts/apply_concept_changes.py:198` calls `uow.concepts.upsert_anchor`.
- `app/core/use_cases/retrieval/read_concepts.py:109,141` calls `get_concept_bundle`.

Test references:
- Concept and read integration tests exercise the concrete repo through `PostgresUnitOfWork`; no direct test import of `IConceptsRepo`.

### `app/infrastructure/db/repos/relational/concepts_repo.py`

Summary:
- Concrete DB adapter for concept graph persistence.
- Currently implements `upsert_concept`; needs explicit add/update methods while preserving natural-key idempotency for relation/claim/anchor/link records.

Importers and references:
- `app/infrastructure/db/uow.py:8,46` imports and instantiates `ConceptsRepo`.
- Implements `IConceptsRepo` from `app/core/interfaces/repos.py:94`.

Test references:
- `tests/operations/concepts/execution/*` exercise concept table writes through `PostgresUnitOfWork`.
- `tests/operations/read/execution/concepts/test_concept_aware_read.py` exercises concept rows through read expansion.

### `app/core/use_cases/agent_operations/concepts/apply.py`

Summary:
- Current concept operation wrapper catches validation/core errors, records telemetry, and calls `execute_concept_command`.
- File stem starts with `apply`; Chunk 5 acceptance and guardrail require no apply files under core use cases.
- Must be deleted and replaced with distinct add/update wrappers.

Importers and references:
- `app/startup/agent_operations.py:19` imports `run_concept_changes_operation`.
- `app/startup/agent_operations.py:117` calls `run_concept_changes_operation`.

Test references:
- `tests/operations/concepts/execution/test_concept_cli_handler.py` exercises concept startup handler.
- CLI surface tests indirectly dispatch concept add/update routes.

### `app/startup/agent_operations.py`

Summary:
- Composition helper currently exposes one `handle_concept` path.
- Must expose distinct concept add/update handler paths that inject `OperationDependencies.id_generator`.

Importers and references:
- Operation CLI endpoints import `handle_create`, `handle_read`, `handle_recall`, `handle_events`, and `handle_update`.
- `tests/operations/concepts/execution/test_concept_cli_handler.py:6` imports `handle_concept`.

Concept-specific references:
- `app/entrypoints/cli/endpoints/internal_agent/concepts/add.py:9,18` imports/calls `handle_concept`.
- `tests/operations/concepts/execution/test_concept_cli_handler.py:18,47,60` calls `handle_concept`.

### `app/entrypoints/cli/protocol/operation_requests.py`

Summary:
- Prepares typed requests from raw CLI payloads.
- Current `prepare_concept_request` hydrates and validates the single concept command.
- Must provide distinct add/update/show preparation paths as needed.

Importers and references:
- `app/entrypoints/cli/endpoints/internal_agent/concepts/add.py:8,17` imports/calls `prepare_concept_request`.
- Other operation endpoints import the non-concept prepare functions and should remain unchanged.

Test references:
- Concept CLI handler and CLI surface tests indirectly cover concept preparation.

### `app/entrypoints/cli/protocol/payload_validation.py`

Summary:
- Imports `ConceptCommandRequest` and validates concept payloads with `validate_concept_schema`.
- Must validate distinct add/update/show contracts while preserving non-concept validators.

Importers and references:
- `app/entrypoints/cli/protocol/operation_requests.py:25,26,198` imports/calls `validate_concept_schema`.
- `tests/operations/concepts/validation/test_concept_contracts.py:3,9,41,65,81` imports/calls `validate_concept_schema`.
- Read/create/update/events tests import other validators from this module and should not be disturbed.

### `app/entrypoints/cli/protocol/hydration.py`

Summary:
- Hydrates raw payloads with inferred repo IDs.
- Current `hydrate_concept_payload` is shared by the single concept path.
- Must hydrate add/update/show concept payloads without requiring `mode`.

Importers and references:
- `app/entrypoints/cli/protocol/operation_requests.py:18,19,197` imports/calls `hydrate_concept_payload`.
- Non-concept hydration tests import other hydration helpers and should remain unchanged.

### `app/entrypoints/cli/endpoints/internal_agent/concepts/add.py`

Summary:
- Current concept add endpoint prepares the single concept command and calls the single startup handler.
- Must call concept add preparation and handler path.

Importers and references:
- `app/entrypoints/cli/main.py:146` imports this endpoint for `concept:add`.
- `app/entrypoints/cli/endpoints/internal_agent/concepts/update.py:8` currently imports and delegates to this endpoint; this must be removed.

Test references:
- `tests/config/test_cli_surface.py` covers concept parser/route surface.
- Concept CLI handler tests exercise startup handling.

### `app/entrypoints/cli/endpoints/internal_agent/concepts/update.py`

Summary:
- Current concept update endpoint delegates to concept add.
- Must call concept update preparation and handler path directly.

Importers and references:
- `app/entrypoints/cli/main.py:150` imports this endpoint for `concept:update`.

Test references:
- `tests/config/test_cli_surface.py` covers concept parser/route surface.

### `app/entrypoints/cli/parser/__init__.py`

Summary:
- Concept help still documents `mode=apply`, `mode=show`, and `upsert_concept`.
- Must teach distinct add/update payloads without apply/upsert language.

Importers and references:
- `app/entrypoints/cli/main.py:12,31` imports/calls `build_parser`.
- `tests/config/test_architecture_boundaries.py:10,91,98` imports/calls `build_parser`.
- `tests/config/test_cli_surface.py:10,192,254` imports/calls parser/main helpers.
- `tests/config/test_onboarding_assets.py:7` imports parser docs.

## Test Files To Update Or Split

### `tests/operations/concepts/execution/test_concept_use_case.py`

Summary:
- One test file currently covers apply, idempotency, invalid relation shape, and show.
- Refactor plan requires tests to split along add/update/show boundaries.

Old references:
- Imports `ConceptCommandRequest` and `execute_concept_command`.
- Uses `mode="apply"`, `mode="show"`, and `type="upsert_concept"`.

Planned replacement files:
- `tests/operations/concepts/execution/test_concept_add_use_case.py`
- `tests/operations/concepts/execution/test_concept_update_use_case.py`
- `tests/operations/concepts/execution/test_concept_show_use_case.py`

### `tests/operations/concepts/execution/test_concept_cli_handler.py`

Summary:
- Tests one startup handler accepting raw concept dicts.
- Must use typed/prepared distinct add/update handlers or endpoint paths.

Old references:
- Imports `handle_concept`.
- Uses `mode="apply"`, `mode="show"`, and `type="upsert_concept"`.

### `tests/operations/concepts/validation/test_concept_contracts.py`

Summary:
- Tests single concept command validation.
- Must test add/update/show validators and strict action payloads.

Old references:
- Imports `validate_concept_schema`.
- Uses `mode="apply"`, `mode="show"`, and `type="upsert_concept"`.

### `tests/operations/read/execution/concepts/test_concept_aware_read.py`

Summary:
- Read tests seed concepts through the old apply command.
- Must seed via add/update use cases or request contracts without touching read expectations.

Old references:
- Imports `ConceptCommandRequest` and `execute_concept_command`.
- Uses `mode="apply"` and `type="upsert_concept"`.

### `tests/config/test_cli_surface.py`

Summary:
- Concept parser test payloads still use `mode="show"`.
- Must use current add/update payload shape and keep add/update command assertions.

## Discovery Commands Used

- `rg -n "app\\.core\\.contracts\\.concepts|ConceptCommandRequest|UpsertConceptAction|AddRelationAction|AddClaimAction|UpsertAnchorAction|AddGroundingAction|LinkMemoryAction|ConceptShowIncludeValue" app tests scripts architectures .refactor -g '*.py' -g '*.md'`
- `rg -n "app\\.core\\.use_cases\\.concepts\\.apply_concept_changes|execute_concept_command|apply_concept_changes" app tests scripts architectures .refactor -g '*.py' -g '*.md'`
- `rg -n "app\\.core\\.use_cases\\.agent_operations\\.concepts\\.apply|run_concept_changes_operation" app tests scripts architectures .refactor -g '*.py' -g '*.md'`
- `rg -n "handle_concept\\b|prepare_concept_request|validate_concept_schema|hydrate_concept_payload" app tests scripts architectures .refactor -g '*.py' -g '*.md'`
- `rg -n "app\\.core\\.interfaces\\.repos|IConceptsRepo|upsert_concept\\b|get_concept_by_ref|list_contains_edges|add_relation\\b|add_claim\\b|upsert_anchor\\b|add_grounding\\b|add_memory_link\\b|add_evidence\\b|get_concept_bundle" app tests -g '*.py'`
- `rg -n "app\\.infrastructure\\.db\\.repos\\.relational\\.concepts_repo|ConceptsRepo\\b" app tests -g '*.py'`
- `rg -n "app\\.entrypoints\\.cli\\.endpoints\\.internal_agent\\.concepts\\.add|concepts\\.add import|concepts\\.update|concept add|concept update|mode\\\":\\\"apply|mode\\\": \\\"apply|upsert_concept|mode\\\":\\\"show|mode\\\": \\\"show" app tests docs onboarding_assets README.md architectures .refactor -g '*.py' -g '*.md' -g '*.txt'`
- `rg -n "uuid4\\(|from uuid import uuid4|app\\.core\\.policies\\.concepts\\.search|list_contains_edges" app/core/use_cases/concepts app/core/policies/concepts tests/config/test_architecture_boundaries.py -g '*.py'`
