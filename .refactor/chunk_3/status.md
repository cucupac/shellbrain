# Chunk 3 Status

## Actor Summary

Moved/renamed files:
- `app/core/entities/memory.py` -> `app/core/entities/memories.py`
- `app/core/validation/memory_semantic.py` -> `app/core/policies/memories/link_rules.py`
- `app/core/validation/memory_integrity.py` -> `app/core/use_cases/memories/reference_checks.py`
- `app/core/use_cases/memories/create_memory.py` -> `app/core/use_cases/memories/add.py`
- `app/core/use_cases/memories/update_memory.py` -> `app/core/use_cases/memories/update.py`
- `app/core/policies/memory_create_policy/plan.py` -> `app/core/policies/memories/add_plan.py`
- `app/core/policies/memory_update_policy/plan.py` -> `app/core/policies/memories/update_plan.py`

Deleted old package paths:
- `app/core/validation/`
- `app/core/policies/memory_create_policy/`
- `app/core/policies/memory_update_policy/`

Importers updated:
- Memory entity importers now use `app.core.entities.memories`.
- Memory semantic-rule importers now use `app.core.policies.memories.link_rules`.
- Memory reference-check importers now use `app.core.use_cases.memories.reference_checks`.
- Memory add/update execution importers now use `app.core.use_cases.memories.add` and `app.core.use_cases.memories.update`.
- Memory plan importers now use `app.core.policies.memories.add_plan` and `app.core.policies.memories.update_plan`.

Tests updated/added:
- Updated direct create/update link-rule tests to new policy path.
- Updated create effect-ordering test to new add-plan path.
- Updated create/update execution tests to new add/update use-case paths.
- Updated create/update/read/concept/telemetry test imports for `Memory`, `MemoryKind`, and `MemoryScope`.
- Added `tests/operations/memory_domain/test_memory_invariants.py` for `MemoryKind.requires_problem_link`, `Memory.is_visible_in`, evidence refs, confidence, salience, and utility vote invariants.

Bounded-judgment calls:
- Added value objects only for fields that recur and have validation/default logic: `EvidenceRefs`, `ConfidenceValue`, `SalienceValue`, and `UtilityVoteValue`.
- Kept existing public function names (`execute_create_memory`, `execute_update_memory`, `validate_create_semantics`, `validate_update_semantics`, `validate_create_integrity`, `validate_update_integrity`) inside the new modules to avoid broad behavioral churn while still deleting old import paths.
- Moved `matures_into` kind validation into pure link policy because it operates on already-loaded kinds and does not hit repositories.

## Acceptance Evidence

Passed:
- `uv run --with pytest python -m pytest tests/operations/memory_domain/test_memory_invariants.py --confcutdir=tests/operations/memory_domain -q`: 4 passed. See `pytest-memory-invariants.log`.
- `uv run --with pytest python -m pytest tests/operations/create/validation/link_rules/test_create_link_rules.py --confcutdir=tests/operations/create/validation/link_rules -q`: 4 passed. See `pytest-create-link-rules.log`.
- `uv run --with pytest python -m pytest tests/operations/update/validation/link_rules/test_update_link_rules.py --confcutdir=tests/operations/update/validation/link_rules -q`: 2 passed. See `pytest-update-link-rules.log`.
- `uv run --with pytest python -m pytest tests/operations/create/execution/effect_ordering/test_create_effect_ordering.py --confcutdir=tests/operations/create/execution/effect_ordering -q`: 1 passed. See `pytest-create-add-plan.log`.
- Focused ruff on Chunk 3 files/tests: passed. See `ruff-focused-after-tests.log`.
- Explicit old-path/import checks for `app.core.validation`, `memory_create_policy`, `memory_update_policy`, `app.core.entities.memory`, `create_memory`, and `update_memory` in `app`/`tests`: no matches. See `acceptance-path-checks.log` and `acceptance-import-checks.log`.

Blocked:
- Focused memory add/update pytest set could not collect because parallel Chunk 2 telemetry work removed `app.core.entities.telemetry` while `app.core.interfaces.repos` still imports it. See `pytest-memory-add-update-uv-python.log`.
- Full `ruff check .` is blocked by `F821 Undefined name self` in `app/core/contracts/concepts.py`, a parallel Chunk 5 file. See `ruff-check-all.log`.
- Relevant architecture boundary subset ran 4 tests: 3 passed, 1 failed because `app/core/use_cases/agent_operations` still exists for a later handler chunk. See `pytest-architecture-boundaries-focused.log`.

## Critic Checklist

Separate critic agent: unavailable in this toolset.

Checklist review:
- Architectural rules: Chunk 3 moved pure memory link rules to `app/core/policies/memories` and repo-backed checks to `app/core/use_cases/memories`; no remaining `app.core.validation` imports in `app` or `tests`.
- Naming conventions: new memory policy paths use `add_plan.py`, `update_plan.py`, and `link_rules.py`; old `_policy` package names are deleted from `app/core`.
- Discovery completeness: `.refactor/chunk_3/discovery.md` records importers and direct tests for every moved source module before mutation.
- Test coverage: direct tests for moved pure rules and add-plan path pass; invariant tests added. Full DB-backed memory tests are blocked before collection by parallel telemetry refactor state, not by Chunk 3 imports.
- Compatibility shims: none added; old modules and packages were deleted rather than re-exported.

Critic outcome:
- No substantive Chunk 3-specific objections remain from the checklist.
- Verification gate is not fully green only because the shared worktree currently has parallel Chunk 2/5/6 blockers outside Chunk 3 ownership.
