"""Compatibility-safe caller-identity errors with concrete remediation guidance."""

from __future__ import annotations

from app.core.contracts.errors import ErrorCode, ErrorDetail


def host_hook_missing_error() -> ErrorDetail:
    """Return the canonical error for missing Claude hook identity injection."""

    return ErrorDetail(
        code=ErrorCode.HOST_HOOK_MISSING,
        message="Claude Code runtime detected but Shellbrain hook identity is missing. Run `shellbrain admin install-claude-hook` in this repo and restart Claude Code.",
    )


def host_identity_unsupported_error() -> ErrorDetail:
    """Return the canonical error for unsupported host identity layouts."""

    return ErrorDetail(
        code=ErrorCode.HOST_IDENTITY_UNSUPPORTED,
        message="This host runtime does not expose enough identity data for Shellbrain to isolate the caller safely.",
    )


def host_identity_drifted_error(*, caller_id: str) -> ErrorDetail:
    """Return the canonical error for trusted identities that can no longer be resolved."""

    return ErrorDetail(
        code=ErrorCode.HOST_IDENTITY_DRIFTED,
        message=f"Trusted caller identity drifted and could not be resolved for `{caller_id}`. Verify the host thread/session still exists and rerun `events`.",
    )
