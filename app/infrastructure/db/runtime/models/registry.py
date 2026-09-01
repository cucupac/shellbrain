"""This module imports all SQLAlchemy table modules so metadata is fully registered."""

from app.infrastructure.db.runtime.models import (  # noqa: F401
    associations,
    concepts,
    episodes,
    evidence,
    experiences,
    instance_metadata,
    knowledge_builder,
    memories,
    problem_runs,
    snapshots,
    telemetry,
    utility,
)
from app.infrastructure.db.runtime.models.metadata import metadata


target_metadata = metadata
