"""Host asset inspection service."""

from __future__ import annotations

from app.infrastructure.host_assets.claude import inspect_claude_assets
from app.infrastructure.host_assets.codex import inspect_codex_assets
from app.infrastructure.host_assets.cursor import inspect_cursor_assets
from app.infrastructure.host_assets.types import HostAssetInspection


def inspect_host_assets() -> HostAssetInspection:
    """Inspect the default Shellbrain-managed host integrations."""

    codex_startup_guidance, codex_skill = inspect_codex_assets()
    claude_startup_guidance, claude_skill, claude_global_hook = inspect_claude_assets()
    cursor_skill, cursor_statusline = inspect_cursor_assets()
    return HostAssetInspection(
        codex_startup_guidance=codex_startup_guidance,
        codex_skill=codex_skill,
        claude_startup_guidance=claude_startup_guidance,
        claude_skill=claude_skill,
        cursor_skill=cursor_skill,
        cursor_statusline=cursor_statusline,
        claude_global_hook=claude_global_hook,
    )
