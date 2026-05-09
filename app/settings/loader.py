"""This module defines YAML-backed configuration loading for policy and runtime settings."""

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from app.core.ports.settings.config import IConfigProvider


class YamlConfigProvider(IConfigProvider):
    """This class loads and serves configuration sections from YAML files."""

    def __init__(self, defaults_dir: Path) -> None:
        """This method loads all default YAML config files from a directory."""

        self._defaults_dir = defaults_dir
        self._read_policy = self._load_yaml("read_policy.yaml")
        self._create_policy = self._load_yaml("create_policy.yaml")
        self._update_policy = self._load_yaml("update_policy.yaml")
        self._thresholds = self._load_yaml("thresholds.yaml")
        self._runtime = self._load_yaml("runtime.yaml")

    def _load_yaml(self, filename: str) -> dict[str, Any]:
        """This method parses a YAML file into a dictionary."""

        path = self._defaults_dir / filename
        with path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
        if not isinstance(data, dict):
            raise ValueError(f"Expected mapping in {path}")
        return data

    def get_read_policy(self) -> dict[str, Any]:
        """This method returns read-policy configuration values."""

        return deepcopy(self._read_policy)

    def get_create_policy(self) -> dict[str, Any]:
        """This method returns create-policy configuration values."""

        return deepcopy(self._create_policy)

    def get_update_policy(self) -> dict[str, Any]:
        """This method returns update-policy configuration values."""

        return deepcopy(self._update_policy)

    def get_thresholds(self) -> dict[str, Any]:
        """This method returns threshold configuration values."""

        return deepcopy(self._thresholds)

    def get_runtime(self) -> dict[str, Any]:
        """This method returns runtime configuration values."""

        return deepcopy(self._runtime)
