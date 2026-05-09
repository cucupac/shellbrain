## Chunk 2 Discovery

Discovery captured before Chunk 2 mutations. The worktree already contains disjoint Chunk 3/4 edits (memory/retrieval paths and related tests); those are treated as user/other-worker changes and must not be reverted.

### Required Inputs Read

- `architectures/refactor.md`
- `.refactor/baseline/import-map.md`
- `.refactor/baseline/docker-failures-categorized.md`

### Modules Moved Or Split

#### `app/core/observability/telemetry/operation_records.py`

Summary: builds operation invocation, read, recall, and write telemetry records; estimates read-pack token size; maps structured errors to telemetry stages.

Importers:
- `app/core/observability/telemetry/read_records.py:3`
- `app/core/observability/telemetry/recall_records.py:3`
- `app/core/observability/telemetry/write_records.py:3`
- `app/core/use_cases/agent_operations/memories/add.py:11`
- `app/core/use_cases/agent_operations/memories/update.py:11`
- `app/core/use_cases/agent_operations/concepts/apply.py:11`
- `app/core/use_cases/agent_operations/events/read.py:13`
- `app/core/use_cases/agent_operations/retrieval/read.py:11`
- `app/core/use_cases/agent_operations/retrieval/recall.py:11`
- `app/core/use_cases/agent_operations/operation_telemetry.py:8`
- `tests/operations/telemetry/execution/read_summaries/test_read_pack_token_estimator.py:5`

Test refs:
- `tests/operations/telemetry/execution/read_summaries/test_read_pack_token_estimator.py:5`
- Indirectly exercised by read, recall, write, operation-invocation, and failure telemetry tests under `tests/operations/telemetry/execution/`.

#### `app/core/observability/telemetry/read_records.py`

Summary: wrapper import for read summary record builders and pack-size estimator.

Importers:
- No direct application importers found other than package-local references through the old telemetry package search.

Test refs:
- No direct tests import this wrapper; read summary tests exercise the builder through command telemetry.

#### `app/core/observability/telemetry/recall_records.py`

Summary: wrapper import for recall summary record builders.

Importers:
- No direct application importers found other than package-local references through the old telemetry package search.

Test refs:
- No direct tests import this wrapper; recall summary tests exercise the builder through command telemetry.

#### `app/core/observability/telemetry/write_records.py`

Summary: wrapper import for write summary record builders.

Importers:
- No direct application importers found other than package-local references through the old telemetry package search.

Test refs:
- No direct tests import this wrapper; write summary tests exercise the builder through command telemetry.

#### `app/core/observability/telemetry/sync_records.py`

Summary: builds episode sync run records and per-tool aggregate records.

Importers:
- `app/infrastructure/process/episode_poller.py:12`
- `app/core/use_cases/agent_operations/events/read.py:14`

Test refs:
- Indirectly exercised by `tests/operations/telemetry/execution/episode_sync_runs/test_episode_sync_run_record_writes.py`
- Indirectly exercised by `tests/operations/telemetry/execution/failure_handling/test_failed_invocation_telemetry.py`

#### `app/core/observability/telemetry/analytics_diagnostics.py`

Summary: pure failure classification helpers for analytics report findings.

Importers:
- `app/core/use_cases/admin/generate_analytics_report.py:11`
- `tests/operations/telemetry/execution/analytics/test_analytics_diagnostics.py:5`

Test refs:
- `tests/operations/telemetry/execution/analytics/test_analytics_diagnostics.py:5`
- Indirectly exercised by `tests/operations/telemetry/execution/analytics/test_analytics_report.py`

#### `app/core/entities/telemetry.py`

Summary: telemetry persistence record dataclasses plus the operation dispatch context alias and session-selection summary.

