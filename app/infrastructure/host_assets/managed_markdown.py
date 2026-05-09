"""Managed markdown block installation and inspection."""

from __future__ import annotations

from pathlib import Path
import re

from app.infrastructure.host_assets.managed_tree import remove_existing_path


def install_managed_markdown_block(
    *,
    source_text: str,
    target_path: Path,
    block_marker: str,
    force: bool,
) -> tuple[str, Path, str | None]:
    """Install or update one managed markdown block inside one user startup file."""

    target_path = target_path.expanduser().resolve()
    start_marker, end_marker = markdown_markers(block_marker)
    block_text = f"{start_marker}\n{source_text.strip()}\n{end_marker}\n"
    if target_path.exists() and target_path.is_dir():
        if not force:
            return (
                "skipped",
                target_path,
                f"unmanaged directory exists at {target_path}; rerun with --force to replace",
            )
        remove_existing_path(target_path)

    status = "installed"
    if target_path.exists():
        try:
            existing_text = target_path.read_text(encoding="utf-8")
        except OSError as exc:
            return "skipped", target_path, f"unable to read {target_path}: {exc}"
        block_status = managed_block_status(
            existing_text=existing_text, block_marker=block_marker
        )
        if block_status == "malformed":
            return (
                "skipped",
                target_path,
                f"managed block markers are malformed in {target_path}",
            )
        if block_status == "present":
            next_text = replace_managed_block(
                existing_text=existing_text,
                block_marker=block_marker,
                block_text=block_text,
            )
            status = "updated"
        else:
            next_text = append_managed_block(
                existing_text=existing_text, block_text=block_text
            )
    else:
        next_text = block_text
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(next_text, encoding="utf-8")
    return status, target_path, None


def inspect_managed_markdown_block(
    *, target_path: Path, block_marker: str
) -> dict[str, object]:
    """Inspect whether one startup file contains one Shellbrain-managed markdown block."""

    resolved_path = target_path.expanduser().resolve()
    if not resolved_path.exists():
        return {
            "path": str(resolved_path),
            "file_exists": False,
            "installed": False,
            "managed": False,
            "malformed": False,
        }
    if resolved_path.is_dir():
        return {
            "path": str(resolved_path),
            "file_exists": False,
            "installed": False,
            "managed": False,
            "malformed": True,
        }
    try:
        existing_text = resolved_path.read_text(encoding="utf-8")
    except OSError:
        return {
            "path": str(resolved_path),
            "file_exists": True,
            "installed": False,
            "managed": False,
            "malformed": True,
        }
    status = managed_block_status(
        existing_text=existing_text, block_marker=block_marker
    )
    return {
        "path": str(resolved_path),
        "file_exists": True,
        "installed": status == "present",
        "managed": status == "present",
        "malformed": status == "malformed",
    }


def markdown_markers(block_marker: str) -> tuple[str, str]:
    """Return the managed markdown start and end markers for one block."""

    return (f"<!-- {block_marker} start -->", f"<!-- {block_marker} end -->")


def managed_block_status(*, existing_text: str, block_marker: str) -> str:
    """Return whether one managed markdown block is present, absent, or malformed."""

    start_marker, end_marker = markdown_markers(block_marker)
    has_start = start_marker in existing_text
    has_end = end_marker in existing_text
    if (
        has_start
        and has_end
        and existing_text.index(start_marker) < existing_text.index(end_marker)
    ):
        return "present"
    if has_start or has_end:
        return "malformed"
    return "absent"


def replace_managed_block(
    *, existing_text: str, block_marker: str, block_text: str
) -> str:
    """Replace one existing managed markdown block in a file."""

    start_marker, end_marker = markdown_markers(block_marker)
    pattern = re.compile(
        rf"{re.escape(start_marker)}.*?{re.escape(end_marker)}\n?", flags=re.DOTALL
    )
    return pattern.sub(block_text, existing_text, count=1)


def append_managed_block(*, existing_text: str, block_text: str) -> str:
    """Append one managed markdown block to a file while preserving unrelated content."""

    stripped = existing_text.rstrip()
    if not stripped:
        return block_text
    return f"{stripped}\n\n{block_text}"
