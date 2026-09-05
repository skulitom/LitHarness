"""Keep `RESEARCH.md` honest: every pointer on it resolves, and it says what it has not read.

`RESEARCH.md` is a map of the research record for a reader new to the repository. A map
decays in two ways: a pointer stops resolving (a ledger entry renumbered, a `FINDINGS.md`
moved), or the record grows past it. This script checks the first and reports the second, so
that updating the page is a queue to work through rather than a re-read of the ledger.

Usage (from the repository root):

    uv run python tools/research_overview.py          # check every pointer, list the queue
    uv run python tools/research_overview.py --quiet  # exit status only

Exit status is 1 when a pointer does not resolve, a state is outside the governance
vocabulary, or the coverage marker is missing; the two untriaged lists are informational.
Everything here is read-only over the working tree, asks git only which cited paths it
ignores (so the check sees what a clone sees), and imports nothing from the package.
`tests/test_research_overview.py` runs the same checks in the suite.

The one convention the page has to keep, because this script leans on it: a bare `§N` is
entry N of `plan/stage-0-decisions.md`, and a section of any other document carries that
document's file name immediately before it (`BRIEF.md §2`, `PLAN.md §1a.3`).
"""

from __future__ import annotations

import argparse
import io
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

REPO: Final = Path(__file__).resolve().parents[1]
OVERVIEW: Final = REPO / "RESEARCH.md"
LEDGER: Final = REPO / "plan" / "stage-0-decisions.md"
GOVERNANCE: Final = REPO / "research" / "quality-measurement" / "EPISTEMIC_GOVERNANCE.md"
RESEARCH: Final = REPO / "research"

#: Top-level directories a cited path may start with. A slash-separated token whose first
#: segment is none of these (`and/or`, `0/16`) is prose, not a pointer.
TRACKED_ROOTS: Final = frozenset(
    {"docs", "migrations", "plan", "research", "src", "tests", "tools"}
)
#: Local, gitignored roots. A pointer into one of these resolves on the box that wrote it and
#: on no clone, which is the shape of a claim with its evidence removed. This set is the
#: prose filter and the no-git fallback; `gitignored` asks git, which also knows the
#: ignored subtrees under tracked roots (`research/quality-measurement/derived/`).
LOCAL_ROOTS: Final = frozenset({"book-library", "dist", "exports", "runs"})
#: Files at the repository root the page may name without a directory in front.
ROOT_FILES: Final = re.compile(
    r"\b(README|PLAN|CLAUDE|AGENTS|CONTRIBUTING|RESEARCH|SECURITY|CODE_OF_CONDUCT)\.md\b"
)

#: A ledger entry number as the ledger writes it: `## 169`, `### 112.7a`, `### 107.9.1`.
_HEADING: Final = re.compile(r"^(#{2,4})\s+(\d+(?:\.\d+)*[a-z]?)(?=[.\s]|$)(.*)$", re.MULTILINE)
#: A section reference on the page, with the token in front of it so the file-name
#: convention can be applied.
_REFERENCE: Final = re.compile(r"(?:(?P<lead>\S+)\s+)?§(?P<number>\d+(?:\.\d+)*[a-z]?)")
#: The coverage marker at the top of the page.
_MARKER: Final = re.compile(
    r"<!--\s*research-overview:\s*ledger through §(?P<through>\d+);"
    r"\s*checked (?P<date>\d{4}-\d{2}-\d{2})\s*-->"
)
#: A slash-separated token: one or more directory segments, then a file name or nothing (a
#: directory cited with its trailing slash).
_PATH: Final = re.compile(r"(?<![\w/:.-])((?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]*)")
#: The research states, read from the governance document's own table rather than copied.
_STATE_ROW: Final = re.compile(r"^\|\s*`([A-Z]+)`\s*\|", re.MULTILINE)
_STATE_TOKEN: Final = re.compile(r"`([A-Z_]+)`")
_STATE_NONE: Final = "—"  # the em dash a row uses to say "a decision, not a claim"


@dataclass(frozen=True)
class Marker:
    through: int
    checked: str


