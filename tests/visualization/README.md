# Test Visualization Report

Pytest automatically generates a terse markdown status report at:

- `tests/visualization/artifacts/write_validation_status.md`

The report is updated on every test run and includes:

- one-line intuitive test docstrings
- `✅`/`❌`/`⚪` status
- category sections (`write/validation`, `read`, `update`)
- directory mapping:
  - `tests/operations/write/validation/**` -> `write/validation`
  - `tests/operations/read/**` -> `read`
  - `tests/operations/update/**` -> `update`
