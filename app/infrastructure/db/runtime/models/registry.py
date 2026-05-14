"""This module imports all SQLAlchemy table modules so metadata is fully registered."""

from app.infrastructure.db.runtime.models import (
    associations,
    concepts,
    episodes,
    evidence,
    experiences,
    instance_metadata,
    knowledge_builder,
    memories,
    problem_runs,
    telemetry,
    utility,
)
from app.infrastructure.db.runtime.models.metadata import metadata


_ = (
    associations,
    concepts,
    episodes,
    evidence,
    experiences,
    instance_metadata,
    knowledge_builder,
    memories,
    problem_runs,
    telemetry,
    utility,
)

target_metadata = metadata
