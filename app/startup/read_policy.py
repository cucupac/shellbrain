"""Defaults for the internal read command."""

from app.core.use_cases.retrieval.read.request import MemoryReadRequest


def get_read_hydration_defaults() -> dict:
    return {
        name: MemoryReadRequest.model_fields[name].default
        for name in ("mode", "include_global", "limit")
    }
