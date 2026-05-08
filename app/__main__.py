"""Allow `python -m app` to invoke the public CLI."""

from app.entrypoints.cli.main import main


if __name__ == "__main__":
    raise SystemExit(main())
