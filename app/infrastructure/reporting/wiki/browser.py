"""Browser helpers for opening Shellbrain Wiki."""

from __future__ import annotations

import webbrowser


def open_wiki(url: str) -> bool:
    """Open the local wiki URL in the default browser."""

    return bool(webbrowser.open(url))
