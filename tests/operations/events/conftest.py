"""Shared fixture wiring for events operation tests."""

from tests.operations._shared.integration_db_fixtures import *  # noqa: F401,F403
from tests.operations.episodes.conftest import (  # noqa: F401
    claude_code_transcript_fixture,
    codex_transcript_fixture,
)
