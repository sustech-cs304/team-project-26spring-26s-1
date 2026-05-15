#!/usr/bin/env python3
"""Generate source code metrics for checked-out project directories."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - used by Python < 3.11
    import tomli as tomllib  # type: ignore[no-redef]

try:
    import lizard
except ModuleNotFoundError as exc:  # pragma: no cover - handled at runtime
    raise SystemExit("Missing dependency: install lizard before running this script.") from exc


SOURCE_EXTENSIONS = {
    ".c",
    ".cc",
    ".cpp",
    ".css",
    ".cts",
    ".cxx",
    ".go",
    ".h",
    ".hpp",
    ".html",
    ".java",
    ".js",
    ".jsx",
    ".mjs",
    ".mts",
    ".py",
    ".pyi",
    ".rs",
    ".sass",
    ".scss",
    ".ts",
    ".tsx",
    ".vue",
}

COMPLEXITY_EXTENSIONS = {
    ".c",
    ".cc",
    ".cpp",
    ".cts",
    ".cxx",
    ".go",
    ".h",
    ".hpp",
    ".java",
    ".js",
    ".jsx",
    ".mjs",
    ".mts",
    ".py",
    ".rs",
    ".ts",
    ".tsx",
    ".vue",
}

EXCLUDED_DIRS = {
    ".git",
    ".github",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "build",
    "coverage",
    "dist",
    "node_modules",
    "target",
    "venv",
}

NODE_DEPENDENCY_SECTIONS = (
    "dependencies",
    "devDependencies",
    "peerDependencies",
    "optionalDependencies",
)

CARGO_DEPENDENCY_SECTIONS = (
    "dependencies",
    "dev-dependencies",
    "build-dependencies",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--project",
        action="append",
        required=True,
        metavar="NAME=PATH",
        help="Project label and path to analyze. Can be provided multiple times.",
    )
    parser.add_argument(
        "--output-dir",
        default="metrics-report",
        help="Directory where summary.md and code-metrics.json will be written.",
    )
    parser.add_argument(
        "--top-functions",
        default=15,
        type=int,
        help="Number of highest-complexity functions to show in the Markdown report.",
    )
    return parser.parse_args()


def parse_project(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise SystemExit(f"Invalid --project value '{value}'. Expected NAME=PATH.")

    name, path = value.split("=", 1)
    name = name.strip()
    if not name:
        raise SystemExit(f"Invalid --project value '{value}'. Project name is empty.")

    root = Path(path).resolve()
    if not root.is_dir():
        raise SystemExit(f"Project path does not exist or is not a directory: {root}")

    return name, root


def is_excluded(path: Path, root: Path) -> bool:
    try:
        relative = path.relative_to(root)
    except ValueError:
        return True

    return any(part in EXCLUDED_DIRS for part in relative.parts)


def iter_project_files(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and not is_excluded(path, root)
    )


def is_source_file(path: Path) -> bool:
    if path.name.endswith(".min.js"):
        return False
    return path.suffix.lower() in SOURCE_EXTENSIONS


def is_complexity_file(path: Path) -> bool:
    if path.name.endswith(".min.js"):
        return False
    return path.suffix.lower() in COMPLEXITY_EXTENSIONS


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def count_loc(path: Path) -> int:
    return sum(1 for line in read_text(path).splitlines() if line.strip())


def normalize_relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def analyze_complexity(path: Path, root: Path) -> tuple[list[dict[str, Any]], str | None]:
    relative = normalize_relative(path, root)
    try:
        result = lizard.analyze_file.analyze_source_code(relative, read_text(path))
    except Exception as exc:  # lizard can fail on malformed or unsupported files
        return [], str(exc)

    functions = []
    for function in result.function_list:
        functions.append(
            {
                "file": relative,
                "name": function.long_name or function.name,
                "start_line": function.start_line,
                "end_line": function.end_line,
                "nloc": function.nloc,
                "cyclomatic_complexity": function.cyclomatic_complexity,
            }
        )
    return functions, None


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    return data if isinstance(data, dict) else {}


def load_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as file:
        data = tomllib.load(file)
    return data if isinstance(data, dict) else {}


def add_dependency(
    dependencies: set[str],
    breakdown: list[dict[str, Any]],
    *,
    ecosystem: str,
    manifest: str,
    section: str,
    names: list[str],
) -> None:
    clean_names = sorted({name for name in names if name})
    for name in clean_names:
        dependencies.add(f"{ecosystem}:{name.lower()}")

    breakdown.append(
        {
            "ecosystem": ecosystem,
            "manifest": manifest,
            "section": section,
            "count": len(clean_names),
            "dependencies": clean_names,
        }
    )


def python_requirement_name(requirement: str) -> str | None:
    value = requirement.strip()
    if not value or value.startswith("#") or value.startswith(("-r", "--")):
        return None
    match = re.match(r"([A-Za-z0-9_.-]+)", value)
    return match.group(1) if match else value


def collect_node_dependencies(root: Path, dependencies: set[str], breakdown: list[dict[str, Any]]) -> None:
    package_json = root / "package.json"
    if not package_json.exists():
        return

    data = load_json(package_json)
    manifest = normalize_relative(package_json, root)
    for section in NODE_DEPENDENCY_SECTIONS:
        section_data = data.get(section, {})
        if isinstance(section_data, dict):
            add_dependency(
                dependencies,
                breakdown,
                ecosystem="npm",
                manifest=manifest,
                section=section,
                names=list(section_data.keys()),
            )


def collect_cargo_table(
    data: dict[str, Any],
    manifest: str,
    dependencies: set[str],
    breakdown: list[dict[str, Any]],
    prefix: str = "",
) -> None:
    for section in CARGO_DEPENDENCY_SECTIONS:
        section_data = data.get(section, {})
        if isinstance(section_data, dict):
            add_dependency(
                dependencies,
                breakdown,
                ecosystem="cargo",
                manifest=manifest,
                section=f"{prefix}{section}",
                names=list(section_data.keys()),
            )


def collect_cargo_dependencies(root: Path, dependencies: set[str], breakdown: list[dict[str, Any]]) -> None:
    for cargo_toml in sorted(root.rglob("Cargo.toml")):
        if is_excluded(cargo_toml, root):
            continue

        data = load_toml(cargo_toml)
        manifest = normalize_relative(cargo_toml, root)
        collect_cargo_table(data, manifest, dependencies, breakdown)

        targets = data.get("target", {})
        if isinstance(targets, dict):
            for target_name, target_data in targets.items():
                if isinstance(target_data, dict):
                    collect_cargo_table(
                        target_data,
                        manifest,
                        dependencies,
                        breakdown,
                        prefix=f"target.{target_name}.",
                    )


def collect_python_dependencies(root: Path, dependencies: set[str], breakdown: list[dict[str, Any]]) -> None:
    for pyproject in sorted(root.rglob("pyproject.toml")):
        if is_excluded(pyproject, root):
            continue

        data = load_toml(pyproject)
        project = data.get("project", {})
        manifest = normalize_relative(pyproject, root)

        if isinstance(project, dict):
            project_dependencies = [
                name
                for name in (python_requirement_name(item) for item in project.get("dependencies", []))
                if name
            ]
            add_dependency(
                dependencies,
                breakdown,
                ecosystem="python",
                manifest=manifest,
                section="project.dependencies",
                names=project_dependencies,
            )

            optional = project.get("optional-dependencies", {})
            if isinstance(optional, dict):
                for group, values in optional.items():
                    optional_dependencies = [
                        name
                        for name in (python_requirement_name(item) for item in values)
                        if name
                    ]
                    add_dependency(
                        dependencies,
                        breakdown,
                        ecosystem="python",
                        manifest=manifest,
                        section=f"project.optional-dependencies.{group}",
                        names=optional_dependencies,
                    )

        poetry = data.get("tool", {}).get("poetry", {}) if isinstance(data.get("tool"), dict) else {}
        if isinstance(poetry, dict):
            poetry_dependencies = poetry.get("dependencies", {})
            if isinstance(poetry_dependencies, dict):
                names = [name for name in poetry_dependencies.keys() if name.lower() != "python"]
                add_dependency(
                    dependencies,
                    breakdown,
                    ecosystem="python",
                    manifest=manifest,
                    section="tool.poetry.dependencies",
                    names=names,
                )

            groups = poetry.get("group", {})
            if isinstance(groups, dict):
                for group, group_data in groups.items():
                    group_dependencies = {}
                    if isinstance(group_data, dict):
                        group_dependencies = group_data.get("dependencies", {})
                    if isinstance(group_dependencies, dict):
                        add_dependency(
                            dependencies,
                            breakdown,
                            ecosystem="python",
                            manifest=manifest,
                            section=f"tool.poetry.group.{group}.dependencies",
                            names=list(group_dependencies.keys()),
                        )

    for requirements in sorted(root.rglob("requirements*.txt")):
        if is_excluded(requirements, root):
            continue

        names = [
            name
            for name in (python_requirement_name(line) for line in read_text(requirements).splitlines())
            if name
        ]
        add_dependency(
            dependencies,
            breakdown,
            ecosystem="python",
            manifest=normalize_relative(requirements, root),
            section="requirements",
            names=names,
        )


def analyze_dependencies(root: Path) -> dict[str, Any]:
    dependencies: set[str] = set()
    breakdown: list[dict[str, Any]] = []

    collect_node_dependencies(root, dependencies, breakdown)
    collect_cargo_dependencies(root, dependencies, breakdown)
    collect_python_dependencies(root, dependencies, breakdown)

    return {
        "direct_dependency_count": len(dependencies),
        "breakdown": breakdown,
    }


def analyze_project(name: str, root: Path) -> dict[str, Any]:
    all_files = iter_project_files(root)
    source_files = [path for path in all_files if is_source_file(path)]

    loc_by_file = [
        {
            "file": normalize_relative(path, root),
            "loc": count_loc(path),
        }
        for path in source_files
    ]

    functions: list[dict[str, Any]] = []
    complexity_errors = []
    complexity_files = [path for path in source_files if is_complexity_file(path)]
    for path in complexity_files:
        file_functions, error = analyze_complexity(path, root)
        functions.extend(file_functions)
        if error:
            complexity_errors.append(
                {
                    "file": normalize_relative(path, root),
                    "error": error,
                }
            )

    total_ccn = sum(function["cyclomatic_complexity"] for function in functions)
    max_function = max(functions, key=lambda item: item["cyclomatic_complexity"], default=None)

    return {
        "name": name,
        "root": str(root),
        "source_file_count": len(source_files),
        "loc": sum(file["loc"] for file in loc_by_file),
        "loc_by_file": loc_by_file,
        "cyclomatic_complexity": {
            "files_analyzed": len(complexity_files),
            "function_count": len(functions),
            "total": total_ccn,
            "average_per_function": round(total_ccn / len(functions), 2) if functions else 0,
            "max": max_function["cyclomatic_complexity"] if max_function else 0,
            "max_function": max_function,
            "functions": functions,
            "errors": complexity_errors,
        },
        "dependencies": analyze_dependencies(root),
    }


def format_int(value: int) -> str:
    return f"{value:,}"


def format_float(value: float) -> str:
    return f"{value:.2f}"


def markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def build_markdown(report: dict[str, Any], top_functions: int) -> str:
    projects = report["projects"]
    rows = []
    for project in projects:
        complexity = project["cyclomatic_complexity"]
        rows.append(
            [
                project["name"],
                format_int(project["source_file_count"]),
                format_int(project["loc"]),
                format_int(complexity["function_count"]),
                format_int(complexity["total"]),
                format_float(complexity["average_per_function"]),
                format_int(complexity["max"]),
                format_int(project["dependencies"]["direct_dependency_count"]),
            ]
        )

    total_source_files = sum(project["source_file_count"] for project in projects)
    total_loc = sum(project["loc"] for project in projects)
    total_functions = sum(project["cyclomatic_complexity"]["function_count"] for project in projects)
    total_ccn = sum(project["cyclomatic_complexity"]["total"] for project in projects)
    total_dependency_count = sum(project["dependencies"]["direct_dependency_count"] for project in projects)
    max_ccn = max((project["cyclomatic_complexity"]["max"] for project in projects), default=0)
    rows.append(
        [
            "total",
            format_int(total_source_files),
            format_int(total_loc),
            format_int(total_functions),
            format_int(total_ccn),
            format_float(total_ccn / total_functions) if total_functions else "0.00",
            format_int(max_ccn),
            format_int(total_dependency_count),
        ]
    )

    lines = [
        "# Code Metrics",
        "",
        f"Generated at: `{report['generated_at']}`",
        "",
        "Scope notes:",
        "- LOC counts non-empty lines in source files; vendor, build, generated output, and VCS folders are excluded.",
        "- Cyclomatic complexity is computed with `lizard` for supported source files.",
        "- Dependencies count direct dependencies declared in manifests, not transitive lockfile entries.",
        "",
        markdown_table(
            [
                "Project",
                "Source files",
                "LOC",
                "Functions",
                "Total CCN",
                "Avg CCN/function",
                "Max CCN",
                "Direct deps",
            ],
            rows,
        ),
    ]

    all_functions = []
    for project in projects:
        for function in project["cyclomatic_complexity"]["functions"]:
            all_functions.append((project["name"], function))

    all_functions.sort(
        key=lambda item: (
            item[1]["cyclomatic_complexity"],
            item[1]["nloc"],
            item[1]["file"],
        ),
        reverse=True,
    )

    lines.extend(["", "## Highest Complexity Functions", ""])
    if all_functions:
        function_rows = []
        for project_name, function in all_functions[:top_functions]:
            location = f"{function['file']}:{function['start_line']}"
            function_rows.append(
                [
                    project_name,
                    format_int(function["cyclomatic_complexity"]),
                    function["name"].replace("|", "\\|"),
                    location,
                    format_int(function["nloc"]),
                ]
            )
        lines.append(markdown_table(["Project", "CCN", "Function", "Location", "NLOC"], function_rows))
    else:
        lines.append("No functions were detected by the complexity analyzer.")

    dependency_rows = []
    for project in projects:
        for item in project["dependencies"]["breakdown"]:
            if item["count"] == 0:
                continue
            dependency_rows.append(
                [
                    project["name"],
                    item["ecosystem"],
                    item["manifest"],
                    item["section"],
                    format_int(item["count"]),
                ]
            )

    lines.extend(["", "## Dependency Breakdown", ""])
    if dependency_rows:
        lines.append(markdown_table(["Project", "Ecosystem", "Manifest", "Section", "Count"], dependency_rows))
    else:
        lines.append("No dependency manifests were detected.")

    errors = [
        (project["name"], error)
        for project in projects
        for error in project["cyclomatic_complexity"]["errors"]
    ]
    if errors:
        lines.extend(["", "## Complexity Analyzer Warnings", ""])
        error_rows = [
            [project_name, error["file"], error["error"].replace("|", "\\|")]
            for project_name, error in errors
        ]
        lines.append(markdown_table(["Project", "File", "Warning"], error_rows))

    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    projects = [parse_project(value) for value in args.project]
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "projects": [analyze_project(name, root) for name, root in projects],
    }

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "code-metrics.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (output_dir / "summary.md").write_text(
        build_markdown(report, args.top_functions),
        encoding="utf-8",
    )

    print(f"Wrote metrics report to {output_dir.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
