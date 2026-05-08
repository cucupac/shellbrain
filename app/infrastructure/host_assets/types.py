"""Result types for Shellbrain-managed host assets."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HostAssetInstallResult:
    """Structured summary for one host-asset installation pass."""

    lines: list[str]


@dataclass(frozen=True)
class HostAssetInspection:
    """Structured status for the default Shellbrain host integrations."""

    codex_startup_guidance: dict[str, object]
    codex_skill: dict[str, object]
    claude_startup_guidance: dict[str, object]
    claude_skill: dict[str, object]
    cursor_skill: dict[str, object]
    cursor_statusline: dict[str, object]
    claude_global_hook: dict[str, object]
