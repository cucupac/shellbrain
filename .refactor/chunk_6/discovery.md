## Chunk 6 Discovery

### Modules Mutated

- `app/core/use_cases/agent_operations/*`: current command orchestration package for memory add/update, retrieval read/recall, events, concepts, validation, telemetry context, guidance, serialization, and dependency bundle.
- `app/startup/agent_operations.py`: composition helper that wires concrete runtime dependencies into the operation runners and exposes public handler functions.
- CLI operation endpoints under `app/entrypoints/cli/endpoints/**`: import startup operation handlers.
- Operation tests under `tests/operations/**`: import startup operation handlers and in a few cases monkeypatch old operation internals.

### Importers

Raw importer scan before mutation:

```text
tests/operations/create/validation/reference_checks/test_create_reference_checks.py:6:from app.startup.agent_operations import handle_create
tests/operations/guidance/execution/update_batch/test_batch_utility_votes.py:5:from app.startup.agent_operations import handle_events, handle_update
app/startup/agent_operations.py:18:from app.core.use_cases.agent_operations.concepts.add import run_concept_add_operation
app/startup/agent_operations.py:19:from app.core.use_cases.agent_operations.concepts.update import run_concept_update_operation
app/startup/agent_operations.py:22:from app.core.use_cases.agent_operations.dependencies import OperationDependencies
app/startup/agent_operations.py:23:from app.core.use_cases.agent_operations.events.read import run_read_events_operation
app/startup/agent_operations.py:24:from app.core.use_cases.agent_operations.memories.add import run_create_memory_operation
app/startup/agent_operations.py:25:from app.core.use_cases.agent_operations.memories.update import run_update_memory_operation
app/startup/agent_operations.py:28:from app.core.use_cases.agent_operations.retrieval.read import run_read_memory_operation
app/startup/agent_operations.py:29:from app.core.use_cases.agent_operations.retrieval.recall import run_recall_memory_operation
tests/operations/create/execution/failure_handling/test_create_failure_handling.py:10:from app.startup.agent_operations import handle_create
tests/operations/guidance/execution/create_solution/test_pending_utility_guidance.py:5:from app.startup.agent_operations import handle_create, handle_events, handle_read
tests/operations/guidance/execution/failure_handling/test_guidance_failures.py:5:from app.startup.agent_operations import handle_update
tests/operations/update/validation/failure_handling/test_update_validation_failure_handling.py:6:from app.startup.agent_operations import handle_update
tests/operations/session_state/execution/create/test_problem_tracking.py:5:from app.startup.agent_operations import handle_create, handle_events
tests/operations/session_state/execution/events/test_events_session_state.py:5:from app.startup.agent_operations import handle_events
tests/operations/concepts/execution/test_concept_cli_handler.py:7:from app.startup.agent_operations import handle_concept_add, handle_concept_update
tests/operations/events/execution/failure_handling/test_events_failure_handling.py:8:from app.startup.agent_operations import handle_events
tests/operations/_shared/docker_persistence_fixtures.py:23:from app.startup.agent_operations import handle_create
tests/operations/read/execution/semantic/test_read_execution_semantic_wiring.py:10:from app.startup.agent_operations import handle_read
tests/operations/events/execution/high_level_behavior/test_events_high_level_behavior.py:9:from app.startup.agent_operations import handle_events
tests/operations/telemetry/execution/recall_summaries/test_recall_summary_record_writes.py:11:from app.startup.agent_operations import handle_recall
tests/operations/telemetry/execution/operation_invocations/test_operation_invocation_record_writes.py:12:from app.startup.agent_operations import handle_create, handle_events, handle_read, handle_update
tests/operations/persistence/execution/local_migration/test_local_postgres_migration_to_shellbrain.py:19:from app.startup.agent_operations import handle_create
tests/operations/telemetry/execution/write_summaries/test_write_summary_record_writes.py:9:from app.startup.agent_operations import handle_create, handle_update
tests/operations/telemetry/execution/read_summaries/test_read_summary_record_writes.py:11:from app.startup.agent_operations import handle_read
tests/operations/telemetry/execution/read_summaries/test_read_summary_record_writes.py:175:monkeypatch old app.core.use_cases.agent_operations.flow_common path
tests/operations/telemetry/execution/failure_handling/test_failed_invocation_telemetry.py:10:from app.startup.agent_operations import handle_create, handle_events, handle_read, handle_update
tests/operations/telemetry/execution/failure_handling/test_failed_invocation_telemetry.py:165:monkeypatch app.startup.agent_operations.normalize_host_transcript
tests/operations/telemetry/execution/failure_handling/test_failed_invocation_telemetry.py:203:monkeypatch old app.core.use_cases.agent_operations.flow_common path
tests/operations/telemetry/execution/episode_sync_runs/test_episode_sync_run_record_writes.py:12:from app.startup.agent_operations import handle_events
app/entrypoints/cli/endpoints/working_agent/recall.py:9:from app.startup.agent_operations import handle_recall
app/entrypoints/cli/endpoints/internal_agent/events.py:9:from app.startup.agent_operations import handle_events
app/entrypoints/cli/endpoints/internal_agent/read.py:9:from app.startup.agent_operations import handle_read
app/entrypoints/cli/endpoints/internal_agent/memories/add.py:10:from app.startup.agent_operations import handle_create
app/entrypoints/cli/endpoints/internal_agent/concepts/add.py:9:from app.startup.agent_operations import handle_concept_add
app/entrypoints/cli/endpoints/internal_agent/memories/update.py:9:from app.startup.agent_operations import handle_update
app/entrypoints/cli/endpoints/internal_agent/concepts/update.py:11:from app.startup.agent_operations import handle_concept_update
```

