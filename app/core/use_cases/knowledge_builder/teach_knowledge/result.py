"""Teaching result with the shared knowledge-build outcome."""

from dataclasses import dataclass

from app.core.use_cases.knowledge_builder.build_knowledge.result import BuildKnowledgeResult


@dataclass(frozen=True, kw_only=True)
class TeachKnowledgeResult(BuildKnowledgeResult):
    """A saved teaching event and its immediate consolidation outcome."""

    episode_id: str
    teaching_event_id: str
    teaching_event_seq: int

    def to_response_data(self) -> dict[str, object]:
        return {
            "episode_id": self.episode_id,
            "teaching_event_id": self.teaching_event_id,
            "teaching_event_seq": self.teaching_event_seq,
            "build_knowledge": super().to_response_data(),
        }
