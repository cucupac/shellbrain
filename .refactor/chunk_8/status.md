# Chunk 8 Status: Ports and Protocol Cleanup

## Summary

- Renamed `app/core/interfaces/` to `app/core/ports/`.
- Split the old catch-all repository port module into:
  - `app/core/ports/memory_repositories.py`
  - `app/core/ports/concept_repositories.py`
  - `app/core/ports/episode_repositories.py`
  - `app/core/ports/retrieval_repositories.py`
  - `app/core/ports/guidance.py`
- Moved append-heavy telemetry write protocols out of core into `app/infrastructure/observability/telemetry/ports.py`.
- Kept only the pending-utility-candidates query as a core guidance port because `app/core/use_cases/build_guidance.py` directly consumes it.
- Split `app/entrypoints/cli/protocol/operation_requests.py` into operation-family protocol modules:
  - `memories.py`
  - `concepts.py`
  - `retrieval.py`
  - `episodes.py`
  - shared result container in `prepared.py`
- Deleted the old `operation_requests.py` protocol catch-all.

## Acceptance Evidence

- `app/core/interfaces/` does not exist.
- `app/entrypoints/cli/protocol/operation_requests.py` does not exist.
- Static scan found no imports of:
  - `app.core.interfaces`
  - `app.core.ports.repos`
  - `app.entrypoints.cli.protocol.operation_requests`
  - `ITelemetryRepo`
- `uvx ruff check .`: passed.
- `git diff --check`: passed.

## Test Evidence

- `env/bin/python -m pytest tests/config/test_architecture_boundaries.py tests/config/test_cli_surface.py tests/config/test_packaging_smoke.py -q`
  - Result: `78 passed`, `2 skipped`, `1 failed`.
  - Failure: `test_infrastructure_does_not_reference_entrypoint_modules`.
  - Failing paths:
    - `app/infrastructure/host_assets/cursor_statusline_config.py`
    - `app/infrastructure/host_identity/claude_hook_install.py`
    - `app/infrastructure/process/episode_sync_launcher.py`
  - Assessment: Chunk 7-owned infrastructure-entrypoint cleanup.
- Focused operation/import suite:
  - `env/bin/python -m pytest tests/operations/create tests/operations/update tests/operations/concepts tests/operations/read/validation tests/operations/recall/validation tests/operations/events tests/operations/guidance tests/operations/telemetry/execution/read_summaries tests/operations/telemetry/execution/recall_summaries tests/operations/telemetry/execution/write_summaries tests/operations/telemetry/execution/operation_invocations tests/operations/telemetry/execution/model_usage -q`
  - Result: `27 passed`, `116 skipped`.
- Broad non-Docker/non-persistence suite:
  - `env/bin/python -m pytest tests -m "not docker and not persistence" -q`
  - Result: `198 passed`, `299 skipped`, `6 deselected`, `1 failed`.
  - Failure: same Chunk 7-owned `test_infrastructure_does_not_reference_entrypoint_modules`.

## Actor-Critic Review

### Critic Objection: `prepared.py` is an extra protocol module beyond the four requested files.

Response: The old catch-all `operation_requests.py` is gone. The requested operation-family modules now own request preparation. `prepared.py` only contains the generic prepared-result envelope and hydration-error helper; duplicating that container in four modules would make the split noisier without improving boundaries.

### Critic Objection: Telemetry is still present on `PostgresUnitOfWork`.

Response: Runtime `PostgresUnitOfWork` still exposes `telemetry` for infrastructure recorders and Chunk 7-owned entrypoint cleanup that still calls `uow.telemetry`. The core `IUnitOfWork` port no longer exposes the append-heavy telemetry write repo. Core guidance depends on `guidance: IPendingUtilityCandidatesRepo`, and `PostgresUnitOfWork` maps that to the same concrete `TelemetryRepo` instance.

### Critic Objection: `TelemetryRepo` still implements a core port.

Response: It implements only `IPendingUtilityCandidatesRepo`, a narrow core query port used by `build_guidance`. The append-heavy telemetry protocol lives in infrastructure and is used structurally by telemetry recorders.

### Critic Objection: Architecture tests still fail.

Response: The only remaining architecture failure is the infrastructure-to-entrypoint string reference check assigned to Chunk 7 in the prompt. Chunk 8-specific path, import, protocol, Ruff, and operation-test evidence is clean.

## Blockers

- No Chunk 8 blocker requiring `BLOCKER.md`.
- Remaining acceptance gap is Chunk 7-owned infrastructure-entrypoint cleanup.
