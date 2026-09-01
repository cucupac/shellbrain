# Ponytail repository audit

## Scope map

The repository is a Python 3.11 package built with setuptools, tested with pytest, and backed by SQLAlchemy, Alembic, PostgreSQL/pgvector, Pydantic, PyYAML, and sentence-transformers. It includes a `uv.lock`, Docker development files, shell/Python scripts, packaged host-onboarding assets, and static documentation. The counts below cover tracked source-like files and exclude bytecode, installed dependencies, and user-untracked files.

| Audit agent | Exclusive subsystem scope | Approximate reviewed volume |
| --- | --- | --- |
| 1. Domain workflows | `app/core/entities`, `app/core/policies`, `app/core/ports`, and `app/core/use_cases/{memories,concepts,episodes,scenarios,snapshots}`; matching `tests/operations/{memories,concepts,episodes,scenarios,snapshots,events,memory_domain,protection,librarian}` | 5,800 production lines; matching operation tests |
| 2. Retrieval and knowledge | `app/core/use_cases/{retrieval,knowledge_builder,metrics}`, and matching `tests/operations/{read,recall,retrieval,knowledge_builder}` | 5,800 production lines; matching operation tests |
| 3. Persistence and schema | `app/infrastructure/db`, `migrations`, and matching `tests/operations/{create,update,evidence,persistence}` | 12,700 production/schema lines; matching operation tests |
| 4. Runtime integration | `app/infrastructure/{embeddings,host_apps,local_state,process,system,telemetry}`, `app/entrypoints`, `app/startup`, `app/settings`, and matching `tests/operations/{identity,session_state,guidance,recovery,resilience,telemetry}` plus `tests/infrastructure` | 27,400 production lines; matching runtime/infrastructure tests |
| 5. Project delivery | repository manifests, Docker files, `scripts`, `onboarding_assets`, `docs`, and the remaining test/support surfaces: `tests/{config,_shared,visualization,conftest.py,__init__.py}` | 5,700 delivery lines; 7,400 test/support lines |

The test directories belong to the production subsystem they exercise. This keeps the five scopes mutually exclusive while requiring call-site, configuration, build, and test reference checks for every deletion. The scope map excludes untracked user files: `agents/`, `docs/architecture/explainer-memory-architecture.html`, and `uv.lock`.

## Agent 1 — Domain workflows

shrink: Replace the lazy `__getattr__` export for memory creation with a direct `execute_create_memory` import. Preserve the same package API without the dynamic dispatcher. [app/core/use_cases/memories/add/__init__.py]
shrink: Replace the lazy `__getattr__` export for memory updates with a direct `execute_update_memory` import. Preserve the same package API without the dynamic dispatcher. [app/core/use_cases/memories/update/__init__.py]
shrink: Replace the lazy `__getattr__` export for concept creation with a direct `add_concepts` import. Preserve the same package API without the dynamic dispatcher. [app/core/use_cases/concepts/add/__init__.py]
shrink: Replace the lazy `__getattr__` export for concept display with a direct `show_concept` import. Preserve the same package API without the dynamic dispatcher. [app/core/use_cases/concepts/show/__init__.py]
shrink: Replace the lazy `__getattr__` export for concept updates with a direct `update_concepts` import. Preserve the same package API without the dynamic dispatcher. [app/core/use_cases/concepts/update/__init__.py]
delete: Remove the unused legacy `MemoryEvidenceLink` and `AssociationEdgeEvidenceLink` records and their ID imports. The unified `EvidenceTarget`/`EvidenceSource`/`EvidenceLinkView` model is the only repository consumer. [app/core/entities/evidence.py]
delete: Remove the unused `MemoryKind.is_mature` property and `is_mature_memory_kind` helper. `MATURE_MEMORY_KIND_VALUES` directly supplies the read defaults and retrieval filters. [app/core/entities/memories.py]
delete: Remove the unused `SessionStateResetReason` enum and its sole `Enum` import. Session reset handling uses `SessionState` directly. [app/core/entities/session_state.py]
yagni: Remove the unused `IKeywordSearch` port. Keyword retrieval uses repository corpus access and lexical policy functions directly. [app/core/ports/embeddings/retrieval.py]
delete: Remove `ShadowGitCaptureResult.tree_sha` and its three write-only constructor values. Capture consumers use the commit and changed-path fields only. [app/core/entities/snapshots.py]
delete: Remove the unused `has_positive_lifecycle_signal` helper and `NO_POSITIVE_RETRIEVAL_STATUSES` constant. Retrieval consumers use `POSITIVE_LIFECYCLE_STATUSES` and `lifecycle_retrieval_multiplier`. [app/core/policies/retrieval/ontology_semantics.py]
delete: Remove the unused `_SECTION_NAMES` mapping. Context-pack assembly names each output section directly. [app/core/policies/retrieval/context_pack.py]
yagni: Remove the unused `payload` parameter from `score_candidates` and its `_ = payload` suppression. Candidate scores depend only on the bucketed candidates. [app/core/policies/retrieval/scoring.py]
delete: Remove the uncalled `ScenarioRecordResult.data` compatibility property. Scenario callers and tests serialize with `to_response_data`. [app/core/use_cases/scenarios/record/result.py]
delete: Remove the uncalled `CaptureSnapshotResult.data` compatibility property. Snapshot callers and tests serialize with `to_response_data`. [app/core/use_cases/snapshots/capture_snapshot/result.py]
shrink: Remove the `ConceptAddResult.to_response_data` wrapper that only returns `data`. The result envelope already accepts the tested `data` mapping. [app/core/use_cases/concepts/add/result.py]
shrink: Remove the `ConceptShowResult.to_response_data` wrapper that only returns `data`. The result envelope already accepts the tested `data` mapping. [app/core/use_cases/concepts/show/result.py]
shrink: Remove the `ConceptUpdateResult.to_response_data` wrapper that only returns `data`. The result envelope already accepts the tested `data` mapping. [app/core/use_cases/concepts/update/result.py]
net: -95 lines, -0 deps possible.

