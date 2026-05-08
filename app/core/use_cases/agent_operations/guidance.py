"""Guidance attachment for agent operation workflows."""

from __future__ import annotations

from app.core.entities.identity import CallerIdentity
from app.core.use_cases.build_guidance import build_pending_utility_guidance


def build_guidance_payloads(
    *,
    uow_factory,
    repo_id: str,
    caller_identity: CallerIdentity | None,
    session_state,
    now_iso: str,
    strong: bool,
) -> list[dict]:
    """Build public guidance payloads from telemetry and session state."""

    if session_state is None:
        return []
    with uow_factory() as guidance_uow:
        decisions = build_pending_utility_guidance(
            repo_id=repo_id,
            caller_identity=caller_identity,
            session_state=session_state,
            telemetry=guidance_uow.telemetry,
            now_iso=now_iso,
            strong=strong,
        )
    return [decision.to_payload() for decision in decisions]


def attach_guidance(result: dict, guidance_payloads: list[dict]) -> None:
    """Attach one or more guidance payloads to a successful result."""

    data = result.setdefault("data", {})
    if not isinstance(data, dict):
        return
    data["guidance"] = guidance_payloads
