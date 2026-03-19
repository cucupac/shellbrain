"""Install the official Claude SessionStart hook for Shellbrain caller identity."""

from __future__ import annotations

import json
from pathlib import Path


def install_claude_hook(*, repo_root: Path) -> Path:
    """Install or update one repo-local Claude settings file with the Shellbrain hook."""

    repo_root = repo_root.resolve()
    settings_path = repo_root / ".claude" / "settings.local.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        settings = {}

    settings["hooks"] = {
        "SessionStart": [
            {
                "matcher": "startup|resume|clear|compact",
                "hooks": [
                    {
                        "type": "command",
                        "command": (
                            "python -m shellbrain.periphery.identity.claude_runtime session-start "
                            "# uses CLAUDE_ENV_FILE to export SHELLBRAIN_HOST_APP=claude_code "
                            "and related Shellbrain identity variables"
                        ),
                    }
                ],
            }
        ]
    }
    settings_path.write_text(json.dumps(settings, indent=2, sort_keys=True), encoding="utf-8")
    return settings_path
