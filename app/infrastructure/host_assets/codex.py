"""Codex host asset install and inspection."""

from __future__ import annotations

from app.infrastructure.host_assets.managed_markdown import (
    install_managed_markdown_block,
    inspect_managed_markdown_block,
)
from app.infrastructure.host_assets.managed_tree import (
    install_asset_tree,
    is_shellbrain_managed_asset,
)
from app.infrastructure.host_assets.packaged_assets import (
    load_packaged_text,
    packaged_asset_root,
)
from app.infrastructure.host_assets.paths import default_codex_home

PRIMARY_CODEX_SKILL_NAME = "shellbrain-session-start"
CODEX_SKILL_NAMES = ("shellbrain-session-start", "shellbrain-usage-review")
CODEX_STARTUP_MARKER = "shellbrain-managed:codex-startup"


def install_codex_assets(*, force: bool, render_install_status) -> list[str]:
    """Install the packaged Codex startup guidance and skills into Codex home."""

    codex_home = default_codex_home()
    skills_root = codex_home / "skills"
    lines: list[str] = []
    lines.append(
        render_install_status(
            "Codex startup guidance",
            install_managed_markdown_block(
                source_text=load_packaged_text("codex", "AGENTS.md"),
                target_path=codex_home / "AGENTS.md",
                block_marker=CODEX_STARTUP_MARKER,
                force=force,
            ),
        )
    )
    for skill_name in CODEX_SKILL_NAMES:
        target_root = skills_root / skill_name
        source_root = packaged_asset_root("codex", skill_name)
        lines.append(
            render_install_status(
                f"Codex skill ({skill_name})",
                install_asset_tree(
                    source_root=source_root,
                    target_root=target_root,
                    asset_kind="codex_skill",
                    force=force,
                ),
            )
        )
    return lines


def inspect_codex_assets() -> tuple[dict[str, object], dict[str, object]]:
    """Inspect the default Codex startup guidance and primary skill."""

    codex_home = default_codex_home()
    codex_root = codex_home / "skills" / PRIMARY_CODEX_SKILL_NAME
    return (
        inspect_managed_markdown_block(
            target_path=codex_home / "AGENTS.md",
            block_marker=CODEX_STARTUP_MARKER,
        ),
        {
            "path": str(codex_root),
            "installed": codex_root.exists(),
            "managed": is_shellbrain_managed_asset(
                target_root=codex_root, asset_kind="codex_skill"
            ),
        },
    )
