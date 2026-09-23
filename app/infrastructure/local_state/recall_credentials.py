"""Load the recall API key from the environment or Shellbrain's private .env."""

import os
import shlex

from app.infrastructure.local_state.paths import get_shellbrain_home


def load_inception_api_key() -> str:
    """Read a literal key without executing shell files or changing the environment."""
    key = os.environ.get("INCEPTION_API_KEY", "").strip()
    if key:
        return key
    path = get_shellbrain_home() / ".env"
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return ""
    for line in lines:
        name, separator, value = line.partition("=")
        if separator and name.strip() == "INCEPTION_API_KEY":
            try:
                values = shlex.split(value, comments=True)
            except ValueError:
                raise ValueError(f"Invalid INCEPTION_API_KEY entry in {path}") from None
            if len(values) > 1:
                raise ValueError(f"Invalid INCEPTION_API_KEY entry in {path}")
            key = values[0].strip() if values else ""
    return key
