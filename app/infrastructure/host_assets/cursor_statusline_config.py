"""Cursor CLI statusline config installation and inspection."""

from __future__ import annotations

import json
from pathlib import Path
import shlex
import sys

from app.infrastructure.host_assets.paths import default_cursor_home

CURSOR_STATUSLINE_MARKER = "shellbrain-managed:cursor-statusline"
DEFAULT_CURSOR_STATUSLINE_MODULE = "app.infrastructure.host_identity.cursor_statusline"


def install_cursor_statusline(
    *, force: bool, statusline_module: str = DEFAULT_CURSOR_STATUSLINE_MODULE
) -> tuple[str, Path, str | None]:
    """Install or update the Shellbrain-managed Cursor CLI statusline command."""

    config_path = default_cursor_home() / "cli-config.json"
    statusline_payload = {
        "type": "command",
        "command": cursor_statusline_command(statusline_module=statusline_module),
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
            return (
                "skipped",
                config_path,
                f"unmanaged malformed config exists at {config_path}; rerun with --force to replace",
            )
    else:
        payload = {}

    existing_statusline = payload.get("statusLine")
    if existing_statusline is not None:
        if not isinstance(existing_statusline, dict):
            if not force:
                return (
                    "skipped",
                    config_path,
                    f"unmanaged statusLine exists in {config_path}; rerun with --force to replace",
                )
        elif not is_managed_cursor_statusline(existing_statusline) and not force:
            return (
                "skipped",
                config_path,
                f"unmanaged statusLine exists in {config_path}; rerun with --force to replace",
            )

    payload["statusLine"] = statusline_payload
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return (
        ("updated" if existing_statusline is not None else "installed"),
        config_path,
        None,
    )


def inspect_cursor_statusline() -> dict[str, object]:
    """Inspect whether Cursor CLI config contains the Shellbrain-managed statusline."""

    config_path = default_cursor_home() / "cli-config.json"
    if not config_path.exists():
        return _statusline_report(
            config_path, installed=False, managed=False, malformed=False
        )
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _statusline_report(
            config_path, installed=False, managed=False, malformed=True
        )
    if not isinstance(payload, dict):
        return _statusline_report(
            config_path, installed=False, managed=False, malformed=True
        )
    statusline = payload.get("statusLine")
    if not isinstance(statusline, dict):
        return _statusline_report(
            config_path, installed=False, managed=False, malformed=False
        )
    executable = command_executable(statusline.get("command"))
    installed = isinstance(statusline.get("command"), str) and bool(
        statusline.get("command", "").strip()
    )
    return {
        "path": str(config_path),
        "installed": installed,
        "managed": is_managed_cursor_statusline(statusline),
        "malformed": False,
        "command_executable": executable,
        "executable_exists": None if executable is None else Path(executable).exists(),
    }


def cursor_statusline_command(
    *, statusline_module: str = DEFAULT_CURSOR_STATUSLINE_MODULE
) -> str:
    """Return the managed Cursor CLI statusline command."""

    command = shlex.join([str(Path(sys.executable).resolve()), "-m", statusline_module])
    return f"{command} # {CURSOR_STATUSLINE_MARKER}"


def is_managed_cursor_statusline(statusline_payload: dict[str, object]) -> bool:
    """Return whether one Cursor CLI statusline config belongs to Shellbrain."""

    command = statusline_payload.get("command")
    return isinstance(command, str) and CURSOR_STATUSLINE_MARKER in command


def command_executable(command: object) -> str | None:
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


def _statusline_report(
    config_path: Path, *, installed: bool, managed: bool, malformed: bool
) -> dict[str, object]:
    return {
        "path": str(config_path),
        "installed": installed,
        "managed": managed,
        "malformed": malformed,
        "command_executable": None,
        "executable_exists": None,
    }
