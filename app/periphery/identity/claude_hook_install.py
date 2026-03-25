"""Install the official Claude SessionStart hook for Shellbrain caller identity."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import shlex
import shutil
import sys


_SESSION_START_MATCHER = "startup|resume|clear|compact"
_MANAGED_MARKER = "shellbrain-managed:session-start"


@dataclass(frozen=True)
class ClaudeHookStatus:
    """Structured inspection data for one Claude settings file."""

    settings_path: Path
    exists: bool
    malformed: bool
    managed: bool
    command_executable: str | None = None
    executable_exists: bool = False


def default_global_claude_settings_path() -> Path:
    """Return the default global Claude settings path."""

    return (Path.home() / ".claude" / "settings.json").resolve()


def install_claude_hook(*, repo_root: Path | None = None, settings_path: Path | None = None) -> Path:
    """Install or update one Claude settings file with the Shellbrain hook."""

    resolved_settings_path = _resolve_settings_path(repo_root=repo_root, settings_path=settings_path)
    resolved_settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings, _backup_path = _load_settings_payload(resolved_settings_path)
    settings["hooks"] = _merged_hooks(settings.get("hooks"))
    resolved_settings_path.write_text(json.dumps(settings, indent=2, sort_keys=True), encoding="utf-8")
    return resolved_settings_path


def inspect_claude_hook(*, settings_path: Path | None = None) -> ClaudeHookStatus:
    """Inspect whether one Claude settings file contains the Shellbrain-managed hook."""

    resolved_settings_path = (settings_path or default_global_claude_settings_path()).expanduser().resolve()
    if not resolved_settings_path.exists():
        return ClaudeHookStatus(
            settings_path=resolved_settings_path,
            exists=False,
            malformed=False,
            managed=False,
            command_executable=None,
            executable_exists=False,
        )
    try:
        settings = json.loads(resolved_settings_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return ClaudeHookStatus(
            settings_path=resolved_settings_path,
            exists=True,
            malformed=True,
            managed=False,
            command_executable=None,
            executable_exists=False,
        )
    if not isinstance(settings, dict):
        return ClaudeHookStatus(
            settings_path=resolved_settings_path,
            exists=True,
            malformed=True,
            managed=False,
            command_executable=None,
            executable_exists=False,
        )
    managed_command = _extract_managed_command(settings.get("hooks"))
    command_executable = _resolve_command_executable(managed_command)
    return ClaudeHookStatus(
        settings_path=resolved_settings_path,
        exists=True,
        malformed=False,
        managed=_hooks_contain_managed_entry(settings.get("hooks")),
        command_executable=command_executable,
        executable_exists=bool(command_executable and Path(command_executable).exists()),
    )


def _managed_command() -> str:
    """Return the Shellbrain-managed Claude SessionStart hook command."""

    executable = str(Path(sys.executable).resolve())
    return (
        f"{shlex.quote(executable)} -m app.periphery.identity.claude_runtime session-start "
        f"# {_MANAGED_MARKER} uses CLAUDE_ENV_FILE to export SHELLBRAIN_HOST_APP=claude_code "
        "and related Shellbrain identity variables"
    )


def _resolve_settings_path(*, repo_root: Path | None, settings_path: Path | None) -> Path:
    """Resolve one Claude settings path from either repo-local or explicit input."""

    if (repo_root is None) == (settings_path is None):
        raise ValueError("Pass exactly one of repo_root or settings_path.")
    if settings_path is not None:
        return Path(settings_path).expanduser().resolve()
    assert repo_root is not None
    return repo_root.resolve() / ".claude" / "settings.local.json"


def _load_settings_payload(settings_path: Path) -> tuple[dict[str, object], Path | None]:
    """Load one Claude settings payload, backing up malformed files when needed."""

    try:
        payload = json.loads(settings_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}, None
    except json.JSONDecodeError:
        return {}, _backup_invalid_settings_file(settings_path)
    if isinstance(payload, dict):
        return payload, None
    return {}, _backup_invalid_settings_file(settings_path)


def _backup_invalid_settings_file(settings_path: Path) -> Path:
    """Back up one malformed settings file before Shellbrain recreates it."""

    settings_path.parent.mkdir(parents=True, exist_ok=True)
    counter = 1
    while True:
        backup_path = settings_path.with_name(f"{settings_path.name}.shellbrain-backup-{counter}")
        if not backup_path.exists():
            shutil.copy2(settings_path, backup_path)
            return backup_path
        counter += 1


def _merged_hooks(hooks: object) -> dict[str, object]:
    """Return hooks with one managed SessionStart entry merged in place."""

    if not isinstance(hooks, dict):
        hooks = {}
    session_start_entries = hooks.get("SessionStart")
    if not isinstance(session_start_entries, list):
        session_start_entries = []

    managed_entry = {
        "matcher": _SESSION_START_MATCHER,
        "hooks": [
            {
                "type": "command",
                "command": _managed_command(),
            }
        ],
    }
    replaced = False
    for index, entry in enumerate(session_start_entries):
        if not isinstance(entry, dict):
            continue
        nested_hooks = entry.get("hooks")
        if not isinstance(nested_hooks, list):
            continue
        if any(_MANAGED_MARKER in str(item.get("command", "")) for item in nested_hooks if isinstance(item, dict)):
            session_start_entries[index] = managed_entry
            replaced = True
            break
    if not replaced:
        session_start_entries.append(managed_entry)
    hooks["SessionStart"] = session_start_entries
    return hooks


def _hooks_contain_managed_entry(hooks: object) -> bool:
    """Return whether hooks already contain the Shellbrain-managed entry."""

    if not isinstance(hooks, dict):
        return False
    session_start_entries = hooks.get("SessionStart")
    if not isinstance(session_start_entries, list):
        return False
    for entry in session_start_entries:
        if not isinstance(entry, dict):
            continue
        nested_hooks = entry.get("hooks")
        if not isinstance(nested_hooks, list):
            continue
        if any(_MANAGED_MARKER in str(item.get("command", "")) for item in nested_hooks if isinstance(item, dict)):
            return True
    return False


def _extract_managed_command(hooks: object) -> str | None:
    """Return the managed Shellbrain command string when present."""

    if not isinstance(hooks, dict):
        return None
    session_start_entries = hooks.get("SessionStart")
    if not isinstance(session_start_entries, list):
        return None
    for entry in session_start_entries:
        if not isinstance(entry, dict):
            continue
        nested_hooks = entry.get("hooks")
        if not isinstance(nested_hooks, list):
            continue
        for item in nested_hooks:
            if not isinstance(item, dict):
                continue
            command = str(item.get("command", ""))
            if _MANAGED_MARKER in command:
                return command
    return None


def _resolve_command_executable(command: str | None) -> str | None:
    """Resolve the executable path from one managed hook command string."""

    if not command:
        return None
    prefix = command.split(" # ", 1)[0].strip()
    if not prefix:
        return None
    try:
        parts = shlex.split(prefix)
    except ValueError:
        return None
    if not parts:
        return None
    executable = parts[0]
    if Path(executable).is_absolute():
        return str(Path(executable).expanduser())
    resolved = shutil.which(executable)
    if resolved is None:
        return None
    return str(Path(resolved).resolve())