### Test Files Referencing Mutated Modules

- Create/update operation tests under `tests/operations/create/**` and `tests/operations/update/**`.
- Read/recall tests under `tests/operations/read/**`, `tests/operations/recall/**`, and telemetry read/recall summary tests.
- Events/session-state/guidance tests under `tests/operations/events/**`, `tests/operations/session_state/**`, and `tests/operations/guidance/**`.
- Concept handler tests under `tests/operations/concepts/execution/test_concept_cli_handler.py`.
- Persistence fixtures/tests that seed through handler functions.
- Telemetry operation invocation, failure, read/write/recall/episode-sync tests.

### Cross-cutting Concerns

- Handler tests still import `app.startup.agent_operations`; Chunk 6 must move these imports to `app.startup.handlers` in the same chunk.
- Telemetry failure tests monkeypatch old core/internal paths; these need to target the new handler modules.
- `OperationDependencies` is not a core dependency bundle after this chunk; it belongs in handler command context.
- `errors.py` and `operation_telemetry.py` provide result envelopes and telemetry context behavior and should move under named handler modules.

### Session State Follow-up

Importer scan before moving session command orchestration out of core:

```text
app/handlers/internal_agent/memories/add.py:23:from app.core.use_cases.manage_session_state import SessionStateManager
app/handlers/internal_agent/memories/update.py:27:from app.core.use_cases.manage_session_state import SessionStateManager
app/handlers/internal_agent/retrieval/read.py:22:from app.core.use_cases.manage_session_state import SessionStateManager
app/handlers/internal_agent/episodes/events.py:29:from app.core.use_cases.manage_session_state import SessionStateManager
app/handlers/working_agent/recall.py:22:from app.core.use_cases.manage_session_state import SessionStateManager
tests/operations/session_state/execution/expiry/test_idle_expiry.py:4:from app.core.use_cases.manage_session_state import SessionStateManager
```

Cross-cutting concern: `SessionStateManager` mutates per-caller command session state and is used only by handlers/session-state tests after command orchestration moves, so it belongs in the handler layer for Chunk 6 acceptance.
