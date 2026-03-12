"""This module defines the CLI entry point for create, read, and update operations."""

import argparse
import json
from pathlib import Path
from typing import Any

from app.boot.config import get_config_provider
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
    config_provider = get_config_provider()
    runtime = config_provider.get_runtime()
    read_policy = config_provider.get_read_policy()
    inferred_repo_id = infer_repo_id()

    cli_runtime_defaults = runtime.get("cli", {})
    limits = read_policy.get("limits") or {}
    expansion = read_policy.get("expansion") or {}
    read_defaults = {
        "default_mode": cli_runtime_defaults.get("default_mode", "targeted"),
        "include_global": cli_runtime_defaults.get("include_global", True),
        "limits_by_mode": {
            "targeted": limits.get("targeted", 8),
            "ambient": limits.get("ambient", 12),
        },
        "semantic_hops": expansion.get("semantic_hops", 2),
        "include_problem_links": expansion.get("include_problem_links", True),
        "include_fact_update_links": expansion.get("include_fact_update_links", True),
        "include_association_links": expansion.get("include_association_links", True),
        "max_association_depth": expansion.get("max_association_depth", 2),
        "min_association_strength": expansion.get("min_association_strength", 0.25),
    }
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
