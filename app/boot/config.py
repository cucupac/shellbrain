"""This module defines boot-time helpers that load YAML-backed configuration providers."""

from app.boot.db import get_defaults_dir
from app.config.loader import YamlConfigProvider


def get_config_provider() -> YamlConfigProvider:
    """This function returns the shared YAML configuration provider instance."""

    return YamlConfigProvider(get_defaults_dir())
