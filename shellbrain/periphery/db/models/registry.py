"""This module imports all SQLAlchemy table modules so metadata is fully registered."""

from shellbrain.periphery.db.models import associations, episodes, evidence, experiences, memories, telemetry, utility
from shellbrain.periphery.db.models.metadata import metadata


_ = (associations, episodes, evidence, experiences, memories, telemetry, utility)

target_metadata = metadata
