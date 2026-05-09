## Chunk 0 Discovery

No source modules were moved or edited in Chunk 0.

### Captured Artifacts

- `git status --short`: `.refactor/baseline/git-status.txt`
- `tree -L 4 app`: `.refactor/baseline/tree-L4-app.txt`
- planned move file list: `.refactor/baseline/planned-move-python-files.txt`
- raw import map: `.refactor/baseline/import-map-raw-rg.txt`
- summarized import map: `.refactor/baseline/import-map.md`
- core SQLAlchemy/raw SQL scan: `.refactor/baseline/core-sqlalchemy-raw-rg.txt`
- infrastructure entrypoint-reference scan: `.refactor/baseline/infrastructure-entrypoint-refs.txt`

### Discovery Agents

- Telemetry/metrics: reported core telemetry builders, telemetry entity records, metrics SQL analysis, and persistence helpers.
- Memory domain: reported `memory.py`, semantic/integrity validation, create/update use cases, and create/update policies.
- Retrieval: reported `memory_retrieval` use cases and `memory_read_policy` pure policy modules.
- Concepts: reported concept contracts, `apply_concept_changes.py`, concept search policy, and concept endpoints.
- Handlers/agent operations: reported current agent-operation orchestration, startup handler imports, CLI endpoint imports, and protocol/context coupling.
- Startup/ports/protocol: reported migrations, embedding startup, runtime/admin startup, `core/interfaces`, protocol operation requests, and entrypoint reference strings.

### Test Evidence

- `.venv/bin/python -m pytest -q tests/config/test_architecture_boundaries.py`: 22 passed.
- `.venv/bin/python -m pytest -q tests -m 'not docker and not persistence and not real_embedding'`: 210 passed, 270 skipped, 7 deselected.
- `uvx ruff check .`: All checks passed.
- Extra Docker-backed baseline run `./scripts/run_tests`: failed before any source move with 52 failed, 435 passed. See `.refactor/baseline/scripts-run-tests.log`.

### Gate State

Chunk 0 did not mutate source. Under the revised baseline rule, Chunk 0 is satisfied:

- focused architecture-boundary tests are green;
- non-Docker suite is green;
- `ruff check .` is green;
- Docker-backed `./scripts/run_tests` was captured as baseline-drift evidence and categorized in `.refactor/baseline/docker-failures-categorized.md`.
