# Remove Public Recall Sources Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove `brief.sources` from `shellbrain recall` output without weakening internal provenance or recall telemetry.

**Architecture:** Delete source rendering at the two shared brief producers: deterministic rendering and provider normalization. Keep `read_trace` and `source_items` as private telemetry because they validate autonomous recall and support observability. Stop mapping those private records back into the public brief. New telemetry rows leave the existing nullable `output_section` database column empty; do not add a migration just to remove historical storage.

**Tech Stack:** Python 3.11, Pydantic, SQLAlchemy, PostgreSQL, pytest.

## Scope Rules

- Remove only the public `brief.sources` field and code or assertions that exist to produce it.
- Keep `status`, the other nine brief fields, `fallback_reason`, and `errors` unchanged.
- Keep autonomous `read_trace`, deterministic `source_items`, `recall_source_items`, and source-based fallback decisions.
- Do not add compatibility code, a response version, a replacement provenance field, or a database migration.
- Do not edit onboarding skills: the audited Codex, Claude, and Cursor guidance describes recall input and does not document `brief.sources`.
- Do not edit historical migrations. The nullable `recall_source_items.output_section` column remains for already-applied schemas and receives `NULL` for new rows.

---

### Task 1: Remove sources from every public brief producer

**Files:**

- Modify: `tests/operations/recall/execution/test_build_context.py`
- Modify: `app/core/use_cases/retrieval/build_context/execute.py`
- Modify: `app/core/use_cases/retrieval/deterministic_graph_recall.py`

- [ ] **Step 1: Change the existing response assertions to define the smaller contract**

Replace the three assertions that read `brief["sources"]` with absence checks, and add the same check to the existing positive deterministic-only case:

```python
assert "sources" not in result.data["brief"]
```

The affected paths are autonomous provider success, deterministic synthesis success, positive deterministic-only fallback, and no-context deterministic output. Do not create a new schema test file.

- [ ] **Step 2: Run the focused test and confirm the old producers fail the new contract**

Run:

```bash
.venv/bin/python -m pytest -q tests/operations/recall/execution/test_build_context.py
```

Expected: the new absence assertions fail because the current brief builders still add `sources`.

- [ ] **Step 3: Delete public source rendering from deterministic briefs**

In `deterministic_brief_from_graph_pack`, remove `"sources"` from both the empty and populated return values. Then delete `_sources_from_graph_pack`; `source_items_from_graph_pack` remains because telemetry still calls it.

The populated brief should end like this:

```python
return {
    "summary": _summary(memories=memories, concepts=concept_items),
    "constraints": _truncate_list(constraints, 6),
    "known_traps": _truncate_list(known_traps, 6),
    "prior_cases": _truncate_list(prior_cases, 6),
    "concept_orientation": _truncate_list(...),
    "anchors": _truncate_list(...),
    "conflicts": _truncate_list(...),
    "gaps": [],
    "next_checks": _next_checks(pack),
}
```

- [ ] **Step 4: Delete public source rendering from provider-normalized briefs**

Make `_normalize_provider_brief` accept only `brief`, remove its `"sources"` entry, and simplify both callers:

```python
brief = _normalize_provider_brief(inner_agent_result.brief or {})
```

```python
brief=_normalize_provider_brief(synthesis_result.brief),
```

Remove `_sources_from_source_items` entirely. Remove `"sources": []` from `_no_context_brief`. Keep `_source_items_from_read_trace`, `_provider_trace_state`, and the private telemetry payload unchanged.

- [ ] **Step 5: Run the focused recall tests**

Run:

```bash
.venv/bin/python -m pytest -q \
  tests/operations/recall/execution/test_build_context.py \
  tests/operations/recall/execution/test_deterministic_graph_recall.py
```

Expected: PASS.

- [ ] **Step 6: Commit the public producer cleanup**

```bash
git add app/core/use_cases/retrieval/build_context/execute.py \
  app/core/use_cases/retrieval/deterministic_graph_recall.py \
  tests/operations/recall/execution/test_build_context.py \
  docs/superpowers/plans/2026-07-14-remove-recall-sources.md
git commit -m "refactor: remove sources from recall briefs"
```