Importers:
- `app/startup/model_usage_backfill.py:13`
- `app/startup/agent_operations.py:17`
- `app/core/interfaces/repos.py:22`
- `app/core/observability/telemetry/sync_records.py:7`
- `app/core/observability/telemetry/operation_records.py:32`
- `app/core/use_cases/record_episode_sync_telemetry.py:7`
- `app/core/use_cases/record_operation_telemetry.py:7`
- `app/core/use_cases/record_model_usage_telemetry.py:7`
- `app/core/use_cases/agent_operations/dependencies.py:10`
- `app/core/use_cases/agent_operations/events_selection.py:9`
- `app/core/use_cases/agent_operations/events/read.py:12`
- `app/core/use_cases/agent_operations/memories/add.py:10`
- `app/core/use_cases/agent_operations/memories/update.py:10`
- `app/core/use_cases/agent_operations/concepts/apply.py:10`
- `app/core/use_cases/agent_operations/retrieval/read.py:10`
- `app/core/use_cases/agent_operations/retrieval/recall.py:10`
- `app/core/use_cases/agent_operations/operation_telemetry.py:7`
- `app/infrastructure/host_transcripts/model_usage.py:13`
- `app/infrastructure/host_transcripts/session_selection.py:11`
- `app/infrastructure/db/repos/relational/telemetry_repo.py:12`

Test refs:
- Indirectly exercised by all telemetry DB write tests and model-usage extraction/backfill tests.

#### `app/core/use_cases/record_operation_telemetry.py`

Summary: thin persistence helper that writes invocation/read/recall/write telemetry through `uow.telemetry`.

Importers:
- `app/core/use_cases/agent_operations/operation_telemetry.py:18`

Test refs:
- Indirectly exercised by operation invocation, read summary, recall summary, write summary, and failure telemetry tests.

#### `app/core/use_cases/record_episode_sync_telemetry.py`

Summary: thin persistence helper that writes episode sync run telemetry through `uow.telemetry`.

Importers:
- `app/infrastructure/process/episode_poller.py:15`
- `app/core/use_cases/agent_operations/operation_telemetry.py:16`

Test refs:
- Indirectly exercised by episode sync run telemetry tests and poller tests.

#### `app/core/use_cases/record_model_usage_telemetry.py`

Summary: thin persistence helper that writes model usage rows through `uow.telemetry`.

Importers:
- `app/startup/model_usage_backfill.py:14`
- `app/infrastructure/process/episode_poller.py:16`
- `app/core/use_cases/agent_operations/operation_telemetry.py:17`

Test refs:
- `tests/operations/telemetry/execution/model_usage/test_model_usage_backfill.py`
- `tests/operations/telemetry/execution/model_usage/test_model_usage_extractors.py`

#### `app/core/use_cases/metrics/agent_behavior_analysis.py`

Summary: mixes SQLAlchemy query code with pure pre/post behavior-analysis metrics and SB checkpoint parsing.

Importers:
- `scripts/agent_behavior_analysis.py:13`
- `tests/operations/telemetry/execution/behavior_analysis/test_agent_behavior_analysis.py:12`
- `tests/operations/telemetry/execution/behavior_analysis/test_checkpoint_parsing.py:7`

Test refs:
- `tests/operations/telemetry/execution/behavior_analysis/test_agent_behavior_analysis.py:12`
- `tests/operations/telemetry/execution/behavior_analysis/test_checkpoint_parsing.py:7`

### Support Modules Requiring Import Or Boundary Updates

#### `app/core/entities/runtime_context.py`

Summary: per-command runtime context currently shared by CLI/startup handlers; will absorb the non-persistence `SessionSelectionSummary` and operation context alias so `app/core/entities/telemetry.py` can be removed.

Importers:
- `app/startup/runtime_context.py:7`
- `app/entrypoints/cli/main.py:59`
- `app/core/observability/telemetry/operation_records.py:31`

Test refs:
- Indirect CLI/runtime-context coverage under operation and telemetry tests.

#### `app/core/interfaces/repos.py`

Summary: repository interfaces, including `ITelemetryRepo`; currently imports telemetry record dataclasses from `app.core.entities.telemetry`.

