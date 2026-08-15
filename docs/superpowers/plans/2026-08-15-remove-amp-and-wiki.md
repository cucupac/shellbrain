# Remove Amp and Shellbrain Wiki Implementation Plan

> **For agentic workers:** Follow this plan task by task. Keep the repository releasable after each commit. Do not retain compatibility aliases, dormant adapters, or replacement abstractions for either removed feature.

**Goal:** Remove every current Amp artifact and the complete experimental Shellbrain Wiki feature, release Shellbrain 0.1.51, and fast-forward the finished work into `main`.

**Architecture:** Delete the Wiki vertical slice from CLI through use cases, reporting, inner-agent execution, persistence ports, relational adapters, and configuration. Remove Wiki-only extensions from shared APIs. Preserve the historical Wiki migration, then add a forward migration that drops its table. Amp has no tracked implementation; delete its untracked plan and add no placeholder provider code.

**Tech Stack:** Python 3.11+, Pydantic, SQLAlchemy/Alembic, pytest, Hatchling, Git, GitHub Actions.

**Spec:** `docs/superpowers/plans/2026-08-15-remove-amp-and-wiki.md` is the canonical removal specification.

## Global Constraints

- Remove features outright. Do not add aliases, compatibility fields, no-op adapters, or feature flags.
- Keep `migrations/versions/20260606_0037_wiki_summaries.py` unchanged because installations may have applied it.
- Add one migration after `20260606_0037` that drops the Wiki table.
- Do not add an Amp dependency. No tracked Amp implementation or Amp SDK dependency exists.
- Preserve unrelated untracked files, especially `docs/architecture/explainer-memory-architecture.html` and `uv.lock`.
- Work on `codex/remove-amp-wiki`, starting from current `origin/main`.
- Release version `0.1.51` with annotated tag `v0.1.51`.
- Push the release tag only after fast-forwarding the finished work into `main`.
- If `origin/main` moves before merge, stop, reconcile it deliberately, and rerun validation.

## Current Evidence

- `main`, `origin/main`, and `v0.1.50` point to `18b44b3`; `pyproject.toml` declares `0.1.50`.
- Amp is absent from tracked source, tests, dependencies, and configuration. Its only artifact is untracked plan `agents/plans/2026-07-27-first-class-amp-cli-support.md`.
- Wiki is a full vertical slice: CLI, local HTTP reporting, use cases, summary inner agent, persistence, tests, and migration `20260606_0037`.
- `.github/workflows/release.yml` publishes wheel and source distributions for pushed `v*` tags.

## Deletion Map

Delete these Wiki-only files and directories:

```text
app/core/entities/repositories.py
app/core/entities/wiki_summaries.py
app/core/policies/wiki_summary_freshness.py
app/core/ports/db/repository_index.py
app/core/ports/db/wiki_summaries.py
app/core/use_cases/wiki/
app/entrypoints/cli/handlers/human/wiki.py
app/infrastructure/db/runtime/models/wiki_summaries.py
app/infrastructure/db/runtime/repos/relational/repository_index_repo.py
app/infrastructure/db/runtime/repos/relational/wiki_summaries_repo.py
app/infrastructure/reporting/wiki/
app/startup/wiki.py
tests/operations/wiki/
```

Remove Wiki declarations from these shared files:

```text
app/core/entities/concepts.py
app/core/entities/evidence.py
app/core/entities/inner_agents.py
app/core/ports/db/concept_repositories.py
app/core/ports/db/memory_repositories.py
app/core/ports/db/unit_of_work.py
app/core/ports/host_apps/inner_agents.py
app/entrypoints/cli/parser/builder.py
app/entrypoints/cli/runner.py
app/entrypoints/cli/runtime.py
app/infrastructure/db/runtime/models/registry.py
app/infrastructure/db/runtime/repos/relational/concepts_repo.py
app/infrastructure/db/runtime/repos/relational/evidence_repo.py
app/infrastructure/db/runtime/repos/relational/memories_repo.py
app/infrastructure/db/runtime/uow.py
app/infrastructure/host_apps/inner_agents/claude_cli.py
app/infrastructure/host_apps/inner_agents/codex_cli.py
app/infrastructure/host_apps/inner_agents/output_parser.py
app/infrastructure/host_apps/inner_agents/prompt.py
app/settings/internal-agents/defaults.yaml
app/startup/cli.py
app/startup/cli_runtime.py
app/startup/internal_agent_config.py
app/startup/internal_agents.py
```

