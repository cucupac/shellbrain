"""Install Shellbrain-managed host assets for Codex and Claude."""

from __future__ import annotations

from dataclasses import dataclass
import importlib.metadata
from importlib import resources
import json
import os
from pathlib import Path
import shutil

from app.periphery.identity.claude_hook_install import (
    default_global_claude_settings_path,
    inspect_claude_hook,
    install_claude_hook,
)


_PRIMARY_CODEX_SKILL_NAME = "shellbrain-session-start"
_PRIMARY_CLAUDE_SKILL_NAME = "shellbrain-session-start"
_CODEX_SKILL_NAMES = ("shellbrain-session-start", "shellbrain-usage-review")
_CLAUDE_SKILL_NAMES = ("shellbrain-session-start", "shellbrain-usage-review")
_CLAUDE_LEGACY_COMMAND = "shellbrain-session-start.md"
_MANAGED_MARKER_FILENAME = ".shellbrain-managed.json"


@dataclass(frozen=True)
class HostAssetInstallResult:
    """Structured summary for one host-asset installation pass."""

    lines: list[str]


@dataclass(frozen=True)
class HostAssetInspection:
    """Structured status for the default Shellbrain host integrations."""

    codex_skill: dict[str, object]
    claude_skill: dict[str, object]
    claude_global_hook: dict[str, object]


def install_host_assets(*, host_mode: str, force: bool = False) -> HostAssetInstallResult:
    """Install one or more Shellbrain-managed host assets."""

    lines: list[str] = []
    if host_mode not in {"auto", "codex", "claude", "all"}:
        raise ValueError(f"Unsupported host asset mode: {host_mode}")
    if host_mode in {"auto", "codex", "all"}:
        lines.extend(_install_codex_skill(force=force))
    if host_mode in {"auto", "claude", "all"}:
        lines.extend(_install_claude_skill(force=force))
    return HostAssetInstallResult(lines=lines)


def _install_codex_skill(*, force: bool) -> list[str]:
    """Install the packaged Codex skill into the default Codex home."""

    skills_root = _default_codex_home() / "skills"
    lines: list[str] = []
    for skill_name in _CODEX_SKILL_NAMES:
        target_root = skills_root / skill_name
        source_root = resources.files("app.onboarding_assets").joinpath("codex", skill_name)
        lines.append(
            _render_install_status(
                f"Codex skill ({skill_name})",
                _install_asset_tree(source_root=source_root, target_root=target_root, asset_kind="codex_skill", force=force),
            )
        )
    return lines


def _install_claude_skill(*, force: bool) -> list[str]:
    """Install the packaged Claude personal skill and global hook."""

    claude_root = _default_claude_root()
    lines: list[str] = []
    for skill_name in _CLAUDE_SKILL_NAMES:
        target_root = claude_root / "skills" / skill_name
        source_root = resources.files("app.onboarding_assets").joinpath("claude", "skills", skill_name)
        lines.append(
            _render_install_status(
                f"Claude skill ({skill_name})",
                _install_asset_tree(source_root=source_root, target_root=target_root, asset_kind="claude_skill", force=force),
            )
        )
    settings_path = install_claude_hook(settings_path=default_global_claude_settings_path())
    lines.append(f"Claude global hook: installed at {settings_path}")
    legacy_command = claude_root / "commands" / _CLAUDE_LEGACY_COMMAND
    if legacy_command.exists():
        lines.append(f"Claude legacy command: preserved at {legacy_command}")
    return lines


