"""This module defines shared side-effect descriptor helpers."""

from typing import Any


def make_side_effect(effect_type: str, params: dict[str, Any]) -> dict[str, Any]:
    """This function creates a normalized side-effect descriptor object."""

    return {"effect_type": effect_type, "params": params}
