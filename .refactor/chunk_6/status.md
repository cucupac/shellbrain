## Chunk 6 Status

Status: complete.

### Files Moved/Renamed/Split

- `app/core/use_cases/agent_operations/dependencies.py` -> `app/handlers/command_context.py`
- `app/core/use_cases/agent_operations/errors.py` -> `app/handlers/result_envelopes.py`
- `app/core/use_cases/agent_operations/operation_telemetry.py` -> `app/handlers/telemetry_sink.py`
- `app/core/use_cases/agent_operations/validation.py` -> `app/handlers/internal_agent/memories/utility_vote_evidence.py`
- `app/core/use_cases/agent_operations/guidance.py` -> folded into `app/handlers/internal_agent/memories/utility_vote_evidence.py`
- `app/core/use_cases/agent_operations/events/read.py` -> `app/handlers/internal_agent/episodes/events.py`
- `app/core/use_cases/agent_operations/events_selection.py` -> `app/handlers/internal_agent/episodes/selection.py`
- `app/core/use_cases/agent_operations/serialization.py` -> `app/handlers/internal_agent/episodes/serialization.py`
- `app/core/use_cases/agent_operations/memories/add.py` -> `app/handlers/internal_agent/memories/add.py`
- `app/core/use_cases/agent_operations/memories/update.py` -> `app/handlers/internal_agent/memories/update.py`
- `app/core/use_cases/agent_operations/concepts/add.py` -> `app/handlers/internal_agent/concepts/add.py`
- `app/core/use_cases/agent_operations/concepts/update.py` -> `app/handlers/internal_agent/concepts/update.py`
- `app/core/use_cases/agent_operations/retrieval/read.py` -> `app/handlers/internal_agent/retrieval/read.py`
- `app/core/use_cases/agent_operations/retrieval/recall.py` -> `app/handlers/working_agent/recall.py`
- `app/core/use_cases/agent_operations/retrieval_execution.py` -> `app/handlers/internal_agent/retrieval/execution.py`
- `app/startup/agent_operations.py` -> `app/startup/handlers.py`
- Operation result envelopes moved out of `app/core/contracts/responses.py` and into `app/handlers/result_envelopes.py`; core now returns `UseCaseResult` payload contracts.
- Best-effort operation telemetry orchestration moved from `app/infrastructure/observability/telemetry/recorder.py` into `app/handlers/telemetry_sink.py`; infrastructure recorder now only persists prepared telemetry records.

### Importers Updated

- CLI operation endpoints now import `app.startup.handlers`.
- Operation and telemetry tests now import `app.startup.handlers`.
- Handler modules import handler helpers from `app.handlers.*`.
- Stale telemetry monkeypatches targeting `app.core.use_cases.agent_operations.flow_common` now target `app.handlers.internal_agent.retrieval.execution`.
- Memory create/update handlers now pass `dependencies.id_generator` into core use cases; direct use-case tests inject deterministic test ID generators.
- Handler modules now wrap core payloads via `ok_envelope(...)` and call `dependencies.telemetry_sink.record(...)`.
- Retrieval compatibility retries for older two-argument test doubles were removed; affected tests now accept the injected settings kwargs.
- Handler and startup wrapper signatures now use `validation_errors=()` per the worked-example convention.
- Memory semantic/reference validation now runs inside `app/core/use_cases/memories/{add.py,update.py}` via `app/core/use_cases/memories/reference_checks.py`; handlers only pass upstream protocol validation errors through and catch `DomainValidationError` envelopes.
- Concept add/update/show now raise typed `DomainValidationError` instead of raw use-case `ValueError`; concept handlers catch typed core errors.
- `app/core/use_cases/manage_session_state.py` -> `app/handlers/session_state.py`; handlers import session command orchestration from the handler layer.

### Verification

- `uvx ruff check .`: passed.
- `git diff --check`: passed.
- Old-path scan for `app.core.use_cases.agent_operations`, `app.startup.agent_operations`, and `flow_common`: no runtime hits.
- `env/bin/python -m pytest -q tests/config/test_architecture_boundaries.py`: 26 passed, 2 failed for future chunks only (`core/interfaces` and infrastructure entrypoint strings).
- Focused handler/CLI/operation suite: 74 passed, 194 skipped.
- Broad non-Docker suite: 197 passed, 299 skipped, 6 deselected, 2 failed for future chunks only (`core/interfaces` and infrastructure entrypoint strings).
- README onboarding assets: 11 passed after preserving installer/upgrade wording.

### Judgment Calls

- Kept small handler-local helpers for event selection, episode serialization, and retrieval execution under `app/handlers/internal_agent/**` to preserve behavior while deleting core command orchestration. These helpers remain inside the handler layer and do not create compatibility shims for old paths.
- Left startup endpoint side-effect reduction for Chunk 7 because the plan assigns CLI side-effect orchestration cleanup to Chunk 7; Chunk 6 now uses `app/startup/handlers.py` as the composition entry for handlers.

### Critic

Critic rounds required: 2.

Round 1: not signed off; raised core envelope ownership, telemetry sink ownership, memory ID generation, retrieval compatibility fallback, and stale guardrail concerns.
Round 2: not signed off; raised handler/startup wrapper `validation_errors=None` defaults. Fixed by changing handlers and public startup wrappers to `validation_errors=()`.
Round 3: not signed off; raised memory semantic/reference validation still running in handlers. Fixed by moving validation orchestration into core memory use cases and raising `DomainValidationError`.
Round 4: not signed off; raised untyped concept core errors and core-owned session command orchestration. Fixed by typing concept use-case/reference errors and moving `SessionStateManager` to `app/handlers/session_state.py`.
Round 5: signed off. No substantive Chunk 6 objections remain; remaining architecture failures are planned Chunk 7/8 work.