## Agent 2 — Retrieval and knowledge

delete: Remove `execute_recall_memory`, which only forwards unchanged arguments to `execute_build_context`; re-export `execute_build_context` under the public recall name. [app/core/use_cases/retrieval/recall/execute.py]
yagni: Replace the read package's lazy `__getattr__` dispatch and `_build_context_pack` forwarding hook with direct imports; its only consumers are two tests that monkeypatch the public lookup. [app/core/use_cases/retrieval/read/__init__.py, app/core/use_cases/retrieval/read/execute.py]
shrink: In `expand_candidates`, merge the duplicate `include_problem_links` and `include_fact_update_links` blocks into one predicate-group loop; the two repeated structural-neighbor branches disappear. [app/core/use_cases/retrieval/expansion.py]
yagni: Replace `build_context.__getattr__` with a direct `execute_build_context` import; no import cycle or deferred-loading consumer exists. [app/core/use_cases/retrieval/build_context/__init__.py]
yagni: In `_select_final_memories`, remove `_FINAL_MEMORY_HARD_CAP` and its `len(selected) >= 32` branch because role quotas total 28 and the fill loop stops at 24. [app/core/use_cases/retrieval/deterministic_graph_recall.py]
yagni: In `_select_concepts`, remove `_CONCEPT_HARD_CAP` because its eight-item slice is always immediately sliced to the six-item target. [app/core/use_cases/retrieval/deterministic_graph_recall.py]
net: -82 lines, -0 deps possible.

## Agent 3 — Persistence and schema

_Audit only; source edits are prohibited._

delete: Remove the unimported runtime SQL-view duplicate. Keep the migration-local `migrations._usage_view_sql` constants used by packaged Alembic upgrades. [app/infrastructure/db/runtime/models/views.py]
delete: Remove the unused restore forwarding module. Use `logical_backup.restore_backup`, which startup and persistence tests already use. [app/infrastructure/db/admin/backups/restore.py]
delete: Remove `to_linked_session`, which has no caller. Pass query rows directly to `linked_session_from_mapping`, as startup already does. [app/infrastructure/db/runtime/queries/model_usage_backfill.py]
delete: Remove the unreferenced `GLOBAL_UTILITY_SQL` migration helper. The initial migration creates `global_utility`; no migration imports this constant. [migrations/_usage_view_sql.py]

net: -1162 lines, -0 deps possible.

## Agent 4 — Runtime integration

yagni: Delete `run_operation_command` in its sole module; it only creates `CliOperationEffects` and delegates to the already lazy `run_cli_operation`. Build the effects in `runner.run_operation_command` and retain that lazy boundary. [app/entrypoints/cli/operation_command.py]
stdlib: Delete the single-use `render` wrapper around `json.dumps`. Call `json.dumps(result, separators=(",", ":"))` in the already importing CLI runner. [app/entrypoints/cli/presenters/json.py]
yagni: Delete the single-use upgrade handler that only invokes its callback. Return `runtime.run_upgrade_command()` directly from the runner's upgrade route. [app/entrypoints/cli/handlers/human/upgrade.py]
net: -51 lines, -0 deps possible.

## Agent 5 — Project delivery

delete: Remove the unused `VisualizationReportPlugin.discovered` property; pytest only registers the plugin and no consumer reads it. Keep `_discovered` as the internal report state. [tests/visualization/report_builder.py]
delete: Remove unused `DiscoveredTest.function_name` and `file_path` fields plus their assignments; rendering uses only `key`, `category_parts`, and `description`. Keep those three fields. [tests/visualization/report_builder.py]

net: -9 lines, -0 deps possible.

## Merged findings

The findings below are deduplicated and ranked by estimated source reduction. Each deletion was re-checked against application imports, tests, package configuration, and migrations. The agent sections keep the scope-level evidence.

### Safe to implement now

