"""Core response payload contracts."""

from typing import Any

from pydantic import BaseModel, Field


class UseCaseResult(BaseModel):
    """Typed payload returned by core use cases before handler wrapping."""

    data: dict[str, Any] = Field(default_factory=dict)
