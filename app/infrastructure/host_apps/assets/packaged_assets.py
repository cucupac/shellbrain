"""Packaged onboarding asset loading."""

from __future__ import annotations

from importlib import resources


def packaged_asset_root(*parts: str):
    """Return one packaged onboarding asset traversable."""

    return resources.files("onboarding_assets").joinpath(*parts)


def load_packaged_text(*parts: str) -> str:
    """Return one packaged text asset from onboarding_assets."""

    return packaged_asset_root(*parts).read_text(encoding="utf-8")
