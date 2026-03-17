"""This module defines boot-time helpers that load YAML-backed configuration providers."""

from functools import lru_cache
from pathlib import Path

from shellbrain.config.loader import YamlConfigProvider


@lru_cache(maxsize=1)
def get_config_provider() -> YamlConfigProvider:
    """This function returns the shared YAML configuration provider instance."""

    defaults_dir = Path(__file__).resolve().parents[1] / "config" / "defaults"
    return YamlConfigProvider(defaults_dir)
