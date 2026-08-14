"""Executable dependency boundaries for the package.

The project has a useful inward dependency direction today, but a diagram cannot stop a
convenient import from reversing it. These tests keep the domain independent, keep provider
and adapter implementations from coupling to each other, and reject internal import cycles.
"""

from __future__ import annotations

import ast
from pathlib import Path

PACKAGE_ROOT = Path(__file__).parents[1] / "src" / "litharness"

ALLOWED_DEPENDENCIES = {
    "domain": frozenset({"domain"}),
    "providers": frozenset({"domain", "providers"}),
    "adapters": frozenset({"domain", "adapters"}),
    "application": frozenset({"domain", "providers", "application"}),
    "entrypoint": frozenset(
        {"domain", "providers", "adapters", "application", "entrypoint"}
    ),
}


def _module_name(path: Path) -> str:
    parts = list(path.relative_to(PACKAGE_ROOT.parent).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _modules() -> dict[str, Path]:
    return {_module_name(path): path for path in PACKAGE_ROOT.rglob("*.py")}


def _layer(module: str) -> str | None:
    parts = module.split(".")
    if len(parts) < 2:
        return None
    if parts[1] in {"cli", "__main__"}:
        return "entrypoint"
    return parts[1] if parts[1] in ALLOWED_DEPENDENCIES else None


def _imports(path: Path, known_modules: set[str]) -> list[tuple[str, int]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend(
                (alias.name, node.lineno)
                for alias in node.names
                if alias.name.startswith("litharness")
            )
        elif isinstance(node, ast.ImportFrom) and node.module:
            if not node.module.startswith("litharness"):
                continue
            # ``from litharness.domain import state`` names a module through its alias,
            # while ``from litharness.domain.state import State`` names a symbol. Prefer
            # the former only when it is a module that actually exists.
            candidates = [f"{node.module}.{alias.name}" for alias in node.names]
            imported_modules = [name for name in candidates if name in known_modules]
            found.extend(
                (name, node.lineno)
                for name in (imported_modules or [node.module])
            )
    return found


def test_dependencies_only_point_outward_to_inward() -> None:
    modules = _modules()
    violations: list[str] = []
    for source, path in sorted(modules.items()):
        source_layer = _layer(source)
        if source_layer is None:
            continue
        allowed = ALLOWED_DEPENDENCIES[source_layer]
        for target, line in _imports(path, set(modules)):
            target_layer = _layer(target)
            if target_layer is not None and target_layer not in allowed:
                violations.append(
                    f"{source}:{line} ({source_layer}) imports {target} ({target_layer})"
                )
    assert not violations, "dependency boundary violations:\n" + "\n".join(violations)


def test_internal_module_graph_has_no_cycles() -> None:
    modules = _modules()
    known = set(modules)
    graph = {
        source: {
            target
            for target, _ in _imports(path, known)
            if target in known and target != source
        }
        for source, path in modules.items()
    }
    visited: set[str] = set()
    active: list[str] = []
    active_set: set[str] = set()

    def visit(module: str) -> list[str] | None:
        if module in active_set:
            start = active.index(module)
            return [*active[start:], module]
        if module in visited:
            return None
        active.append(module)
        active_set.add(module)
        for dependency in sorted(graph[module]):
            cycle = visit(dependency)
            if cycle is not None:
                return cycle
        active.pop()
        active_set.remove(module)
        visited.add(module)
        return None

    for module in sorted(graph):
        cycle = visit(module)
        assert cycle is None, "internal import cycle: " + " -> ".join(cycle)