---

### Task 2: Remove the obsolete agent output contract and documentation

**Files:**

- Modify: `tests/infrastructure/test_codex_inner_agent.py`
- Modify: `app/infrastructure/host_apps/inner_agents/prompt.py`
- Modify: `tests/config/test_cli_surface.py`
- Modify: `README.md`

- [ ] **Step 1: Update the existing prompt tests first**

In `test_build_context_prompt_allows_read_only_shellbrain_commands`, replace the `used_in` assertion with:

```python
assert '"sources":' not in prompt
assert "used_in" not in prompt
```

In `test_build_context_synthesis_prompt_uses_only_deterministic_pack`, replace the positive provenance assertion with:

```python
assert '"sources":' not in prompt
assert "deterministic source provenance" not in prompt
```

- [ ] **Step 2: Run the prompt tests and confirm they fail against the stale prompt**

Run:

```bash
.venv/bin/python -m pytest -q tests/infrastructure/test_codex_inner_agent.py
```

Expected: the two changed assertions fail because the prompt still requests or describes public sources.

- [ ] **Step 3: Remove sources from the autonomous output contract**

In `render_build_context_prompt`, delete the `output_contract.brief.sources` object. Keep `read_trace.source_ids` and `read_trace.concept_refs`; they are private evidence that validates the autonomous result.

Update the autonomous prose to say:

```text
Full provenance belongs in telemetry; keep visible anchors minimal.
```

End the brief-field list at `next_checks` instead of `sources`.

- [ ] **Step 4: Remove the stale synthesis claim**

Remove both the redundant prohibition and the now-false sentence saying Shellbrain attaches deterministic source provenance after synthesis. The output contract already defines the canonical shape:

```text
Return only valid JSON matching `output_contract`. Return a `brief` object only.
Keep each list compact.
```

- [ ] **Step 5: Update the public example and the CLI test fixture**

In `README.md`, change “with sources cited” to “for the task at hand” and remove the `sources` array from the response example. In `test_main_dispatches_recall_query`, reduce the fake brief to:

```python
"brief": {"summary": "stub"},
```

No onboarding asset changes are needed: the repository-wide audit found no documented public source field there.

- [ ] **Step 6: Run prompt, CLI, and documentation-facing tests**

Run:

```bash
.venv/bin/python -m pytest -q \
  tests/infrastructure/test_codex_inner_agent.py \
  tests/infrastructure/test_claude_inner_agent.py \
  tests/config/test_cli_surface.py \
  tests/config/test_onboarding_assets.py
```

Expected: PASS.

- [ ] **Step 7: Commit the prompt and documentation cleanup**

```bash
git add app/infrastructure/host_apps/inner_agents/prompt.py \
  tests/infrastructure/test_codex_inner_agent.py \
  tests/config/test_cli_surface.py \
  README.md
git commit -m "docs: remove recall sources from the public contract"
```

---

### Task 3: Stop labeling private telemetry as a public sources section

**Files:**

- Modify: `tests/operations/recall/execution/test_build_context.py`
- Modify: `tests/operations/telemetry/execution/recall_summaries/test_recall_summary_record_writes.py`
- Modify: `app/core/use_cases/retrieval/build_context/execute.py`
- Modify: `app/core/use_cases/retrieval/deterministic_graph_recall.py`
- Modify: `app/infrastructure/telemetry/recall_records.py`
- Modify: `app/infrastructure/telemetry/records.py`

- [ ] **Step 1: Tighten the existing telemetry assertions**

In the autonomous provider test, assert the private source rows no longer claim a public output section:

```python
source_items = result.data["_telemetry"]["source_items"]
assert source_items
assert all("output_section" not in item for item in source_items)
```

In the recall telemetry integration test:

- replace both public `brief["sources"]` assertions with `assert "sources" not in ...`;
- change the three expected `output_section` values from `"sources"` to `None`;
- remove `"sources": []` from `_FakeInnerAgentRunner.brief`.

Keep every assertion that proves `recall_source_items` rows are persisted.

