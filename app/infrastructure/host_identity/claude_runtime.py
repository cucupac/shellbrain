"""Claude runtime identity helpers and SessionStart hook entrypoint."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

from app.core.entities.identity import CallerIdentity, IdentityTrustLevel


def resolve_trusted_claude_caller_identity() -> CallerIdentity | None:
    """Resolve one trusted Claude caller from Shellbrain hook environment variables."""

    if os.getenv("SHELLBRAIN_HOST_APP") != "claude_code":
        return None
    session_key = os.getenv("SHELLBRAIN_HOST_SESSION_KEY")
    transcript_path = os.getenv("SHELLBRAIN_TRANSCRIPT_PATH")
    if not session_key or not transcript_path:
        return None
    agent_key = os.getenv("SHELLBRAIN_AGENT_KEY") or None
    if "/subagents/" in transcript_path and agent_key is None:
        return CallerIdentity(
            host_app="claude_code",
            host_session_key=session_key,
            trust_level=IdentityTrustLevel.UNSUPPORTED,
        )
    return CallerIdentity(
        host_app="claude_code",
        host_session_key=session_key,
        agent_key=agent_key,
        trust_level=IdentityTrustLevel.TRUSTED,
    )


def detect_claude_runtime_without_hook() -> bool:
    """Return whether Claude seems present but trusted hook identity is missing."""

    if os.getenv("SHELLBRAIN_HOST_APP") == "claude_code":
        return False
    return any(
        os.getenv(name)
        for name in ("CLAUDE_SESSION_ID", "CLAUDE_CODE_REMOTE_SESSION_ID", "CLAUDE_CODE_AGENT_NAME")
    )


def resolve_trusted_claude_transcript_path() -> Path | None:
    """Return the trusted Claude transcript path injected by the Shellbrain hook when present."""

    transcript_path = os.getenv("SHELLBRAIN_TRANSCRIPT_PATH")
    if not transcript_path:
        return None
    return Path(transcript_path).expanduser().resolve()


def main(argv: list[str] | None = None) -> int:
    """Entrypoint for the Claude SessionStart hook helper."""

    parser = argparse.ArgumentParser(prog="shellbrain-claude-runtime")
    parser.add_argument("command", choices=("session-start",))
    args = parser.parse_args(argv)
    if args.command != "session-start":
        return 2
    payload = json.load(sys.stdin)
    session_id = str(payload.get("session_id") or "")
    transcript_path = str(payload.get("transcript_path") or "")
    if not session_id or not transcript_path:
        return 1
    env_file = os.getenv("CLAUDE_ENV_FILE")
    if not env_file:
        return 0
    with Path(env_file).open("a", encoding="utf-8") as handle:
        handle.write("export SHELLBRAIN_HOST_APP=claude_code\n")
        handle.write(f"export SHELLBRAIN_HOST_SESSION_KEY={session_id}\n")
        handle.write(f"export SHELLBRAIN_TRANSCRIPT_PATH={transcript_path}\n")
        handle.write(f"export SHELLBRAIN_CALLER_ID=claude_code:{session_id}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
