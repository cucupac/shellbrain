## Chunk 1 Status

Status: complete under the Chunk 1 guardrail acceptance rule.

### Changes

- Added guardrails for forbidden old directories:
  - `app/core/observability`
  - `app/core/validation`
  - `app/core/use_cases/agent_operations`
  - `app/application`
- Added guardrail requiring `app/core/ports` and forbidding `app/core/interfaces`.
- Added guardrail forbidding SQLAlchemy imports under `app/core`.
- Added guardrail forbidding `apply*` files under core use cases.
- Added guardrail forbidding hard-coded `app.entrypoints` module strings under infrastructure.

### Verification

- `.venv/bin/python -m pytest -q tests/config/test_architecture_boundaries.py`
  - Expected result: 5 failed, 22 passed.
  - The 5 failures match baseline-known old paths and strings only.
- `uvx ruff check tests/config/test_architecture_boundaries.py`
  - Result: All checks passed.

### Critic

Critic rounds: 1.

Result: no substantive objections.
