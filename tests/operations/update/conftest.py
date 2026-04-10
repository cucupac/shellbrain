"""Shared fixture wiring for update operation tests."""

import pytest

from tests.operations._shared.integration_db_fixtures import *  # noqa: F401,F403


@pytest.fixture(autouse=True)
def _seed_repo_a_evidence_events(clear_database, seed_default_evidence_events):  # noqa: ANN001
    """Seed default repo-a episode events so evidence refs point to real stored events."""

    _ = clear_database
    seed_default_evidence_events(repo_id="repo-a")
