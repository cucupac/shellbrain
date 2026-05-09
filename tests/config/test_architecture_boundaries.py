"""Architecture boundary checks for the app package layout."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from app.infrastructure.cli.parser import build_parser


REPO_ROOT = Path(__file__).resolve().parents[2]
APP_ROOT = REPO_ROOT / "app"


def _python_files(package_dir: Path) -> list[Path]:
    return sorted(
        path for path in package_dir.rglob("*.py") if "__pycache__" not in path.parts
    )


def _imported_modules(path: Path) -> list[tuple[int, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append((node.lineno, node.module))
    return imports


def _assert_no_forbidden_imports(
    package: str, forbidden_prefixes: tuple[str, ...]
) -> None:
    violations: list[str] = []
    for path in _python_files(APP_ROOT / package):
        for line_no, module_name in _imported_modules(path):
            if module_name.startswith(forbidden_prefixes):
                rel_path = path.relative_to(REPO_ROOT)
                violations.append(f"{rel_path}:{line_no} imports {module_name}")

    assert not violations, "Forbidden architecture imports:\n" + "\n".join(violations)


def test_core_does_not_import_edge_packages() -> None:
    _assert_no_forbidden_imports(
        "core",
        (
            "app.startup",
            "app.infrastructure",
            "app.entrypoints",
        ),
    )


def test_infrastructure_does_not_import_startup_or_entrypoints() -> None:
    _assert_no_forbidden_imports(
        "infrastructure",
        (
            "app.startup",
            "app.entrypoints",
        ),
    )


def test_entrypoints_do_not_import_infrastructure_directly() -> None:
    _assert_no_forbidden_imports(
        "entrypoints",
        ("app.infrastructure",),
    )


def test_startup_does_not_import_entrypoints() -> None:
    _assert_no_forbidden_imports(
        "startup",
        ("app.entrypoints",),
    )


def test_followup_refactor_removed_old_layer_paths() -> None:
    forbidden_paths = (
        APP_ROOT / "handlers",
        APP_ROOT / "startup" / "handlers.py",
        APP_ROOT / "infrastructure" / "observability",
        APP_ROOT / "core" / "contracts" / "requests.py",
        APP_ROOT / "entrypoints" / "cli" / "parser",
        APP_ROOT / "entrypoints" / "cli" / "protocol",
        APP_ROOT / "entrypoints" / "cli" / "presenters",
        APP_ROOT / "entrypoints" / "cli" / "endpoints",
    )
    violations = [
        str(path.relative_to(REPO_ROOT)) for path in forbidden_paths if path.exists()
    ]
    assert not violations, (
        "Forbidden follow-up refactor paths still exist:\n" + "\n".join(violations)
    )


def test_cli_entrypoint_main_is_startup_shim() -> None:
    path = APP_ROOT / "entrypoints" / "cli" / "main.py"
    app_imports = [
        module_name
        for _line_no, module_name in _imported_modules(path)
        if module_name.startswith("app.")
    ]
    assert app_imports == ["app.startup.cli"]


def test_periphery_package_is_gone() -> None:
    assert not (APP_ROOT / "periphery").exists()


def test_cli_legacy_module_is_gone() -> None:
    assert not (APP_ROOT / "entrypoints" / "cli" / "legacy.py").exists()


def test_top_level_create_and_update_commands_are_gone() -> None:
    parser = build_parser()
    choices = parser._subparsers._group_actions[0].choices
    assert "create" not in choices
    assert "update" not in choices


def test_bare_concept_payload_is_rejected() -> None:
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["concept", "--json", "{}"])


def test_operation_flow_is_gone() -> None:
    assert not (APP_ROOT / "core" / "use_cases" / "operation_flow.py").exists()
    assert not (
        APP_ROOT / "core" / "use_cases" / "agent_operations" / "support.py"
    ).exists()


def test_refactor_old_layer_directories_are_gone() -> None:
    forbidden_paths = (
        APP_ROOT / "core" / "observability",
        APP_ROOT / "core" / "validation",
        APP_ROOT / "core" / "use_cases" / "agent_operations",
        APP_ROOT / "application",
    )
    violations = [
        str(path.relative_to(REPO_ROOT)) for path in forbidden_paths if path.exists()
    ]
    assert not violations, (
        "Forbidden old architecture directories still exist:\n" + "\n".join(violations)
    )


def test_core_ports_replace_interfaces() -> None:
    violations: list[str] = []
    if not (APP_ROOT / "core" / "ports").is_dir():
        violations.append("app/core/ports is missing")
    if (APP_ROOT / "core" / "interfaces").exists():
        violations.append("app/core/interfaces still exists")
    assert not violations, "Core ports must replace interfaces:\n" + "\n".join(
        violations
    )


def test_core_ports_are_grouped_by_adapter_category() -> None:
    ports_root = APP_ROOT / "core" / "ports"
    expected_categories = {
        "db",
        "embeddings",
        "local_state",
        "reporting",
        "runtime",
        "settings",
    }
    categories = {
        path.name
        for path in ports_root.iterdir()
        if path.is_dir() and "__pycache__" not in path.parts
    }
    flat_modules = [
        str(path.relative_to(REPO_ROOT))
        for path in ports_root.glob("*.py")
        if path.name != "__init__.py"
    ]
    missing_categories = sorted(expected_categories - categories)
    assert not flat_modules and not missing_categories, (
        "Core ports should be grouped by adapter category:\n"
        + "\n".join(flat_modules + missing_categories)
    )


def test_core_contracts_do_not_own_raw_cli_protocol() -> None:
    assert not (APP_ROOT / "core" / "contracts" / "agent_requests.py").exists()
    assert not (APP_ROOT / "core" / "contracts" / "request_hydration.py").exists()


def test_direct_core_directories_have_boundary_readmes() -> None:
    missing = [
        str(path.relative_to(REPO_ROOT))
        for path in sorted((APP_ROOT / "core").iterdir())
        if path.is_dir()
        and "__pycache__" not in path.parts
        and not (path / "README.md").is_file()
    ]
    assert not missing, "Core directories missing README.md:\n" + "\n".join(missing)


def test_core_use_cases_do_not_accept_raw_payloads() -> None:
    violations: list[str] = []
    forbidden_annotations = {
        "dict",
        "Dict",
        "Mapping",
        "MutableMapping",
        "dict[str, Any]",
        "Mapping[str, Any]",
    }
    for path in _python_files(APP_ROOT / "core" / "use_cases"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef) or node.name.startswith("_"):
                continue
            for arg in list(node.args.args) + list(node.args.kwonlyargs):
                if arg.arg != "payload":
                    continue
                annotation = (
                    ast.unparse(arg.annotation) if arg.annotation is not None else ""
                )
                if not annotation or annotation in forbidden_annotations:
                    violations.append(
                        f"{path.relative_to(REPO_ROOT)}:{node.lineno} {node.name} accepts raw payload"
                    )
    assert not violations, (
        "Core use cases should receive typed contracts, not raw CLI payloads:\n"
        + "\n".join(violations)
    )


def test_startup_jobs_package_is_gone() -> None:
    assert not (APP_ROOT / "startup" / "jobs.py").exists()
    assert not (APP_ROOT / "startup" / "jobs").exists()


def test_generic_dumping_ground_modules_are_gone_from_main_layers() -> None:
    forbidden_names = {
        "common.py",
        "flow_common.py",
        "support.py",
        "helpers.py",
        "utils.py",
        "operations.py",
        "_shared",
    }
    violations = [
        str(path.relative_to(REPO_ROOT))
        for root in (
            APP_ROOT / "core",
            APP_ROOT / "startup",
            APP_ROOT / "infrastructure",
        )
        for path in root.rglob("*")
        if "__pycache__" not in path.parts and path.name in forbidden_names
    ]
    assert not violations, (
        "Rename dumping-ground modules by the concept they actually represent:\n"
        + "\n".join(violations)
    )


def test_startup_has_no_process_or_postgres_mechanics() -> None:
    forbidden = (
        "import subprocess",
        "subprocess.",
        "import psycopg",
        "psycopg.",
        "time.sleep",
        '["docker"',
        "docker info",
        "Docker daemon",
    )
    violations: list[str] = []
    for path in _python_files(APP_ROOT / "startup"):
        text = path.read_text(encoding="utf-8")
        for needle in forbidden:
            if needle in text:
                violations.append(f"{path.relative_to(REPO_ROOT)} contains {needle!r}")
    assert not violations, (
        "Startup contains concrete process/DB mechanics:\n" + "\n".join(violations)
    )


def test_infrastructure_package_initializers_stay_thin() -> None:
    violations: list[str] = []
    for path in _python_files(APP_ROOT / "infrastructure"):
        if path.name != "__init__.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                violations.append(
                    f"{path.relative_to(REPO_ROOT)}:{node.lineno} defines {node.name}"
                )
    assert not violations, (
        "Infrastructure package initializers should only re-export names:\n"
        + "\n".join(violations)
    )


def test_core_policy_smell_packages_are_gone() -> None:
    assert not list((APP_ROOT / "core").rglob("_shared"))
    assert not (APP_ROOT / "core" / "policies" / "telemetry").exists()
    assert not (APP_ROOT / "core" / "policies" / "validation").exists()


def test_core_does_not_import_sqlalchemy() -> None:
    forbidden_modules = ("sqlalchemy",)
    violations: list[str] = []
    for path in _python_files(APP_ROOT / "core"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith(forbidden_modules):
                        violations.append(
                            f"{path.relative_to(REPO_ROOT)}:{node.lineno} imports {alias.name}"
                        )
            elif (
                isinstance(node, ast.ImportFrom)
                and node.module
                and node.module.startswith(forbidden_modules)
            ):
                imported = ", ".join(alias.name for alias in node.names)
                violations.append(
                    f"{path.relative_to(REPO_ROOT)}:{node.lineno} imports {imported} from {node.module}"
                )
    assert not violations, (
        "Core must not depend on SQLAlchemy types or SQL helpers:\n"
        + "\n".join(violations)
    )


def test_core_use_case_apply_files_are_gone() -> None:
    violations = [
        str(path.relative_to(REPO_ROOT))
        for path in _python_files(APP_ROOT / "core" / "use_cases")
        if path.stem.startswith("apply")
    ]
    assert not violations, (
        "Core use cases should expose add/update/show/read paths, not apply files:\n"
        + "\n".join(violations)
    )


def test_core_policies_do_not_generate_ids_or_execute_plans() -> None:
    violations: list[str] = []
    for path in _python_files(APP_ROOT / "core" / "policies"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for line_no, module_name in _imported_modules(path):
            if (
                module_name.endswith("IIdGenerator")
                or module_name == "app.core.ports.runtime.idgen"
            ):
                violations.append(
                    f"{path.relative_to(REPO_ROOT)}:{line_no} imports {module_name}"
                )
            if module_name.startswith("app.core.ports"):
                violations.append(
                    f"{path.relative_to(REPO_ROOT)}:{line_no} imports {module_name}"
                )
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "uuid4"
            ):
                violations.append(
                    f"{path.relative_to(REPO_ROOT)}:{node.lineno} calls uuid4()"
                )
            if isinstance(node, ast.FunctionDef) and node.name.startswith("apply_"):
                violations.append(
                    f"{path.relative_to(REPO_ROOT)}:{node.lineno} defines {node.name}"
                )
            if isinstance(node, ast.Name) and node.id == "IIdGenerator":
                violations.append(
                    f"{path.relative_to(REPO_ROOT)}:{node.lineno} references IIdGenerator"
                )
    assert not violations, (
        "Core policies should plan, not generate IDs or execute effects:\n"
        + "\n".join(violations)
    )


def test_db_adapters_do_not_import_read_or_concept_scoring_policy() -> None:
    forbidden_prefixes = (
        "app.core.policies.retrieval.bm25",
        "app.core.policies.retrieval.lexical_query",
        "app.core.policies.retrieval.scoring",
        "app.core.policies.concepts.search",
    )
    violations: list[str] = []
    for path in _python_files(APP_ROOT / "infrastructure" / "db"):
        for line_no, module_name in _imported_modules(path):
            if module_name.startswith(forbidden_prefixes):
                violations.append(
                    f"{path.relative_to(REPO_ROOT)}:{line_no} imports {module_name}"
                )
    assert not violations, (
        "DB adapters should return rows, not own ranking/search policy:\n"
        + "\n".join(violations)
    )


def test_infrastructure_does_not_reference_entrypoint_modules() -> None:
    forbidden_strings = (
        "app.entrypoints",
        "app.entrypoints.cli",
        "app.entrypoints.jobs",
        "app.entrypoints.host_hooks",
        "python -m app",
    )
    violations: list[str] = []
    for path in _python_files(APP_ROOT / "infrastructure"):
        text = path.read_text(encoding="utf-8")
        for needle in forbidden_strings:
            if needle in text:
                violations.append(f"{path.relative_to(REPO_ROOT)} contains {needle!r}")
    assert not violations, (
        "Infrastructure must not reference entrypoint module paths:\n"
        + "\n".join(violations)
    )


def test_telemetry_builders_use_injected_timestamps() -> None:
    violations: list[str] = []
    for path in _python_files(APP_ROOT / "infrastructure" / "telemetry"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "now"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "datetime"
            ):
                violations.append(
                    f"{path.relative_to(REPO_ROOT)}:{node.lineno} calls datetime.now()"
                )
    assert not violations, (
        "Telemetry builders should receive timestamps from callers:\n"
        + "\n".join(violations)
    )


def test_handlers_and_refactored_use_cases_use_injected_clock_and_ids() -> None:
    violations: list[str] = []
    scan_roots = (
        APP_ROOT / "infrastructure" / "cli" / "handlers",
        APP_ROOT / "core" / "use_cases" / "memories",
        APP_ROOT / "core" / "use_cases" / "concepts",
        APP_ROOT / "core" / "use_cases" / "retrieval",
    )
    for scan_root in scan_roots:
        for path in _python_files(scan_root):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "now"
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "datetime"
                ):
                    violations.append(
                        f"{path.relative_to(REPO_ROOT)}:{node.lineno} calls datetime.now()"
                    )
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "uuid4"
                ):
                    violations.append(
                        f"{path.relative_to(REPO_ROOT)}:{node.lineno} calls uuid4()"
                    )
    assert not violations, (
        "Handlers and refactored use cases should use injected clock and id generator:\n"
        + "\n".join(violations)
    )


def test_deleted_agent_operations_tree_is_not_a_guardrail_target() -> None:
    assert not (APP_ROOT / "core" / "use_cases" / "agent_operations").exists()


def test_planned_effects_use_typed_params() -> None:
    path = APP_ROOT / "core" / "contracts" / "planned_effects.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    violations: list[str] = []
    handled_source = "\n".join(
        (
            (APP_ROOT / "core" / "use_cases" / "plan_execution.py").read_text(
                encoding="utf-8"
            ),
            (
                APP_ROOT
                / "infrastructure"
                / "telemetry"
                / "operation_invocations.py"
            ).read_text(encoding="utf-8"),
        )
    )
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "params"
        ):
            annotation = ast.unparse(node.annotation)
            if annotation == "dict[str, Any]":
                violations.append(
                    f"{path.relative_to(REPO_ROOT)}:{node.lineno} PlannedEffect.params is dict[str, Any]"
                )
        if isinstance(node, ast.FunctionDef) and node.name in {"__getitem__", "get"}:
            violations.append(
                f"{path.relative_to(REPO_ROOT)}:{node.lineno} keeps mapping-style compatibility"
            )
    from app.core.contracts.planned_effects import EffectType

    for effect_type in EffectType:
        if f"EffectType.{effect_type.name}" not in handled_source:
            violations.append(
                f"{effect_type.name} is not handled by execution/telemetry"
            )
    assert not violations, (
        "Planned effects should be typed and exhaustively handled:\n"
        + "\n".join(violations)
    )


def test_docs_and_onboarding_do_not_teach_removed_cli_aliases() -> None:
    forbidden = (
        "shellbrain create --json",
        "shellbrain update --json",
        "bare concept --json",
        "<strong>create</strong>",
        "<strong>update</strong>",
        "Legacy alias",
    )
    roots = [
        REPO_ROOT / "docs",
        REPO_ROOT / "onboarding_assets",
        REPO_ROOT / "README.md",
    ]
    violations: list[str] = []
    for root in roots:
        paths = [root] if root.is_file() else sorted(root.rglob("*"))
        for path in paths:
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for needle in forbidden:
                if needle in text:
                    violations.append(
                        f"{path.relative_to(REPO_ROOT)} contains {needle!r}"
                    )
    assert not violations, (
        "Docs/onboarding should teach current CLI names only:\n" + "\n".join(violations)
    )
