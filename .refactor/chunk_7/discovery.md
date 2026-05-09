# Chunk 7 Discovery: Startup and Entrypoints

## Ownership Boundary

- Chunk 7 owns startup/admin/entrypoint orchestration cleanup only.
- Chunk 8 owns `app/core/interfaces -> ports` rename and CLI protocol operation request splitting. This chunk must leave those paths alone unless a focused Chunk 7 test requires a small compatibility update.
- Current worktree is already heavily modified by parallel chunks. This discovery treats existing uncommitted files as user/parallel-agent state and avoids unrelated reversions.

## Target Modules

- `app/startup/admin_initialize.py`
  - Current machine init wiring and concrete mechanics live here.
  - Concrete mechanics found here before mutation:
    - Docker prerequisite/recovery imports via `app.infrastructure.runtime.docker_prerequisites`.
    - Postgres revision reads via `fetch_schema_revision`.
    - `wait_for_postgres` passed directly as a port.
    - Alembic migration application through `app.startup.migrations`.
    - embedding prewarm with `importlib.metadata`, `os.environ["HF_HOME"]`, cache directory creation, and `SentenceTransformersEmbeddingProvider`.
  - Importers/tests:
    - `app/entrypoints/cli/endpoints/human/init.py`
    - `tests/operations/recovery/execution/test_init_bootstrap.py`
    - `tests/config/test_cli_surface.py`

- `app/startup/migrations.py`
  - Current packaged Alembic runner imports startup config (`admin_db`, `db`) and infrastructure Postgres admin helpers.
  - Importers/tests:
    - `app/startup/admin_initialize.py`
    - `app/entrypoints/cli/endpoints/human/admin.py`
    - `tests/operations/recovery/execution/test_init_bootstrap.py`
    - `tests/config/test_cli_surface.py`
    - `tests/config/test_packaging_smoke.py`

- `app/entrypoints/cli/main.py`
  - Current CLI entrypoint still performs operation side-effect orchestration:
    - resolves repo context
    - resolves caller identity and sets runtime context
    - checks unsafe DB role
    - auto-registers repo
    - starts episode sync
    - patches poller telemetry flags
  - Direct helper imports to startup are lazy, but orchestration belongs in handlers/startup wiring.
  - Importers/tests:
    - `app/__main__.py`
    - `tests/config/test_cli_surface.py`
    - `tests/operations/telemetry/execution/metrics/test_metrics_cli.py`
    - `tests/operations/telemetry/execution/operation_invocations/test_operation_invocation_record_writes.py`

- `app/startup/cli.py`
  - Current CLI composition helper imports infrastructure directly for identity, repo registration, instance guard, and upgrade.
  - This is an acceptable startup wiring surface, but operation-command side effects should be callable as a single startup-composed handler instead of being orchestrated in the entrypoint.
  - Importers/tests:
    - `app/entrypoints/cli/main.py`
    - `app/entrypoints/cli/endpoints/human/upgrade.py`
    - `tests/config/test_cli_surface.py`

## Existing Handler Surface

- `app/startup/handlers.py` already composes public operation handlers and imports concrete infrastructure adapters.
- `app/handlers/*` contains operation-level orchestration and is the right place for CLI command execution logic that is independent of parse/presentation.
- `app/handlers/command_context.py` owns the injected operation dependency bundle.

## Required Moves

- Create `app/infrastructure/postgres_admin/migrations.py` for concrete Alembic migration mechanics.
- Keep `app/startup/migrations.py` as startup wiring/configuration around the infrastructure migration runner, or update callers to use a new startup wiring module without adding old-path re-export shims.
- Create `app/infrastructure/runtime/embedding_prewarm.py` for concrete embedding prewarm mechanics.
- Create/keep `app/startup/runtime_admin.py` as init/repair wiring. The current equivalent is `app/startup/admin_initialize.py`; tests currently patch that path, so either tests need updating or `admin_initialize.py` must remain as real code rather than a compatibility re-export.
- Move operation side-effect orchestration out of `app/entrypoints/cli/main.py` into handler/startup wiring while keeping entrypoints responsible for parse, hydrate/load payload, call, and present.

## Focused Tests/Gates

- Required gate from prompt:
  - `env/bin/python -m pytest tests/config/test_cli_surface.py tests/config/test_runtime_usage.py tests/config/test_upgrade_command.py tests/operations/recovery tests/operations/telemetry/execution/metrics -q`
  - `uvx ruff check .`
  - `git diff --check`
- Additional static acceptance checks:
  - startup should not contain subprocess imports, psycopg imports, Docker checks, sleeps, or real polling loops.
  - entrypoints should not import infrastructure directly.
  - avoid edits under `app/core/interfaces` and `app/entrypoints/cli/protocol/operation_requests.py`.
