"""Fixture wiring for telemetry-first operation tests."""

from __future__ import annotations

import pytest
from sqlalchemy import text

from shellbrain.periphery.db.models.registry import target_metadata
from tests.operations._shared.docker_persistence_fixtures import *  # noqa: F401,F403
from tests.operations._shared.integration_db_fixtures import (  # noqa: F401
    count_rows,
    db_dsn,
    fetch_rows,
    integration_engine,
    integration_session_factory,
    seed_default_evidence_events,
    seed_episode,
    seed_episode_event,
    seed_memory,
    stub_embedding_provider,
    uow_factory,
)
from tests.operations._shared.telemetry_db_fixtures import *  # noqa: F401,F403
from tests.operations.episodes.conftest import claude_code_transcript_fixture, codex_transcript_fixture  # noqa: F401


@pytest.fixture
def telemetry_db_reset(integration_engine):
    """Truncate all relational tables before one DB-backed telemetry test."""

    table_names = [table.name for table in reversed(target_metadata.sorted_tables)]
    if table_names:
        joined = ", ".join(table_names)
        with integration_engine.begin() as conn:
            conn.execute(text(f"TRUNCATE TABLE {joined} RESTART IDENTITY CASCADE;"))
