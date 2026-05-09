## Chunk 5 Status

Status: complete.

## Actor Summary

Files split or renamed:
- Deleted `app/core/use_cases/concepts/apply_concept_changes.py`.
- Added `app/core/use_cases/concepts/add.py`.
- Added `app/core/use_cases/concepts/update.py`.
- Added `app/core/use_cases/concepts/show.py`.
- Added `app/core/use_cases/concepts/reference_checks.py`.
- Added `app/core/use_cases/concepts/containment_checks.py`.
- Added `app/core/use_cases/concepts/views.py`.
- Added `app/core/policies/concepts/relation_rules.py`.
- Deleted `app/core/use_cases/agent_operations/concepts/apply.py`.
- Added `app/core/use_cases/agent_operations/concepts/add.py`.
- Added `app/core/use_cases/agent_operations/concepts/update.py`.
- Split `tests/operations/concepts/execution/test_concept_use_case.py` into add/update/show test files.

Importers updated:
- Concept contracts now expose `ConceptAddRequest`, `ConceptUpdateRequest`, and `ConceptShowRequest`.
- CLI protocol now has distinct `prepare_concept_add_request`, `prepare_concept_update_request`, and `prepare_concept_show_request`.
- CLI validation now has distinct add/update/show validators.
- CLI hydration now has distinct add/update/show hydration helpers.
- Concept add endpoint calls `handle_concept_add`.
- Concept update endpoint calls `handle_concept_update` and no longer imports the add endpoint.
- Startup wiring imports distinct concept add/update operation wrappers.
- Concept-aware read tests seed via `add_concepts` and `update_concepts`.

Judgment calls:
- `concept add` creates concept containers only and fails on existing concept slug.
- `concept update` updates existing concept containers and adds truth-bearing graph records for existing concepts.
- Standalone anchor creation is named `ensure_anchor` at the contract level because anchors remain natural-key-idempotent support records.
- `show_concept` remains a core use case for tests/internal reads, but no CLI show route was added because the target tree lists only concept add/update endpoints.

## Acceptance Evidence

- No `apply_concept_changes.py`:
  - `.refactor/chunk_5/acceptance-checks.log` command passed.
- No `apply*.py` concept use-case file:
  - `.refactor/chunk_5/acceptance-checks.log` command passed.
- `concepts/update.py` does not import `concepts/add.py`:
  - `.refactor/chunk_5/acceptance-checks.log` command passed.
- Concept update endpoint does not import concept add endpoint:
  - `.refactor/chunk_5/acceptance-checks.log` command passed.
- Concept tests pass:
  - `.venv/bin/python -m pytest -q tests/operations/concepts`
  - Result: 6 passed, 10 skipped.
- Concept-aware read tests were run:
  - `.venv/bin/python -m pytest -q tests/operations/read/execution/concepts`
  - Result: 5 skipped.
- Relevant architecture boundary tests pass:
  - `test_core_use_case_apply_files_are_gone`
  - `test_core_policies_do_not_generate_ids_or_execute_plans`
  - `test_agent_operations_use_injected_clock_and_ids`
  - Result: 3 passed.
- CLI surface tests pass:
  - `.venv/bin/python -m pytest -q tests/config/test_cli_surface.py`
  - Result: 47 passed.
- Ruff passes:
  - `uvx ruff check .`
  - Result: All checks passed.
- Whitespace check passes:
  - `git diff --check`
  - Result: passed.

## Critic Fallback

Could not spawn a separate critic subagent from this environment, so this fallback checklist was applied.

Checklist:
- Architecture: relation shape/cycle rules moved out of orchestration; repo-backed checks are in named use-case check modules.
- Naming: add/update/show paths are explicit; no apply file remains in concept core or agent-operation concept wrappers.
- ID generation: concept core use cases receive `IIdGenerator`; direct `uuid4()` is absent from concept core use cases and policies.
- CLI boundary: concept add/update endpoints call distinct preparation and startup handler paths.
- Discovery completeness: importers found in discovery were updated; old symbol/path `rg` checks across `app` and `tests` are clean.
- Test coverage: old combined concept use-case test file was deleted and replaced by add/update/show-specific files.

Critic outcome: no substantive objections from the fallback review.

## Blockers

None for Chunk 5.

## Shellbrain Closeout

- Created problem memory `e14fd17d-7070-4705-9521-288ec07ec5f4`.
- Created solution memory `7d28bc27-532a-4a3e-8e9e-dc34ab768d4e`.
- Created change memory `26eef299-b82e-4f56-b4de-45fd1bf828c9`.
- Recorded utility votes for memories `7fb72f07-9489-41b4-8255-381c9472236c`, `78c55eff-e7fd-4b7b-a274-6de8542b6305`, and `4ae2b8ec-dedc-4834-8f63-31d1bc865f29`.
