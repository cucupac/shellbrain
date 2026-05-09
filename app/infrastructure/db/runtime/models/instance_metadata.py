"""SQLAlchemy Core table for instance classification and safety metadata."""

from sqlalchemy import Column, String, Table, Text
from sqlalchemy.dialects.postgresql import TIMESTAMP

from app.infrastructure.db.runtime.models.metadata import metadata


instance_metadata = Table(
    "instance_metadata",
    metadata,
    Column("instance_id", String, primary_key=True),
    Column("instance_mode", String, nullable=False),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("created_by", String, nullable=False),
    Column("notes", Text, nullable=True),
)
