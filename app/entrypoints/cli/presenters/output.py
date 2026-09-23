"""Human-readable recall in terminals; complete JSON for pipes."""

import json
import os
import shutil
import sys
import textwrap
from typing import Any


def print_result(result: dict[str, Any], *, command: str) -> None:
    """Present successful recall briefs without changing machine output."""

    if not sys.stdout.isatty():
        print(json.dumps(result, separators=(",", ":")))
        return
    if command != "recall" or result.get("status") != "ok" or result.get("errors"):
        print(json.dumps(result, indent=2))
        return

    color = not os.environ.get("NO_COLOR") and os.environ.get("TERM") != "dumb"
    width = max(20, min(88, shutil.get_terminal_size().columns))
    print(render_recall(result["data"], width=width, color=color))


def render_recall(data: dict[str, Any], *, width: int, color: bool) -> str:
    """Render every nonempty brief section with aligned, wrapped bullets."""

    def style(text: str, code: str) -> str:
        return f"\033[{code}m{text}\033[0m" if color else text

    def wrap(text: str, indent: str, continuation: str) -> str:
        # Escape terminal controls from recalled text before adding our own colors.
        safe = "".join(
            f"\\u{ord(char):04x}" if ord(char) < 32 or 127 <= ord(char) < 160 else char
            for char in text
        )
        return textwrap.fill(
            safe,
            width=width,
            initial_indent=indent,
            subsequent_indent=continuation,
            break_long_words=False,
            break_on_hyphens=False,
        )

    brief = data["brief"]
    lines = ["", style("  SHELLBRAIN · RECALL", "2"), ""]
    if not brief["memories"]:
        lines.extend(
            [
                wrap(
                    "No relevant memories found for this question.", "    • ", "      "
                ),
                "",
            ]
        )
        return "\n".join(lines)
    for field in ("memories", "code"):
        if not brief[field]:
            continue
        lines.append(style(f"  {field.capitalize()}", "1;36"))
        for item in brief[field]:
            bullet = wrap(item, "    • ", "      ")
            if field == "code":
                bullet = style(bullet, "2")
            else:
                bullet = bullet.replace("    • ", "    " + style("•", "2") + " ", 1)
            lines.append(bullet)
        lines.append("")
    return "\n".join(lines)
