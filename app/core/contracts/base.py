"""Shared contract model primitives."""

from pydantic import BaseModel, ConfigDict


class StrictBaseModel(BaseModel):
    """Base model for typed core contracts that reject unknown fields."""

    model_config = ConfigDict(extra="forbid")
