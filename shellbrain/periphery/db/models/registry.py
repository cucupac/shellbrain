"""This module imports all SQLAlchemy table modules so metadata is fully registered."""

from shellbrain.periphery.db.models import (
    associations,
    episodes,
    evidence,
    experiences,
    instance_metadata,
    memories,
    telemetry,
    utility,
)
from shellbrain.periphery.db.models.metadata import metadata


_ = (associations, episodes, evidence, experiences, instance_metadata, memories, telemetry, utility)

target_metadata = metadata
