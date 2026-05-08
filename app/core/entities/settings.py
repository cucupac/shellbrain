"""Typed policy settings consumed by core use cases and policies."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Mapping

from app.core.entities.memory import MATURE_MEMORY_KIND_VALUES


SUPPORTED_READ_MODES = ("targeted", "ambient")


@dataclass(frozen=True)
class ReadPolicySettings:
    """Read-policy settings resolved by startup and passed into core."""

    default_mode: str
    include_global: bool
    limits_by_mode: Mapping[str, int]
    expand: Mapping[str, Any]
    quotas_by_mode: Mapping[str, Mapping[str, int]]
    retrieval: Mapping[str, float]

    def hydration_defaults(self) -> dict[str, Any]:
        return {
            "default_mode": self.default_mode,
            "include_global": self.include_global,
            "limits_by_mode": dict(self.limits_by_mode),
            "expand": deepcopy(dict(self.expand)),
        }

    def retrieval_defaults(self) -> dict[str, float]:
        return {key: float(value) for key, value in self.retrieval.items()}

    def resolve_mode(self, mode: str | None, *, field: str = "read.mode") -> str:
        resolved = self.default_mode if mode is None else mode
        if not isinstance(resolved, str) or resolved not in SUPPORTED_READ_MODES:
            raise ValueError(f"{field} must be one of: {', '.join(SUPPORTED_READ_MODES)}")
        return resolved

    def resolve_limit(self, *, mode: str, explicit_limit: int | None) -> int:
        if explicit_limit is not None:
            return int(explicit_limit)
        resolved_mode = self.resolve_mode(mode)
        return int(self.limits_by_mode[resolved_mode])

    def resolve_quotas(self, *, mode: str) -> dict[str, int]:
        resolved_mode = self.resolve_mode(mode)
        quotas = self.quotas_by_mode[resolved_mode]
        return {bucket: int(value) for bucket, value in quotas.items()}

    def resolve_payload_defaults(self, payload: dict[str, Any]) -> dict[str, Any]:
        resolved = dict(payload)
        resolved["mode"] = self.resolve_mode(resolved.get("mode"))
        if resolved.get("include_global") is None:
            resolved["include_global"] = self.include_global
        if resolved.get("limit") is None:
            resolved["limit"] = int(self.limits_by_mode[resolved["mode"]])
        if resolved.get("kinds") is None:
            resolved["kinds"] = list(MATURE_MEMORY_KIND_VALUES)

        incoming_expand = resolved.get("expand")
        merged_expand = deepcopy(dict(self.expand))
        if incoming_expand is None:
            resolved["expand"] = merged_expand
            return resolved
        if not isinstance(incoming_expand, dict):
            raise ValueError("read.expand must be a mapping")
        for key, value in incoming_expand.items():
            if value is not None:
                merged_expand[key] = value
        resolved["expand"] = merged_expand
        return resolved

    def to_dict(self) -> dict[str, Any]:
        return {
            "default_mode": self.default_mode,
            "include_global": self.include_global,
            "limits_by_mode": dict(self.limits_by_mode),
            "expand": deepcopy(dict(self.expand)),
            "quotas_by_mode": {
                mode: dict(quotas)
                for mode, quotas in self.quotas_by_mode.items()
            },
            "retrieval": dict(self.retrieval),
        }


@dataclass(frozen=True)
class CreatePolicySettings:
    """Create-policy validation and hydration settings."""

    gates: tuple[str, ...]
    defaults: Mapping[str, Any]

    def hydration_defaults(self) -> dict[str, Any]:
        return dict(self.defaults)

    def to_dict(self) -> dict[str, Any]:
        return {"gates": list(self.gates), "defaults": dict(self.defaults)}


@dataclass(frozen=True)
class UpdatePolicySettings:
    """Update-policy validation settings."""

    gates: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {"gates": list(self.gates)}


@dataclass(frozen=True)
class ThresholdSettings:
    """Retrieval score thresholds used by core read policy."""

    semantic_threshold: float
    keyword_threshold: float

    def to_dict(self) -> dict[str, float]:
        return {
            "semantic_threshold": float(self.semantic_threshold),
            "keyword_threshold": float(self.keyword_threshold),
        }


def default_read_policy_settings() -> ReadPolicySettings:
    """Return packaged read defaults for direct core callers and tests."""

    return ReadPolicySettings(
        default_mode="targeted",
        include_global=True,
        limits_by_mode={"targeted": 8, "ambient": 12},
        expand={
            "semantic_hops": 2,
            "include_problem_links": True,
            "include_fact_update_links": True,
            "include_association_links": True,
            "max_association_depth": 2,
            "min_association_strength": 0.25,
        },
        quotas_by_mode={
            "targeted": {"direct": 4, "explicit": 3, "implicit": 1},
            "ambient": {"direct": 4, "explicit": 5, "implicit": 3},
        },
        retrieval={"semantic_weight": 1.0, "keyword_weight": 1.0, "k_rrf": 20.0},
    )


def default_threshold_settings() -> ThresholdSettings:
    """Return packaged retrieval thresholds for direct core callers and tests."""

    return ThresholdSettings(semantic_threshold=0.25, keyword_threshold=0.0)
