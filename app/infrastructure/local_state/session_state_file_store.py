"""JSON file-backed implementation of repo-local per-caller session state."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from app.core.entities.session_state import SessionState
from app.core.ports.local_state.session_state_store import ISessionStateStore


class SessionStateFileCorruptionError(ValueError):
    """Raised when an existing session-state file is not valid current state."""

    def __init__(self, *, path: Path, reason: str) -> None:
        self.path = path
        self.reason = reason
        super().__init__(f"Corrupt session state file at {path}: {reason}")


class FileSessionStateStore(ISessionStateStore):
    """Persist trusted per-caller session state under one repo-local runtime directory."""

    def load(self, *, repo_root: Path, caller_id: str) -> SessionState | None:
        """Load one caller state when the corresponding file exists."""

        path = self._path_for(repo_root=repo_root, caller_id=caller_id)
        try:
            return _load_state_file(path)
        except FileNotFoundError:
            return None

    def save(self, *, repo_root: Path, state: SessionState) -> None:
        """Persist one caller state under its canonical caller id."""

        path = self._path_for(
            repo_root=repo_root, caller_id=state.caller_id, host_app=state.host_app
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(asdict(state), indent=2, sort_keys=True)
        with NamedTemporaryFile(
            "w", encoding="utf-8", dir=path.parent, delete=False
        ) as handle:
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
        for path in sorted(session_root.rglob("*.json")):
            try:
                states.append(_load_state_file(path))
            except FileNotFoundError:
                continue
        return states

    def gc(self, *, repo_root: Path, older_than_iso: str) -> list[str]:
        """Delete caller states last seen before the given cutoff."""

        cutoff = _parse_iso(older_than_iso)
        deleted: list[str] = []
        for state in self.list(repo_root=repo_root):
            last_seen = _parse_iso(state.last_seen_at)
            if last_seen >= cutoff:
                continue
            self.delete(repo_root=repo_root, caller_id=state.caller_id)
            deleted.append(state.caller_id)
        return deleted

    def _path_for(
        self, *, repo_root: Path, caller_id: str, host_app: str | None = None
    ) -> Path:
        """Return the storage path for one caller id."""

        repo_root = Path(repo_root).resolve()
        if host_app is None:
            host_app = caller_id.split(":", 1)[0]
        filename = f"{caller_id.replace(':', '__')}.json"
        return repo_root / ".shellbrain" / "session_state" / host_app / filename


def _load_state_file(path: Path) -> SessionState:
    """Read and validate one existing session-state file."""

    payload = _load_payload(path)
    return _state_from_payload(path=path, payload=payload)


def _load_payload(path: Path) -> dict[str, object]:
    """Read one session-state payload, preserving missing-vs-corrupt semantics."""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise
    except json.JSONDecodeError as exc:
        raise SessionStateFileCorruptionError(
            path=path, reason=f"invalid JSON: {exc.msg}"
        ) from exc
    if not isinstance(payload, dict):
        raise SessionStateFileCorruptionError(
            path=path, reason="payload must be a JSON object"
        )
    return payload


def _state_from_payload(*, path: Path, payload: dict[str, object]) -> SessionState:
    """Validate one JSON object against the current session-state schema."""

    try:
        state = SessionState(**payload)
    except TypeError as exc:
        raise SessionStateFileCorruptionError(
            path=path, reason="payload does not match the current session-state schema"
        ) from exc
    _validate_state(path=path, state=state)
    return state


def _validate_state(*, path: Path, state: SessionState) -> None:
    """Reject persisted states whose dataclass fields are not trustworthy."""

    for field_name in (
        "caller_id",
        "host_app",
        "host_session_key",
        "session_started_at",
        "last_seen_at",
    ):
        if not isinstance(getattr(state, field_name), str):
            raise SessionStateFileCorruptionError(
                path=path, reason=f"{field_name} must be a string"
            )

    for field_name in (
        "agent_key",
        "current_problem_id",
        "last_events_episode_id",
        "last_events_at",
        "last_guidance_at",
        "last_guidance_problem_id",
    ):
        value = getattr(state, field_name)
        if value is not None and not isinstance(value, str):
            raise SessionStateFileCorruptionError(
                path=path, reason=f"{field_name} must be null or a string"
            )

    if not isinstance(state.last_events_event_ids, list) or any(
        not isinstance(event_id, str) for event_id in state.last_events_event_ids
    ):
        raise SessionStateFileCorruptionError(
            path=path, reason="last_events_event_ids must be a list of strings"
    )

    for field_name in ("session_started_at", "last_seen_at"):
        _validate_iso_field(
            path=path, field_name=field_name, value=getattr(state, field_name)
        )
    for field_name in ("last_events_at", "last_guidance_at"):
        value = getattr(state, field_name)
        if value is not None:
            _validate_iso_field(path=path, field_name=field_name, value=value)


def _validate_iso_field(*, path: Path, field_name: str, value: str) -> None:
    """Reject invalid persisted timestamp strings."""

    try:
        _parse_iso(value)
    except ValueError as exc:
        raise SessionStateFileCorruptionError(
            path=path, reason=f"{field_name} must be a valid ISO timestamp"
        ) from exc


def _parse_iso(value: str) -> datetime:
    """Parse one ISO timestamp into a timezone-aware datetime."""

    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
