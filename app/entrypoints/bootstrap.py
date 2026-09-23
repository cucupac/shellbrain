"""Private installer entrypoint for initialization and test database migrations."""

import argparse
from pathlib import Path


def main(argv=None) -> int:
    """Compose bootstrap dependencies only for an installer invocation."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--migrate-only", action="store_true")
    parser.add_argument("--repo-root")
    parser.add_argument("--repo-id")
    parser.add_argument("--storage", choices=("managed", "external"))
    parser.add_argument("--admin-dsn")
    parser.add_argument("--skip-model-download", action="store_true")
    parser.add_argument("--no-host-assets", action="store_true")
    args = parser.parse_args(argv)
    from app.startup import migrations, runtime_admin
    from app.entrypoints.cli.handlers.human.init import run

    if args.migrate_only:
        migrations.upgrade_database()
        print("Applied shellbrain schema migrations to head.")
        return 0
    return run(
        args,
        resolve_admin_repo_root=lambda root: Path(root or Path.cwd()).resolve(),
        should_register_repo=runtime_admin.should_register_repo_during_init,
        run_init=runtime_admin.run_init,
        init_success_presenter_context=runtime_admin.init_success_presenter_context,
    )


if __name__ == "__main__":
    raise SystemExit(main())
