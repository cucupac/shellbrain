# Chunk 8 Discovery: Ports and Protocol Cleanup

## Ownership Boundary

- Chunk 8 owns `app/core/interfaces -> app/core/ports`, splitting repository ports, moving telemetry write protocols out of core, and splitting CLI operation protocol request preparation.
- Chunk 7 is running in parallel and owns startup/entrypoint side-effect cleanup. This chunk will avoid startup mechanics except import updates required by moved ports/protocol modules.
- The worktree is already heavily modified by other chunks. Existing uncommitted files are treated as user/parallel-agent state and must not be reverted.

## Target Modules Before Mutation

- `app/core/interfaces/`
  - Files: `clock.py`, `config.py`, `embeddings.py`, `idgen.py`, `metrics.py`, `repos.py`, `retrieval.py`, `session_state_store.py`, `unit_of_work.py`, `__init__.py`.
  - Also contains generated `__pycache__` files, which must not keep the old directory alive.
- `app/core/interfaces/repos.py`
  - Current catch-all repository port file:
    - memory/write domain: `IMemoriesRepo`, `IExperiencesRepo`, `IAssociationsRepo`, `IUtilityRepo`, `IEvidenceRepo`
    - concept domain: `IConceptsRepo`
    - episode domain: `IEpisodesRepo`
    - retrieval capabilities: `ISemanticRetrievalRepo`, `IKeywordRetrievalRepo`, `IReadPolicyRepo`
    - telemetry persistence/query: `ITelemetryRepo`
  - Bounded split target:
    - domain repository ports under core ports by domain: memory, concepts, episodes
    - retrieval repository ports under core ports as retrieval capabilities
    - pending-utility guidance query as a small core guidance port because `app/core/use_cases/build_guidance.py` consumes it
    - append-heavy telemetry repository protocol outside core under infrastructure observability telemetry
- `app/core/interfaces/unit_of_work.py`
  - Imports all repo ports from `repos.py`, exposes repository attributes, `telemetry`, and vector search.
  - Needs to import split core ports and expose only the core guidance query port, not append-heavy telemetry write protocol.
- `app/core/interfaces/metrics.py`
  - Core metrics dashboard use case consumes renderer/artifact/browser ports; this is a core port, not telemetry persistence.
- `app/entrypoints/cli/protocol/operation_requests.py`
  - Current protocol catch-all request preparation file:
    - memory add/update: `prepare_create_request`, `prepare_update_request`
    - retrieval: `prepare_read_request`, `prepare_recall_request`
    - episodes: `prepare_events_request`
    - concepts: `prepare_concept_add_request`, `prepare_concept_update_request`, `prepare_concept_show_request`
    - shared `PreparedOperationRequest` and `_hydrate_or_error`
  - Split target:
    - `memories.py`
    - `concepts.py`
    - `retrieval.py`
    - `episodes.py`
    - no old-path re-export shim and no `operation_requests.py`

## Importers Found

Raw commands:

- `rg -n "app\\.core\\.interfaces|core\\.interfaces|from app\\.core\\.interfaces|import app\\.core\\.interfaces" app tests scripts`
- `rg -n "operation_requests|prepare_(create|read|recall|events|update|concept_add|concept_update|concept_show)_request|PreparedOperationRequest" app tests scripts`
- `rg -n "\\.telemetry|uow\\.telemetry|telemetry:" app/core app/handlers app/infrastructure app/startup tests`

### Core Interfaces Importers

