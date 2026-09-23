"""Validated limits for evidence sent to recall synthesis."""

from pydantic import BaseModel, ConfigDict, Field


class RecallSettings(BaseModel):
    """Keep recall tuning separate from knowledge-builder retrieval."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    max_memories: int = Field(default=12, ge=2, le=100)
    max_concepts: int = Field(default=4, ge=0, le=20)
    max_neighbor_concepts: int = Field(default=2, ge=0, le=20)
    max_claims_per_concept: int = Field(default=3, ge=1, le=20)
    max_groundings_per_concept: int = Field(default=2, ge=0, le=20)
    max_input_tokens: int = Field(default=8000, ge=2000, le=100_000)