## Task 1: Establish the Branch and Baseline

**Files:** delete `agents/plans/2026-07-27-first-class-amp-cli-support.md`.

- [ ] **Confirm the start and create the branch.**

```bash
git fetch origin
git status --short
test "$(git branch --show-current)" = "main"
test "$(git rev-parse main)" = "$(git rev-parse origin/main)"
test "$(git describe --tags --exact-match main)" = "v0.1.50"
git switch -c codex/remove-amp-wiki
./scripts/run_tests
```

Expected: baseline passes; unrelated untracked files remain untracked.

- [ ] **Delete the untracked Amp plan and prove no implementation exists.**

```bash
test ! -e agents/plans/2026-07-27-first-class-amp-cli-support.md
git grep -n -i -E 'amp-sdk|amp_sdk|ampcode|AMP_CURRENT_THREAD_ID|provider:[[:space:]]*amp' -- ':!docs/superpowers/plans/**'
rg -n -i '(^|[^&[:alnum:]_])amp([^;[:alnum:]_]|$)' app tests pyproject.toml requirements.txt migrations .github || true
```

Expected: no results. Add no Amp tombstone or disabled provider.

## Task 2: Delete the Complete Wiki Runtime Slice

**Files:** all paths in the Deletion Map; shared tests above plus `tests/config/test_packaging_smoke.py` and `tests/infrastructure/test_codex_inner_agent.py`.

- [ ] **Delete every Wiki-only path with patch-based deletion.** Leave no empty package or re-export module.

- [ ] **Remove CLI composition.** Remove Wiki help, examples, `_WIKI_HELP`, parser, and options from `builder.py`; dispatch from `runner.py`; `run_wiki` from both runtime protocols; startup wiring from `startup/cli.py`.

- [ ] **Remove the Wiki summary inner agent end to end.** Remove:

  - `"wiki_summary"` and `WikiSummarySettings` from inner-agent entities.
  - `WikiSummaryAgentRequest`, `WikiSummaryAgentResult`, and `IWikiSummaryAgentRunner` from the port.
  - Wiki config, provider checks, getters, factories, and `_runner_for` types from startup.
  - The entire `wiki_summary:` block from defaults.
  - Wiki prompt rendering and output parsing.
  - Wiki methods, imports, result helpers, and error helpers from Codex and Claude runners.
  - `"wiki_summary"` from the Codex admin-environment scrub set.

- [ ] **Remove persistence and shared Wiki extensions.** Remove:

  - `repository_index` and `wiki_summaries` from the unit-of-work port and implementation.
  - Wiki model registration.
  - `ConceptEvidence.evidence_id`.
  - `EvidenceLinkedTarget` and `EvidenceDetail`.
  - `list_concepts` and `find_concepts_for_anchor_ids` from port and adapter.
  - `IMemoriesRepo.list_recent` and implementation.
  - `IEvidenceRepo.get_evidence_detail`, `_linked_target_from_row`, and implementation.
  - Wiki-only `evidence_id` selection and mapping in concept conversion.

Do not generalize or relocate these APIs; they have no non-Wiki callers.

- [ ] **Finish shared test cleanup.** Remove all Wiki command, help, dispatch, option, config, runner, model, parser, and inner-agent-mode cases and imports. Remove the obsolete Wiki settings assertion from packaging smoke. Do not add tombstone tests for a deleted command or deleted config field.

