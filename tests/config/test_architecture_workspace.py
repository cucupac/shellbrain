"""Workspace-level architecture guardrails."""

from __future__ import annotations

import stat
from pathlib import Path

from tests._shared.architecture import (
    EffectImportRule,
    direct_package_dirs,
    effect_import_violations,
    forbidden_import_violations,
    iter_import_references,
    module_matches_prefix,
    production_python_files,
    pyproject_dependency_names,
    pyproject_package_roots,
    python_files,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
APP_ROOT = REPO_ROOT / "app"
PYPROJECT = REPO_ROOT / "pyproject.toml"

ARCHITECTURE_CONTRACTS = {
    "app": ("tests/config/test_architecture_boundaries.py",),
    "app.core": ("tests/config/test_architecture_boundaries.py",),
    "app.entrypoints": ("tests/config/test_architecture_boundaries.py",),
    "app.infrastructure": ("tests/config/test_architecture_boundaries.py",),
    "app.settings": ("tests/config/test_architecture_boundaries.py",),
    "app.startup": ("tests/config/test_architecture_boundaries.py",),
    "migrations": ("tests/config/test_architecture_workspace.py",),
    "onboarding_assets": ("tests/config/test_architecture_workspace.py",),
}

EFFECT_IMPORT_RULES = (
    EffectImportRule(
        name="database and migration",
        forbidden_prefixes=("alembic", "pgvector", "psycopg", "sqlalchemy"),
        allowed_module_prefixes=("app.infrastructure.db", "migrations"),
    ),
    EffectImportRule(
        name="subprocess",
        forbidden_prefixes=("subprocess",),
        allowed_module_prefixes=(
            "app.infrastructure.db.admin.backups",
            "app.infrastructure.db.admin.provisioning",
            "app.infrastructure.host_apps.inner_agents",
            "app.infrastructure.local_state.repo_registration_store",
            "app.infrastructure.process.episode_sync",
            "app.infrastructure.system.package_upgrade",
        ),
    ),
    EffectImportRule(
        name="socket",
        forbidden_prefixes=("socket",),
        allowed_module_prefixes=(
            "app.infrastructure.db.admin.provisioning.managed_local",
            "app.infrastructure.local_state",
            "app.infrastructure.process.episode_sync",
        ),
    ),
    EffectImportRule(
        name="network client",
        forbidden_prefixes=("httpx", "requests"),
        allowed_module_prefixes=(),
    ),
)


def test_packaged_source_roots_have_architecture_contracts() -> None:
    declared_roots = pyproject_package_roots(PYPROJECT)
    covered_roots = {
        contract.split(".", maxsplit=1)[0] for contract in ARCHITECTURE_CONTRACTS
    }

    missing = sorted(declared_roots - covered_roots)
    assert not missing, "Packaged roots missing architecture contracts:\n" + "\n".join(
        missing
    )


def test_direct_app_packages_have_architecture_contracts() -> None:
    actual_packages = direct_package_dirs(APP_ROOT)
    covered_packages = {
        contract.removeprefix("app.")
        for contract in ARCHITECTURE_CONTRACTS
        if contract.startswith("app.") and contract.count(".") == 1
    }

    missing = sorted(actual_packages - covered_packages)
    assert not missing, "app packages missing architecture contracts:\n" + "\n".join(
        missing
    )


def test_architecture_contract_test_files_exist() -> None:
    missing: list[str] = []
    for test_paths in ARCHITECTURE_CONTRACTS.values():
        for test_path in test_paths:
            if not (REPO_ROOT / test_path).is_file():
                missing.append(test_path)

    assert not missing, "Architecture contract test files are missing:\n" + "\n".join(
        sorted(set(missing))
    )


def test_static_test_helpers_are_not_production_dependencies() -> None:
    production_files = production_python_files(
        REPO_ROOT,
        package_roots=pyproject_package_roots(PYPROJECT),
    )

    violations = forbidden_import_violations(
        production_files,
        ("tests",),
        repo_root=REPO_ROOT,
    )
    runtime_dependencies = pyproject_dependency_names(PYPROJECT)
    forbidden_runtime_dependencies = sorted(
        runtime_dependencies & {"pytest", "ruff", "mypy", "black", "pre-commit"}
    )
    violations.extend(
        f"pyproject.toml declares test/dev dependency {dependency!r} as runtime"
        for dependency in forbidden_runtime_dependencies
    )

    assert not violations, (
        "Static architecture helpers must stay test-only:\n" + "\n".join(violations)
    )


def test_effect_imports_stay_in_owner_modules() -> None:
    production_files = production_python_files(
        REPO_ROOT,
        package_roots=pyproject_package_roots(PYPROJECT),
    )
    violations = effect_import_violations(
        production_files,
        EFFECT_IMPORT_RULES,
        repo_root=REPO_ROOT,
    )

    assert not violations, "Effect imports outside owner modules:\n" + "\n".join(
        violations
    )


def test_migrations_only_depend_on_db_schema_surfaces() -> None:
    allowed_app_prefixes = (
        "app.infrastructure.db.runtime.models.registry",
        "app.infrastructure.db.runtime.models.views",
    )
    violations: list[str] = []
    for ref in iter_import_references(python_files(REPO_ROOT / "migrations")):
        if not ref.module_name.startswith("app."):
            continue
        if module_matches_prefix(ref.module_name, allowed_app_prefixes):
            continue
        violations.append(
            f"{ref.path.relative_to(REPO_ROOT)}:{ref.line_no} imports {ref.module_name}"
        )

    assert not violations, (
        "Migrations should depend only on DB schema metadata surfaces:\n"
        + "\n".join(violations)
    )


def test_onboarding_assets_are_packaged_data_not_runtime_code() -> None:
    python_paths = python_files(REPO_ROOT / "onboarding_assets")
    runtime_files = [
        str(path.relative_to(REPO_ROOT))
        for path in python_paths
        if path.name != "__init__.py"
    ]
    import_violations = forbidden_import_violations(
        python_paths,
        ("app", "migrations"),
        repo_root=REPO_ROOT,
    )

    assert not runtime_files and not import_violations, (
        "onboarding_assets should remain package data, not runtime behavior:\n"
        + "\n".join(runtime_files + import_violations)
    )


def test_architecture_check_command_is_wired_to_developer_workflow() -> None:
    script = REPO_ROOT / "scripts" / "architecture_check"
    makefile = REPO_ROOT / "Makefile"
    hook = REPO_ROOT / ".githooks" / "pre-commit"

    violations: list[str] = []
    if not script.is_file():
        violations.append("scripts/architecture_check is missing")
    if script.is_file() and not script.stat().st_mode & stat.S_IXUSR:
        violations.append("scripts/architecture_check is not executable")
    if not makefile.is_file() or "architecture-check:" not in makefile.read_text(
        encoding="utf-8"
    ):
        violations.append("Makefile is missing architecture-check target")
    if not hook.is_file():
        violations.append(".githooks/pre-commit is missing")
    elif "scripts/architecture_check" not in hook.read_text(encoding="utf-8"):
        violations.append(".githooks/pre-commit does not run scripts/architecture_check")
    elif not hook.stat().st_mode & stat.S_IXUSR:
        violations.append(".githooks/pre-commit is not executable")

    assert not violations, (
        "Architecture guardrails must be runnable before commits:\n"
        + "\n".join(violations)
    )


def test_ci_runs_architecture_check_before_db_backed_tests() -> None:
    workflow = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )
    architecture_index = workflow.find("Run architecture guardrails")
    full_tests_index = workflow.find("Run tests")

    assert architecture_index >= 0, "CI is missing Run architecture guardrails step"
    assert full_tests_index >= 0, "CI is missing Run tests step"
    assert architecture_index < full_tests_index, (
        "CI should run static architecture guardrails before DB-backed tests"
    )
