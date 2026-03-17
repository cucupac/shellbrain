# Test Visualization Report

Pytest automatically generates a terse markdown status report at:

- `tests/visualization/artifacts/tests_status.md`

The report is updated on every test run and includes:

- one-line intuitive test docstrings
- `✅`/`❌`/`⚪` status
- full-suite discovery across `tests/config/*` and `tests/operations/*`
- top-level headings for the major test groups:
  - `# Config Tests`
  - `# Create Tests`
  - `# Episodes Tests`
  - `# Events Tests`
  - `# Persistence Tests`
  - `# Read Tests`
  - `# Update Tests`
- nested headings for validation/execution groupings and deeper folder slices
- one-line descriptions computed deterministically from test-function docstring first lines
- helper/report files are excluded:
  - `tests/visualization/*`
  - `conftest.py`
  - `__init__.py`
  - private/helper paths such as `_shared`
- directory mapping:
  - `tests/config/**` -> `# Config Tests`
  - `tests/operations/<operation>/validation/**` -> `<operation>/validation`
  - `tests/operations/<operation>/execution/**` -> `<operation>/execution`
  - `tests/operations/<operation>/**` (when no validation/execution split exists) -> `<operation>`
