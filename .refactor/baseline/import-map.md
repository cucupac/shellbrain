## Baseline Import Map

Raw importer capture is in `.refactor/baseline/import-map-raw-rg.txt`.
Planned Python files are in `.refactor/baseline/planned-move-python-files.txt`.

### Chunk 2: Telemetry and Metrics

- `app/core/observability/telemetry/operation_records.py` is imported by telemetry wrapper modules, agent operation runners, and `tests/operations/telemetry/execution/read_summaries/test_read_pack_token_estimator.py`.
- `app/core/observability/telemetry/sync_records.py` is imported by `app/infrastructure/process/episode_poller.py` and `app/core/use_cases/agent_operations/events/read.py`.
- `app/core/observability/telemetry/analytics_diagnostics.py` is imported by `app/core/use_cases/admin/generate_analytics_report.py` and analytics tests.
- `app/core/entities/telemetry.py` is imported by startup handler wiring, telemetry repos/builders, model-usage/session-selection adapters, and agent operation runners.
- `app/core/use_cases/metrics/agent_behavior_analysis.py` is imported by `scripts/agent_behavior_analysis.py` and behavior-analysis telemetry tests.
- Telemetry persistence helpers in `app/core/use_cases/record_*_telemetry.py` are imported by process/orchestration paths.

### Chunk 3: Memory Domain

- `app/core/entities/memory.py` is imported by repo interfaces, plan execution, concept apply, read concepts, validation modules, memory create policy, settings, DB memory repo, and create/update/read/concept tests.
- `app/core/validation/memory_semantic.py` is imported by `app/core/use_cases/agent_operations/validation.py` and create/update link-rule tests.
- `app/core/validation/memory_integrity.py` is imported by `app/core/use_cases/agent_operations/validation.py` and update reference-check tests.
- `app/core/use_cases/memories/create_memory.py` is imported by the create agent-operation runner and create execution tests.
- Current update use case is `app/core/use_cases/memories/update_memory.py`, not `app/core/use_cases/memories/update.py`; it is imported by the update agent-operation runner and update execution tests.
- `app/core/policies/memory_create_policy/plan.py` is imported by `create_memory.py` and create effect-order tests.
- `app/core/policies/memory_update_policy/plan.py` is imported by `update_memory.py`.

### Chunk 4: Retrieval

- `app/core/use_cases/memory_retrieval/read_memory.py` is imported by recall and agent retrieval execution; direct tests cover scoring, determinism, high-level behavior, context-pack shape, semantic wiring, concept-aware read, semantic read, and expansion.
- `app/core/use_cases/memory_retrieval/context_pack_pipeline.py` is imported by `read_memory.py`; several tests monkeypatch pipeline-stage symbols.
- `app/core/use_cases/memory_retrieval/expansion.py`, `read_concepts.py`, `recall_memory.py`, and `seed_retrieval.py` are imported by retrieval pipeline modules and read/recall tests.
- `app/core/policies/memory_read_policy/context_pack_builder.py` is imported by retrieval pipeline and context-pack tests.
- `bm25.py`, `fusion_rrf.py`, `lexical_query.py`, `scoring.py`, and `expansion.py` are imported by retrieval use cases or tests and are architecture-guarded as pure policy.

### Chunk 5: Concepts

- `app/core/contracts/concepts.py` is imported by startup handlers, concept apply use case, concept agent operation, CLI protocol validation, and concept/read tests.
- `app/core/contracts/requests.py` owns `ReadConceptsExpandRequest`, imported by CLI payload validation and read concept rendering.
- `app/core/use_cases/concepts/apply_concept_changes.py` is imported by the concept agent-operation wrapper and concept/read tests.
- `app/core/policies/concepts/search.py` is imported by read concept rendering and guarded as pure policy.
- CLI concept add endpoint is imported by `app/entrypoints/cli/main.py` and by the concept update endpoint; the update endpoint currently delegates to add.

### Chunk 6: Handlers

- `app/core/use_cases/agent_operations/*` is imported mainly by `app/startup/agent_operations.py`; internal modules share `dependencies.py`, `errors.py`, `validation.py`, `operation_telemetry.py`, `events_selection.py`, `serialization.py`, and `retrieval_execution.py`.
- `app/startup/agent_operations.py` is imported by all operation CLI endpoints and many operation tests.
- `app/entrypoints/cli/protocol/operation_requests.py` is imported by all internal/working-agent operation endpoints.
- Telemetry context currently flows through `app/startup/runtime_context.py`, `app/core/entities/runtime_context.py`, and `app/core/entities/telemetry.py`.

### Chunks 7 and 8: Startup, Entrypoints, Ports, Protocol

- `app/startup/migrations.py` is imported by `app/startup/admin_initialize.py` and human admin endpoint.
- `app/startup/embeddings.py` is imported by startup use-case/repo wiring.
- `app/startup/admin_initialize.py`, `admin.py`, `admin_db.py`, and `admin_diagnose.py` are imported by human endpoints and config tests.
- `app/core/interfaces/*` is imported across core use cases, infrastructure adapters, startup, settings loader, and tests.
- `app/entrypoints/cli/protocol/operation_requests.py` is the protocol choke point for operation endpoints.
- `rg` found no direct `app.infrastructure` imports inside `app/entrypoints`; infrastructure does contain hard-coded entrypoint module strings in process/host asset launch configuration.
