"""This module imports all SQLAlchemy table modules so metadata is fully registered."""

from app.infrastructure.db.models import (
    associations,
    concepts,
    episodes,
    evidence,
    experiences,
    instance_metadata,
    memories,
    problem_runs,
    telemetry,
    utility,
)
from app.infrastructure.db.models.metadata import metadata


_ = (associations, concepts, episodes, evidence, experiences, instance_metadata, memories, problem_runs, telemetry, utility)

target_metadata = metadata
