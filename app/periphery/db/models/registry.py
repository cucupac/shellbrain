"""This module imports all SQLAlchemy table modules so metadata is fully registered."""

from app.periphery.db.models import associations, episodes, evidence, experiences, memories, utility
from app.periphery.db.models.metadata import metadata


_ = (associations, episodes, evidence, experiences, memories, utility)

target_metadata = metadata
