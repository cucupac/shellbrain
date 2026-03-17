"""This module defines standardized response envelopes for operation results."""

from typing import Any, Literal

from pydantic import BaseModel, Field

from shellbrain.core.contracts.errors import ErrorDetail


class OperationResult(BaseModel):
    """This model defines a deterministic response envelope for all operations."""

    status: Literal["ok", "error"]
    data: dict[str, Any] = Field(default_factory=dict)
    errors: list[ErrorDetail] = Field(default_factory=list)
