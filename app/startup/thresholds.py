"""Boot-time helpers for normalized retrieval threshold settings."""

from app.startup.config import get_config_provider
from app.core.entities.settings import ThresholdSettings


def get_typed_threshold_settings() -> ThresholdSettings:
    """Return typed retrieval thresholds from YAML config."""

    thresholds = get_config_provider().get_thresholds()
    semantic_threshold = thresholds.get("semantic_threshold")
    keyword_threshold = thresholds.get("keyword_threshold")
    if isinstance(semantic_threshold, bool) or not isinstance(semantic_threshold, (int, float)):
        raise ValueError("thresholds.semantic_threshold must be numeric")
    if isinstance(keyword_threshold, bool) or not isinstance(keyword_threshold, (int, float)):
        raise ValueError("thresholds.keyword_threshold must be numeric")
    return ThresholdSettings(
        semantic_threshold=float(semantic_threshold),
        keyword_threshold=float(keyword_threshold),
    )


def get_threshold_settings() -> dict[str, float]:
    """Return normalized retrieval thresholds from YAML config."""

    return get_typed_threshold_settings().to_dict()
