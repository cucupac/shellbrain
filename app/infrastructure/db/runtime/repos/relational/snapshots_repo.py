"""Relational persistence for shadow snapshots and solution deltas."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import case, desc, or_, select

from app.core.entities.snapshots import (
    ShadowSnapshot,
    ShadowSnapshotReason,
    SolutionDelta,
)
from app.core.ports.db.snapshots import ISnapshotsRepo
from app.infrastructure.db.runtime.models.snapshots import (
    shadow_snapshots,
    solution_deltas,
)


class SnapshotsRepo(ISnapshotsRepo):
    """Persist code-evidence metadata in PostgreSQL."""

    def __init__(self, session) -> None:
        """Store the active SQLAlchemy session."""

        self._session = session

    def latest_snapshot(self, *, repo_id: str, repo_root: str) -> ShadowSnapshot | None:
        """Return the newest shadow snapshot for one repo root."""

        row = (
            self._session.execute(
                select(shadow_snapshots)
                .where(
                    shadow_snapshots.c.repo_id == repo_id,
                    shadow_snapshots.c.repo_root == repo_root,
                )
                .order_by(
                    desc(shadow_snapshots.c.created_at),
                    desc(shadow_snapshots.c.id),
                )
                .limit(1)
            )
            .mappings()
            .first()
        )
        return _snapshot_from_row(row) if row is not None else None

    def latest_snapshot_at_or_before_event(
        self,
        *,
        repo_id: str,
        repo_root: str,
        episode_id: str,
        event_seq: int,
    ) -> ShadowSnapshot | None:
        """Return the latest valid base snapshot for an episode event boundary."""

        seq_rank = case(
            (shadow_snapshots.c.captured_after_event_seq.is_(None), -1),
            else_=shadow_snapshots.c.captured_after_event_seq,
        )
        row = (
            self._session.execute(
                select(shadow_snapshots)
                .where(
                    shadow_snapshots.c.repo_id == repo_id,
                    shadow_snapshots.c.repo_root == repo_root,
                    or_(
                        shadow_snapshots.c.episode_id == episode_id,
                        shadow_snapshots.c.episode_id.is_(None),
                    ),
                    or_(
                        shadow_snapshots.c.captured_after_event_seq.is_(None),
                        shadow_snapshots.c.captured_after_event_seq <= event_seq,
                    ),
                )
                .order_by(desc(seq_rank), desc(shadow_snapshots.c.created_at))
                .limit(1)
            )
            .mappings()
            .first()
        )
        return _snapshot_from_row(row) if row is not None else None

    def latest_snapshot_in_event_window(
        self,
        *,
        repo_id: str,
        repo_root: str,
        episode_id: str,
        opened_event_seq: int,
        closed_event_seq: int,
    ) -> ShadowSnapshot | None:
        """Return the latest valid final snapshot captured in a scenario window."""

        row = (
            self._session.execute(
                select(shadow_snapshots)
                .where(
                    shadow_snapshots.c.repo_id == repo_id,
                    shadow_snapshots.c.repo_root == repo_root,
                    shadow_snapshots.c.episode_id == episode_id,
                    shadow_snapshots.c.reason != ShadowSnapshotReason.BASELINE_ONLY.value,
                    shadow_snapshots.c.captured_after_event_seq >= opened_event_seq,
                    shadow_snapshots.c.captured_after_event_seq <= closed_event_seq,
                )
                .order_by(
                    desc(shadow_snapshots.c.captured_after_event_seq),
                    desc(shadow_snapshots.c.created_at),
                )
                .limit(1)
            )
            .mappings()
            .first()
        )
        return _snapshot_from_row(row) if row is not None else None

    def get_solution_delta_for_problem_run(
        self, *, problem_run_id: str
    ) -> SolutionDelta | None:
        """Return an existing delta for one problem run."""

        row = (
            self._session.execute(
                select(solution_deltas).where(
                    solution_deltas.c.problem_run_id == problem_run_id
                )
            )
            .mappings()
            .first()
        )
        return _delta_from_row(row) if row is not None else None

    def add_snapshot(self, snapshot: ShadowSnapshot) -> None:
        """Persist one shadow snapshot metadata row."""

        self._session.execute(
            shadow_snapshots.insert().values(
                id=snapshot.id,
                repo_id=snapshot.repo_id,
                repo_root=snapshot.repo_root,
                episode_id=snapshot.episode_id,
                captured_after_event_seq=snapshot.captured_after_event_seq,
                operation_invocation_id=snapshot.operation_invocation_id,
                shadow_commit_sha=snapshot.shadow_commit_sha,
                parent_shadow_commit_sha=snapshot.parent_shadow_commit_sha,
                changed_paths_json=list(snapshot.changed_paths),
                reason=snapshot.reason.value,
                created_at=snapshot.created_at or datetime.now(timezone.utc),
            )
        )

    def add_solution_delta(self, delta: SolutionDelta) -> None:
        """Persist one solution delta metadata row."""

        self._session.execute(
            solution_deltas.insert().values(
                id=delta.id,
                problem_run_id=delta.problem_run_id,
                repo_id=delta.repo_id,
                repo_root=delta.repo_root,
                episode_id=delta.episode_id,
                base_snapshot_id=delta.base_snapshot_id,
                final_snapshot_id=delta.final_snapshot_id,
                patch_sha=delta.patch_sha,
                changed_paths_json=list(delta.changed_paths),
                created_at=delta.created_at or datetime.now(timezone.utc),
            )
        )


def _snapshot_from_row(row) -> ShadowSnapshot:
    """Map one relational row to a core snapshot entity."""

    return ShadowSnapshot(
        id=row["id"],
        repo_id=row["repo_id"],
        repo_root=row["repo_root"],
        episode_id=row["episode_id"],
        captured_after_event_seq=row["captured_after_event_seq"],
        operation_invocation_id=row["operation_invocation_id"],
        shadow_commit_sha=row["shadow_commit_sha"],
        parent_shadow_commit_sha=row["parent_shadow_commit_sha"],
        changed_paths=tuple(row["changed_paths_json"] or ()),
        reason=ShadowSnapshotReason(row["reason"]),
        created_at=row["created_at"],
    )


def _delta_from_row(row) -> SolutionDelta:
    """Map one relational row to a core solution delta entity."""

    return SolutionDelta(
        id=row["id"],
        problem_run_id=row["problem_run_id"],
        repo_id=row["repo_id"],
        repo_root=row["repo_root"],
        episode_id=row["episode_id"],
        base_snapshot_id=row["base_snapshot_id"],
        final_snapshot_id=row["final_snapshot_id"],
        patch_sha=row["patch_sha"],
        changed_paths=tuple(row["changed_paths_json"] or ()),
        created_at=row["created_at"],
    )
