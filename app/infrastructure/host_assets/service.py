"""Install Shellbrain-managed host assets for Codex, Claude, and Cursor."""

from __future__ import annotations

from pathlib import Path

from app.infrastructure.host_assets.claude import install_claude_assets
from app.infrastructure.host_assets.codex import install_codex_assets
from app.infrastructure.host_assets.cursor import install_cursor_assets
from app.infrastructure.host_assets.types import HostAssetInstallResult


def install_host_assets(*, host_mode: str, force: bool = False) -> HostAssetInstallResult:
    """Install one or more Shellbrain-managed host assets."""

    lines: list[str] = []
    if host_mode not in {"auto", "codex", "claude", "cursor", "all"}:
        raise ValueError(f"Unsupported host asset mode: {host_mode}")
    if host_mode in {"auto", "codex", "all"}:
        lines.extend(install_codex_assets(force=force, render_install_status=render_install_status))
    if host_mode in {"auto", "claude", "all"}:
        lines.extend(install_claude_assets(force=force, render_install_status=render_install_status))
    if host_mode in {"auto", "cursor", "all"}:
        lines.extend(install_cursor_assets(force=force, render_install_status=render_install_status))
    return HostAssetInstallResult(lines=lines)


def render_install_status(label: str, result: tuple[str, Path, str | None]) -> str:
    """Render one installer result tuple into a user-facing line."""

    status, target_root, reason = result
    if status == "installed":
        return f"{label}: installed at {target_root}"
    if status == "updated":
        return f"{label}: updated at {target_root}"
    if reason is None:
        return f"{label}: skipped"
    return f"{label}: skipped ({reason})"
