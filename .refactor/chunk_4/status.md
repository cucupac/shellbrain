# Chunk 4 Status

## Actor Summary

Moved retrieval use cases:
- `app/core/use_cases/memory_retrieval/__init__.py` -> `app/core/use_cases/retrieval/__init__.py`
- `app/core/use_cases/memory_retrieval/context_pack_pipeline.py` -> `app/core/use_cases/retrieval/context_pack_pipeline.py`
- `app/core/use_cases/memory_retrieval/expansion.py` -> `app/core/use_cases/retrieval/expansion.py`
- `app/core/use_cases/memory_retrieval/read_concepts.py` -> `app/core/use_cases/retrieval/read_concepts.py`
- `app/core/use_cases/memory_retrieval/read_memory.py` -> `app/core/use_cases/retrieval/read.py`
- `app/core/use_cases/memory_retrieval/recall_memory.py` -> `app/core/use_cases/retrieval/recall.py`
- `app/core/use_cases/memory_retrieval/seed_retrieval.py` -> `app/core/use_cases/retrieval/seed_retrieval.py`

Moved retrieval policies:
- `app/core/policies/memory_read_policy/__init__.py` -> `app/core/policies/retrieval/__init__.py`
- `app/core/policies/memory_read_policy/README.md` -> `app/core/policies/retrieval/README.md`
- `app/core/policies/memory_read_policy/bm25.py` -> `app/core/policies/retrieval/bm25.py`
- `app/core/policies/memory_read_policy/context_pack_builder.py` -> `app/core/policies/retrieval/context_pack.py`
- `app/core/policies/memory_read_policy/expansion.py` -> `app/core/policies/retrieval/expansion.py`
- `app/core/policies/memory_read_policy/fusion_rrf.py` -> `app/core/policies/retrieval/fusion_rrf.py`
- `app/core/policies/memory_read_policy/lexical_query.py` -> `app/core/policies/retrieval/lexical_query.py`
- `app/core/policies/memory_read_policy/scoring.py` -> `app/core/policies/retrieval/scoring.py`

Contracts updated:
- Added `app/core/contracts/retrieval.py` for `MemoryReadRequest`, `MemoryRecallRequest`, `ReadExpandRequest`, and `ReadConceptsExpandRequest`.
- Removed read/recall request definitions from `app/core/contracts/requests.py`.
- Updated read/recall callers, protocol validation, telemetry importers, and tests to import read/recall contracts from `app.core.contracts.retrieval`.

Importers updated:
- Startup and agent-operation retrieval execution.
- CLI operation request preparation and payload validation.
- Read execution tests, context-pack tests, scoring tests, telemetry monkeypatch paths, and config threshold usage tests.
- Retrieval policy imports now use `app.core.policies.retrieval`, with `context_pack` replacing `context_pack_builder`.

Acceptance evidence:
- `old-path-scan.log`: no filesystem or import hits for old retrieval package paths.
- `py-compile-retrieval.log`: moved retrieval contracts, use cases, and policies compile.
- `retrieval-contract-smoke.log`: retrieval contracts and context-pack policy import and execute in a minimal smoke.
- `pytest-architecture-boundary-retrieval.log`: relevant DB-adapter retrieval-policy boundary test passed.
- `ruff-check-chunk4-files.log`: ruff passed on Chunk 4 retrieval files and importers.

Blocked evidence:
- `pytest-read-recall.log`: full read/recall tests do not collect because parallel Chunk 2 moved telemetry entities while `app.core.interfaces.repos` still imports `app.core.entities.telemetry`.
- `pytest-read-execution-focused.log` and `pytest-config-focused.log`: focused execution/config slices are blocked by the same missing telemetry entity.
- `ruff-check.log`: full `ruff check .` is blocked by an unrelated Chunk 5 concept-contract error in `app/core/contracts/concepts.py`.
- `pytest-architecture-boundaries.log`: full architecture boundary suite has expected non-Chunk-4 failures for agent operations, interfaces/ports, metrics SQLAlchemy, concept apply files, infrastructure entrypoint strings, and a stale observability path in one guard.

## Critic Checklist

- [x] Discovery before mutation was recorded in `.refactor/chunk_4/discovery.md`.
- [x] No `app/core/use_cases/memory_retrieval` package remains.
- [x] No `app/core/policies/memory_read_policy` package remains.
- [x] No old retrieval import paths or `context_pack_builder` references remain under `app` or `tests`.
- [x] `context_pack_builder.py` was renamed to `context_pack.py`, and imports/tests were updated.
- [x] Read/recall contracts moved to a retrieval contract module with callers updated.
- [x] No compatibility shims or old-path re-exports were added.
- [x] Moved retrieval files compile and pass focused ruff.
- [ ] Full read/recall tests pass. Blocked by parallel Chunk 2 telemetry state, not by Chunk 4 retrieval paths.
- [ ] Full `ruff check .` passes. Blocked by parallel Chunk 5 concept-contract state.
- [ ] Full architecture boundary suite passes. Blocked by pre-existing/future-chunk guard failures outside Chunk 4.

