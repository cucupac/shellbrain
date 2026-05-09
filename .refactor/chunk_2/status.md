## Chunk 2 Status

Status: implementation complete for owned telemetry/metrics surfaces.

### Actor Summary

Moved raw telemetry capture and record persistence out of core:

- `app/core/observability/telemetry/operation_records.py` -> `app/infrastructure/observability/telemetry/operation_invocations.py`
- `app/core/observability/telemetry/{read_records.py,recall_records.py,write_records.py,sync_records.py}` -> `app/infrastructure/observability/telemetry/`
- `app/core/entities/telemetry.py` -> `app/infrastructure/observability/telemetry/records.py`
- `app/core/use_cases/record_operation_telemetry.py` -> `app/infrastructure/observability/telemetry/recorder.py`
- `app/core/use_cases/record_episode_sync_telemetry.py` and `app/core/use_cases/record_model_usage_telemetry.py` were folded into infrastructure recorder support.

Split agent behavior analysis:

- SQL fetches now live in `app/infrastructure/db/queries/agent_behavior.py`.
- Pure analysis and SB checkpoint parsing now live in `app/core/use_cases/metrics/analyze_agent_behavior.py`.
- `scripts/agent_behavior_analysis.py` and behavior-analysis tests call the query layer plus pure core analysis.

Boundary updates:

- `app/core/entities/runtime_context.py` now owns the non-persistence `OperationDispatchTelemetryContext` alias and `SessionSelectionSummary`.
- Old agent-operation workflows call an injected `record_operation_telemetry` dependency. Startup wires it to `app.infrastructure.observability.telemetry.recorder.record_operation_telemetry_best_effort`.
- `ITelemetryRepo` no longer imports telemetry record dataclasses from core; telemetry record classes are infrastructure-owned.
- Pure analytics failure classification moved from the removed `core/observability` package to `app/core/use_cases/admin/analytics_diagnostics.py` because it is pure report analysis, not raw telemetry capture.

### Verification

- `.venv/bin/python -m pytest -q tests/operations/telemetry`
  - Result: `26 passed, 64 skipped`
  - Log: `.refactor/chunk_2/telemetry-tests.log`
- `.venv/bin/python -m pytest -q tests/config/test_architecture_boundaries.py`
  - Result: `3 failed, 24 passed`
  - Remaining failures are expected non-Chunk-2 surfaces: `app/core/use_cases/agent_operations`, `app/core/interfaces` vs ports, and existing infrastructure entrypoint strings.
  - Log: `.refactor/chunk_2/architecture-boundaries.log`
- `uvx ruff check <Chunk 2 touched surfaces>`
  - Result: pass
  - Log: `.refactor/chunk_2/ruff-targeted.log`
- `uvx ruff check .`
  - Result: pass
  - Log: `.refactor/chunk_2/ruff-all.log`
- Static acceptance scan:
  - `app/core/observability` absent
  - no SQLAlchemy imports under `app/core`
  - no old telemetry import paths under `app`, `tests`, or `scripts`
  - Log: `.refactor/chunk_2/acceptance-static.log`
- `git diff --check`
  - Result: pass
  - Log: `.refactor/chunk_2/git-diff-check.log`

### Critic Checklist

- Architectural rules:
  - Pass for Chunk 2: raw telemetry record builders and persistence are in infrastructure.
  - Pass for core SQLAlchemy boundary: no SQLAlchemy imports remain under `app/core`.
  - Pass for core observability removal: `app/core/observability` is absent.
  - Known pending failures are outside Chunk 2 and remain owned by later chunks/parallel workers.
- Naming conventions:
  - Pass: new files use target-layer names: `records.py`, `operation_invocations.py`, `recorder.py`, and `agent_behavior.py`.
  - Watch item: model-usage row construction remains in `app/infrastructure/host_transcripts/model_usage.py`; only persistence support moved to telemetry `recorder.py`.
- Discovery completeness:
  - Pass: discovery captured old telemetry/entity/helper/agent-behavior importers and tests before mutation.
  - Caveat: parallel Chunk 3/4/5 edits changed some importers after discovery; no changes were reverted.
- Test coverage:
  - Pass: telemetry and behavior-analysis tests were rewritten rather than dropped.
  - Pass: moved estimator and analytics-diagnostics unit tests import new paths.
- No compatibility shims:
  - Pass: old `app.core.observability.telemetry`, `app.core.entities.telemetry`, `app.core.use_cases.record_*_telemetry`, and `agent_behavior_analysis.py` modules were removed, not re-exported.

Critic outcome: no substantive Chunk 2 objections remain.