delete: Remove the unimported duplicate runtime SQL-view module; historical migrations keep their own view SQL. [app/infrastructure/db/runtime/models/views.py] Implementation: applied; full suite passed.
delete: Remove the unused backup-restore forwarding module; startup already injects `logical_backup.restore_backup`. [app/infrastructure/db/admin/backups/restore.py] Implementation: applied; full suite passed.
yagni: Delete the single-use operation-command wrapper; construct `CliOperationEffects` in the existing lazy runner helper. [app/entrypoints/cli/operation_command.py] Implementation: applied; full suite passed.
delete: Remove unused legacy evidence-link records; the unified evidence model is the sole consumer. [app/core/entities/evidence.py] Implementation: applied; full suite passed.
shrink: Merge the structural problem-link and fact-update loops in `expand_candidates`; the duplicate neighbor branches disappear. [app/core/use_cases/retrieval/expansion.py] Implementation: applied; full suite passed.
delete: Remove the write-only `ShadowGitCaptureResult.tree_sha` field. [app/core/entities/snapshots.py] Implementation: applied; full suite passed.
delete: Remove the unused model-usage row mapper and pass query mappings to the existing core mapper. [app/infrastructure/db/runtime/queries/model_usage_backfill.py] Implementation: applied; full suite passed.
stdlib: Remove the single-use JSON `render` wrapper and use `json.dumps` in the CLI runner. [app/entrypoints/cli/presenters/json.py] Implementation: applied; full suite passed.
yagni: Remove the single-use upgrade handler and call the runtime callback from the runner route. [app/entrypoints/cli/handlers/human/upgrade.py] Implementation: applied; full suite passed.
delete: Remove unused `MemoryKind` maturity helpers. [app/core/entities/memories.py] Implementation: applied; full suite passed.
delete: Remove the unused session-reset enum. [app/core/entities/session_state.py] Implementation: applied; full suite passed.
yagni: Remove the unused keyword-search port. [app/core/ports/embeddings/retrieval.py] Implementation: applied; full suite passed.
delete: Remove unused lifecycle and context-pack constants/helpers. [app/core/policies/retrieval/ontology_semantics.py] Implementation: applied; full suite passed.
delete: Remove the unused context-pack section-name map. [app/core/policies/retrieval/context_pack.py] Implementation: applied; full suite passed.
yagni: Remove the unused `score_candidates` payload parameter; candidates are its sole input. Update direct calls and test doubles to the one-argument policy API. [app/core/policies/retrieval/scoring.py, app/core/use_cases/retrieval/context_pack_pipeline.py] Implementation: applied; full suite passed.
delete: Remove unused result compatibility properties and no-op response wrappers. [app/core/use_cases/scenarios/record/result.py] Implementation: applied; full suite passed.
delete: Remove unused result compatibility properties and no-op response wrappers. [app/core/use_cases/snapshots/capture_snapshot/result.py] Implementation: applied; full suite passed.
delete: Remove unused concept result response wrappers. [app/core/use_cases/concepts/add/result.py] Implementation: applied; full suite passed.
delete: Remove unused concept result response wrappers. [app/core/use_cases/concepts/show/result.py] Implementation: applied; full suite passed.
delete: Remove unused concept result response wrappers. [app/core/use_cases/concepts/update/result.py] Implementation: applied; full suite passed.
yagni: Remove redundant final-memory and concept hard caps; established role quotas and target slices already bound output. [app/core/use_cases/retrieval/deterministic_graph_recall.py] Implementation: applied; full suite passed.
delete: Remove the unreferenced migration SQL constant. [migrations/_usage_view_sql.py] Implementation: applied; full suite passed.
delete: Remove unused visualization-plugin metadata. [tests/visualization/report_builder.py] Implementation: applied; full suite passed.

### Needs follow-up evidence

yagni: Remove the recall forwarding function only after a public API compatibility check confirms the recall name can alias build-context without obscuring the workflow boundary. [app/core/use_cases/retrieval/recall/execute.py]

### Intentionally retained

The lazy exports for memory, concept, read, and build-context packages remain. They preserve existing import seams; the read seam is an explicit test hook restored by history. [app/core/use_cases/memories/add/__init__.py]

The read package's lazy `build_context_pack` hook remains. Two behavior tests monkeypatch the public lookup, so direct imports would remove a deliberate test seam. [app/core/use_cases/retrieval/read/__init__.py]

All seven declared production dependencies have direct production consumers. No manifest or lockfile change is supported. [pyproject.toml]

## Implementation and validation

Implemented every item in Safe to implement now. The source delta is 1,349 net lines removed. No dependency changed.

Deferred: the recall forwarding alias needs a public API compatibility decision.

Retained: the lazy package exports and the public read hook preserve current import and test seams. All declared production dependencies have active production consumers.

Validation passed:

- `python -m compileall -q app tests migrations`
- 163 focused tests passed; 27 environment-dependent tests skipped.
- After the scoring API cleanup, `scripts/run_tests` with the repository `.venv` completed: 745 passed in 166.53 seconds.
- `uv build` created the source distribution and wheel in a temporary directory.
- `git diff --check` and the repository-wide stale-reference search passed.

No configured type checker or linter was available in the repository environment.

Estimated cyclomatic complexity fell from 18 to 17 in `expand_candidates` and from 15 to 14 in `_select_final_memories`. `_select_concepts` remains 7 after redundant cap removal.
