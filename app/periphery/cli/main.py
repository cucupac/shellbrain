"""This module defines the CLI entry point for create, read, and update operations."""

import argparse
import json
from pathlib import Path
from typing import Any

from app.boot.read_policy import get_read_hydration_defaults
from app.boot.use_cases import get_embedding_model, get_embedding_provider_factory, get_uow_factory
from app.periphery.cli.handlers import handle_create, handle_read, handle_update
from app.periphery.cli.hydration import (
    hydrate_create_payload,
    hydrate_read_payload,
    hydrate_update_payload,
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
    parser.add_argument("command", choices=["create", "read", "update"])
    parser.add_argument("--json", dest="json_text")
    parser.add_argument("--json-file", dest="json_file")
    args = parser.parse_args()

    payload = _load_payload(args.json_text, args.json_file)
    inferred_repo_id = infer_repo_id()
    read_defaults = get_read_hydration_defaults()
    create_defaults = {"scope": "repo", "confidence": 0.75}

    uow_factory = get_uow_factory()
    embedding_provider_factory = get_embedding_provider_factory()
    embedding_model = get_embedding_model()

    if args.command == "create":
        payload = hydrate_create_payload(payload, inferred_repo_id=inferred_repo_id, defaults=create_defaults)
        result = handle_create(
            payload,
            uow_factory=uow_factory,
            embedding_provider_factory=embedding_provider_factory,
            embedding_model=embedding_model,
        )
    elif args.command == "read":
        payload = hydrate_read_payload(payload, inferred_repo_id=inferred_repo_id, defaults=read_defaults)
        result = handle_read(payload, uow_factory=uow_factory)
    else:
        payload = hydrate_update_payload(payload, inferred_repo_id=inferred_repo_id)
        result = handle_update(payload, uow_factory=uow_factory)

    print(render(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
