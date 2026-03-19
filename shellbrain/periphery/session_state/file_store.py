"""JSON file-backed implementation of repo-local per-caller session state."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from shellbrain.core.entities.session_state import SessionState
from shellbrain.core.interfaces.session_state_store import ISessionStateStore


class FileSessionStateStore(ISessionStateStore):
    """Persist trusted per-caller session state under one repo-local runtime directory."""

    def load(self, *, repo_root: Path, caller_id: str) -> SessionState | None:
        """Load one caller state when the corresponding file exists."""

        path = self._path_for(repo_root=repo_root, caller_id=caller_id)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return None
        if not isinstance(payload, dict):
            return None
        return SessionState(**payload)

    def save(self, *, repo_root: Path, state: SessionState) -> None:
        """Persist one caller state under its canonical caller id."""

        path = self._path_for(repo_root=repo_root, caller_id=state.caller_id, host_app=state.host_app)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(asdict(state), indent=2, sort_keys=True)
        with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
            handle.write(payload)
            temp_path = Path(handle.name)
        os.replace(temp_path, path)

    def delete(self, *, repo_root: Path, caller_id: str) -> None:
        """Delete one caller state when its file exists."""

        path = self._path_for(repo_root=repo_root, caller_id=caller_id)
        try:
            path.unlink()
        except FileNotFoundError:
            return

    def list(self, *, repo_root: Path) -> list[SessionState]:
        """Return every parseable caller state stored for the repo root."""

        session_root = Path(repo_root).resolve() / ".shellbrain" / "session_state"
        if not session_root.exists():
            return []
        states: list[SessionState] = []
        for path in session_root.rglob("*.json"):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (FileNotFoundError, json.JSONDecodeError):
                continue
            if not isinstance(payload, dict):
                continue
            states.append(SessionState(**payload))
        return states

    def gc(self, *, repo_root: Path, older_than_iso: str) -> list[str]:
        """Delete caller states last seen before the given cutoff."""

        cutoff = _parse_iso(older_than_iso)
        deleted: list[str] = []
        for state in self.list(repo_root=repo_root):
            try:
                last_seen = _parse_iso(state.last_seen_at)
            except ValueError:
                last_seen = datetime.min.replace(tzinfo=timezone.utc)
            if last_seen >= cutoff:
                continue
            self.delete(repo_root=repo_root, caller_id=state.caller_id)
            deleted.append(state.caller_id)
        return deleted

    def _path_for(self, *, repo_root: Path, caller_id: str, host_app: str | None = None) -> Path:
        """Return the storage path for one caller id."""

        repo_root = Path(repo_root).resolve()
        if host_app is None:
            host_app = caller_id.split(":", 1)[0]
        filename = f"{caller_id.replace(':', '__')}.json"
        return repo_root / ".shellbrain" / "session_state" / host_app / filename


def _parse_iso(value: str) -> datetime:
    """Parse one ISO timestamp into a timezone-aware datetime."""

    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