- `app/handlers/command_context.py`: clock/id/session-state ports.
- `app/handlers/session_state.py`: clock/session-state ports.
- `app/handlers/telemetry_sink.py`: clock port.
- `app/settings/loader.py`: config port.
- `app/startup/embeddings.py`: embedding port.
- `app/infrastructure/runtime/system_clock.py`: clock port.
- `app/infrastructure/runtime/uuid_generator.py`: id port.
- `app/infrastructure/local_state/session_state_file_store.py`: session-state store port.
- `app/infrastructure/embeddings/local_provider.py`: embedding port.
- `app/infrastructure/embeddings/query_vector_search.py`: embedding and vector-search ports.
- `app/infrastructure/db/uow.py`: unit-of-work and vector-search ports.
- `app/infrastructure/observability/telemetry/recorder.py`: unit-of-work port for telemetry writes.
- `app/infrastructure/db/repos/relational/*_repo.py`: repository ports from `repos.py`.
- `app/infrastructure/db/repos/semantic/*_repo.py`: retrieval repository ports from `repos.py`.
- `app/core/use_cases/memories/*`: embedding/id/unit-of-work ports.
- `app/core/use_cases/concepts/*`: id/unit-of-work ports.
- `app/core/use_cases/retrieval/*`: unit-of-work, repository, and vector-search ports.
- `app/core/use_cases/metrics/generate_dashboard.py`: metrics dashboard ports.
- `app/core/use_cases/build_guidance.py`: currently imports `ITelemetryRepo` only for `list_pending_utility_candidates`.
- `app/core/use_cases/plan_execution.py`: embedding and unit-of-work ports.
- `app/core/use_cases/sync_episode.py`: unit-of-work port.

### CLI Protocol Importers

- `app/entrypoints/cli/endpoints/internal_agent/memories/add.py`: `prepare_create_request`
- `app/entrypoints/cli/endpoints/internal_agent/memories/update.py`: `prepare_update_request`
- `app/entrypoints/cli/endpoints/internal_agent/read.py`: `prepare_read_request`
- `app/entrypoints/cli/endpoints/working_agent/recall.py`: `prepare_recall_request`
- `app/entrypoints/cli/endpoints/internal_agent/events.py`: `prepare_events_request`
- `app/entrypoints/cli/endpoints/internal_agent/concepts/add.py`: `prepare_concept_add_request`
- `app/entrypoints/cli/endpoints/internal_agent/concepts/update.py`: `prepare_concept_update_request`

### Telemetry Port Importers

- `app/infrastructure/observability/telemetry/recorder.py` writes append-heavy telemetry through `uow.telemetry`.
- `app/handlers/telemetry_sink.py` calls telemetry recorder helpers.
- `app/infrastructure/process/episode_poller.py` and `app/startup/model_usage_backfill.py` call telemetry recorder helpers.
- `app/handlers/internal_agent/memories/utility_vote_evidence.py` passes `guidance_uow.telemetry` into core guidance.
- `app/core/use_cases/build_guidance.py` only needs `list_pending_utility_candidates`, so the core port should be a narrow guidance query instead of the full telemetry write repo.
- `app/infrastructure/db/repos/relational/telemetry_repo.py` implements both append-heavy telemetry writes and the pending-utility candidate query.

## Tests To Update Or Run

- Required gate:
  - `env/bin/python -m pytest tests/config/test_architecture_boundaries.py tests/config/test_cli_surface.py tests/config/test_packaging_smoke.py -q`
  - `env/bin/python -m pytest tests -m "not docker and not persistence" -q` if feasible
  - `uvx ruff check .`
  - `git diff --check`
- Focused tests affected by import paths/protocol moves:
  - `tests/operations/create/execution/*`
  - `tests/operations/concepts/execution/test_concept_*_use_case.py`
  - `tests/operations/concepts/execution/test_concept_cli_handler.py`
  - `tests/operations/read/validation/unit/test_read_schema.py`
  - `tests/operations/recall/validation/unit/test_recall_schema.py`
  - `tests/operations/events/execution/*`
  - `tests/operations/guidance/execution/*`
  - `tests/operations/telemetry/execution/read_summaries/test_read_summary_record_writes.py`
  - `tests/operations/telemetry/execution/recall_summaries/test_recall_summary_record_writes.py`
  - `tests/operations/telemetry/execution/write_summaries/test_write_summary_record_writes.py`
  - `tests/operations/telemetry/execution/operation_invocations/test_operation_invocation_record_writes.py`
  - `tests/operations/telemetry/execution/model_usage/test_model_usage_backfill.py`

## Static Acceptance Checks

- `app/core/interfaces/` must not exist.
- `app/entrypoints/cli/protocol/operation_requests.py` must not exist.
- No imports of `app.core.interfaces`.
- No imports of `app.entrypoints.cli.protocol.operation_requests`.
- No core import of infrastructure.
- No append-heavy telemetry repository protocol in core.
