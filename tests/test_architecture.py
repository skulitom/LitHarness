"""Executable boundaries for the package: its dependencies, and its prose.

The project has a useful inward dependency direction today, but a diagram cannot stop a
convenient import from reversing it. These tests keep the domain independent, keep provider
and adapter implementations from coupling to each other, and reject internal import cycles.

**And they check the docstrings, because in this repo the docstrings are load-bearing.** The
comments here carry the reasons, the refuted alternatives and their measurements, and readers
— human and otherwise — act on them. Nothing type-checked a word of that, and the record says
what happens: `jobs.priority` was documented as inert in four places for two stages after it
stopped being, and a claim that a list of uncalled promises was empty survived exactly one
commit. Prose decays like code and had none of code's guards.

These are the cheapest approximations of a type-check for it — a symbol the prose names in
backticks should be findable, and a test it cites as evidence should exist — and they are the
two failures that actually happened.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import litharness_contracts as lc

PACKAGE_ROOT = Path(__file__).parents[1] / "src" / "litharness"
REPO_ROOT = Path(__file__).parents[1]

#: The inward direction, and `application` is the row that carries the argument.
#:
#: It reaches persistence through `application/ports.py` and never imports `adapters`, and it
#: now reaches generation the same way. **The half-inverted state is the one this rule
#: replaced**: `application` held a concrete `ProviderRegistry` import in three modules while
#: `conductor.HealthResettable` typed the very same object structurally, with a docstring
#: saying it keeps the dependency "at the handler layer instead of the loop". So the direction
#: was already decided and enforced in one place out of four, which is the worst of both — a
#: reader could not tell whether the concrete import was a decision or an oversight.
#:
#: Dropping `providers` here is what makes `TextGenerator` load-bearing rather than decorative.
#: `cli` is the composition root and still binds the concrete registry, which is the one place
#: that should.
ALLOWED_DEPENDENCIES = {
    "domain": frozenset({"domain"}),
    "providers": frozenset({"domain", "providers"}),
    "adapters": frozenset({"domain", "adapters"}),
    "application": frozenset({"domain", "application"}),
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


# --- the prose ------------------------------------------------------------------------

#: Backtick-quoted names in `src/` docstrings that deliberately name nothing here. Empty
#: today, and it should stay short: this project's style is to name a refuted alternative
#: (`plan/stage-0-decisions.md` is full of them), so a genuinely absent name belongs here
#: **with its reason**, not silently outside the check.
PROSE_ALLOWED: dict[str, str] = {}

#: A name worth resolving: it has an underscore, a dot, or an initial capital. A single
#: lowercase word in backticks is ordinary emphasis far more often than it is a symbol.
_SYMBOLISH = re.compile(r"`([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)`")


def _repo_corpus() -> str:
    parts = [path.read_text(encoding="utf-8") for path in PACKAGE_ROOT.rglob("*.py")]
    parts += [path.read_text(encoding="utf-8") for path in (REPO_ROOT / "tests").rglob("*.py")]
    parts += [path.read_text(encoding="utf-8") for path in (REPO_ROOT / "migrations").glob("*.sql")]
    parts.append((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return "\n".join(parts)


def test_every_symbol_the_prose_names_still_exists() -> None:
    """A docstring naming a function that was renamed is worse than one saying nothing: it
    teaches the wrong thing to whoever reads it next, and reads as current because it is
    sitting beside working code.

    Contract names are skipped — those belong to `litharness_contracts` and are checked by
    its own suite — and so are plain lowercase words, which are emphasis more often than
    they are symbols.
    """
    contract_names = set(dir(lc))
    corpus = _repo_corpus()
    stale: list[str] = []
    for path in sorted(PACKAGE_ROOT.rglob("*.py")):
        for name in sorted(set(_SYMBOLISH.findall(path.read_text(encoding="utf-8")))):
            head, tail = name.split(".")[0], name.split(".")[-1]
            if "_" not in name and "." not in name and not name[0].isupper():
                continue
            if head in contract_names or tail in contract_names or name in PROSE_ALLOWED:
                continue
            if not re.search(rf"\b{re.escape(tail)}\b", corpus):
                stale.append(f"{path.relative_to(PACKAGE_ROOT).as_posix()}: `{name}`")
    assert not stale, (
        "prose names symbols that no longer exist:\n"
        + "\n".join(stale)
        + "\n(rename the reference, or record it in PROSE_ALLOWED with why it is absent)"
    )


def test_every_test_cited_as_evidence_exists() -> None:
    """The project cites tests by name as proof that a clause holds — `PLAN.md` §17 does it
    for every Stage 0 exit criterion. A citation that no longer resolves is a claim with its
    evidence removed, and it looks exactly like a claim with evidence.

    Checked over `src/` and `plan/stage-0-decisions.md`, the two places that cite *this*
    repo's tests. `PLAN.md` and the other companion docs also discuss siblings' suites, which
    this repo cannot resolve and should not pretend to.
    """
    tests_dir = REPO_ROOT / "tests"
    suite = "\n".join(path.read_text(encoding="utf-8") for path in tests_dir.rglob("*.py"))
    sources = [*PACKAGE_ROOT.rglob("*.py"), REPO_ROOT / "plan" / "stage-0-decisions.md"]
    stale: list[str] = []
    for path in sources:
        text = path.read_text(encoding="utf-8")
        for name in sorted(set(re.findall(r"`(test_[a-z0-9_]+)`", text))):
            if re.search(rf"def {re.escape(name)}\b", suite):
                continue
            if (tests_dir / f"{name}.py").exists():
                continue  # a module, cited as a whole
            stale.append(f"{path.relative_to(REPO_ROOT).as_posix()}: `{name}`")
    assert not stale, "cited tests that do not exist:\n" + "\n".join(stale)


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


def test_the_registry_still_satisfies_the_port_the_application_asks_for() -> None:
    """`application` names `TextGenerator`; `cli` hands it a `ProviderRegistry`. Nothing in
    the application layer can check that, because the rule above forbids it the import.

    mypy checks the fit where `cli` wires them, which is the right place and an easy one to
    lose: the wiring is one keyword argument, and a refactor that routes the registry through
    an `Any`-typed factory would drop the check with no diagnostic anywhere. This asserts the
    contract directly, so the port cannot drift from its only implementation in silence.

    Structural, not nominal — `ProviderRegistry` does not inherit from anything, and the whole
    value of the port is that a future in-memory or remote generator implements it without
    knowing it exists.
    """
    from litharness.application.ports import TextGenerator
    from litharness.providers.registry import ProviderRegistry

    registry = ProviderRegistry(providers=(), order=())
    generator: TextGenerator = registry

    for method in ("resolve", "complete", "reset_health"):
        assert callable(getattr(generator, method)), f"the port names {method}"