Importers:
- `app/core/interfaces/unit_of_work.py:6`
- `app/core/use_cases/build_guidance.py:10`
- Retrieval and repo adapter imports throughout core/infrastructure, including already-modified Chunk 3/4 surfaces.

Test refs:
- Broad indirect coverage through DB, retrieval, guidance, and telemetry tests.

#### `app/core/use_cases/agent_operations/dependencies.py`

Summary: dependency bundle for old agent-operation orchestration until Chunk 6 moves this surface to handlers.

Importers:
- `app/startup/agent_operations.py:20`
- `app/core/use_cases/agent_operations/concepts/apply.py:12`
- `app/core/use_cases/agent_operations/events/read.py:15`
- `app/core/use_cases/agent_operations/events_selection.py:10`
- `app/core/use_cases/agent_operations/memories/add.py:12`
- `app/core/use_cases/agent_operations/memories/update.py:12`
- `app/core/use_cases/agent_operations/retrieval/read.py:12`
- `app/core/use_cases/agent_operations/retrieval/recall.py:12`
- `app/core/use_cases/agent_operations/retrieval_execution.py:6`
- `app/core/use_cases/agent_operations/operation_telemetry.py:14`

Test refs:
- Indirectly exercised by all startup agent operation tests and telemetry operation tests.

#### `app/core/use_cases/agent_operations/operation_telemetry.py`

Summary: currently owns context synthesis and best-effort telemetry persistence for old agent-operation workflows.

Importers:
- `app/core/use_cases/agent_operations/memories/add.py:18`
- `app/core/use_cases/agent_operations/memories/update.py:18`
- `app/core/use_cases/agent_operations/concepts/apply.py:14`
- `app/core/use_cases/agent_operations/events/read.py:22`
- `app/core/use_cases/agent_operations/retrieval/read.py:14`
- `app/core/use_cases/agent_operations/retrieval/recall.py:14`

Test refs:
- Indirectly exercised by all command telemetry tests.

#### Agent-operation runners importing moved telemetry paths

Importers:
- `app/core/use_cases/agent_operations/memories/add.py:10-11`
- `app/core/use_cases/agent_operations/memories/update.py:10-11`
- `app/core/use_cases/agent_operations/concepts/apply.py:10-11`
- `app/core/use_cases/agent_operations/events/read.py:12-14`
- `app/core/use_cases/agent_operations/events_selection.py:9`
- `app/core/use_cases/agent_operations/retrieval/read.py:10-11`
- `app/core/use_cases/agent_operations/retrieval/recall.py:10-11`

Test refs:
- Operation telemetry tests under `tests/operations/telemetry/execution/`.
- Existing Docker failure categorization marks telemetry rewrites for Chunk 2.

#### Startup and infrastructure import updates

Importers:
- `app/startup/agent_operations.py:17`
- `app/startup/model_usage_backfill.py:13-14`
- `app/infrastructure/process/episode_poller.py:12,15-16`
- `app/infrastructure/host_transcripts/model_usage.py:13`
- `app/infrastructure/host_transcripts/session_selection.py:11`
- `app/infrastructure/db/repos/relational/telemetry_repo.py:12`

Test refs:
- `tests/operations/telemetry/execution/model_usage/test_model_usage_backfill.py`
- `tests/operations/telemetry/execution/model_usage/test_model_usage_extractors.py`
- `tests/operations/telemetry/execution/episode_sync_runs/test_episode_sync_run_record_writes.py`
- `tests/operations/telemetry/execution/operation_invocations/test_operation_invocation_record_writes.py`

#### Architecture guardrail test adjustment

Summary: `tests/config/test_architecture_boundaries.py` currently reads `app/core/observability/telemetry/operation_records.py` while checking planned-effect exhaustiveness. Deleting `app/core/observability` requires this reference to move to the new telemetry infrastructure module.

Importers:
- Direct pytest collection only.

Test refs:
- `tests/config/test_architecture_boundaries.py::test_planned_effects_use_typed_params`
