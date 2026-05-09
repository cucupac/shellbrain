## Chunk 1 Discovery

Chunk 1 adds guardrail tests only. No source modules are moved, renamed, split, or deleted in this chunk.

### Baseline Old Structures Covered

- `app/core/observability`
- `app/core/validation`
- `app/core/use_cases/agent_operations`
- `app/core/interfaces`
- no `app/core/ports` directory yet
- `app/core/use_cases/concepts/apply_concept_changes.py`
- `app/core/use_cases/agent_operations/concepts/apply.py`
- `app/core/use_cases/metrics/agent_behavior_analysis.py` imports SQLAlchemy `text`, `Connection`, and `Engine`
- infrastructure hard-coded entrypoint strings:
  - `app/infrastructure/process/episode_sync_launcher.py`
  - `app/infrastructure/host_identity/claude_hook_install.py`
  - `app/infrastructure/host_assets/cursor_statusline_config.py`

### Expected Chunk 1 Guardrail Failures

The new guardrails should fail only for these baseline-known old structures and strings until later chunks remove them.
