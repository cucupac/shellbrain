"""This module defines relational repository operations for association structures."""

from datetime import datetime, timezone

from sqlalchemy import case, select, update

from app.core.entities.associations import (
    AssociationEdge,
    AssociationObservation,
    AssociationSourceMode,
    AssociationState,
)
from app.core.ports.memory_repositories import IAssociationsRepo
from app.infrastructure.db.models.associations import (
    association_edges,
    association_observations,
)


class AssociationsRepo(IAssociationsRepo):
    """This class provides persistence operations for association edges and observations."""

    def __init__(self, session) -> None:
        """This method stores the active DB session for repository operations."""

        self._session = session

    def upsert_edge(self, edge: AssociationEdge) -> AssociationEdge:
        """This method inserts or updates an association edge and returns the stored edge."""

        existing = (
            self._session.execute(
                select(association_edges).where(
                    association_edges.c.repo_id == edge.repo_id,
                    association_edges.c.from_memory_id == edge.from_memory_id,
                    association_edges.c.to_memory_id == edge.to_memory_id,
                    association_edges.c.relation_type == edge.relation_type.value,
                )
            )
            .mappings()
            .first()
        )

        now = datetime.now(timezone.utc)
        if existing is None:
            self._session.execute(
                association_edges.insert().values(
                    id=edge.id,
                    repo_id=edge.repo_id,
                    from_memory_id=edge.from_memory_id,
                    to_memory_id=edge.to_memory_id,
                    relation_type=edge.relation_type.value,
                    source_mode=edge.source_mode.value,
                    state=edge.state.value,
                    strength=edge.strength,
                    obs_count=0,
                    positive_obs=0,
                    negative_obs=0,
                    salience_sum=0.0,
                    created_at=now,
                    updated_at=now,
                )
            )
            return edge

        source_mode = existing["source_mode"]
        if source_mode != edge.source_mode.value and source_mode != "mixed":
            source_mode = "mixed"
        strength = max(float(existing["strength"]), edge.strength)
        self._session.execute(
            update(association_edges)
            .where(association_edges.c.id == existing["id"])
            .values(
                source_mode=source_mode,
                state=edge.state.value,
                strength=strength,
                updated_at=now,
            )
        )
        return AssociationEdge(
            id=existing["id"],
            repo_id=edge.repo_id,
            from_memory_id=edge.from_memory_id,
            to_memory_id=edge.to_memory_id,
            relation_type=edge.relation_type,
            source_mode=AssociationSourceMode(source_mode),
            state=AssociationState(edge.state.value),
            strength=strength,
        )

    def append_observation(self, observation: AssociationObservation) -> None:
        """This method appends an immutable association observation row."""

        now = datetime.now(timezone.utc)
        self._session.execute(
            association_observations.insert().values(
                id=observation.id,
                repo_id=observation.repo_id,
                edge_id=observation.edge_id,
                from_memory_id=observation.from_memory_id,
                to_memory_id=observation.to_memory_id,
                relation_type=observation.relation_type.value,
                source=observation.source,
                problem_id=observation.problem_id,
                episode_id=observation.episode_id,
                valence=observation.valence,
                salience=observation.salience,
                created_at=now,
            )
        )
        if observation.edge_id:
            self._session.execute(
                update(association_edges)
                .where(association_edges.c.id == observation.edge_id)
                .values(
                    obs_count=association_edges.c.obs_count + 1,
                    positive_obs=association_edges.c.positive_obs
                    + case((observation.valence > 0, 1), else_=0),
                    negative_obs=association_edges.c.negative_obs
                    + case((observation.valence < 0, 1), else_=0),
                    salience_sum=association_edges.c.salience_sum
                    + observation.salience,
                    last_reinforced_at=now,
                    updated_at=now,
                )
            )
