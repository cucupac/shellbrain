"""Core working-session lifecycle rules for per-caller session state."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone

from app.core.entities.identity import CallerIdentity, IdentityTrustLevel
from app.core.entities.session_state import SessionState
from app.core.ports.clock import IClock
from app.core.ports.session_state_store import ISessionStateStore


IDLE_EXPIRY = timedelta(hours=24)
GC_EXPIRY = timedelta(days=7)


class SessionStateManager:
    """Application service for loading, touching, and mutating working session state."""

    def __init__(self, *, store: ISessionStateStore, clock: IClock) -> None:
        """Capture the persistence store and clock dependency."""

        self._store = store
        self._clock = clock

    def load_active_state(
        self, *, repo_root, caller_identity: CallerIdentity | None
    ) -> SessionState | None:
        """Load and touch the active caller state when identity is trusted."""

        if (
            caller_identity is None
            or caller_identity.trust_level != IdentityTrustLevel.TRUSTED
        ):
            return None
        now_iso = self._now_iso()
        state = self._store.load(
            repo_root=repo_root, caller_id=caller_identity.canonical_id or ""
        )
        if state is None:
            state = SessionState(
                caller_id=caller_identity.canonical_id or "",
                host_app=caller_identity.host_app,
                host_session_key=caller_identity.host_session_key,
                agent_key=caller_identity.agent_key,
                session_started_at=now_iso,
                last_seen_at=now_iso,
            )
        else:
            state = self.reset_if_idle(state, now_iso=now_iso)
            state.last_seen_at = now_iso
        self._store.save(repo_root=repo_root, state=state)
        return state

    def record_events(
        self,
        *,
        repo_root,
        caller_identity: CallerIdentity | None,
        episode_id: str,
        event_ids: list[str],
    ) -> SessionState | None:
        """Persist the latest events context for one trusted caller."""

        state = self.load_active_state(
            repo_root=repo_root, caller_identity=caller_identity
        )
        if state is None:
            return None
        now_iso = self._now_iso()
        state.last_events_episode_id = episode_id
        state.last_events_event_ids = list(event_ids)
        state.last_events_at = now_iso
        state.last_seen_at = now_iso
        self._store.save(repo_root=repo_root, state=state)
        return state

    def record_problem(
        self,
        *,
        repo_root,
        caller_identity: CallerIdentity | None,
        problem_id: str,
    ) -> SessionState | None:
        """Persist the active problem for one trusted caller."""

        state = self.load_active_state(
            repo_root=repo_root, caller_identity=caller_identity
        )
        if state is None:
            return None
        state.current_problem_id = problem_id
        state.last_seen_at = self._now_iso()
        self._store.save(repo_root=repo_root, state=state)
        return state

    def record_guidance(
        self,
        *,
        repo_root,
        caller_identity: CallerIdentity | None,
        problem_id: str,
    ) -> SessionState | None:
        """Persist the latest emitted guidance timestamp for one trusted caller."""

        state = self.load_active_state(
            repo_root=repo_root, caller_identity=caller_identity
        )
        if state is None:
            return None
        now_iso = self._now_iso()
        state.last_guidance_problem_id = problem_id
        state.last_guidance_at = now_iso
        state.last_seen_at = now_iso
        self._store.save(repo_root=repo_root, state=state)
        return state

    def clear_for_caller(self, *, repo_root, caller_id: str) -> None:
        """Delete one caller state."""

        self._store.delete(repo_root=repo_root, caller_id=caller_id)

    def garbage_collect(self, *, repo_root) -> list[str]:
        """Delete states older than the configured GC threshold."""

        cutoff_iso = (self._now() - GC_EXPIRY).isoformat()
        return self._store.gc(repo_root=repo_root, older_than_iso=cutoff_iso)

    @staticmethod
    def reset_if_idle(state: SessionState, *, now_iso: str) -> SessionState:
        """Reset working-session fields when the caller has been idle too long."""

        try:
            last_seen = _parse_iso(state.last_seen_at)
        except ValueError:
            last_seen = datetime.min.replace(tzinfo=timezone.utc)
        now = _parse_iso(now_iso)
        if now - last_seen < IDLE_EXPIRY:
            return state
        return replace(
            state,
            session_started_at=now_iso,
            last_seen_at=now_iso,
            current_problem_id=None,
            last_events_episode_id=None,
            last_events_event_ids=[],
            last_events_at=None,
            last_guidance_at=None,
            last_guidance_problem_id=None,
        )

    def _now(self) -> datetime:
        """Return the current UTC time using the injected clock when present."""

        return self._clock.now()

    def _now_iso(self) -> str:
        """Return the current UTC time in ISO-8601 form."""

        return self._now().isoformat()


def _parse_iso(value: str) -> datetime:
    """Parse one ISO timestamp into a timezone-aware datetime."""

    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
