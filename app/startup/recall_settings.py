"""Load machine-local YAML overrides for recall evidence limits."""

from pathlib import Path

import yaml

from app.core.entities.recall_settings import RecallSettings
from app.infrastructure.local_state.paths import get_shellbrain_home


def load_recall_settings() -> RecallSettings:
    """Use packaged defaults when absent; reject malformed overrides."""
    path = get_shellbrain_home() / "recall.yaml"
    return read_recall_settings(path)


def read_recall_settings(path: Path) -> RecallSettings:
    """Parse one settings document without modifying user configuration."""
    try:
        payload = yaml.safe_load(path.read_text())
    except FileNotFoundError:
        return RecallSettings()
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid recall settings: {path}: {exc}") from exc
    if not isinstance(payload, dict) or set(payload) != {"recall"}:
        raise ValueError(f"Invalid recall settings: {path}: expected a recall mapping")
    try:
        return RecallSettings.model_validate(payload["recall"])
    except ValueError as exc:
        raise ValueError(f"Invalid recall settings: {path}: {exc}") from exc
