"""This module defines the CLI entry point for create, read, and update operations."""

import argparse
import json
from pathlib import Path
from typing import Any

from app.boot.create_policy import get_create_hydration_defaults
from app.boot.read_policy import get_read_hydration_defaults
from app.boot.use_cases import get_embedding_model, get_embedding_provider_factory, get_uow_factory
from app.periphery.cli.handlers import handle_create, handle_events, handle_read, handle_update
from app.periphery.cli.hydration import (
    infer_repo_id,
)
from app.periphery.cli.presenter_json import render


def _load_payload(json_text: str | None, json_file: str | None) -> dict[str, Any]:
    """This function loads a payload from either inline JSON text or a JSON file."""

    if json_text:
        return json.loads(json_text)
    if json_file:
        content = Path(json_file).read_text(encoding="utf-8")
        return json.loads(content)
    raise ValueError("Either --json or --json-file is required")


def main() -> int:
    """This function parses CLI arguments and dispatches to operation handlers."""

    parser = argparse.ArgumentParser(prog="memory")
    parser.add_argument("command", choices=["create", "read", "update", "events"])
    parser.add_argument("--json", dest="json_text")
    parser.add_argument("--json-file", dest="json_file")
    args = parser.parse_args()

    payload = _load_payload(args.json_text, args.json_file)
    inferred_repo_id = infer_repo_id()
    read_defaults = get_read_hydration_defaults()
    create_defaults = get_create_hydration_defaults()

    uow_factory = get_uow_factory()
    embedding_provider_factory = get_embedding_provider_factory()
    embedding_model = get_embedding_model()

    if args.command == "create":
        result = handle_create(
            payload,
            uow_factory=uow_factory,
            embedding_provider_factory=embedding_provider_factory,
            embedding_model=embedding_model,
            inferred_repo_id=inferred_repo_id,
            defaults=create_defaults,
        )
    elif args.command == "read":
        result = handle_read(
            payload,
            uow_factory=uow_factory,
            inferred_repo_id=inferred_repo_id,
            defaults=read_defaults,
        )
    elif args.command == "update":
        result = handle_update(payload, uow_factory=uow_factory, inferred_repo_id=inferred_repo_id)
    else:
        result = handle_events(
            payload,
            uow_factory=uow_factory,
            inferred_repo_id=inferred_repo_id,
            repo_root=Path.cwd().resolve(),
        )

    if result.get("status") == "ok":
        try:
            from app.periphery.episodes.launcher import ensure_episode_sync_started

            ensure_episode_sync_started(repo_id=inferred_repo_id, repo_root=Path.cwd().resolve())
        except Exception:
            pass

    print(render(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
