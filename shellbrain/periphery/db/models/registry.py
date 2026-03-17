"""This module imports all SQLAlchemy table modules so metadata is fully registered."""

from shellbrain.periphery.db.models import associations, episodes, evidence, experiences, memories, utility
from shellbrain.periphery.db.models.metadata import metadata


_ = (associations, episodes, evidence, experiences, memories, utility)

target_metadata = metadata
