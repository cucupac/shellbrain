# Chunk 7 Status: Startup and Entrypoints

## Result

- Moved concrete Alembic migration mechanics into `app/infrastructure/postgres_admin/migrations.py`.
- Moved concrete embedding prewarm mechanics into `app/infrastructure/runtime/embedding_prewarm.py`.
- Added `app/infrastructure/runtime/init_admin.py` as the managed-runtime init effect facade.
- Moved init wiring to `app/startup/runtime_admin.py` and removed the old `app/startup/admin_initialize.py` path instead of keeping a re-export shim.
- Kept `app/startup/migrations.py` as startup configuration/error translation around the infrastructure migration runner.
- Moved agent-operation CLI side-effect orchestration into `app/handlers/cli_operation.py`, wired by `app/startup/cli.py`.
- Left Chunk 8-owned `app/core/interfaces` and `app/entrypoints/cli/protocol/operation_requests.py` untouched.

## Acceptance Evidence

- Discovery was written before code mutation: `.refactor/chunk_7/discovery.md`.
- Required pytest gate:
  - `env/bin/python -m pytest tests/config/test_cli_surface.py tests/config/test_runtime_usage.py tests/config/test_upgrade_command.py tests/operations/recovery tests/operations/telemetry/execution/metrics -q`
  - Result: `80 passed, 17 skipped in 0.67s`.
- Ruff:
  - `uvx ruff check .`
  - Result: `All checks passed!`
- Whitespace:
  - `git diff --check`
  - Result: clean.
- Static acceptance checks:
  - `rg -n "from app\\.infrastructure|import app\\.infrastructure" app/entrypoints` returns no matches.
  - `rg -n "subprocess|psycopg|ensure_docker_runtime_available|recover_managed_machine_config_from_docker|sleep\\(|time\\.sleep|while .*poll|HF_HOME|importlib\\.metadata|os\\.environ" app/startup` returns no matches.

## Actor-Critic Review

- Objection: `app/entrypoints/cli/endpoints/human/admin.py` briefly imported an infrastructure migration exception, violating entrypoint boundaries.
  - Fix: `app/startup/migrations.py` now translates infrastructure revision-ahead errors into `DatabaseMigrationConflictError`; the entrypoint catches only startup-level errors.
- Objection: moving `admin_initialize.py` could become an old-path shim if left behind.
  - Fix: the old file was removed; callers/tests now use `app.startup.runtime_admin`.
- Objection: startup still needs to invoke managed runtime prerequisite/recovery behavior during init.
  - Fix: concrete Docker-named mechanics are behind `app.infrastructure.runtime.init_admin`; startup wires generic managed-runtime effects.
- Objection: CLI main could still own side effects if helper wrappers remained.
  - Fix: operation context, unsafe-role check, repo auto-registration, sync launch, and poller telemetry updates moved to `app.handlers.cli_operation` and `app.startup.cli`.
- Residual risk: `app/startup/embeddings.py` still constructs the runtime embedding provider for normal command execution. This is outside the requested prewarm move and is covered by `tests/config/test_runtime_usage.py`.

## Blockers

- None.