def inspect_host_assets() -> HostAssetInspection:
    """Inspect the default Shellbrain-managed host integrations."""

    codex_root = _default_codex_home() / "skills" / _PRIMARY_CODEX_SKILL_NAME
    claude_root = _default_claude_root()
    claude_skill_root = claude_root / "skills" / _PRIMARY_CLAUDE_SKILL_NAME
    claude_hook = inspect_claude_hook(settings_path=default_global_claude_settings_path())
    return HostAssetInspection(
        codex_skill={
            "path": str(codex_root),
            "installed": codex_root.exists(),
            "managed": _is_shellbrain_managed_asset(target_root=codex_root, asset_kind="codex_skill"),
        },
        claude_skill={
            "path": str(claude_skill_root),
            "installed": claude_skill_root.exists(),
            "managed": _is_shellbrain_managed_asset(target_root=claude_skill_root, asset_kind="claude_skill"),
        },
        claude_global_hook={
            "path": str(claude_hook.settings_path),
            "installed": claude_hook.exists,
            "managed": claude_hook.managed,
            "malformed": claude_hook.malformed,
            "command_executable": claude_hook.command_executable,
            "executable_exists": claude_hook.executable_exists,
        },
    )


def _render_install_status(label: str, result: tuple[str, Path, str | None]) -> str:
    """Render one installer result tuple into a user-facing line."""

    status, target_root, reason = result
    if status == "installed":
        return f"{label}: installed at {target_root}"
    if status == "updated":
        return f"{label}: updated at {target_root}"
    if reason is None:
        return f"{label}: skipped"
    return f"{label}: skipped ({reason})"


def _install_asset_tree(*, source_root, target_root: Path, asset_kind: str, force: bool) -> tuple[str, Path, str | None]:
    """Install one packaged asset tree into one target root safely."""

    if target_root.exists():
        if _is_shellbrain_managed_asset(target_root=target_root, asset_kind=asset_kind):
            _remove_existing_path(target_root)
            status = "updated"
        elif force:
            _remove_existing_path(target_root)
            status = "installed"
        else:
            return "skipped", target_root, f"unmanaged install exists at {target_root}; rerun with --force to replace"
    else:
        status = "installed"
    target_root.parent.mkdir(parents=True, exist_ok=True)
    _copy_traversable_tree(source_root=source_root, target_root=target_root)
    _write_managed_marker(target_root=target_root, asset_kind=asset_kind)
    return status, target_root, None


def _copy_traversable_tree(*, source_root, target_root: Path) -> None:
    """Copy one packaged traversable tree into one filesystem path."""

    target_root.mkdir(parents=True, exist_ok=True)
    for child in source_root.iterdir():
        child_target = target_root / child.name
        if child.is_dir():
            _copy_traversable_tree(source_root=child, target_root=child_target)
            continue
        child_target.write_bytes(child.read_bytes())


def _write_managed_marker(*, target_root: Path, asset_kind: str) -> None:
    """Write one Shellbrain-managed marker for one installed asset root."""

    marker = {
        "managed_by": "shellbrain",
        "asset_kind": asset_kind,
        "version": _installed_shellbrain_version(),
    }
    (target_root / _MANAGED_MARKER_FILENAME).write_text(json.dumps(marker, indent=2, sort_keys=True), encoding="utf-8")


def _installed_shellbrain_version() -> str:
    """Return the installed Shellbrain package version, falling back in editable dev mode."""

    try:
        return importlib.metadata.version("shellbrain")
    except importlib.metadata.PackageNotFoundError:
        return "dev"


def _is_shellbrain_managed_asset(*, target_root: Path, asset_kind: str) -> bool:
    """Return whether one target root is already managed by Shellbrain for the same asset kind."""

    marker_path = target_root / _MANAGED_MARKER_FILENAME
    try:
        payload = json.loads(marker_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return False
    return payload.get("managed_by") == "shellbrain" and payload.get("asset_kind") == asset_kind


def _remove_existing_path(path: Path) -> None:
    """Remove one filesystem path whether it is a file or directory."""

    if path.is_dir():
        shutil.rmtree(path)
        return
    path.unlink()


def _default_codex_home() -> Path:
    """Return the default Codex home path for host assets."""

    raw = os.getenv("CODEX_HOME")
    if raw:
        return Path(raw).expanduser().resolve()
    return (Path.home() / ".codex").resolve()


def _default_claude_root() -> Path:
    """Return the default Claude home path for host assets."""

    return (Path.home() / ".claude").resolve()