@dataclass(frozen=True)
class Report:
    """What the audit found. `ok` is the exit status; the two untriaged lists are the queue."""

    broken_sections: tuple[str, ...]
    broken_paths: tuple[str, ...]
    local_paths: tuple[str, ...]
    invalid_states: tuple[str, ...]
    marker: Marker | None
    untriaged_entries: tuple[str, ...]
    unmentioned_registrations: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return (
            not self.broken_sections
            and not self.broken_paths
            and not self.local_paths
            and not self.invalid_states
            and self.marker is not None
        )


def ledger_entries(ledger: str) -> dict[str, str]:
    """Every numbered heading in the ledger, number to title, sub-sections included."""
    return {number: title.strip() for _, number, title in _HEADING.findall(ledger)}


def section_references(overview: str) -> list[str]:
    """The ledger entries the page cites. A `§` whose preceding token names another document
    (`BRIEF.md §2`, `PLAN.md §1a.3`) belongs to that document and is not returned."""
    found: list[str] = []
    for match in _REFERENCE.finditer(overview):
        lead = (match.group("lead") or "").rstrip(")]:,;'\"")
        if lead.lower().endswith(".md"):
            continue
        found.append(match.group("number"))
    return found


def path_references(overview: str) -> list[str]:
    """Every repo-relative path the page cites, root files included, in order of appearance."""
    found: list[str] = []
    for match in _PATH.finditer(overview):
        candidate = match.group(1)
        if overview[match.end() : match.end() + 1] == "*":
            continue  # a glob names a family of files, not one pointer
        head = candidate.split("/", 1)[0]
        if head in TRACKED_ROOTS or head in LOCAL_ROOTS:
            found.append(candidate)
    found.extend(match.group(0) for match in ROOT_FILES.finditer(overview))
    return found


