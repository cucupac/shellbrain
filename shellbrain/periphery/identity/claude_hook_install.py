"""Install the official Claude SessionStart hook for Shellbrain caller identity."""

from __future__ import annotations

import json
from pathlib import Path


_SESSION_START_MATCHER = "startup|resume|clear|compact"
_MANAGED_MARKER = "shellbrain-managed:session-start"


def install_claude_hook(*, repo_root: Path) -> Path:
    """Install or update one repo-local Claude settings file with the Shellbrain hook."""

    repo_root = repo_root.resolve()
    settings_path = repo_root / ".claude" / "settings.local.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        settings = {}
    if not isinstance(settings, dict):
        settings = {}
    hooks = settings.get("hooks")
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
    settings["hooks"] = hooks
    settings_path.write_text(json.dumps(settings, indent=2, sort_keys=True), encoding="utf-8")
    return settings_path


def _managed_command() -> str:
    """Return the Shellbrain-managed Claude SessionStart hook command."""

    return (
        "python -m shellbrain.periphery.identity.claude_runtime session-start "
        f"# {_MANAGED_MARKER} uses CLAUDE_ENV_FILE to export SHELLBRAIN_HOST_APP=claude_code "
        "and related Shellbrain identity variables"
    )