- [ ] **Prove runtime deletion and run focused validation.**

```bash
test ! -d app/core/use_cases/wiki
test ! -d app/infrastructure/reporting/wiki
test ! -d tests/operations/wiki
rg -n -i '\bwiki\b|wiki_summary|WikiSummary|run_wiki|wiki_summaries|RepositoryIndex|RepositorySummary' app tests README.md docs onboarding_assets pyproject.toml --glob '!docs/superpowers/plans/**'
.venv/bin/python -m compileall -q app
.venv/bin/python -m pytest -q tests/config/test_architecture_boundaries.py tests/config/test_cli_surface.py tests/config/test_loader.py tests/infrastructure/test_codex_inner_agent.py
```

Expected: search has no results and tests pass.

- [ ] **Commit without staging unrelated files.**

```bash
git add -u
git add docs/superpowers/plans/2026-08-15-remove-amp-and-wiki.md
git diff --cached --name-status
git status --short
git commit -m "refactor: remove experimental wiki"
```

## Task 3: Remove the Wiki Table from the Live Schema

**Files:** create `migrations/versions/20260815_0038_drop_wiki_summaries.py`; modify both packaging-smoke tests and `.github/workflows/release.yml`; preserve `20260606_0037_wiki_summaries.py` unchanged.

- [ ] **Make both packaging tests require `CURRENT_ALEMBIC_HEAD = "20260815_0038"`.** After a fresh installed-package migration, query `SELECT to_regclass('public.wiki_summaries');` and assert `None`.

- [ ] **Run the schema contract before creating the migration.**

```bash
.venv/bin/python -m pytest -q tests/config/test_packaging_smoke.py tests/operations/telemetry/execution/packaging_smoke/test_installed_package_migrates_usage_telemetry_schema.py
```

Expected: fail because the new head does not exist.

- [ ] **Create revision `20260815_0038` with `down_revision = "20260606_0037"`.** `upgrade()` drops `idx_wiki_summaries_repo_status_updated`, then `wiki_summaries`. `downgrade()` copies the exact `op.create_table` and `op.create_index` definitions from `0037`; it restores an empty cache, not deleted data. Do not edit history.

```python
def upgrade() -> None:
    op.drop_index("idx_wiki_summaries_repo_status_updated", table_name="wiki_summaries")
    op.drop_table("wiki_summaries")
```

- [ ] **Add the cleanup migration to the release workflow's required wheel-file set.**

```text
migrations/versions/20260815_0038_drop_wiki_summaries.py
```

- [ ] **Validate and commit the schema cleanup.**

```bash
.venv/bin/python -m pytest -q tests/config/test_packaging_smoke.py tests/operations/telemetry/execution/packaging_smoke/test_installed_package_migrates_usage_telemetry_schema.py
rg -n -i '\bwiki\b|wiki_summary|wiki_summaries' migrations/versions
git add migrations/versions/20260815_0038_drop_wiki_summaries.py tests/config/test_packaging_smoke.py tests/operations/telemetry/execution/packaging_smoke/test_installed_package_migrates_usage_telemetry_schema.py .github/workflows/release.yml
git diff --cached --name-status
git commit -m "db: drop wiki summary cache"
```

Expected: tests pass; only migrations `0037` and `0038` contain Wiki schema terms.

## Task 4: Validate and Prepare Release 0.1.51

**Files:** modify `pyproject.toml`.

- [ ] **Run complete validation and final searches.**

```bash
./scripts/run_tests
git grep -n -i -E 'amp-sdk|amp_sdk|ampcode|AMP_CURRENT_THREAD_ID|provider:[[:space:]]*amp' -- ':!docs/superpowers/plans/**'
rg -n -i '\bwiki\b|wiki_summary|WikiSummary|run_wiki|wiki_summaries|RepositoryIndex|RepositorySummary' app tests README.md docs onboarding_assets pyproject.toml --glob '!docs/superpowers/plans/**' --glob '!tests/config/test_packaging_smoke.py'
rg -n -i '\bwiki\b|wiki_summary|wiki_summaries' migrations/versions tests/config/test_packaging_smoke.py
```

