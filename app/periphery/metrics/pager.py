"""Terminal presentation helpers for cross-repo metrics snapshots."""

from __future__ import annotations

import os
import select
import sys
import termios
import tty
from pathlib import Path
from typing import Any, Callable, Sequence, TextIO


def present_metrics_repo_pager(
    *,
    entries: Sequence[dict[str, Any]],
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    open_dashboard: Callable[[Path], bool] | None = None,
) -> None:
    """Render one terminal view for metrics entries, with arrow-key browsing when interactive."""

    input_stream = stdin or sys.stdin
    output_stream = stdout or sys.stdout
    if not entries:
        output_stream.write("No metrics snapshots are available.\n")
        return
    if not _supports_interactive_view(input_stream=input_stream, output_stream=output_stream):
        output_stream.write(_render_non_interactive(entries))
        output_stream.flush()
        return
    _run_interactive_view(entries=entries, input_stream=input_stream, output_stream=output_stream, open_dashboard=open_dashboard)


def _supports_interactive_view(*, input_stream: TextIO, output_stream: TextIO) -> bool:
    """Return whether raw-key interactive controls are safe for this process."""

    try:
        if not input_stream.isatty() or not output_stream.isatty():
            return False
        input_stream.fileno()
        termios.tcgetattr(input_stream.fileno())
        return True
    except (AttributeError, OSError, termios.error):
        return False


def _run_interactive_view(
    *,
    entries: Sequence[dict[str, Any]],
    input_stream: TextIO,
    output_stream: TextIO,
    open_dashboard: Callable[[Path], bool] | None,
) -> None:
    """Run one arrow-key pager loop over repo metrics entries."""

    index = 0
    notice = "Use left/right arrows to switch repos. Press q to exit."
    fd = input_stream.fileno()
    original_attrs = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        while True:
            output_stream.write(_clear_screen())
            output_stream.write(_render_entry(entries=entries, index=index, notice=notice, interactive=True))
            output_stream.flush()

            key = _read_key(fd)
            if key == "next":
                index = (index + 1) % len(entries)
                notice = "Moved to next repo."
                continue
            if key == "prev":
                index = (index - 1) % len(entries)
                notice = "Moved to previous repo."
                continue
            if key == "open":
                if open_dashboard is None:
                    notice = "Browser helper unavailable in this mode."
                else:
                    html_path = _entry_paths(entries[index]).get("html_path")
                    if isinstance(html_path, Path) and bool(open_dashboard(html_path)):
                        notice = f"Opened dashboard: {html_path}"
                    else:
                        notice = "Could not open dashboard automatically."
                continue
            if key == "quit":
                break
            notice = "Unrecognized key. Use arrows, o, or q."
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, original_attrs)
        output_stream.write(_clear_screen())
        output_stream.write(_render_entry(entries=entries, index=index, notice="Exited metrics viewer.", interactive=False))
        output_stream.flush()


def _read_key(fd: int) -> str:
    """Decode one keyboard event into a pager command."""

    first = os.read(fd, 1)
    if first in (b"q", b"Q", b"\x03", b"\x04"):
        return "quit"
    if first in (b"o", b"O"):
        return "open"
    if first in (b"l", b"L", b"n", b"N", b"\r", b"\n", b" "):
        return "next"
    if first in (b"h", b"H", b"p", b"P"):
        return "prev"
    if first != b"\x1b":
        return "noop"
    if not _ready(fd):
        return "quit"
    second = os.read(fd, 1)
    if second != b"[":
        return "noop"
    if not _ready(fd):
        return "noop"
    third = os.read(fd, 1)
    if third in (b"C", b"B"):
        return "next"
    if third in (b"D", b"A"):
        return "prev"
    return "noop"


def _ready(fd: int) -> bool:
    """Return whether one byte is ready to read from the terminal."""

    readable, _, _ = select.select([fd], [], [], 0.05)
    return bool(readable)


def _render_non_interactive(entries: Sequence[dict[str, Any]]) -> str:
    """Render all repo metrics entries for non-interactive stdout targets."""

    blocks: list[str] = []
    total = len(entries)
    for index in range(total):
        blocks.append(_render_entry(entries=entries, index=index, notice="", interactive=False))
    return "\n\n".join(blocks) + "\n"


def _render_entry(*, entries: Sequence[dict[str, Any]], index: int, notice: str, interactive: bool) -> str:
    """Render one repo metrics entry as plain terminal text."""

    entry = entries[index]
    snapshot = _entry_snapshot(entry)
    paths = _entry_paths(entry)

    lines = [
        f"Shellbrain Metrics Viewer [{index + 1}/{len(entries)}]",
        f"Repo: {snapshot.get('repo_id', 'unknown')}",
        f"Status: {snapshot.get('status', 'unknown')} ({snapshot.get('confidence', 'unknown')} confidence)",
        f"Window: {snapshot.get('window_days', '?')} days",
        f"Generated: {snapshot.get('generated_at', 'unknown')}",
        "",
        "Metrics:",
    ]
    for metric in list(snapshot.get("metrics", []))[:4]:
        lines.append(f"  - {_render_metric_line(metric)}")
    lines.extend(
        [
            "",
            f"JSON: {paths.get('json_path', 'n/a')}",
            f"Markdown: {paths.get('md_path', 'n/a')}",
            f"Dashboard: {paths.get('html_path', 'n/a')}",
        ]
    )
    if interactive:
        lines.extend(
            [
                "",
                "Controls: <- -> (or h/l) move | o open dashboard | q quit",
                f"Notice: {notice}",
            ]
        )
    elif notice:
        lines.extend(["", f"Notice: {notice}"])
    return "\n".join(lines)


def _entry_snapshot(entry: dict[str, Any]) -> dict[str, Any]:
    """Return the snapshot payload for one pager entry."""

    snapshot = entry.get("snapshot")
    return snapshot if isinstance(snapshot, dict) else {}


def _entry_paths(entry: dict[str, Any]) -> dict[str, Path]:
    """Return artifact paths for one pager entry."""

    raw = entry.get("paths")
    if not isinstance(raw, dict):
        return {}
    normalized: dict[str, Path] = {}
    for key, value in raw.items():
        if isinstance(value, Path):
            normalized[str(key)] = value
        elif isinstance(value, str):
            normalized[str(key)] = Path(value)
    return normalized


def _render_metric_line(metric: object) -> str:
    """Render one compact metric line."""

    if not isinstance(metric, dict):
        return "invalid metric payload"
    name = str(metric.get("name", "metric"))
    format_name = str(metric.get("format", "score"))
    current = _format_metric_value(metric.get("current"), format_name)
    previous = _format_metric_value(metric.get("previous"), format_name)
    delta = _format_delta(metric.get("delta"), format_name)
    sample_count = metric.get("sample_count")
    sample_display = f"n={int(sample_count)}" if isinstance(sample_count, int | float) else "n=?"
    return f"{name}: now {current} | prev {previous} | delta {delta} | {sample_display}"


def _format_metric_value(value: object, format_name: str) -> str:
    """Format one metric value according to the metric card format field."""

    if value is None:
        return "n/a"
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return "n/a"
    if format_name == "percent":
        return f"{numeric * 100:.1f}%"
    return f"{numeric:.3f}"


def _format_delta(value: object, format_name: str) -> str:
    """Format one metric delta with explicit sign direction."""

    if value is None:
        return "n/a"
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return "n/a"
    if format_name == "percent":
        return f"{numeric * 100:+.1f}pp"
    return f"{numeric:+.3f}"


def _clear_screen() -> str:
    """Return one ANSI clear-screen sequence."""

    return "\x1b[2J\x1b[H"
