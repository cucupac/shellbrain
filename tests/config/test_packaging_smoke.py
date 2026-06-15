"""Clean-room packaging and install smoke coverage for the public CLI."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess

import psycopg
import pytest
from tests._shared.packaging_smoke_helpers import (
    create_isolated_install,
    create_temp_database,
    drop_temp_database,
    prepare_git_snapshot,
    replace_database_dsn,
    repo_root as resolve_repo_root,
)

CURRENT_ALEMBIC_HEAD = "20260606_0037"


def test_editable_install_should_expose_shellbrain_help_in_a_clean_room(
    tmp_path: Path,
) -> None:
    """editable installs should expose the shellbrain console script outside this repository."""

    repo_root = resolve_repo_root()
    external_repo = tmp_path / "external-editable-repo"
    external_repo.mkdir()
    python_executable, shellbrain_executable = create_isolated_install(
        tmp_path=tmp_path,
        name="editable-install",
        install_spec=str(repo_root),
        editable=True,
        install_runtime_deps=False,
    )

    completed = subprocess.run(
        [shellbrain_executable, "--help"],
        check=True,
        cwd=external_repo,
        text=True,
        capture_output=True,
        env=os.environ.copy(),
    )

    assert python_executable.exists()
    assert shellbrain_executable.exists()
    assert "shellbrain admin migrate" in completed.stdout
    assert "shellbrain upgrade" in completed.stdout
    assert "closed or idle-stable" in completed.stdout
    assert "Explicit teach agents run immediately" in completed.stdout


def test_git_file_install_should_expose_shellbrain_help_in_a_clean_room(
    tmp_path: Path,
) -> None:
    """git-url installs should expose the shellbrain console script outside this repository."""

    if shutil.which("git") is None:
        pytest.skip("git is required for git+file install smoke tests")

    repo_root = resolve_repo_root()
    git_snapshot = prepare_git_snapshot(tmp_path, repo_root)
    external_repo = tmp_path / "external-git-repo"
    external_repo.mkdir()
    _, shellbrain_executable = create_isolated_install(
        tmp_path=tmp_path,
        name="git-install",
        install_spec=f"git+file://{git_snapshot}",
        editable=False,
        install_runtime_deps=False,
    )

    completed = subprocess.run(
        [shellbrain_executable, "--help"],
        check=True,
        cwd=external_repo,
        text=True,
        capture_output=True,
        env=os.environ.copy(),
    )

    assert shellbrain_executable.exists()
    assert "Audience lanes" in completed.stdout
    assert "Working agents" in completed.stdout
    assert "Internal recall agents" in completed.stdout
    assert "shellbrain upgrade" in completed.stdout
    assert "read" in completed.stdout
    assert "events" in completed.stdout


def test_editable_install_should_package_onboarding_assets_in_a_clean_room(
    tmp_path: Path,
) -> None:
    """editable installs should expose packaged onboarding assets through importlib.resources."""

    repo_root = resolve_repo_root()
    external_repo = tmp_path / "external-assets-repo"
    external_repo.mkdir()
    python_executable, _ = create_isolated_install(
        tmp_path=tmp_path,
        name="assets-install",
        install_spec=str(repo_root),
        editable=True,
        install_runtime_deps=False,
    )

    completed = subprocess.run(
        [
            str(python_executable),
            "-c",
            (
                "from importlib import resources; "
                "root = resources.files('onboarding_assets'); "
                "print(root.joinpath('codex', 'shellbrain', 'agents', 'openai.yaml').read_text()); "
                "print(root.joinpath('codex', 'shellbrain', 'assets', 'shellbrain_logo.png').is_file()); "
                "print(root.joinpath('claude', 'skills', 'shellbrain', 'SKILL.md').read_text()); "
                "print(root.joinpath('codex', 'shellbrain-usage-review', 'agents', 'openai.yaml').read_text()); "
                "print(root.joinpath('codex', 'shellbrain-usage-review', 'assets', 'shellbrain_logo.png').is_file()); "
                "print(root.joinpath('claude', 'skills', 'shellbrain-usage-review', 'SKILL.md').read_text().splitlines()[0])"
            ),
        ],
        check=True,
        cwd=external_repo,
        text=True,
        capture_output=True,
        env=os.environ.copy(),
    )

    assert 'display_name: "Shellbrain"' in completed.stdout
    assert "True" in completed.stdout
    assert "# Shellbrain Recall Workflow" in completed.stdout
    assert 'display_name: "Shellbrain Usage Review"' in completed.stdout
    assert "# Shellbrain Usage Review" in completed.stdout


def test_git_file_install_should_package_onboarding_assets_in_a_clean_room(
    tmp_path: Path,
) -> None:
    """git-url installs should also carry the packaged onboarding assets."""

    if shutil.which("git") is None:
        pytest.skip("git is required for git+file install smoke tests")

    repo_root = resolve_repo_root()
    git_snapshot = prepare_git_snapshot(tmp_path, repo_root)
    external_repo = tmp_path / "external-assets-git-repo"
    external_repo.mkdir()
    python_executable, _ = create_isolated_install(
        tmp_path=tmp_path,
        name="assets-git-install",
        install_spec=f"git+file://{git_snapshot}",
        editable=False,
        install_runtime_deps=False,
    )

    completed = subprocess.run(
        [
            str(python_executable),
            "-c",
            (
                "from importlib import resources; "
                "root = resources.files('onboarding_assets'); "
                "print(root.joinpath('codex', 'shellbrain', 'agents', 'openai.yaml').read_text()); "
                "print(root.joinpath('codex', 'shellbrain', 'assets', 'shellbrain_logo.png').is_file()); "
                "print(root.joinpath('claude', 'skills', 'shellbrain', 'SKILL.md').read_text()); "
                "print(root.joinpath('codex', 'shellbrain-usage-review', 'agents', 'openai.yaml').read_text()); "
                "print(root.joinpath('codex', 'shellbrain-usage-review', 'assets', 'shellbrain_logo.png').is_file()); "
                "print(root.joinpath('claude', 'skills', 'shellbrain-usage-review', 'SKILL.md').read_text().splitlines()[0])"
            ),
        ],
        check=True,
        cwd=external_repo,
        text=True,
        capture_output=True,
        env=os.environ.copy(),
    )

    assert 'display_name: "Shellbrain"' in completed.stdout
    assert "True" in completed.stdout
    assert "# Shellbrain Recall Workflow" in completed.stdout
    assert 'display_name: "Shellbrain Usage Review"' in completed.stdout
    assert "# Shellbrain Usage Review" in completed.stdout


def test_git_file_install_should_package_internal_agent_settings(
    tmp_path: Path,
) -> None:
    """git-url installs should carry packaged internal-agent YAML defaults."""

    if shutil.which("git") is None:
        pytest.skip("git is required for git+file install smoke tests")

    repo_root = resolve_repo_root()
    git_snapshot = prepare_git_snapshot(tmp_path, repo_root)
    external_repo = tmp_path / "external-internal-agent-settings-repo"
    external_repo.mkdir()
    python_executable, _ = create_isolated_install(
        tmp_path=tmp_path,
        name="internal-agent-settings-git-install",
        install_spec=f"git+file://{git_snapshot}",
        editable=False,
        install_runtime_deps=False,
    )

    completed = subprocess.run(
        [
            str(python_executable),
            "-c",
            (
                "from importlib import resources; "
                    "settings = resources.files('app').joinpath('settings', 'internal-agents', 'defaults.yaml').read_text(); "
                "print(settings)"
            ),
        ],
        check=True,
        cwd=external_repo,
        text=True,
        capture_output=True,
        env=os.environ.copy(),
    )

    assert "build_context:" in completed.stdout
    assert "model: gpt-5.4-mini" in completed.stdout
    assert "build_knowledge:\n  provider: codex\n  model: gpt-5.4-mini\n  reasoning: xhigh" in completed.stdout
    assert "reasoning: medium" in completed.stdout


def test_admin_migrate_should_initialize_schema_from_an_installed_package(
    tmp_path: Path,
) -> None:
    """installed-package admin migrate should initialize an empty database from packaged artifacts."""

    base_dsn = os.getenv("SHELLBRAIN_DB_DSN_TEST")
    admin_base_dsn = os.getenv("SHELLBRAIN_DB_ADMIN_DSN_TEST", base_dsn or "")
    if not base_dsn or not admin_base_dsn:
        pytest.skip(
            "Set SHELLBRAIN_DB_DSN_TEST to run packaging migration smoke tests."
        )

    repo_root = resolve_repo_root()
    external_repo = tmp_path / "external-migrate-repo"
    external_repo.mkdir()
    _, shellbrain_executable = create_isolated_install(
        tmp_path=tmp_path,
        name="migrate-install",
        install_spec=str(repo_root),
        editable=True,
        install_runtime_deps=True,
    )

    package_dsn, admin_dsn, db_name = create_temp_database(base_dsn, admin_base_dsn)
    package_admin_dsn = replace_database_dsn(admin_base_dsn, db_name)
    try:
        completed = subprocess.run(
            [shellbrain_executable, "admin", "migrate"],
            check=True,
            cwd=external_repo,
            text=True,
            capture_output=True,
            env={
                **os.environ,
                "SHELLBRAIN_DB_DSN": package_dsn,
                "SHELLBRAIN_DB_ADMIN_DSN": package_admin_dsn,
                "SHELLBRAIN_INSTANCE_MODE": "test",
            },
        )

        with psycopg.connect(package_dsn.replace("+psycopg", "")) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT to_regclass('public.memories');")
                memories_table = cur.fetchone()[0]
                cur.execute("SELECT to_regclass('public.episode_events');")
                episode_events_table = cur.fetchone()[0]
                cur.execute("SELECT to_regclass('public.concepts');")
                concepts_table = cur.fetchone()[0]
                cur.execute("SELECT version_num FROM alembic_version;")
                alembic_version = cur.fetchone()[0]
                cur.execute(
                    """
                    SELECT conname
                      FROM pg_constraint
                     WHERE conrelid = 'knowledge_build_runs'::regclass
                       AND conname IN (
                         'ck_knowledge_build_runs_trigger',
                         'knowledge_build_runs_trigger_check'
                       );
                    """
                )
                knowledge_build_trigger_constraints = {row[0] for row in cur}
                cur.execute(
                    """
                    INSERT INTO episodes (
                      id, repo_id, thread_id, status, host_app
                    )
                    VALUES (
                      'packaging-trigger-episode',
                      'example/repo',
                      'packaging-trigger-thread',
                      'active',
                      'codex'
                    );
                    """
                )
                for trigger in ("watermark_stable", "explicit_teach"):
                    cur.execute(
                        """
                        INSERT INTO knowledge_build_runs (
                          id,
                          repo_id,
                          episode_id,
                          trigger,
                          status,
                          event_watermark,
                          provider,
                          model,
                          reasoning,
                          started_at
                        )
                        VALUES (
                          %s,
                          'example/repo',
                          'packaging-trigger-episode',
                          %s,
                          'ok',
                          1,
                          'codex',
                          'gpt-5.4-mini',
                          'medium',
                          NOW()
                        );
                        """,
                        (f"packaging-trigger-{trigger}", trigger),
                    )

        assert memories_table is not None
        assert episode_events_table is not None
        assert concepts_table is not None
        assert alembic_version == CURRENT_ALEMBIC_HEAD
        assert knowledge_build_trigger_constraints == {"ck_knowledge_build_runs_trigger"}
        assert "Applied shellbrain schema migrations to head." in completed.stdout
    finally:
        drop_temp_database(admin_dsn, db_name)


def test_admin_migrate_should_preserve_data_and_retire_frontier_and_memory_anchors(
    tmp_path: Path,
) -> None:
    """installed-package admin migrate should preserve durable data while retiring deprecated ontology terms."""

    base_dsn = os.getenv("SHELLBRAIN_DB_DSN_TEST")
    admin_base_dsn = os.getenv("SHELLBRAIN_DB_ADMIN_DSN_TEST", base_dsn or "")
    if not base_dsn or not admin_base_dsn:
        pytest.skip(
            "Set SHELLBRAIN_DB_DSN_TEST to run packaging migration smoke tests."
        )

    repo_root = resolve_repo_root()
    external_repo = tmp_path / "external-frontier-migrate-repo"
    external_repo.mkdir()
    python_executable, shellbrain_executable = create_isolated_install(
        tmp_path=tmp_path,
        name="frontier-migrate-install",
        install_spec=str(repo_root),
        editable=True,
        install_runtime_deps=True,
    )

    package_dsn, admin_dsn, db_name = create_temp_database(base_dsn, admin_base_dsn)
    package_admin_dsn = replace_database_dsn(admin_base_dsn, db_name)
    shellbrain_home = tmp_path / ".shellbrain-home-frontier-migrate"
    command_env = {
        **os.environ,
        "SHELLBRAIN_DB_DSN": package_dsn,
        "SHELLBRAIN_DB_ADMIN_DSN": package_admin_dsn,
        "SHELLBRAIN_INSTANCE_MODE": "test",
        "SHELLBRAIN_HOME": str(shellbrain_home),
    }
    raw_package_dsn = package_dsn.replace("+psycopg", "")

    try:
        subprocess.run(
            [
                str(python_executable),
                "-c",
                "from app.startup.migrations import upgrade_database; upgrade_database('20260520_0028')",
            ],
            check=True,
            cwd=external_repo,
            text=True,
            capture_output=True,
            env=command_env,
        )

        with psycopg.connect(raw_package_dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT version_num FROM alembic_version;")
                assert cur.fetchone()[0] == "20260520_0028"
                cur.execute(
                    """
                    INSERT INTO memories (id, repo_id, scope, kind, text)
                    VALUES
                      ('pre0009-problem', 'example/repo', 'repo', 'problem', 'pre-frontier problem'),
                      ('pre0009-fact', 'example/repo', 'repo', 'fact', 'pre-frontier fact'),
                      ('frontier-before-cleanup', 'example/repo', 'repo', 'frontier', 'frontier should be retired'),
                      ('mature-after-upgrade', 'example/repo', 'repo', 'fact', 'mature target'),
                      ('solution-anchor-memory', 'example/repo', 'repo', 'solution', 'solution linked through memory anchor'),
                      ('failed-tactic-before-structural', 'example/repo', 'repo', 'failed_tactic', 'failed tactic before structural cleanup'),
                      ('change-before-structural', 'example/repo', 'repo', 'change', 'change before structural cleanup'),
                      ('new-fact-before-structural', 'example/repo', 'repo', 'fact', 'new fact before structural cleanup')
                    """
                )
                cur.execute(
                    """
                    INSERT INTO problem_attempts (problem_id, attempt_id, role, created_at)
                    VALUES
                      ('pre0009-problem', 'solution-anchor-memory', 'solution', NOW()),
                      ('pre0009-problem', 'failed-tactic-before-structural', 'failed_tactic', NOW())
                    """
                )
                cur.execute(
                    """
                    INSERT INTO fact_updates (
                      id, old_fact_id, change_id, new_fact_id, created_at
                    )
                    VALUES (
                      'fact-update-before-structural',
                      'pre0009-fact',
                      'change-before-structural',
                      'new-fact-before-structural',
                      NOW()
                    )
                    """
                )
                cur.execute(
                    """
                    INSERT INTO association_edges (id, repo_id, from_memory_id, to_memory_id, relation_type)
                    VALUES ('pre0009-edge', 'example/repo', 'pre0009-problem', 'pre0009-fact', 'depends_on')
                    """
                )
                cur.execute(
                    """
                    INSERT INTO episodes (id, repo_id, thread_id, host_app, status)
                    VALUES (
                      'legacy-evidence-episode',
                      'example/repo',
                      'thread-legacy-evidence',
                      'codex',
                      'active'
                    )
                    """
                )
                cur.execute(
                    """
                    INSERT INTO episode_events (
                      id, episode_id, seq, host_event_key, source, content
                    )
                    VALUES (
                      'legacy-evidence-event',
                      'legacy-evidence-episode',
                      1,
                      'legacy-evidence-event',
                      'user',
                      '{"content_text":"legacy evidence"}'
                    )
                    """
                )
                cur.execute(
                    """
                    INSERT INTO evidence_refs (id, repo_id, ref, episode_event_id)
                    VALUES (
                      'legacy-evidence-ref',
                      'example/repo',
                      'legacy-evidence-event',
                      'legacy-evidence-event'
                    )
                    """
                )
                cur.execute(
                    """
                    INSERT INTO memory_evidence (memory_id, evidence_id)
                    VALUES ('pre0009-problem', 'legacy-evidence-ref')
                    """
                )
                cur.execute(
                    """
                    INSERT INTO association_edge_evidence (edge_id, evidence_id)
                    VALUES ('pre0009-edge', 'legacy-evidence-ref')
                    """
                )
                cur.execute(
                    """
                    INSERT INTO utility_observations (
                      id, memory_id, problem_id, vote, rationale, created_at
                    )
                    VALUES (
                      'legacy-utility-observation',
                      'pre0009-fact',
                      'pre0009-problem',
                      1.0,
                      'Legacy utility evidence.',
                      NOW()
                    )
                    """
                )
                cur.execute(
                    """
                    INSERT INTO utility_observation_evidence (observation_id, evidence_id)
                    VALUES ('legacy-utility-observation', 'legacy-evidence-ref')
                    """
                )
                cur.execute(
                    """
                    INSERT INTO fact_update_evidence (fact_update_id, evidence_id)
                    VALUES ('fact-update-before-structural', 'legacy-evidence-ref')
                    """
                )
                cur.execute(
                    """
                    INSERT INTO association_edges (id, repo_id, from_memory_id, to_memory_id, relation_type)
                    VALUES ('matures-into-edge', 'example/repo', 'frontier-before-cleanup', 'mature-after-upgrade', 'matures_into')
                    """
                )
                cur.execute(
                    """
                    INSERT INTO association_observations (
                      id, repo_id, edge_id, from_memory_id, to_memory_id, relation_type, source, valence
                    )
                    VALUES (
                      'matures-into-observation',
                      'example/repo',
                      'matures-into-edge',
                      'frontier-before-cleanup',
                      'mature-after-upgrade',
                      'matures_into',
                      'agent_explicit',
                      1.0
                    )
                    """
                )
                cur.execute(
                    """
                    INSERT INTO concepts (id, repo_id, slug, name, kind)
                    VALUES ('concept-memory-anchor', 'example/repo', 'memory-anchor-concept', 'Memory Anchor Concept', 'domain')
                    """
                )
                cur.execute(
                    """
                    INSERT INTO anchors (id, repo_id, kind, locator_json, canonical_locator_hash)
                    VALUES
                      ('memory-anchor-solution', 'example/repo', 'memory', '{"memory_id":"solution-anchor-memory"}'::jsonb, 'hash-memory-anchor-solution'),
                      ('file-anchor-stays', 'example/repo', 'file', '{"path":"app/refunds.py"}'::jsonb, 'hash-file-anchor-stays')
                    """
                )
                cur.execute(
                    """
                    INSERT INTO concept_groundings (
                      id, repo_id, concept_id, role, anchor_id, confidence, source_kind, source_ref, created_by
                    )
                    VALUES
                      ('memory-anchor-grounding', 'example/repo', 'concept-memory-anchor', 'implementation', 'memory-anchor-solution', 0.8, 'manual', 'seed', 'manual'),
                      ('file-anchor-grounding', 'example/repo', 'concept-memory-anchor', 'implementation', 'file-anchor-stays', 0.7, 'manual', 'seed', 'manual')
                    """
                )
                cur.execute(
                    """
                    INSERT INTO concept_evidence (
                      id, repo_id, target_type, target_id, evidence_kind, anchor_id
                    )
                    VALUES (
                      'memory-anchor-evidence',
                      'example/repo',
                      'grounding',
                      'memory-anchor-grounding',
                      'anchor',
                      'memory-anchor-solution'
                    )
                    """
                )
                cur.execute(
                    """
                    INSERT INTO concept_memory_links (
                      id, repo_id, concept_id, role, memory_id, status, confidence,
                      source_kind, source_ref, created_by
                    )
                    VALUES
                      (
                        'legacy-role-warned',
                        'example/repo',
                        'concept-memory-anchor',
                        'warned_about',
                        'pre0009-problem',
                        'active',
                        0.41,
                        'manual',
                        'legacy-role-seed',
                        'manual'
                      ),
                      (
                        'legacy-role-changed',
                        'example/repo',
                        'concept-memory-anchor',
                        'changed',
                        'pre0009-fact',
                        'active',
                        0.42,
                        'manual',
                        'legacy-role-seed',
                        'manual'
                      ),
                      (
                        'legacy-role-validated',
                        'example/repo',
                        'concept-memory-anchor',
                        'validated',
                        'mature-after-upgrade',
                        'active',
                        0.43,
                        'manual',
                        'legacy-role-seed',
                        'manual'
                      ),
                      (
                        'legacy-role-contradicted',
                        'example/repo',
                        'concept-memory-anchor',
                        'contradicted',
                        'solution-anchor-memory',
                        'active',
                        0.44,
                        'manual',
                        'legacy-role-seed',
                        'manual'
                      )
                    """
                )

        completed = subprocess.run(
            [shellbrain_executable, "admin", "migrate"],
            check=True,
            cwd=external_repo,
            text=True,
            capture_output=True,
            env=command_env,
        )

        with psycopg.connect(raw_package_dsn, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT version_num FROM alembic_version;")
                assert cur.fetchone()[0] == CURRENT_ALEMBIC_HEAD
                cur.execute("SELECT to_regclass('public.concept_lifecycle_events');")
                assert cur.fetchone()[0] == "concept_lifecycle_events"
                cur.execute("SELECT to_regclass('public.memory_lifecycle_events');")
                assert cur.fetchone()[0] == "memory_lifecycle_events"
                cur.execute(
                    "SELECT to_regclass('public.structural_memory_relations');"
                )
                assert cur.fetchone()[0] == "structural_memory_relations"
                for retired_table in (
                    "memory_evidence",
                    "fact_update_evidence",
                    "association_edge_evidence",
                    "utility_observation_evidence",
                    "concept_evidence",
                    "problem_attempts",
                    "fact_updates",
                ):
                    cur.execute(f"SELECT to_regclass('public.{retired_table}');")
                    assert cur.fetchone()[0] is None

                cur.execute(
                    """
                    INSERT INTO concept_claims (
                      id, repo_id, concept_id, claim_type, text, normalized_text,
                      status, invalidated_at, updated_by
                    )
                    VALUES (
                      'archived-claim-after-cleanup',
                      'example/repo',
                      'concept-memory-anchor',
                      'definition',
                      'Archived claims are allowed after lifecycle migration.',
                      'archived claims are allowed after lifecycle migration.',
                      'archived',
                      NOW(),
                      'manual'
                    )
                    """
                )
                cur.execute(
                    """
                    INSERT INTO concept_lifecycle_events (
                      id, repo_id, target_type, target_id, from_status, to_status,
                      rationale, actor
                    )
                    VALUES (
                      'claim-lifecycle-event-after-cleanup',
                      'example/repo',
                      'claim',
                      'archived-claim-after-cleanup',
                      'active',
                      'archived',
                      'Packaging smoke validates lifecycle event schema.',
                      'manual'
                    )
                    """
                )
                cur.execute(
                    """
                    INSERT INTO evidence_refs (
                      id, repo_id, kind, ref, canonical_hash, note
                    )
                    VALUES (
                      'claim-lifecycle-event-evidence-after-cleanup',
                      'example/repo',
                      'manual',
                      'Packaging smoke concept lifecycle evidence.',
                      'packaging-smoke-concept-lifecycle-evidence',
                      'Lifecycle event evidence remains accepted.'
                    )
                    """
                )
                cur.execute(
                    """
                    INSERT INTO evidence_links (
                      id, repo_id, target_type, target_id, evidence_id, evidence_role
                    )
                    VALUES (
                      'claim-lifecycle-event-evidence-link-after-cleanup',
                      'example/repo',
                      'concept_lifecycle_event',
                      'claim-lifecycle-event-after-cleanup',
                      'claim-lifecycle-event-evidence-after-cleanup',
                      'supports'
                    )
                    """
                )
                cur.execute(
                    """
                    INSERT INTO memory_lifecycle_events (
                      id, repo_id, memory_id, from_status, to_status,
                      rationale, actor
                    )
                    VALUES (
                      'memory-lifecycle-event-after-cleanup',
                      'example/repo',
                      'pre0009-fact',
                      'active',
                      'maybe_stale',
                      'Packaging smoke validates memory lifecycle event schema.',
                      'manual'
                    )
                    """
                )
                cur.execute(
                    """
                    INSERT INTO evidence_refs (
                      id, repo_id, kind, ref, canonical_hash, note
                    )
                    VALUES (
                      'memory-lifecycle-event-evidence-after-cleanup',
                      'example/repo',
                      'manual',
                      'Packaging smoke memory lifecycle evidence.',
                      'packaging-smoke-memory-lifecycle-evidence',
                      'Memory lifecycle event evidence target remains accepted.'
                    )
                    """
                )
                cur.execute(
                    """
                    INSERT INTO evidence_links (
                      id, repo_id, target_type, target_id, evidence_id, evidence_role
                    )
                    VALUES (
                      'memory-lifecycle-event-evidence-link-after-cleanup',
                      'example/repo',
                      'memory_lifecycle_event',
                      'memory-lifecycle-event-after-cleanup',
                      'memory-lifecycle-event-evidence-after-cleanup',
                      'supports'
                    )
                    """
                )

                cur.execute(
                    "SELECT kind, text, status FROM memories WHERE id = 'pre0009-problem';"
                )
                assert cur.fetchone() == (
                    "problem",
                    "pre-frontier problem",
                    "active",
                )

                cur.execute(
                    "SELECT kind, text, status FROM memories WHERE id = 'pre0009-fact';"
                )
                assert cur.fetchone() == ("fact", "pre-frontier fact", "active")

                cur.execute(
                    "SELECT kind, text, status FROM memories WHERE id = 'solution-anchor-memory';"
                )
                assert cur.fetchone() == (
                    "solution",
                    "solution linked through memory anchor",
                    "active",
                )

                cur.execute(
                    "SELECT relation_type FROM association_edges WHERE id = 'pre0009-edge';"
                )
                assert cur.fetchone() == ("depends_on",)

                cur.execute(
                    "SELECT id FROM memories WHERE id = 'frontier-before-cleanup';"
                )
                assert cur.fetchone() is None

                cur.execute(
                    "SELECT id FROM association_edges WHERE id = 'matures-into-edge';"
                )
                assert cur.fetchone() is None

                cur.execute(
                    """
                    SELECT er.kind, el.target_type, el.target_id, el.evidence_role
                    FROM evidence_links el
                    JOIN evidence_refs er ON er.id = el.evidence_id
                    WHERE el.repo_id = 'example/repo'
                      AND el.evidence_id = 'legacy-evidence-ref'
                      AND el.target_type = 'memory';
                    """
                )
                assert cur.fetchone() == (
                    "episode_event",
                    "memory",
                    "pre0009-problem",
                    "supports",
                )
                cur.execute(
                    """
                    SELECT target_type, target_id, evidence_role
                    FROM evidence_links
                    WHERE repo_id = 'example/repo'
                      AND evidence_id = 'legacy-evidence-ref'
                      AND target_type IN ('association_edge', 'utility_observation')
                    ORDER BY target_type, target_id;
                    """
                )
                assert cur.fetchall() == [
                    ("association_edge", "pre0009-edge", "supports"),
                    (
                        "utility_observation",
                        "legacy-utility-observation",
                        "supports",
                    ),
                ]

                cur.execute(
                    """
                    SELECT subject_memory_id, predicate, object_memory_id
                    FROM structural_memory_relations
                    ORDER BY subject_memory_id, predicate, object_memory_id;
                    """
                )
                assert cur.fetchall() == [
                    (
                        "new-fact-before-structural",
                        "explained_by_change",
                        "change-before-structural",
                    ),
                    ("pre0009-fact", "explained_by_change", "change-before-structural"),
                    ("pre0009-fact", "superseded_by", "new-fact-before-structural"),
                    (
                        "pre0009-problem",
                        "failed_with",
                        "failed-tactic-before-structural",
                    ),
                    ("pre0009-problem", "solved_by", "solution-anchor-memory"),
                ]

                cur.execute(
                    """
                    SELECT count(*)
                    FROM evidence_links
                    WHERE target_type = 'structural_memory_relation'
                      AND evidence_id = 'legacy-evidence-ref';
                    """
                )
                assert cur.fetchone() == (3,)

                cur.execute(
                    "SELECT id FROM association_observations WHERE id = 'matures-into-observation';"
                )
                assert cur.fetchone() is None

                cur.execute("SELECT kind FROM anchors WHERE id = 'file-anchor-stays';")
                assert cur.fetchone() == ("file",)

                cur.execute(
                    "SELECT id FROM anchors WHERE id = 'memory-anchor-solution';"
                )
                assert cur.fetchone() is None

                cur.execute(
                    "SELECT id FROM concept_groundings WHERE id = 'memory-anchor-grounding';"
                )
                assert cur.fetchone() is None

                cur.execute(
                    """
                    SELECT role, memory_id, confidence, source_kind, source_ref, created_by
                    FROM concept_memory_links
                    WHERE concept_id = 'concept-memory-anchor'
                      AND memory_id = 'solution-anchor-memory';
                    """
                )
                assert cur.fetchone() == (
                    "solution_for",
                    "solution-anchor-memory",
                    0.8,
                    "manual",
                    "seed",
                    "manual",
                )

                cur.execute(
                    """
                    SELECT er.kind, er.memory_id, el.target_type, el.evidence_role
                    FROM evidence_links el
                    JOIN evidence_refs er ON er.id = el.evidence_id
                    WHERE el.repo_id = 'example/repo'
                      AND el.target_type = 'concept_memory_link'
                      AND el.target_id IN (
                        SELECT id
                        FROM concept_memory_links
                        WHERE concept_id = 'concept-memory-anchor'
                          AND memory_id = 'solution-anchor-memory'
                      );
                    """
                )
                assert cur.fetchone() == (
                    "memory",
                    "solution-anchor-memory",
                    "concept_memory_link",
                    "supports",
                )

                cur.execute(
                    """
                    SELECT id, role, memory_id, confidence, source_kind, source_ref, created_by
                    FROM concept_memory_links
                    WHERE id LIKE 'legacy-role-%'
                    ORDER BY id;
                    """
                )
                assert cur.fetchall() == [
                    (
                        "legacy-role-changed",
                        "change_relevant_to",
                        "pre0009-fact",
                        0.42,
                        "manual",
                        "legacy-role-seed",
                        "manual",
                    ),
                    (
                        "legacy-role-contradicted",
                        "warns_about",
                        "solution-anchor-memory",
                        0.44,
                        "manual",
                        "legacy-role-seed",
                        "manual",
                    ),
                    (
                        "legacy-role-validated",
                        "example_of",
                        "mature-after-upgrade",
                        0.43,
                        "manual",
                        "legacy-role-seed",
                        "manual",
                    ),
                    (
                        "legacy-role-warned",
                        "warns_about",
                        "pre0009-problem",
                        0.41,
                        "manual",
                        "legacy-role-seed",
                        "manual",
                    ),
                ]

                cur.execute(
                    """
                    SELECT count(*)
                    FROM concept_memory_links
                    WHERE role IN ('changed', 'validated', 'contradicted', 'warned_about');
                    """
                )
                assert cur.fetchone() == (0,)

                with pytest.raises(psycopg.Error):
                    cur.execute(
                        """
                        INSERT INTO concept_memory_links (
                          id, repo_id, concept_id, role, memory_id
                        )
                        VALUES (
                          'legacy-role-after-cleanup',
                          'example/repo',
                          'concept-memory-anchor',
                          'validated',
                          'pre0009-problem'
                        )
                        """
                    )

                with pytest.raises(psycopg.Error):
                    cur.execute(
                        """
                        INSERT INTO memories (id, repo_id, scope, kind, text, status)
                        VALUES ('frontier-after-cleanup', 'example/repo', 'repo', 'frontier', 'frontier no longer allowed', 'active')
                        """
                    )
                conn.rollback()
                with pytest.raises(psycopg.Error):
                    cur.execute(
                        """
                        INSERT INTO association_edges (id, repo_id, from_memory_id, to_memory_id, relation_type)
                        VALUES ('matures-after-cleanup', 'example/repo', 'pre0009-problem', 'pre0009-fact', 'matures_into')
                        """
                    )
                conn.rollback()
                with pytest.raises(psycopg.Error):
                    cur.execute(
                        """
                        INSERT INTO structural_memory_relations (
                          id, repo_id, subject_memory_id, predicate, object_memory_id
                        )
                        VALUES (
                          'depends-on-structural-after-cleanup',
                          'example/repo',
                          'pre0009-problem',
                          'depends_on',
                          'solution-anchor-memory'
                        )
                        """
                    )
                conn.rollback()
                with pytest.raises(psycopg.Error):
                    cur.execute(
                        """
                        INSERT INTO anchors (id, repo_id, kind, locator_json, canonical_locator_hash)
                        VALUES ('memory-anchor-after-cleanup', 'example/repo', 'memory', '{"memory_id":"pre0009-fact"}'::jsonb, 'hash-memory-anchor-after-cleanup')
                        """
                    )
                conn.rollback()

        assert "Applied shellbrain schema migrations to head." in completed.stdout
    finally:
        drop_temp_database(admin_dsn, db_name)


def test_admin_migrate_should_abort_on_unconvertible_memory_anchor(
    tmp_path: Path,
) -> None:
    """installed-package admin migrate should fail before cleanup when a memory anchor cannot be converted."""

    base_dsn = os.getenv("SHELLBRAIN_DB_DSN_TEST")
    admin_base_dsn = os.getenv("SHELLBRAIN_DB_ADMIN_DSN_TEST", base_dsn or "")
    if not base_dsn or not admin_base_dsn:
        pytest.skip(
            "Set SHELLBRAIN_DB_DSN_TEST to run packaging migration smoke tests."
        )

    repo_root = resolve_repo_root()
    external_repo = tmp_path / "external-invalid-memory-anchor-repo"
    external_repo.mkdir()
    python_executable, shellbrain_executable = create_isolated_install(
        tmp_path=tmp_path,
        name="invalid-memory-anchor-install",
        install_spec=str(repo_root),
        editable=True,
        install_runtime_deps=True,
    )

    package_dsn, admin_dsn, db_name = create_temp_database(base_dsn, admin_base_dsn)
    package_admin_dsn = replace_database_dsn(admin_base_dsn, db_name)
    shellbrain_home = tmp_path / ".shellbrain-home-invalid-memory-anchor"
    command_env = {
        **os.environ,
        "SHELLBRAIN_DB_DSN": package_dsn,
        "SHELLBRAIN_DB_ADMIN_DSN": package_admin_dsn,
        "SHELLBRAIN_INSTANCE_MODE": "test",
        "SHELLBRAIN_HOME": str(shellbrain_home),
    }
    raw_package_dsn = package_dsn.replace("+psycopg", "")

    try:
        subprocess.run(
            [
                str(python_executable),
                "-c",
                "from app.startup.migrations import upgrade_database; upgrade_database('20260520_0028')",
            ],
            check=True,
            cwd=external_repo,
            text=True,
            capture_output=True,
            env=command_env,
        )

        with psycopg.connect(raw_package_dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO memories (id, repo_id, scope, kind, text)
                    VALUES ('normal-memory', 'example/repo', 'repo', 'fact', 'normal fact')
                    """
                )
                cur.execute(
                    """
                    INSERT INTO anchors (id, repo_id, kind, locator_json, canonical_locator_hash)
                    VALUES ('invalid-memory-anchor', 'example/repo', 'memory', '{}'::jsonb, 'hash-invalid-memory-anchor')
                    """
                )

        completed = subprocess.run(
            [shellbrain_executable, "admin", "migrate"],
            check=False,
            cwd=external_repo,
            text=True,
            capture_output=True,
            env=command_env,
        )

        assert completed.returncode != 0
        assert (
            "Cannot convert memory anchors with missing locator_json.memory_id"
            in completed.stderr
        )

        with psycopg.connect(raw_package_dsn, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT version_num FROM alembic_version;")
                assert cur.fetchone()[0] == "20260520_0028"
                cur.execute("SELECT kind FROM memories WHERE id = 'normal-memory';")
                assert cur.fetchone() == ("fact",)
    finally:
        drop_temp_database(admin_dsn, db_name)