def gitignored(repo: Path, paths: list[str]) -> frozenset[str]:
    """The cited paths git would not commit, asked of git itself, so the check sees what a
    clone sees. `Path.exists` cannot: a gitignored subtree under a tracked root
    (`research/quality-measurement/derived/`, excerpt-bearing by `.gitignore`) is present on
    the box that wrote the page and in no clone. The page cited one on 2026-09-05, the suite
    passed here and every CI job failed. Without git, or outside a repository, the answer is
    the empty set and the check degrades to the working tree, which is what it was."""
    if not paths:
        return frozenset()
    try:
        completed = subprocess.run(
            ["git", "-C", str(repo), "check-ignore", "-z", "--stdin"],
            input="".join(f"{path}\0" for path in paths).encode("utf-8"),
            capture_output=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return frozenset()
    if completed.returncode not in (0, 1):  # 0: some are ignored; 1: none; 128: no repository
        return frozenset()
    return frozenset(completed.stdout.decode("utf-8").split("\0")) - {""}


def state_cells(overview: str) -> list[str]:
    """The `state` cell of every row of every table that has a `state` column."""
    cells: list[str] = []
    column: int | None = None
    for line in overview.splitlines():
        if not line.startswith("|"):
            column = None
            continue
        parts = [part.strip() for part in line.strip().strip("|").split("|")]
        if column is None:
            if "state" in [part.lower() for part in parts]:
                column = [part.lower() for part in parts].index("state")
            continue
        if all(set(part) <= {"-", ":"} for part in parts):
            continue  # the separator row
        if column < len(parts):
            cells.append(parts[column])
    return cells


def governance_states(governance: str) -> frozenset[str]:
    """The claim states, as the governance document's table lists them."""
    return frozenset(_STATE_ROW.findall(governance))


def coverage_marker(overview: str) -> Marker | None:
    match = _MARKER.search(overview)
    if match is None:
        return None
    return Marker(through=int(match.group("through")), checked=match.group("date"))


def _invalid_states(cells: list[str], states: frozenset[str]) -> list[str]:
    invalid: list[str] = []
    for cell in cells:
        tokens = _STATE_TOKEN.findall(cell)
        foreign = [token for token in tokens if token not in states]
        if foreign:
            invalid.append(f"{cell!r}: not a governance state: {', '.join(foreign)}")
        elif not tokens and _STATE_NONE not in cell:
            invalid.append(f"{cell!r}: no state and no em dash")
    return invalid


def _registrations(research: Path) -> list[Path]:
    files = [
        *research.rglob("FINDINGS*.md"),
        *research.rglob("PREREG*.md"),
    ]
    return sorted(path for path in files if "__pycache__" not in path.parts)


def audit(
    overview: str | None = None,
    ledger: str | None = None,
    governance: str | None = None,
    repo: Path = REPO,
) -> Report:
    """Run every check over the page. The texts default to the working tree's files so a test
    can pass a fixture instead."""
    if overview is None:
        overview = (repo / OVERVIEW.name).read_text(encoding="utf-8")
    if ledger is None:
        ledger = (repo / LEDGER.relative_to(REPO)).read_text(encoding="utf-8")
    if governance is None:
        governance = (repo / GOVERNANCE.relative_to(REPO)).read_text(encoding="utf-8")

    entries = ledger_entries(ledger)
    broken_sections = tuple(
        f"§{number}"
        for number in dict.fromkeys(section_references(overview))
        if number not in entries
    )

    cited_paths = list(dict.fromkeys(path_references(overview)))
    ignored = gitignored(repo, cited_paths)
    broken_paths: list[str] = []
    local_paths: list[str] = []
    for cited in cited_paths:
        if cited.split("/", 1)[0] in LOCAL_ROOTS or cited in ignored:
            local_paths.append(cited)
        elif not (repo / cited).exists():
            broken_paths.append(cited)

    invalid_states = tuple(_invalid_states(state_cells(overview), governance_states(governance)))

    marker = coverage_marker(overview)
    untriaged: list[str] = []
    if marker is not None:
        for level, number, title in _HEADING.findall(ledger):
            if level == "##" and int(number.split(".")[0]) > marker.through:
                untriaged.append(f"§{number}{title}")

    unmentioned: list[str] = []
    research = repo / RESEARCH.relative_to(REPO)
    for path in _registrations(research):
        relative = path.relative_to(repo).as_posix()
        parent = path.parent.relative_to(repo).as_posix() + "/"
        if relative not in overview and parent not in overview:
            unmentioned.append(relative)

    return Report(
        broken_sections=broken_sections,
        broken_paths=tuple(broken_paths),
        local_paths=tuple(local_paths),
        invalid_states=invalid_states,
        marker=marker,
        untriaged_entries=tuple(untriaged),
        unmentioned_registrations=tuple(unmentioned),
    )


def render(report: Report) -> str:
    lines: list[str] = []
    if report.marker is None:
        lines.append(
            "no coverage marker: add `<!-- research-overview: ledger through §N; "
            "checked YYYY-MM-DD -->` near the top of RESEARCH.md"
        )
    else:
        lines.append(
            f"coverage marker: ledger through §{report.marker.through}, "
            f"checked {report.marker.checked}"
        )
    for title, items in (
        ("ledger entries cited that do not exist", report.broken_sections),
        ("paths cited that do not exist", report.broken_paths),
        ("paths cited that git ignores, present here and in no clone", report.local_paths),
        ("state cells outside the governance vocabulary", report.invalid_states),
    ):
        if items:
            lines.append(f"\n{title}:")
            lines.extend(f"  {item}" for item in items)
    lines.append("\nledger entries past the marker (the update queue):")
    lines.extend(f"  {item}" for item in report.untriaged_entries or ("none",))
    lines.append("\nregistrations and findings the page does not mention:")
    lines.extend(f"  {item}" for item in report.unmentioned_registrations or ("none",))
    lines.append("\nresult: " + ("ok" if report.ok else "pointers need repair"))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--quiet", action="store_true", help="print nothing; exit status only")
    args = parser.parse_args(argv)
    report = audit()
    if not args.quiet:
        if isinstance(sys.stdout, io.TextIOWrapper):
            sys.stdout.reconfigure(encoding="utf-8")  # the page and the ledger are UTF-8
        print(render(report))
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
