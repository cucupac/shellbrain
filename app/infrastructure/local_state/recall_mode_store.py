"""Machine-local recall mode override storage."""

from __future__ import annotations

import os
from pathlib import Path
import tomllib

from app.infrastructure.local_state.paths import get_shellbrain_home


RECALL_MODE_FAST = "fast"
RECALL_MODE_FULL = "full"
DEFAULT_RECALL_MODE = RECALL_MODE_FULL
VALID_RECALL_MODES = {RECALL_MODE_FAST, RECALL_MODE_FULL}


def get_recall_mode_path() -> Path:
    """Return the machine-local recall mode override path."""

    return get_shellbrain_home() / "recall.toml"


def load_recall_mode(path: Path | None = None) -> tuple[str, Path, bool]:
    """Return recall mode, config path, and whether an override file exists."""

    target = path or get_recall_mode_path()
    try:
        text = target.read_text(encoding="utf-8")
    except FileNotFoundError:
        return DEFAULT_RECALL_MODE, target, False
    try:
        payload = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"Invalid recall mode config at {target}: {exc}") from exc
    if set(payload) != {"mode"}:
        raise ValueError(
            f"Invalid recall mode config at {target}: expected only the 'mode' key."
        )
    mode = payload.get("mode")
    if not isinstance(mode, str) or mode not in VALID_RECALL_MODES:
        raise ValueError(
            f"Invalid recall mode config at {target}: mode must be 'fast' or 'full'."
        )
    return mode, target, True


def save_recall_mode(mode: str, path: Path | None = None) -> tuple[str, Path, bool]:
    """Persist one machine-local recall mode override."""

    if mode not in VALID_RECALL_MODES:
        raise ValueError("Recall mode must be 'fast' or 'full'.")
    target = path or get_recall_mode_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(f'mode = "{mode}"\n', encoding="utf-8")
    try:
        os.chmod(target, 0o600)
    except OSError:
        pass
    return mode, target, True
