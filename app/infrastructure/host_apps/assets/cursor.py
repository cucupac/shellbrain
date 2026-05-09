"""Cursor host asset install and inspection."""

from __future__ import annotations

from app.infrastructure.host_apps.assets.cursor_statusline_config import (
    install_cursor_statusline,
    inspect_cursor_statusline,
)
from app.infrastructure.host_apps.assets.managed_tree import (
    install_asset_tree,
    is_shellbrain_managed_asset,
)
from app.infrastructure.host_apps.assets.packaged_assets import packaged_asset_root
from app.infrastructure.host_apps.assets.paths import default_cursor_home

PRIMARY_CURSOR_SKILL_NAME = "shellbrain-session-start"
CURSOR_SKILL_NAMES = ("shellbrain-session-start", "shellbrain-usage-review")


def install_cursor_assets(
    *, force: bool, render_install_status, statusline_module: str | None = None
) -> list[str]:
    """Install the packaged Cursor skills into the default Cursor home."""

    cursor_root = default_cursor_home()
    lines: list[str] = []
    for skill_name in CURSOR_SKILL_NAMES:
        target_root = cursor_root / "skills" / skill_name
        source_root = packaged_asset_root("cursor", "skills", skill_name)
        lines.append(
            render_install_status(
                f"Cursor skill ({skill_name})",
                install_asset_tree(
                    source_root=source_root,
                    target_root=target_root,
                    asset_kind="cursor_skill",
                    force=force,
                ),
            )
        )
    lines.append(
        render_install_status(
            "Cursor statusline",
            install_cursor_statusline(
                force=force,
                **(
                    {}
                    if statusline_module is None
                    else {"statusline_module": statusline_module}
                ),
            ),
        )
    )
    return lines


def inspect_cursor_assets() -> tuple[dict[str, object], dict[str, object]]:
    """Inspect the default Cursor primary skill and statusline."""

    cursor_root = default_cursor_home() / "skills" / PRIMARY_CURSOR_SKILL_NAME
    return (
        {
            "path": str(cursor_root),
            "installed": cursor_root.exists(),
            "managed": is_shellbrain_managed_asset(
                target_root=cursor_root, asset_kind="cursor_skill"
            ),
        },
        inspect_cursor_statusline(),
    )
