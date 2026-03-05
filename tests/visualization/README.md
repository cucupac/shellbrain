# Test Visualization Report

Pytest automatically generates a terse markdown status report at:

- `tests/visualization/artifacts/tests_status.md`

The report is updated on every test run and includes:

- one-line intuitive test docstrings
- `✅`/`❌`/`⚪` status
- category sections computed deterministically from `tests/operations/*` folder paths
- one-line descriptions computed deterministically from test-function docstring first lines
- directory mapping:
  - `tests/operations/<operation>/validation/**` -> `<operation>/validation`
  - `tests/operations/<operation>/execution/**` -> `<operation>/execution`
  - `tests/operations/<operation>/**` (when no validation/execution split exists) -> `<operation>`
