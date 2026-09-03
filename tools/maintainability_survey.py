"""Numbers about the codebase's shape, from scripts and never from memory.

`plan/maintainability-survey.md` is written from this file's output, and the reason it is a
script rather than a session's notes is the one `PLAN.md`'s header records: the number the
project reports about itself is the one to distrust first. Every table in the survey names
the subcommand that regenerates it, so a later session re-runs the command instead of
trusting the page.

Usage (from the repository root):

    uv run python tools/maintainability_survey.py sizes
    uv run python tools/maintainability_survey.py sections
    uv run python tools/maintainability_survey.py imports
    uv run python tools/maintainability_survey.py constants
    uv run python tools/maintainability_survey.py citations --sample 50 --out FILE
    uv run python tools/maintainability_survey.py ledger-tests
    uv run python tools/maintainability_survey.py helpers
    uv run python tools/maintainability_survey.py stores
    uv run python tools/maintainability_survey.py durations JUNIT_XML --top 20

Everything here is read-only over the working tree. Nothing opens a database, nothing calls
a model, and nothing imports the package: `sizes`, `sections`, `imports` and `constants`
parse source with `ast` and `tokenize`, `citations` and `ledger-tests` grep the ledger, and
`durations` reads a JUnit XML that `uv run pytest --junitxml=FILE` wrote earlier — the suite
itself is the one sustained job on this box and this script never starts it.
"""

from __future__ import annotations

import argparse
import ast
import io
import re
import sys
import tokenize
import xml.etree.ElementTree as ElementTree
from collections import Counter, defaultdict
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from itertools import pairwise
from pathlib import Path
from typing import Final

REPO: Final = Path(__file__).resolve().parents[1]
PACKAGE: Final = REPO / "src" / "litharness"
TESTS: Final = REPO / "tests"
LEDGER: Final = REPO / "plan" / "stage-0-decisions.md"


def _package_modules() -> list[Path]:
    return sorted(PACKAGE.rglob("*.py"))


def _relative(path: Path) -> str:
    return path.relative_to(REPO).as_posix()