Expected: tests pass; no Amp or live Wiki results; only migrations `0037` and `0038` contain Wiki terms.

- [ ] **Change `version = "0.1.50"` to `version = "0.1.51"`.**

- [ ] **Build and inspect isolated release artifacts.**

```bash
release_dist="$(mktemp -d)"
.venv/bin/python -m build --outdir "$release_dist"
.venv/bin/python -m twine check "$release_dist"/*
RELEASE_DIST="$release_dist" .venv/bin/python - <<'PY'
import os
from pathlib import Path
from zipfile import ZipFile

wheel = next(Path(os.environ["RELEASE_DIST"]).glob("shellbrain-0.1.51-*.whl"))
with ZipFile(wheel) as archive:
    names = archive.namelist()
assert any(name.endswith("migrations/versions/20260815_0038_drop_wiki_summaries.py") for name in names)
assert not any(
    name.startswith("app/")
    and ("/wiki/" in name or name.endswith("wiki.py") or "wiki_summaries.py" in name)
    for name in names
)
PY
```

Expected: build and Twine checks pass; the wheel includes `0038` and no Wiki application module.

- [ ] **Commit the release version.**

```bash
git add pyproject.toml
git diff --cached
git commit -m "release: 0.1.51"
git status --short
```

Expected: only the two preserved unrelated untracked files remain.

## Task 5: Fast-Forward to Main, Tag, and Publish

- [ ] **Recheck remote-main safety.**

```bash
git fetch origin
test "$(git rev-parse main)" = "$(git rev-parse origin/main)"
test -z "$(git tag --list v0.1.51)"
```

Stop if either assertion fails.

- [ ] **Fast-forward into main and create the tag.**

```bash
git switch main
git merge --ff-only codex/remove-amp-wiki
test "$(git rev-parse main)" = "$(git rev-parse codex/remove-amp-wiki)"
git tag -a v0.1.51 -m "Shellbrain 0.1.51"
test "$(git rev-list -n 1 v0.1.51)" = "$(git rev-parse main)"
```

- [ ] **Push main, then the release tag.**

```bash
git push origin main
git push origin v0.1.51
```

Expected: the tag push starts `.github/workflows/release.yml`.

- [ ] **Wait for publication and verify final state.**

```bash
run_id="$(gh run list --workflow Release --limit 20 --json databaseId,headBranch --jq '.[] | select(.headBranch == "v0.1.51") | .databaseId' | head -n 1)"
test -n "$run_id"
gh run watch "$run_id" --exit-status
git status --short
git log --oneline --decorate -5
```

Expected: workflow succeeds; `main`, `origin/main`, and `v0.1.51` point to the same commit. If publication fails after pushing the tag, do not move or reuse it; fix forward with the next patch version.

## Final Acceptance Criteria

- [ ] No Amp source, dependency, configuration, test, implementation plan, or compatibility stub remains; this removal plan is the only Amp planning record.
- [ ] CLI help, parsing, dispatch, and runtime composition contain no Wiki command.
- [ ] Inner-agent defaults and strict configuration contain no `wiki_summary` field.
- [ ] No Wiki runtime, inner-agent, reporting, persistence, model, or test package remains.
- [ ] Migration `0037` is unchanged; `0038` drops `wiki_summaries` and is Alembic head.
- [ ] Fresh installed-package migration leaves no `wiki_summaries` table.
- [ ] Full tests and release artifact checks pass.
- [ ] `pyproject.toml` declares `0.1.51`.
- [ ] `main`, `origin/main`, and annotated tag `v0.1.51` point to the release commit.
- [ ] The tag-triggered release workflow succeeds.
