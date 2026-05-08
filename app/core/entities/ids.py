"""Semantic identifiers and value aliases used across core contracts."""

from __future__ import annotations

from typing import NewType


MemoryId = NewType("MemoryId", str)
RepoId = NewType("RepoId", str)
EpisodeId = NewType("EpisodeId", str)
EvidenceRefText = NewType("EvidenceRefText", str)
EvidenceId = NewType("EvidenceId", str)
InvocationId = NewType("InvocationId", str)
AssociationEdgeId = NewType("AssociationEdgeId", str)

Confidence = NewType("Confidence", float)
Salience = NewType("Salience", float)
UtilityVote = NewType("UtilityVote", float)