def _module_name(path: Path) -> str:
    parts = list(path.relative_to(PACKAGE.parent).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _table(headers: Sequence[str], rows: Iterable[Sequence[object]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines.extend("| " + " | ".join(str(cell) for cell in row) + " |" for row in rows)
    return "\n".join(lines)


# --------------------------------------------------------------------------------- sizes


@dataclass(frozen=True, slots=True)
class Shape:
    path: str
    lines: int
    code: int
    docstring: int
    comment: int
    blank: int
    public: int
    private: int
    exported: int | None

    @property
    def prose_share(self) -> float:
        return (self.docstring + self.comment) / self.lines if self.lines else 0.0


def _docstring_lines(tree: ast.Module) -> set[int]:
    """Every physical line a docstring occupies: module, class and function docstrings."""
    lines: set[int] = set()
    nodes: list[ast.AST] = [tree]
    nodes.extend(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)
    )
    for node in nodes:
        body = getattr(node, "body", [])
        if not body:
            continue
        first = body[0]
        if (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        ):
            end = first.end_lineno or first.lineno
            lines.update(range(first.lineno, end + 1))
    return lines


def _comment_only_lines(source: str) -> set[int]:
    """Lines whose only token is a comment. A trailing comment on a code line is code."""
    comment_lines: set[int] = set()
    code_lines: set[int] = set()
    tokens = tokenize.generate_tokens(io.StringIO(source).readline)
    for token in tokens:
        if token.type == tokenize.COMMENT:
            comment_lines.add(token.start[0])
        elif token.type not in {
            tokenize.NL,
            tokenize.NEWLINE,
            tokenize.INDENT,
            tokenize.DEDENT,
            tokenize.ENDMARKER,
        }:
            code_lines.update(range(token.start[0], token.end[0] + 1))
    return comment_lines - code_lines


def _public_names(tree: ast.Module) -> tuple[list[str], list[str], int | None]:
    public: list[str] = []
    private: list[str] = []
    exported: int | None = None
    for node in tree.body:
        names: list[str] = []
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            names = [node.name]
        elif isinstance(node, ast.Assign):
            names = [target.id for target in node.targets if isinstance(target, ast.Name)]
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names = [node.target.id]
        for name in names:
            if name == "__all__":
                value = node.value if isinstance(node, ast.Assign | ast.AnnAssign) else None
                if isinstance(value, ast.List | ast.Tuple):
                    exported = len(value.elts)
                continue
            if name.startswith("__"):
                continue
            (private if name.startswith("_") else public).append(name)
    return public, private, exported


def shape_of(path: Path) -> Shape:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    physical = source.splitlines()
    docstrings = _docstring_lines(tree)
    comments = _comment_only_lines(source) - docstrings
    blank = {number for number, line in enumerate(physical, start=1) if not line.strip()}
    blank -= docstrings
    public, private, exported = _public_names(tree)
    total = len(physical)
    return Shape(
        path=_relative(path),
        lines=total,
        code=total - len(docstrings) - len(comments) - len(blank),
        docstring=len(docstrings),
        comment=len(comments),
        blank=len(blank),
        public=len(public),
        private=len(private),
        exported=exported,
    )


def cmd_sizes(args: argparse.Namespace) -> int:
    shapes = sorted((shape_of(path) for path in _package_modules()), key=lambda s: -s.lines)
    rows = [
        (
            shape.path.removeprefix("src/litharness/"),
            shape.lines,
            shape.code,
            shape.docstring,
            shape.comment,
            f"{shape.prose_share:.0%}",
            shape.public,
            shape.private,
            "" if shape.exported is None else shape.exported,
        )
        for shape in shapes
        if shape.lines >= args.min_lines
    ]
    print(
        _table(
            (
                "module",
                "lines",
                "code",
                "docstring",
                "comment",
                "prose",
                "public",
                "private",
                "__all__",
            ),
            rows,
        )
    )
    total = sum(shape.lines for shape in shapes)
    prose = sum(shape.docstring + shape.comment for shape in shapes)
    code = sum(shape.code for shape in shapes)
    print()
    print(
        f"{len(shapes)} modules, {total} lines: {code} code, {prose} docstring or comment "
        f"({prose / total:.0%}), {total - code - prose} blank."
    )
    top = shapes[:5]
    print(
        f"The five largest hold {sum(s.lines for s in top)} lines "
        f"({sum(s.lines for s in top) / total:.0%} of the package)."
    )
    return 0


# ------------------------------------------------------------------------------ sections


@dataclass(frozen=True, slots=True)
class Definition:
    name: str
    kind: str
    line: int
    end: int

    @property
    def span(self) -> int:
        return self.end - self.line + 1


def _definitions(tree: ast.Module) -> list[Definition]:
    found: list[Definition] = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            found.append(Definition(node.name, "def", node.lineno, node.end_lineno or node.lineno))
        elif isinstance(node, ast.ClassDef):
            found.append(
                Definition(node.name, "class", node.lineno, node.end_lineno or node.lineno)
            )
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    found.append(
                        Definition(target.id, "const", node.lineno, node.end_lineno or node.lineno)
                    )
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            found.append(
                Definition(node.target.id, "const", node.lineno, node.end_lineno or node.lineno)
            )
    return found


_SECTION = re.compile(r"^# -{3,}\s*(?P<title>.*?)\s*-*\s*$")


def _sections(source: str) -> list[tuple[int, str]]:
    """`# --- title ---` markers, the convention the larger modules already use."""
    found: list[tuple[int, str]] = []
    for number, line in enumerate(source.splitlines(), start=1):
        match = _SECTION.match(line)
        if match and match.group("title"):
            found.append((number, match.group("title").strip(" -")))
    return found


def _references(tree: ast.Module, names: set[str]) -> dict[str, set[str]]:
    """Which top-level names each top-level definition mentions, by bare name."""
    out: dict[str, set[str]] = {}
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            continue
        mentioned = {
            sub.id for sub in ast.walk(node) if isinstance(sub, ast.Name) and sub.id in names
        }
        mentioned.discard(node.name)
        out[node.name] = mentioned
    return out


def cmd_sections(args: argparse.Namespace) -> int:
    for module in args.modules:
        path = REPO / module
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        definitions = _definitions(tree)
        sections = _sections(source)
        print(f"## {module}")
        print()
        if sections:
            bounds = [*sections, (len(source.splitlines()) + 1, "")]
            rows = []
            for (start, title), (stop, _) in pairwise(bounds):
                inside = [d for d in definitions if start <= d.line < stop]
                rows.append(
                    (
                        title,
                        f"{start}-{stop - 1}",
                        stop - start,
                        len([d for d in inside if d.kind != "const"]),
                        len([d for d in inside if not d.name.startswith("_")]),
                    )
                )
            print(_table(("section", "lines", "span", "defs", "public"), rows))
        else:
            print("(no `# ---` section markers)")
        print()
        if args.defs:
            print(
                _table(
                    ("name", "kind", "lines", "span"),
                    [(d.name, d.kind, f"{d.line}-{d.end}", d.span) for d in definitions],
                )
            )
            print()
        if args.matrix and sections:
            names = {d.name for d in definitions}
            refs = _references(tree, names)
            bounds = [*sections, (len(source.splitlines()) + 1, "")]
            section_of: dict[str, str] = {}
            for (start, title), (stop, _) in pairwise(bounds):
                for d in definitions:
                    if start <= d.line < stop:
                        section_of[d.name] = title
            crossings: dict[tuple[str, str], list[str]] = defaultdict(list)
            for user, mentioned in refs.items():
                for name in sorted(mentioned):
                    here, there = section_of.get(user), section_of.get(name)
                    if here and there and here != there:
                        crossings[(here, there)].append(f"{user} -> {name}")
            print("cross-section references (a definition in one section naming one in another):")
            print()
            print(
                _table(
                    ("from section", "to section", "refs", "examples"),
                    [
                        (
                            a,
                            b,
                            len(items),
                            "; ".join(items[:4]) + (" ..." if len(items) > 4 else ""),
                        )
                        for (a, b), items in sorted(crossings.items(), key=lambda kv: -len(kv[1]))
                    ],
                )
            )
            print()
        if args.coupling:
            names = {d.name for d in definitions}
            refs = _references(tree, names)
            private = {name for name in names if name.startswith("_")}
            shared = {
                helper: sorted(user for user, mentioned in refs.items() if helper in mentioned)
                for helper in sorted(private)
            }
            rows = [
                (helper, len(users), ", ".join(users[:6]) + (" ..." if len(users) > 6 else ""))
                for helper, users in shared.items()
                if users
            ]
            rows.sort(key=lambda row: -int(row[1]))
            print("private helpers by number of top-level users:")
            print()
            print(_table(("helper", "users", "used by"), rows))
            print()
    return 0


# ------------------------------------------------------------------------ the import graph


def _imports(path: Path, known: set[str]) -> list[tuple[str, int]]:
    """The same resolution `tests/test_architecture.py::_imports` applies."""
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
            candidates = [f"{node.module}.{alias.name}" for alias in node.names]
            modules = [name for name in candidates if name in known]
            found.extend((name, node.lineno) for name in (modules or [node.module]))
    return found


def _graph() -> dict[str, set[str]]:
    modules = {_module_name(path): path for path in _package_modules()}
    known = set(modules)
    return {
        source: {
            target for target, _ in _imports(path, known) if target in known and target != source
        }
        for source, path in modules.items()
    }


def _layer(module: str) -> str:
    parts = module.split(".")
    if len(parts) < 2 or parts[1] in {"cli", "__main__"}:
        return "entrypoint"
    return parts[1]


def _levels(graph: dict[str, set[str]]) -> dict[str, int]:
    """Longest-path depth from the leaves: a module's level is one above its deepest import."""
    memo: dict[str, int] = {}

    def level(module: str) -> int:
        if module in memo:
            return memo[module]
        memo[module] = 0
        deps = [d for d in graph.get(module, set()) if d in graph]
        memo[module] = 1 + max((level(d) for d in deps), default=-1)
        return memo[module]

    for module in graph:
        level(module)
    return memo


def cmd_imports(args: argparse.Namespace) -> int:
    graph = _graph()
    importers: dict[str, set[str]] = defaultdict(set)
    for source, targets in graph.items():
        for target in targets:
            importers[target].add(source)

    edges = Counter((_layer(s), _layer(t)) for s, ts in graph.items() for t in ts)
    print("## Layer edges (source layer -> target layer, count of module edges)")
    print()
    print(_table(("from", "to", "edges"), sorted(edges.items(), key=lambda kv: -kv[1])))
    print()

    stated = {
        "domain never imports application": not any(
            _layer(t) == "application"
            for s, ts in graph.items()
            if _layer(s) == "domain"
            for t in ts
        ),
        "extraction imports gamesystem": "litharness.domain.gamesystem"
        in graph["litharness.domain.extraction"],
        "gamesystem never imports extraction": "litharness.domain.extraction"
        not in graph["litharness.domain.gamesystem"],
        "genre imports extraction": "litharness.domain.extraction"
        in graph["litharness.domain.genre"],
    }
    print("## Stated directions (CONTRIBUTING.md and the maintainability brief)")
    print()
    print(_table(("rule", "holds"), [(rule, "yes" if ok else "NO") for rule, ok in stated.items()]))
    print()

    domain = {
        m: {t for t in ts if _layer(t) == "domain"}
        for m, ts in graph.items()
        if _layer(m) == "domain"
    }
    levels = _levels(domain)
    print("## Domain modules by import depth (level 0 imports no other domain module)")
    print()
    by_level: dict[int, list[str]] = defaultdict(list)
    for module, level in levels.items():
        by_level[level].append(module.removeprefix("litharness.domain."))
    print(
        _table(
            ("level", "modules"),
            [(lvl, ", ".join(sorted(mods))) for lvl, mods in sorted(by_level.items())],
        )
    )
    print()

    print("## Domain modules: what each imports inside the domain, and who imports it")
    print()
    rows = []
    for module in sorted(domain):
        short = module.removeprefix("litharness.domain.")
        outs = sorted(t.removeprefix("litharness.domain.") for t in domain[module])
        ins = sorted(s.removeprefix("litharness.") for s in importers[module])
        rows.append((short, len(outs), ", ".join(outs) or "-", len(ins), ", ".join(ins) or "-"))
    rows.sort(key=lambda row: (-int(row[3]), row[0]))
    print(_table(("module", "out", "imports", "in", "imported by (src)"), rows))
    print()

    if args.tests:
        test_importers: Counter[str] = Counter()
        for path in sorted(TESTS.rglob("*.py")):
            text = path.read_text(encoding="utf-8")
            for module in graph:
                short = module.removeprefix("litharness.")
                if re.search(
                    rf"\blitharness\.{re.escape(short)}\b"
                    rf"|from litharness\.{re.escape(short.rsplit('.', 1)[0])} import "
                    rf"[^\n]*\b{re.escape(short.rsplit('.', 1)[-1])}\b",
                    text,
                ):
                    test_importers[module] += 1
        print("## Test modules importing each package module (top 25)")
        print()
        print(
            _table(
                ("module", "test modules"),
                [(m.removeprefix("litharness."), n) for m, n in test_importers.most_common(25)],
            )
        )
        print()
    return 0


# ------------------------------------------------------------------------------ constants


@dataclass(frozen=True, slots=True)
class Constant:
    module: str
    line: int
    name: str
    value: str
    numeric: bool
    reason: str


def _reason_above(lines: list[str], lineno: int) -> str:
    """The `#:` block immediately above an assignment, first line only."""
    block: list[str] = []
    index = lineno - 2
    while index >= 0 and lines[index].lstrip().startswith("#:"):
        block.insert(0, lines[index].lstrip()[2:].strip())
        index -= 1
    if block:
        return block[0]
    return ""


def _reason_below(body: list[ast.stmt], position: int) -> str:
    if position + 1 < len(body):
        nxt = body[position + 1]
        if (
            isinstance(nxt, ast.Expr)
            and isinstance(nxt.value, ast.Constant)
            and isinstance(nxt.value.value, str)
        ):
            return nxt.value.value.strip().splitlines()[0]
    return ""


def _is_numeric(node: ast.expr) -> bool:
    if isinstance(node, ast.Constant):
        return isinstance(node.value, int | float) and not isinstance(node.value, bool)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return _is_numeric(node.operand)
    if isinstance(node, ast.Tuple):
        return bool(node.elts) and all(_is_numeric(e) for e in node.elts)
    if isinstance(node, ast.BinOp):
        return _is_numeric(node.left) and _is_numeric(node.right)
    return False


def constants_of(path: Path) -> list[Constant]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    lines = source.splitlines()
    found: list[Constant] = []
    for position, node in enumerate(tree.body):
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
        ):
            name, value = node.targets[0].id, node.value
        elif (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.value is not None
        ):
            name, value = node.target.id, node.value
        else:
            continue
        if not re.fullmatch(r"_?[A-Z][A-Z0-9_]*", name):
            continue
        reason = _reason_above(lines, node.lineno) or _reason_below(tree.body, position)
        rendered = ast.get_source_segment(source, value) or ""
        rendered = " ".join(rendered.split())
        if len(rendered) > 40:
            rendered = rendered[:37] + "..."
        found.append(
            Constant(
                module=_relative(path).removeprefix("src/litharness/"),
                line=node.lineno,
                name=name,
                value=rendered,
                numeric=_is_numeric(value),
                reason=(reason[:90] + "...") if len(reason) > 90 else reason,
            )
        )
    return found


def _budget_rows() -> list[tuple[str, str, int]]:
    """The prompt budgets pinned in `tests/test_prompt_budget.py`, and conftest's one number."""
    rows: list[tuple[str, str, int]] = []
    for relative in ("tests/test_prompt_budget.py", "tests/conftest.py"):
        path = REPO / relative
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            target: ast.expr | None = None
            value: ast.expr | None = None
            if isinstance(node, ast.Assign) and len(node.targets) == 1:
                target, value = node.targets[0], node.value
            elif isinstance(node, ast.AnnAssign):
                target, value = node.target, node.value
            if not isinstance(target, ast.Name) or value is None:
                continue
            if not re.fullmatch(r"[A-Z][A-Z0-9_]*", target.id):
                continue
            if isinstance(value, ast.Dict):
                for key, item in zip(value.keys, value.values, strict=True):
                    if (
                        isinstance(key, ast.Constant)
                        and isinstance(item, ast.Constant)
                        and isinstance(item.value, int)
                    ):
                        rows.append((f"{relative}::{target.id}", str(key.value), item.value))
            elif (
                isinstance(value, ast.Constant)
                and isinstance(value.value, int)
                and not isinstance(value.value, bool)
            ):
                rows.append((f"{relative}::{target.id}", "", value.value))
    return rows


def cmd_constants(args: argparse.Namespace) -> int:
    found = [c for path in _package_modules() for c in constants_of(path)]
    numeric = [c for c in found if c.numeric]
    with_reason = [c for c in found if c.reason]
    print(
        f"{len(found)} module-level UPPER_CASE names in the package; {len(numeric)} numeric; "
        f"{len(with_reason)} carry a `#:` block or docstring saying why "
        f"({len([c for c in numeric if c.reason])} of the numeric ones)."
    )
    print()
    print("## Numeric constants (value and the first line of the reason)")
    print()
    print(
        _table(
            ("home", "name", "value", "why (first line)"),
            [(f"{c.module}:{c.line}", c.name, c.value, c.reason or "(none)") for c in numeric],
        )
    )
    print()
    if args.all:
        print("## Every other documented constant")
        print()
        print(
            _table(
                ("home", "name", "value", "why (first line)"),
                [
                    (f"{c.module}:{c.line}", c.name, c.value, c.reason)
                    for c in with_reason
                    if not c.numeric
                ],
            )
        )
        print()
    print("## Budgets pinned in the suite")
    print()
    print(_table(("home", "row", "value"), _budget_rows()))
    return 0


# ------------------------------------------------------------------------------ citations

_CITATION = re.compile(r"§\s?(?P<major>\d+)(?:\.(?P<minor>\d+))?")


@dataclass(frozen=True, slots=True)
class Citation:
    path: str
    line: int
    entry: str
    text: str


def _numbered_headings(document: Path) -> tuple[set[str], set[str]]:
    """Numbered headings in a planning document: `## N.` majors and `### N.M` minors.

    `PLAN.md` also numbers `1a` and its sub-sections `1a.1`; the letter is kept, since a
    docstring cites it the same way.
    """
    majors: set[str] = set()
    minors: set[str] = set()
    for line in document.read_text(encoding="utf-8").splitlines():
        if match := re.match(r"^## (\d+[a-z]?)[.\s]", line):
            majors.add(match.group(1))
        elif match := re.match(r"^### (\d+[a-z]?)\.(\d+)", line):
            minors.add(f"{match.group(1)}.{match.group(2)}")
    return majors, minors


def _ledger_entries() -> tuple[set[str], set[str]]:
    return _numbered_headings(LEDGER)


def _resolves(entry: str, majors: set[str], minors: set[str]) -> bool:
    major = entry.split(".")[0]
    if major not in majors:
        return False
    return "." not in entry or entry in minors


def _citations(paths: Iterable[Path]) -> Iterator[Citation]:
    for path in paths:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            for match in _CITATION.finditer(line):
                entry = match.group("major")
                if match.group("minor"):
                    entry += "." + match.group("minor")
                yield Citation(_relative(path), number, entry, line.strip())


def cmd_citations(args: argparse.Namespace) -> int:
    majors, minors = _ledger_entries()
    plan_majors, plan_minors = _numbered_headings(REPO / "PLAN.md")
    sites = list(_citations(_package_modules()))
    if args.tests:
        sites.extend(_citations(sorted(TESTS.rglob("*.py"))))
    entries = Counter(site.entry for site in sites)
    in_ledger = {e for e in entries if _resolves(e, majors, minors)}
    in_plan = {e for e in entries if _resolves(e, plan_majors, plan_minors)}
    unresolved = {e: n for e, n in entries.items() if e not in in_ledger and e not in in_plan}
    print(
        f"{len(sites)} citation sites, {len(entries)} distinct entries "
        f"({len([e for e in entries if '.' not in e])} majors, "
        f"{len([e for e in entries if '.' in e])} sub-entries). A `§` names either a stage-0 "
        f"entry or a PLAN.md section, and the text around it says which: "
        f"{len(in_ledger - in_plan)} entries resolve only in the ledger, "
        f"{len(in_plan - in_ledger)} "
        f"only in PLAN.md, {len(in_ledger & in_plan)} in both (ambiguous by number alone). "
        f"The ledger has {len(majors)} numbered entries and {len(minors)} numbered sub-entries; "
        f"PLAN.md has {len(plan_majors)} and {len(plan_minors)}."
    )
    print()
    print("## Cited entries with no heading in either document")
    print()
    rows = []
    for entry, count in sorted(unresolved.items(), key=lambda kv: (-kv[1], kv[0])):
        where = sorted(
            f"{s.path.removeprefix('src/litharness/')}:{s.line}" for s in sites if s.entry == entry
        )
        rows.append((entry, count, ", ".join(where[:4]) + (" ..." if len(where) > 4 else "")))
    print(_table(("entry", "sites", "where"), rows) if rows else "(none)")
    print()
    print("## Entries whose number exists in both documents (context decides)")
    print()
    both = sorted(
        in_ledger & in_plan, key=lambda e: (int(re.sub(r"[a-z]", "", e.split(".")[0])), e)
    )
    print(", ".join(f"§{e} ({entries[e]})" for e in both) or "(none)")
    print()
    print("## Most-cited entries")
    print()
    print(_table(("entry", "sites"), entries.most_common(args.top)))
    print()
    modules = Counter(site.path.removeprefix("src/litharness/") for site in sites)
    print("## Citation sites per module (top)")
    print()
    print(_table(("module", "sites"), modules.most_common(args.top)))
    if args.out:
        sample = _sample(sites, args.sample)
        out = Path(args.out)
        out.write_text(_render_sample(sample), encoding="utf-8")
        print()
        print(f"wrote {len(sample)} sample sites with context to {out}")
    return 0


def _sample(sites: Sequence[Citation], size: int) -> list[Citation]:
    """Every k-th site in (path, line) order: deterministic, spread across modules."""
    ordered = sorted(sites, key=lambda s: (s.path, s.line))
    if size <= 0 or size >= len(ordered):
        return list(ordered)
    step = len(ordered) / size
    return [ordered[int(i * step)] for i in range(size)]


def _render_sample(sample: Sequence[Citation]) -> str:
    chunks: list[str] = []
    for index, site in enumerate(sample, start=1):
        lines = (REPO / site.path).read_text(encoding="utf-8").splitlines()
        lo, hi = max(1, site.line - 3), min(len(lines), site.line + 3)
        context = "\n".join(f"{n:>5}: {lines[n - 1]}" for n in range(lo, hi + 1))
        chunks.append(
            f"### {index}. §{site.entry} at {site.path}:{site.line}\n\n```\n{context}\n```\n"
        )
    return "\n".join(chunks)


# --------------------------------------------------------------------------- ledger tests

_TEST_NAME = re.compile(r"\btest_[a-z0-9_]+")


def cmd_ledger_tests(args: argparse.Namespace) -> int:
    text = LEDGER.read_text(encoding="utf-8")
    backticked = set(re.findall(r"`(test_[a-z0-9_]+)`", text))
    every = set(_TEST_NAME.findall(text))
    definitions: dict[str, set[str]] = defaultdict(set)
    modules = {path.stem for path in TESTS.glob("test_*.py")}
    for path in sorted(TESTS.rglob("*.py")):
        for match in re.finditer(
            r"^\s*(?:async\s+)?def (test_[a-z0-9_]+)",
            path.read_text(encoding="utf-8"),
            re.MULTILINE,
        ):
            definitions[match.group(1)].add(path.stem)
    per_module: Counter[str] = Counter()
    unresolved: list[str] = []
    for name in sorted(every):
        if name in definitions:
            for module in definitions[name]:
                per_module[module] += 1
        elif name in modules:
            per_module[name] += 0
        else:
            unresolved.append(name)
    functions = [n for n in every if n in definitions]
    print(
        f"{len(every)} distinct `test_` tokens in the ledger: {len(functions)} name a test "
        f"function, {len([n for n in every if n in modules])} name a test module, "
        f"{len(unresolved)} resolve to nothing. "
        f"{len(backticked)} are backticked, which is the form `tests/test_architecture.py` checks."
    )
    print()
    print("## Ledger-cited test functions per test module")
    print()
    print(_table(("module", "cited functions"), [(m, n) for m, n in per_module.most_common() if n]))
    print()
    if unresolved:
        print("## Tokens that resolve to no function or module (checked only when backticked)")
        print()
        print(
            _table(
                ("token", "backticked"),
                [(n, "yes" if n in backticked else "no") for n in unresolved],
            )
        )
        print()
    if args.uncited:
        cited_modules = {m for m, n in per_module.items() if n} | {n for n in every if n in modules}
        print("## Test modules the ledger never names, by function or by file")
        print()
        print(", ".join(sorted(modules - cited_modules)))
    return 0


# ------------------------------------------------------------------------ duplicated helpers


def _normalised_body(source: str, node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    """A function's source with its docstring removed and whitespace collapsed, so two
    helpers that differ only in name, layout or the reason they give compare equal."""
    body = ast.get_source_segment(source, node) or ""
    first = node.body[0] if node.body else None
    if (
        isinstance(first, ast.Expr)
        and isinstance(first.value, ast.Constant)
        and isinstance(first.value.value, str)
    ):
        body = body.replace(ast.get_source_segment(source, first) or "", "", 1)
    body = re.sub(r"\s+", " ", body)
    return re.sub(r"^(async )?def \w+", "def X", body)


def cmd_helpers(args: argparse.Namespace) -> int:
    """Module-level helpers and fixtures defined under the same name in several test modules,
    and whether their bodies are actually the same."""
    seen: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    for path in sorted(TESTS.glob("test_*.py")):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        for node in tree.body:
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            if node.name.startswith("test_"):
                continue
            signature = ", ".join(arg.arg for arg in node.args.args)
            seen[node.name].append((path.stem, _normalised_body(source, node), signature))
    repeated = {name: items for name, items in seen.items() if len(items) >= args.min}
    rows = []
    identical_total = 0
    for name, items in sorted(repeated.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        by_body: dict[str, list[str]] = defaultdict(list)
        for stem, body, _ in items:
            by_body[body].append(stem)
        identical = [sorted(stems) for stems in by_body.values() if len(stems) > 1]
        identical_total += sum(len(group) - 1 for group in identical)
        rows.append(
            (
                name,
                len(items),
                len(by_body),
                "; ".join(", ".join(group) for group in identical) or "-",
                ", ".join(sorted({sig or "()" for _, _, sig in items})),
            )
        )
    print(
        f"{len(repeated)} helper or fixture names are defined in {args.min} or more test "
        f"modules; {identical_total} of those definitions are byte-for-byte repeats of another "
        f"(docstrings and layout aside). A name defined several times with distinct bodies is "
        f"several fixtures sharing a name, not a duplicate."
    )
    print()
    print(
        _table(
            ("name", "defs", "distinct bodies", "identical across", "signatures"),
            rows[: args.top],
        )
    )
    return 0


# ---------------------------------------------------------------------------------- stores

_STORE_MARKERS: Final = {
    "store": re.compile(r"\bSqliteStore\b|\bsqlite3\b|\.db\b"),
    "filesystem": re.compile(
        r"\btmp_path\b|\btmp_path_factory\b|\.write_text\(|\.write_bytes\(|\bopen\(|\bmkdir\("
    ),
    "subprocess": re.compile(r"\bsubprocess\b"),
    "cli": re.compile(r"\bmain\(\[|\bmain\(\s*\[|\bcli\.main\("),
}


@dataclass(slots=True)
class TestModuleProfile:
    module: str
    tests: int = 0
    hits: Counter[str] = field(default_factory=Counter)


def cmd_stores(args: argparse.Namespace) -> int:
    profiles: list[TestModuleProfile] = []
    for path in sorted(TESTS.glob("test_*.py")):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        profile = TestModuleProfile(path.stem)
        module_level = "\n".join(
            ast.get_source_segment(source, node) or ""
            for node in tree.body
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)
        )
        module_hits = {
            kind for kind, pattern in _STORE_MARKERS.items() if pattern.search(module_level)
        }
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name.startswith(
                "test_"
            ):
                profile.tests += 1
                body = ast.get_source_segment(source, node) or ""
                for kind, pattern in _STORE_MARKERS.items():
                    if pattern.search(body) or kind in module_hits:
                        profile.hits[kind] += 1
        profiles.append(profile)
    total = sum(p.tests for p in profiles)
    totals: Counter[str] = Counter()
    for profile in profiles:
        totals.update(profile.hits)
    print(
        f"{total} test functions in {len(profiles)} modules; touching a store: {totals['store']}, "
        f"the filesystem: {totals['filesystem']}, a subprocess: {totals['subprocess']}, "
        f"the CLI's `main`: {totals['cli']} (a test counts once per kind; a marker in a "
        f"module-level fixture or helper counts for every test in that module)."
    )
    print()
    rows = [
        (
            p.module,
            p.tests,
            p.hits["store"],
            p.hits["filesystem"],
            p.hits["subprocess"],
            p.hits["cli"],
        )
        for p in profiles
        if p.hits["store"] or p.hits["filesystem"] or p.hits["subprocess"] or p.hits["cli"]
    ]
    rows.sort(key=lambda row: (-int(row[2]) - int(row[3]), row[0]))
    print(_table(("module", "tests", "store", "filesystem", "subprocess", "cli"), rows[: args.top]))
    return 0


# ------------------------------------------------------------------------------- durations


def cmd_durations(args: argparse.Namespace) -> int:
    root = ElementTree.parse(args.junit).getroot()
    per_test: list[tuple[float, str, str]] = []
    per_module: dict[str, list[float]] = defaultdict(list)
    for case in root.iter("testcase"):
        module = (
            case.get("classname", "").split(".")[-1]
            if "." in case.get("classname", "")
            else case.get("classname", "")
        )
        classname = case.get("classname", "")
        module = (
            classname.split(".")[1] if classname.startswith("tests.") else classname.split(".")[0]
        )
        seconds = float(case.get("time", "0") or 0.0)
        per_test.append((seconds, module, case.get("name", "")))
        per_module[module].append(seconds)
    total = sum(s for s, _, _ in per_test)
    print(
        f"{len(per_test)} test cases in {len(per_module)} modules; {total:.0f}s of test time "
        f"summed "
        f"over cases (wall time is lower under xdist and is recorded beside this table)."
    )
    print()
    print("## Slowest tests")
    print()
    print(
        _table(
            ("seconds", "module", "test"),
            [(f"{s:.1f}", m, n) for s, m, n in sorted(per_test, reverse=True)[: args.top]],
        )
    )
    print()
    print("## Test time per module (top)")
    print()
    rows = [
        (m, len(ts), f"{sum(ts):.1f}", f"{max(ts):.1f}", f"{sum(ts) / total:.0%}")
        for m, ts in sorted(per_module.items(), key=lambda kv: -sum(kv[1]))
    ]
    print(_table(("module", "tests", "seconds", "slowest", "share"), rows[: args.top]))
    print()
    over = [(s, m, n) for s, m, n in per_test if s >= args.slow]
    print(
        f"{len(over)} tests take {args.slow:.0f}s or longer and hold "
        f"{sum(s for s, _, _ in over):.0f}s "
        f"({sum(s for s, _, _ in over) / total:.0%}) of the summed time."
    )
    return 0


# ------------------------------------------------------------------------------------ main

_LARGEST: Final = (
    "src/litharness/cli.py",
    "src/litharness/domain/extraction.py",
    "src/litharness/domain/gamesystem.py",
    "src/litharness/domain/worlds.py",
    "src/litharness/application/planner.py",
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sizes = sub.add_parser("sizes", help="lines, prose share and public names per module")
    sizes.add_argument("--min-lines", type=int, default=0)
    sizes.set_defaults(func=cmd_sizes)

    sections = sub.add_parser("sections", help="what the largest modules hold, by section marker")
    sections.add_argument("modules", nargs="*", default=list(_LARGEST))
    sections.add_argument("--defs", action="store_true", help="list every top-level definition")
    sections.add_argument("--coupling", action="store_true", help="private helpers by user count")
    sections.add_argument("--matrix", action="store_true", help="references across section markers")
    sections.set_defaults(func=cmd_sections)

    imports = sub.add_parser("imports", help="the import graph against the stated direction")
    imports.add_argument(
        "--tests", action="store_true", help="count test modules per package module"
    )
    imports.set_defaults(func=cmd_imports)

    constants = sub.add_parser("constants", help="documented constants and the pinned budgets")
    constants.add_argument("--all", action="store_true", help="include non-numeric constants")
    constants.set_defaults(func=cmd_constants)

    citations = sub.add_parser(
        "citations", help="§ citations in code against the ledger's headings"
    )
    citations.add_argument("--sample", type=int, default=50)
    citations.add_argument("--out", help="write the sample with context here")
    citations.add_argument("--top", type=int, default=15)
    citations.add_argument(
        "--tests", action="store_true", help="include tests/ as citation sources"
    )
    citations.set_defaults(func=cmd_citations)

    ledger = sub.add_parser("ledger-tests", help="test names the ledger cites, and where they live")
    ledger.add_argument("--uncited", action="store_true")
    ledger.set_defaults(func=cmd_ledger_tests)

    helpers = sub.add_parser(
        "helpers", help="test helpers defined under one name in several modules"
    )
    helpers.add_argument("--min", type=int, default=2, help="modules a name must appear in")
    helpers.add_argument("--top", type=int, default=40)
    helpers.set_defaults(func=cmd_helpers)

    stores = sub.add_parser(
        "stores", help="which tests touch a store, the filesystem, or a subprocess"
    )
    stores.add_argument("--top", type=int, default=40)
    stores.set_defaults(func=cmd_stores)

    durations = sub.add_parser(
        "durations", help="per-module and slowest-test durations from a JUnit XML"
    )
    durations.add_argument("junit")
    durations.add_argument("--top", type=int, default=20)
    durations.add_argument("--slow", type=float, default=5.0, help="threshold in seconds")
    durations.set_defaults(func=cmd_durations)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    # The survey is pasted into a Markdown file; a console code page that is not UTF-8 would
    # otherwise mangle every em dash a docstring's first line carries.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = build_parser().parse_args(argv)
    result: int = args.func(args)
    return result


if __name__ == "__main__":
    sys.exit(main())
