"""Claude host asset install and inspection."""

from __future__ import annotations

from app.infrastructure.host_apps.assets.managed_markdown import (
    install_managed_markdown_block,
    inspect_managed_markdown_block,
)
from app.infrastructure.host_apps.assets.managed_tree import (
    install_asset_tree,
    is_shellbrain_managed_asset,
)
from app.infrastructure.host_apps.assets.packaged_assets import (
    load_packaged_text,
    packaged_asset_root,
)
from app.infrastructure.host_apps.assets.paths import default_claude_root
from app.infrastructure.host_apps.identity.claude_hook_install import (
    default_global_claude_settings_path,
    inspect_claude_hook,
    install_claude_hook,
)

PRIMARY_CLAUDE_SKILL_NAME = "shellbrain-session-start"
CLAUDE_SKILL_NAMES = ("shellbrain-session-start", "shellbrain-usage-review")
CLAUDE_STARTUP_MARKER = "shellbrain-managed:claude-startup"


def install_claude_assets(
    *, force: bool, render_install_status, session_start_module: str | None = None
) -> list[str]:
    """Install the packaged Claude startup guidance, skills, and global hook."""

    claude_root = default_claude_root()
    lines: list[str] = []
    lines.append(
        render_install_status(
            "Claude startup guidance",
            install_managed_markdown_block(
                source_text=load_packaged_text("claude", "CLAUDE.md"),
                target_path=claude_root / "CLAUDE.md",
                block_marker=CLAUDE_STARTUP_MARKER,
                force=force,
            ),
        )
    )
    for skill_name in CLAUDE_SKILL_NAMES:
        target_root = claude_root / "skills" / skill_name
        source_root = packaged_asset_root("claude", "skills", skill_name)
        lines.append(
            render_install_status(
                f"Claude skill ({skill_name})",
                install_asset_tree(
                    source_root=source_root,
                    target_root=target_root,
                    asset_kind="claude_skill",
                    force=force,
                ),
            )
        )
    settings_path = install_claude_hook(
        settings_path=default_global_claude_settings_path(),
        **(
            {}
            if session_start_module is None
            else {"session_start_module": session_start_module}
        ),
    )
    lines.append(f"Claude global hook: installed at {settings_path}")
    return lines


def inspect_claude_assets() -> tuple[
    dict[str, object], dict[str, object], dict[str, object]
]:
    """Inspect the default Claude startup guidance, primary skill, and global hook."""

    claude_root = default_claude_root()
    claude_skill_root = claude_root / "skills" / PRIMARY_CLAUDE_SKILL_NAME
    claude_hook = inspect_claude_hook(
        settings_path=default_global_claude_settings_path()
    )
    return (
        inspect_managed_markdown_block(
            target_path=claude_root / "CLAUDE.md",
            block_marker=CLAUDE_STARTUP_MARKER,
        ),
        {
            "path": str(claude_skill_root),
            "installed": claude_skill_root.exists(),
            "managed": is_shellbrain_managed_asset(
                target_root=claude_skill_root, asset_kind="claude_skill"
            ),
        },
        {
            "path": str(claude_hook.settings_path),
            "installed": claude_hook.exists,
            "managed": claude_hook.managed,
            "malformed": claude_hook.malformed,
            "command_executable": claude_hook.command_executable,
            "executable_exists": claude_hook.executable_exists,
        },
    )
