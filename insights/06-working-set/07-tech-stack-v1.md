# Tech Stack v1

Status: ratified for implementation start.

## Core runtime

- Language: Python 3.12.
- Interface mode: CLI-first for agent integration.
- Interface style: JSON in / JSON out.

## Application shape

- One core Python package for memory logic (policy + retrieval + persistence orchestration).
- One CLI adapter that:
  - accepts compact agent payloads,
  - performs contextual hydration,
  - validates against strict internal contracts,
  - emits structured JSON responses/errors.

## Storage and retrieval

- Primary database: PostgreSQL 16.
- Embeddings: pgvector.
- Keyword retrieval: PostgreSQL full-text search.
- Association/dependency traversal: relational link tables + bounded traversal logic.

## Durability and portability requirements

- Mandatory persistence property:
  - memory data must survive container deletion and Docker uninstall.
- Local deployment requirement:
  - PostgreSQL data directory must use a host bind mount path (outside Docker-managed volume lifecycle).
- Portability requirement:
  - maintain logical backup/export capability (`pg_dump`/`pg_dumpall`) so data can be moved to another machine/runtime without Docker-coupled state.

## Data layer and migrations

- SQLAlchemy Core (explicit SQL-oriented data access).
- Alembic for schema migrations.

## Background processing

- Initial v1: in-process/session-end consolidation commands for implicit reinforcement.
- Optional later: queue-backed worker if operational load requires it.

## Validation and tests

- Pydantic v2 for request/response schema validation.
- pytest for:
  - contract tests,
  - read/write policy tests,
  - retrieval/context-pack behavior tests.

## CLI expectations

- Commands map to `create`, `read`, `update`.
- Support:
  - `--json '<payload>'`
  - `--json-file <path>`
  - deterministic JSON output for both success and failures.

## Not yet locked

- Final CLI command names/subcommands and output envelope schema.
- Final background-worker escalation criteria (when to move beyond in-process jobs).
