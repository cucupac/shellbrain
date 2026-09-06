"""Typed retrieval thresholds."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ThresholdSettings:
    """Retrieval score thresholds used by core read policy."""

    semantic_threshold: float
    keyword_threshold: float

    def to_dict(self) -> dict[str, float]:
        return {
            "semantic_threshold": float(self.semantic_threshold),
            "keyword_threshold": float(self.keyword_threshold),
        }


def default_threshold_settings() -> ThresholdSettings:
    """Return packaged retrieval thresholds for direct core callers and tests."""

    return ThresholdSettings(semantic_threshold=0.25, keyword_threshold=0.0)
