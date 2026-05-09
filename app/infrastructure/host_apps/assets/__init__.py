"""Public host-assets adapter surface."""

from app.infrastructure.host_apps.assets.inspection import inspect_host_assets
from app.infrastructure.host_apps.assets.service import install_host_assets
from app.infrastructure.host_apps.assets.types import (
    HostAssetInspection,
    HostAssetInstallResult,
)

__all__ = [
    "HostAssetInspection",
    "HostAssetInstallResult",
    "inspect_host_assets",
    "install_host_assets",
]
