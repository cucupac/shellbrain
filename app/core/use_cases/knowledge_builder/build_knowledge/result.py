"""Result types for build_knowledge lifecycle runs."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.entities.knowledge_builder import KnowledgeBuildRunStatus


@dataclass(frozen=True)
class BuildKnowledgeResult:
    """Typed result for one build_knowledge lifecycle run."""

    status: KnowledgeBuildRunStatus
    run_id: str | None
    event_watermark: int
    previous_event_watermark: int | None
    provider: str
    model: str
    reasoning: str
    write_count: int = 0
    skipped_item_count: int = 0
    run_summary: str | None = None
    error_code: str | None = None
    error_message: str | None = None

    @property
    def data(self) -> dict[str, object]:
        return self.to_response_data()

    def to_response_data(self) -> dict[str, object]:
        """Return a stable diagnostic shape."""

        return {
            "status": self.status.value,
            "run_id": self.run_id,
            "event_watermark": self.event_watermark,
            "previous_event_watermark": self.previous_event_watermark,
            "provider": self.provider,
            "model": self.model,
            "reasoning": self.reasoning,
            "write_count": self.write_count,
            "skipped_item_count": self.skipped_item_count,
            "run_summary": self.run_summary,
            "error_code": self.error_code,
            "error_message": self.error_message,
        }
