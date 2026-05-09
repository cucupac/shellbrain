"""Managed filesystem-tree installation for packaged host assets."""

from __future__ import annotations

import importlib.metadata
import json
from pathlib import Path
import shutil

MANAGED_MARKER_FILENAME = ".shellbrain-managed.json"


def install_asset_tree(
    *, source_root, target_root: Path, asset_kind: str, force: bool
) -> tuple[str, Path, str | None]:
    """Install one packaged asset tree into one target root safely."""

    if target_root.exists():
        if is_shellbrain_managed_asset(target_root=target_root, asset_kind=asset_kind):
            remove_existing_path(target_root)
            status = "updated"
        elif force:
            remove_existing_path(target_root)
            status = "installed"
        else:
            return (
                "skipped",
                target_root,
                f"unmanaged install exists at {target_root}; rerun with --force to replace",
            )
    else:
        status = "installed"
    target_root.parent.mkdir(parents=True, exist_ok=True)
    copy_traversable_tree(source_root=source_root, target_root=target_root)
    write_managed_marker(target_root=target_root, asset_kind=asset_kind)
    return status, target_root, None


def copy_traversable_tree(*, source_root, target_root: Path) -> None:
    """Copy one packaged traversable tree into one filesystem path."""

    target_root.mkdir(parents=True, exist_ok=True)
    for child in source_root.iterdir():
        child_target = target_root / child.name
        if child.is_dir():
            copy_traversable_tree(source_root=child, target_root=child_target)
            continue
        child_target.write_bytes(child.read_bytes())


def write_managed_marker(*, target_root: Path, asset_kind: str) -> None:
    """Write one Shellbrain-managed marker for one installed asset root."""

    marker = {
        "managed_by": "shellbrain",
        "asset_kind": asset_kind,
        "version": installed_shellbrain_version(),
    }
    (target_root / MANAGED_MARKER_FILENAME).write_text(
        json.dumps(marker, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def is_shellbrain_managed_asset(*, target_root: Path, asset_kind: str) -> bool:
    """Return whether one target root is already managed by Shellbrain for the same asset kind."""

    marker_path = target_root / MANAGED_MARKER_FILENAME
    try:
        payload = json.loads(marker_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return False
    return (
        payload.get("managed_by") == "shellbrain"
        and payload.get("asset_kind") == asset_kind
    )


def remove_existing_path(path: Path) -> None:
    """Remove one filesystem path whether it is a file or directory."""

    if path.is_dir():
        shutil.rmtree(path)
        return
    path.unlink()


def installed_shellbrain_version() -> str:
    """Return the installed Shellbrain package version, falling back in editable dev mode."""

    try:
        return importlib.metadata.version("shellbrain")
    except importlib.metadata.PackageNotFoundError:
        return "dev"
