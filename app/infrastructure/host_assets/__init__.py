"""Install Shellbrain-managed host assets for Codex, Claude, and Cursor."""

from __future__ import annotations

from dataclasses import dataclass
import importlib.metadata
from importlib import resources
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import sys

from app.infrastructure.host_identity.claude_hook_install import (
    default_global_claude_settings_path,
    inspect_claude_hook,
    install_claude_hook,
)


_PRIMARY_CODEX_SKILL_NAME = "shellbrain-session-start"
_PRIMARY_CLAUDE_SKILL_NAME = "shellbrain-session-start"
_PRIMARY_CURSOR_SKILL_NAME = "shellbrain-session-start"
_CODEX_SKILL_NAMES = ("shellbrain-session-start", "shellbrain-usage-review")
_CLAUDE_SKILL_NAMES = ("shellbrain-session-start", "shellbrain-usage-review")
_CURSOR_SKILL_NAMES = ("shellbrain-session-start", "shellbrain-usage-review")
_CLAUDE_LEGACY_COMMAND = "shellbrain-session-start.md"
_MANAGED_MARKER_FILENAME = ".shellbrain-managed.json"
_CODEX_STARTUP_MARKER = "shellbrain-managed:codex-startup"
_CLAUDE_STARTUP_MARKER = "shellbrain-managed:claude-startup"
_CURSOR_STATUSLINE_MARKER = "app.entrypoints.host_hooks.cursor_statusline"


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


def install_host_assets(*, host_mode: str, force: bool = False) -> HostAssetInstallResult:
    """Install one or more Shellbrain-managed host assets."""

    lines: list[str] = []
    if host_mode not in {"auto", "codex", "claude", "cursor", "all"}:
        raise ValueError(f"Unsupported host asset mode: {host_mode}")
    if host_mode in {"auto", "codex", "all"}:
        lines.extend(_install_codex_skill(force=force))
    if host_mode in {"auto", "claude", "all"}:
        lines.extend(_install_claude_skill(force=force))
    if host_mode in {"auto", "cursor", "all"}:
        lines.extend(_install_cursor_skill(force=force))
    return HostAssetInstallResult(lines=lines)


def _install_codex_skill(*, force: bool) -> list[str]:
    """Install the packaged Codex startup guidance and skills into Codex home."""

    codex_home = _default_codex_home()
    skills_root = codex_home / "skills"
    lines: list[str] = []
    lines.append(
        _render_install_status(
            "Codex startup guidance",
            _install_managed_markdown_block(
                source_text=_load_packaged_text("codex", "AGENTS.md"),
                target_path=codex_home / "AGENTS.md",
                block_marker=_CODEX_STARTUP_MARKER,
                force=force,
            ),
        )
    )
    for skill_name in _CODEX_SKILL_NAMES:
        target_root = skills_root / skill_name
        source_root = resources.files("onboarding_assets").joinpath("codex", skill_name)
        lines.append(
            _render_install_status(
                f"Codex skill ({skill_name})",
                _install_asset_tree(source_root=source_root, target_root=target_root, asset_kind="codex_skill", force=force),
            )
        )
    return lines


def _install_claude_skill(*, force: bool) -> list[str]:
    """Install the packaged Claude startup guidance, skills, and global hook."""

    claude_root = _default_claude_root()
    lines: list[str] = []
    lines.append(
        _render_install_status(
            "Claude startup guidance",
            _install_managed_markdown_block(
                source_text=_load_packaged_text("claude", "CLAUDE.md"),
                target_path=claude_root / "CLAUDE.md",
                block_marker=_CLAUDE_STARTUP_MARKER,
                force=force,
            ),
        )
    )
    for skill_name in _CLAUDE_SKILL_NAMES:
        target_root = claude_root / "skills" / skill_name
        source_root = resources.files("onboarding_assets").joinpath("claude", "skills", skill_name)
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


