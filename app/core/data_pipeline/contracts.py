"""This module defines placeholder contracts for data-pipeline stage inputs and outputs."""

from dataclasses import dataclass
from typing import Any


@dataclass(kw_only=True)
class PipelineStageResult:
    """This dataclass captures a normalized stage output payload."""

    stage: str
    payload: dict[str, Any]
