"""Retrieval thresholds shared with direct core callers."""

from app.core.entities.settings import ThresholdSettings, default_threshold_settings


def get_typed_threshold_settings() -> ThresholdSettings:
    return default_threshold_settings()