def _install_cursor_skill(*, force: bool) -> list[str]:
    """Install the packaged Cursor skills into the default Cursor home."""

    cursor_root = _default_cursor_home()
    lines: list[str] = []
    for skill_name in _CURSOR_SKILL_NAMES:
        target_root = cursor_root / "skills" / skill_name
        source_root = resources.files("onboarding_assets").joinpath("cursor", "skills", skill_name)
        lines.append(
            _render_install_status(
                f"Cursor skill ({skill_name})",
                _install_asset_tree(source_root=source_root, target_root=target_root, asset_kind="cursor_skill", force=force),
            )
        )
    lines.append(
        _render_install_status(
            "Cursor statusline",
            _install_cursor_statusline(force=force),
        )
    )
    return lines


def inspect_host_assets() -> HostAssetInspection:
    """Inspect the default Shellbrain-managed host integrations."""

    codex_home = _default_codex_home()
    codex_root = codex_home / "skills" / _PRIMARY_CODEX_SKILL_NAME
    claude_root = _default_claude_root()
    claude_skill_root = claude_root / "skills" / _PRIMARY_CLAUDE_SKILL_NAME
    cursor_root = _default_cursor_home() / "skills" / _PRIMARY_CURSOR_SKILL_NAME
    claude_hook = inspect_claude_hook(settings_path=default_global_claude_settings_path())
    return HostAssetInspection(
        codex_startup_guidance=_inspect_managed_markdown_block(
            target_path=codex_home / "AGENTS.md",
            block_marker=_CODEX_STARTUP_MARKER,
        ),
        codex_skill={
            "path": str(codex_root),
            "installed": codex_root.exists(),
            "managed": _is_shellbrain_managed_asset(target_root=codex_root, asset_kind="codex_skill"),
        },
        claude_startup_guidance=_inspect_managed_markdown_block(
            target_path=claude_root / "CLAUDE.md",
            block_marker=_CLAUDE_STARTUP_MARKER,
        ),
        claude_skill={
            "path": str(claude_skill_root),
            "installed": claude_skill_root.exists(),
            "managed": _is_shellbrain_managed_asset(target_root=claude_skill_root, asset_kind="claude_skill"),
        },
        cursor_skill={
            "path": str(cursor_root),
            "installed": cursor_root.exists(),
            "managed": _is_shellbrain_managed_asset(target_root=cursor_root, asset_kind="cursor_skill"),
        },
        cursor_statusline=_inspect_cursor_statusline(),
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


def _install_cursor_statusline(*, force: bool) -> tuple[str, Path, str | None]:
    """Install or update the Shellbrain-managed Cursor CLI statusline command."""

    config_path = _default_cursor_home() / "cli-config.json"
    statusline_payload = {
        "type": "command",
        "command": _cursor_statusline_command(),
        "padding": 2,
        "updateIntervalMs": 300,
        "timeoutMs": 2000,
    }
    if config_path.exists():
        try:
            payload = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return "skipped", config_path, f"unable to read {config_path}: {exc}"
        if not isinstance(payload, dict):
            return "skipped", config_path, f"unmanaged malformed config exists at {config_path}; rerun with --force to replace"
    else:
        payload = {}

    existing_statusline = payload.get("statusLine")
    if existing_statusline is not None:
        if not isinstance(existing_statusline, dict):
            if not force:
                return "skipped", config_path, f"unmanaged statusLine exists in {config_path}; rerun with --force to replace"
        elif not _is_managed_cursor_statusline(existing_statusline) and not force:
            return "skipped", config_path, f"unmanaged statusLine exists in {config_path}; rerun with --force to replace"

    payload["statusLine"] = statusline_payload
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return ("updated" if existing_statusline is not None else "installed"), config_path, None


def _load_packaged_text(*parts: str) -> str:
    """Return one packaged text asset from onboarding_assets."""

    return resources.files("onboarding_assets").joinpath(*parts).read_text(encoding="utf-8")


def _install_managed_markdown_block(
    *,
    source_text: str,
    target_path: Path,
    block_marker: str,
    force: bool,
) -> tuple[str, Path, str | None]:
    """Install or update one managed markdown block inside one user startup file."""

    target_path = target_path.expanduser().resolve()
    start_marker, end_marker = _markdown_markers(block_marker)
    block_text = f"{start_marker}\n{source_text.strip()}\n{end_marker}\n"
    if target_path.exists() and target_path.is_dir():
        if not force:
            return "skipped", target_path, f"unmanaged directory exists at {target_path}; rerun with --force to replace"
        _remove_existing_path(target_path)

    status = "installed"
    if target_path.exists():
        try:
            existing_text = target_path.read_text(encoding="utf-8")
        except OSError as exc:
            return "skipped", target_path, f"unable to read {target_path}: {exc}"
        block_status = _managed_block_status(existing_text=existing_text, block_marker=block_marker)
        if block_status == "malformed":
            return "skipped", target_path, f"managed block markers are malformed in {target_path}"
        if block_status == "present":
            next_text = _replace_managed_block(existing_text=existing_text, block_marker=block_marker, block_text=block_text)
            status = "updated"
        else:
            next_text = _append_managed_block(existing_text=existing_text, block_text=block_text)
    else:
        next_text = block_text
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(next_text, encoding="utf-8")
    return status, target_path, None


def _install_asset_tree(*, source_root, target_root: Path, asset_kind: str, force: bool) -> tuple[str, Path, str | None]:
    """Install one packaged asset tree into one target root safely."""

    if target_root.exists():
        if _is_shellbrain_managed_asset(target_root=target_root, asset_kind=asset_kind):
            _remove_existing_path(target_root)
            status = "updated"
        elif _is_legacy_shellbrain_asset(target_root=target_root, asset_kind=asset_kind):
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


def _inspect_cursor_statusline() -> dict[str, object]:
    """Inspect whether Cursor CLI config contains the Shellbrain-managed statusline."""

    config_path = _default_cursor_home() / "cli-config.json"
    if not config_path.exists():
        return {
            "path": str(config_path),
            "installed": False,
            "managed": False,
            "malformed": False,
            "command_executable": None,
            "executable_exists": None,
        }
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {
            "path": str(config_path),
            "installed": False,
            "managed": False,
            "malformed": True,
            "command_executable": None,
            "executable_exists": None,
        }
    if not isinstance(payload, dict):
        return {
            "path": str(config_path),
            "installed": False,
            "managed": False,
            "malformed": True,
            "command_executable": None,
            "executable_exists": None,
        }
    statusline = payload.get("statusLine")
    if not isinstance(statusline, dict):
        return {
            "path": str(config_path),
            "installed": False,
            "managed": False,
            "malformed": False,
            "command_executable": None,
            "executable_exists": None,
        }
    executable = _command_executable(statusline.get("command"))
    installed = isinstance(statusline.get("command"), str) and bool(statusline.get("command", "").strip())
    return {
        "path": str(config_path),
        "installed": installed,
        "managed": _is_managed_cursor_statusline(statusline),
        "malformed": False,
        "command_executable": executable,
        "executable_exists": None if executable is None else Path(executable).exists(),
    }


def _is_shellbrain_managed_asset(*, target_root: Path, asset_kind: str) -> bool:
    """Return whether one target root is already managed by Shellbrain for the same asset kind."""

    marker_path = target_root / _MANAGED_MARKER_FILENAME
    try:
        payload = json.loads(marker_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return False
    return payload.get("managed_by") == "shellbrain" and payload.get("asset_kind") == asset_kind


def _is_legacy_shellbrain_asset(*, target_root: Path, asset_kind: str) -> bool:
    """Return whether one target root looks like a pre-marker Shellbrain-managed asset."""

    if asset_kind != "codex_skill" or target_root.name != "shellbrain-session-start":
        return False
    skill_path = target_root / "SKILL.md"
    openai_path = target_root / "agents" / "openai.yaml"
    request_shapes = target_root / "references" / "request-shapes.md"
    session_workflow = target_root / "references" / "session-workflow.md"
    required_paths = (skill_path, openai_path, request_shapes, session_workflow)
    if not all(path.is_file() for path in required_paths):
        return False
    try:
        skill_text = skill_path.read_text(encoding="utf-8")
        openai_text = openai_path.read_text(encoding="utf-8")
    except OSError:
        return False
    return (
        "name: shellbrain-session-start" in skill_text
        and "Use Shellbrain as a case-based reasoning system" in skill_text
        and 'display_name: "Shellbrain Session Start"' in openai_text
        and "shellbrain-session-start" in openai_text
    )


def _inspect_managed_markdown_block(*, target_path: Path, block_marker: str) -> dict[str, object]:
    """Inspect whether one startup file contains one Shellbrain-managed markdown block."""

    resolved_path = target_path.expanduser().resolve()
    if not resolved_path.exists():
        return {
            "path": str(resolved_path),
            "file_exists": False,
            "installed": False,
            "managed": False,
            "malformed": False,
        }
    if resolved_path.is_dir():
        return {
            "path": str(resolved_path),
            "file_exists": False,
            "installed": False,
            "managed": False,
            "malformed": True,
        }
    try:
        existing_text = resolved_path.read_text(encoding="utf-8")
    except OSError:
        return {
            "path": str(resolved_path),
            "file_exists": True,
            "installed": False,
            "managed": False,
            "malformed": True,
        }
    status = _managed_block_status(existing_text=existing_text, block_marker=block_marker)
    return {
        "path": str(resolved_path),
        "file_exists": True,
        "installed": status == "present",
        "managed": status == "present",
        "malformed": status == "malformed",
    }


def _markdown_markers(block_marker: str) -> tuple[str, str]:
    """Return the managed markdown start and end markers for one block."""

    return (f"<!-- {block_marker} start -->", f"<!-- {block_marker} end -->")


def _managed_block_status(*, existing_text: str, block_marker: str) -> str:
    """Return whether one managed markdown block is present, absent, or malformed."""

    start_marker, end_marker = _markdown_markers(block_marker)
    has_start = start_marker in existing_text
    has_end = end_marker in existing_text
    if has_start and has_end and existing_text.index(start_marker) < existing_text.index(end_marker):
        return "present"
    if has_start or has_end:
        return "malformed"
    return "absent"


def _replace_managed_block(*, existing_text: str, block_marker: str, block_text: str) -> str:
    """Replace one existing managed markdown block in a file."""

    start_marker, end_marker = _markdown_markers(block_marker)
    pattern = re.compile(rf"{re.escape(start_marker)}.*?{re.escape(end_marker)}\n?", flags=re.DOTALL)
    return pattern.sub(block_text, existing_text, count=1)


def _append_managed_block(*, existing_text: str, block_text: str) -> str:
    """Append one managed markdown block to a file while preserving unrelated content."""

    stripped = existing_text.rstrip()
    if not stripped:
        return block_text
    return f"{stripped}\n\n{block_text}"


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


def _default_cursor_home() -> Path:
    """Return the default Cursor home path for host assets."""

    raw = os.getenv("CURSOR_HOME")
    if raw:
        return Path(raw).expanduser().resolve()
    return (Path.home() / ".cursor").resolve()


def _cursor_statusline_command() -> str:
    """Return the managed Cursor CLI statusline command."""

    return shlex.join([str(Path(sys.executable).resolve()), "-m", "app.entrypoints.host_hooks.cursor_statusline"])


def _is_managed_cursor_statusline(statusline_payload: dict[str, object]) -> bool:
    """Return whether one Cursor CLI statusline config belongs to Shellbrain."""

    command = statusline_payload.get("command")
    return isinstance(command, str) and _CURSOR_STATUSLINE_MARKER in command


def _command_executable(command: object) -> str | None:
    """Extract the executable path from one shell-style command string."""

    if not isinstance(command, str) or not command.strip():
        return None
    try:
        parsed = shlex.split(command)
    except ValueError:
        return None
    if not parsed:
        return None
    return str(Path(parsed[0]).expanduser().resolve())