- [ ] **Step 2: Run the focused unit test and confirm the stale labels fail**

Run:

```bash
.venv/bin/python -m pytest -q tests/operations/recall/execution/test_build_context.py
```

Expected: the new private-telemetry assertion fails because source items still contain `output_section="sources"`.

- [ ] **Step 3: Remove the obsolete mapping from in-memory telemetry**

Delete `"output_section": "sources"` from both source-item builders:

- `source_items_from_graph_pack`
- `_source_items_from_read_trace`

Their rows should contain only `ordinal`, `source_kind`, `source_id`, and `input_section`.

- [ ] **Step 4: Let the existing nullable database column default to NULL**

Remove `output_section` from `RecallSourceItemRecord` and stop passing it in `build_recall_summary_records`. The repository insert already uses `asdict`, so omitting the field lets PostgreSQL store `NULL` without new code:

```python
@dataclass(frozen=True)
class RecallSourceItemRecord:
    invocation_id: str
    ordinal: int
    source_kind: str
    source_id: str
    input_section: str
```

Do not modify `migrations/versions/20260508_0016_recall_telemetry.py` or add a migration. Do not remove the column from SQLAlchemy table metadata; it describes the already-deployed table.

- [ ] **Step 5: Run the focused non-persistence tests**

Run:

```bash
.venv/bin/python -m pytest -q \
  tests/operations/recall/execution/test_build_context.py \
  tests/operations/recall/execution/test_deterministic_graph_recall.py
```

Expected: PASS. The PostgreSQL assertion is exercised by the complete suite in Task 4.

- [ ] **Step 6: Commit the telemetry cleanup**

```bash
git add app/core/use_cases/retrieval/build_context/execute.py \
  app/core/use_cases/retrieval/deterministic_graph_recall.py \
  app/infrastructure/telemetry/recall_records.py \
  app/infrastructure/telemetry/records.py \
  tests/operations/recall/execution/test_build_context.py \
  tests/operations/telemetry/execution/recall_summaries/test_recall_summary_record_writes.py
git commit -m "refactor: keep recall provenance private"
```

---

### Task 4: Verify the deletion is complete

**Files:**

- Verify only; no planned modifications.

- [ ] **Step 1: Search for stale public-contract references**

Run:

```bash
rg -n '"sources":|with sources cited|deterministic source provenance|"used_in"' \
  app/core/use_cases/retrieval \
  app/infrastructure/host_apps/inner_agents/prompt.py \
  README.md docs onboarding_assets \
  --glob '!docs/superpowers/plans/**'
rg -n 'brief.*\["sources"\]' \
  tests/operations/recall \
  tests/operations/telemetry/execution/recall_summaries \
  tests/config/test_cli_surface.py
```

Expected: no matches. Generic internal names such as `source_items`, `source_ids`, `has_sources`, and the historical migration constraint are intentionally retained.

- [ ] **Step 2: Run the focused recall surface**

Run:

```bash
.venv/bin/python -m pytest -q \
  tests/config/test_cli_surface.py \
  tests/config/test_onboarding_assets.py \
  tests/operations/recall \
  tests/infrastructure/test_codex_inner_agent.py \
  tests/infrastructure/test_claude_inner_agent.py
```

Expected: PASS.

- [ ] **Step 3: Run the guarded complete suite, including PostgreSQL telemetry**

Run:

```bash
./scripts/run_tests
```

Expected: PASS, including `test_recall_summary_record_writes.py`, with persisted private source rows and `output_section IS NULL`.

- [ ] **Step 4: Check the final diff**

Run:

```bash
git diff --check HEAD~3..HEAD
git status --short
```

Expected: no whitespace errors and no uncommitted implementation changes.

## Deliberately Skipped

- No response version or compatibility shim: callers receive the smaller brief immediately.
- No replacement `citations`, `evidence`, or `provenance` field: that would recreate the clutter under a new name.
- No change to recall retrieval, source validation, fallback logic, or telemetry source rows.
- No database migration: the nullable historical column can safely remain empty.
- No skill or onboarding rewrite: none of those assets expose the response field being removed.
