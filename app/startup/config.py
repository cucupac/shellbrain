"""Boot-time helpers that load app-packaged configuration."""

from functools import lru_cache
from pathlib import Path

from app.startup.settings import YamlConfigProvider


@lru_cache(maxsize=1)
def get_config_provider() -> YamlConfigProvider:
    """This function returns the shared YAML configuration provider instance."""

    defaults_dir = Path(__file__).resolve().parents[1] / "settings" / "defaults"
    return YamlConfigProvider(defaults_dir)
