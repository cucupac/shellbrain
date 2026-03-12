"""Boot-time helpers for normalized retrieval threshold settings."""

from app.boot.config import get_config_provider


def get_threshold_settings() -> dict[str, float]:
    """Return normalized retrieval thresholds from YAML config."""

    thresholds = get_config_provider().get_thresholds()
    return {
        "semantic_threshold": float(thresholds.get("semantic_threshold", 0.0)),
        "keyword_threshold": float(thresholds.get("keyword_threshold", 0.0)),
    }
