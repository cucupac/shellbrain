"""Allow `python -m shellbrain` to invoke the public CLI."""

from shellbrain.periphery.cli.main import main


if __name__ == "__main__":
    raise SystemExit(main())
