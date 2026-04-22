"""This module imports all SQLAlchemy table modules so metadata is fully registered."""

from app.periphery.db.models import (
    associations,
    concepts,
    episodes,
    evidence,
    experiences,
    instance_metadata,
    memories,
    telemetry,
    utility,
)
from app.periphery.db.models.metadata import metadata


_ = (associations, concepts, episodes, evidence, experiences, instance_metadata, memories, telemetry, utility)

target_metadata = metadata
