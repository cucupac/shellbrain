"""CLI entrypoint for repo-local episodic transcript sync."""

from __future__ import annotations

import argparse
from pathlib import Path

from app.startup.episode_poller import run_episode_poller


def main() -> int:
    """Parse job arguments and run the startup-composed poller."""

    parser = argparse.ArgumentParser(prog="shellbrain-episode-poller")
    parser.add_argument("--repo-id", required=True)
    parser.add_argument("--repo-root", required=True)
    args = parser.parse_args()

    run_episode_poller(repo_id=args.repo_id, repo_root=Path(args.repo_root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
