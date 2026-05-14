"""Request types for build_knowledge lifecycle runs."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.entities.knowledge_builder import KnowledgeBuildTrigger


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BuildKnowledgeRequest(_StrictModel):
    """Core request to consolidate one episode through build_knowledge."""

    repo_id: str = Field(min_length=1)
    repo_root: str = Field(min_length=1)
    episode_id: str = Field(min_length=1)
    trigger: KnowledgeBuildTrigger

    @field_validator("repo_id", "repo_root", "episode_id")
    @classmethod
    def _validate_non_blank(cls, value: str) -> str:
        """Require explicit non-blank identifiers."""

        text = value.strip()
        if not text:
            raise ValueError("value must be non-empty")
        return text
