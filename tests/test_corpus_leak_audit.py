"""The one exemption in the leak audit, pinned so it cannot widen quietly.

`corpus_leak_audit.py` is a CI step on a public repository whose measurements run over corpora it
does not own. It went red on 2026-08-20 against two of its **own** GPU thermal traces: `nvidia-smi`
output has no spaces, so `content.split()` counted one "word" per line and read a 5,837-line CSV
as a 5,837-word excerpt.

Deleting the files would not have fixed it — the audit reads every blob any commit ever pointed
at, which is the property that makes it worth having — so the classifier had to learn the
difference between telemetry and prose. **An exemption in a leak audit is a dangerous thing to
add**, so these tests exist to hold it to the shape that makes it safe: a telemetry field is a
number, a flag, or a short enumerated token, and prose cannot be encoded that way without ceasing
to be prose.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
RESEARCH = REPO / "research" / "quality-measurement"
PACKAGE = REPO / "src" / "litharness"

audit = pytest.importorskip(
    "corpus_leak_audit", reason="research module; needs the quality-measurement path"
)

#: A real trace's shape: one long header and thousands of data rows. The header's field names
#: exceed the field-width cap and are *expected* to fail — one row in several thousand, which is
#: what the 98% tolerance is for. A five-line fixture would put the header at 20% and read as
#: prose, which is correct behaviour and the reason this fixture is realistic rather than tidy.
TELEMETRY = (
    "elapsed_s,temperature.gpu,power.draw,clocks_event_reasons.hw_thermal_slowdown\n"
    + "".join(f"{i * 10}.0,{44 + i % 20},{31.85 + i},Not Active\n" for i in range(200))
)

PROSE = (
    "He walked in, and she left without a word.\n"
    "The archive was cold, the lamps unlit, and nobody had signed the register.\n"
    "She had been waiting, he realised, for most of an hour.\n"
    "Outside, the rain had started again, and the road would be impassable by dark.\n"
)


def test_machine_telemetry_is_recognised():
    assert audit.is_delimited_telemetry(TELEMETRY)


def test_prose_with_commas_is_not_telemetry():
    """The obvious smuggling route: prose has commas, so prose has "fields".

    It fails on field *width* — a clause is three or more words and a telemetry field is at most
    two — which is the property that makes the exemption safe rather than merely narrow.
    """
    assert not audit.is_delimited_telemetry(PROSE)


def test_prose_without_commas_is_not_telemetry():
    """A line with no delimiter is not counted toward the telemetry share, so it drags the ratio
    down rather than being waved through."""
    lines = "\n".join(
        "Zorian walked through the gates of Cyoria once more and the loop began again."
        for _ in range(50)
    )
    assert not audit.is_delimited_telemetry(lines)


def test_prose_appended_to_telemetry_is_not_telemetry():
    """The real attack: hide an excerpt at the end of a legitimate trace.

    The 98% tolerance exists for a CSV header and a trailing partial line from a killed process,
    and it has to be tight enough that a passage cannot ride in under it.
    """
    assert not audit.is_delimited_telemetry(TELEMETRY + PROSE)


def test_a_short_file_is_never_telemetry():
    """Under three rows there is not enough shape to tell, so the answer is no and it gets
    scanned as prose."""
    assert not audit.is_delimited_telemetry("a,b\n1,2\n")


def test_the_exemption_is_reported_rather_than_silent():
    """A check that quietly excludes material is the shape of every proxy this project has had to
    refute, so the audit prints the count and names the files."""
    source = (RESEARCH / "corpus_leak_audit.py").read_text(encoding="utf-8")
    assert "skipped as delimited telemetry" in source


def test_the_whole_file_prose_threshold_still_bites():
    """The exemption must not have disabled the check it sits inside."""
    long_prose = " ".join(f"word{i}" for i in range(audit.WHOLE_FILE_WORDS + 10))
    found, unwalked = audit.scan_blob("results/notes.txt", long_prose)
    assert found and found[0][0] == "<whole file>"
    assert not unwalked


def test_project_authored_forge_exemptions_are_exact_paths_and_fields():
    for suffix in "abcde":
        path = f"reader-book-forge-{suffix}/forge.json"
        assert audit.is_ours_path_field(path, ".candidates[0].premise")
        assert audit.is_ours_path_field(path, ".candidates[1].world.rule")
        assert audit.is_ours_path_field(path, ".candidates[2].seed.records[3].value")
        assert audit.is_ours_path_field(
            path, ".candidates[1].screen.answers.regular.expect_next"
        )
        assert not audit.is_ours_path_field(path, ".source_excerpt")
        assert not audit.is_ours_path_field(
            path, ".candidates[1].screen.answers.regular.source_excerpt"
        )
    assert not audit.is_ours_path_field(
        "reader-book-forge-f/forge.json", ".candidates[0].premise"
    )
    assert frozenset({"reader-book-forge/refused.txt"}) == audit.OURS_EXACT_PATHS


# --------------------------------------------------------------- RS1, the half nothing checked

#: Names that mark a corpus *source*, for the string half of the RS1 check below.
#:
#: **Narrow and honest about it**, which is `directors.prose_axes_named`'s own trade: a
#: paraphrase gets through and no list fixes that. What it buys is that the sources this project
#: actually reads cannot be named in package code by somebody who did not know the rule.
#:
#: `mirrorbench` was in this tuple and came out: it names a sibling *repository* and an
#: interpreter, not a corpus, and it fired on `domain/policy.py` quoting that project's finding
#: in an exception message. A marker that refuses a legitimate line is measuring the wrong thing,
#: which is `roster.machinery_words`' recorded trade in a second place.
CORPUS_MARKERS: tuple[str, ...] = (
    "corpora/",
    ".parquet",
    "royalroad",
    "quality-measurement",
    "human-excerpts",
    "mother of learning",
    "toll.db",
    "toll-scenes",
)


def _package_sources() -> list[tuple[Path, ast.Module]]:
    return [
        (path, ast.parse(path.read_text(encoding="utf-8")))
        for path in sorted(PACKAGE.rglob("*.py"))
    ]


def _docstring_nodes(tree: ast.Module) -> set[int]:
    """Every string constant that is a docstring, by identity.

    Docstrings are excluded from the string check because **the rule is about code, not about
    prose**: `domain/rivals.py`'s own docstring explains at length which corpora it does not
    read, and a check that refused it would refuse the module most careful about the rule.
    """
    found: set[int] = set()
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if not isinstance(
            node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        ) or not body:
            continue
        first = body[0]
        if (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        ):
            found.add(id(first.value))
    return found


def _research_imports(tree: ast.Module, forbidden: frozenset[str]) -> list[str]:
    """Every import in `tree` whose top-level name is a research module."""
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or ""]
        else:
            continue
        found.extend(name for name in names if name.split(".")[0] in forbidden)
    return found


def _corpus_strings(tree: ast.Module) -> list[tuple[int, str]]:
    """Every non-docstring string literal in `tree` that names a corpus source."""
    docstrings = _docstring_nodes(tree)
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if (
            not isinstance(node, ast.Constant)
            or not isinstance(node.value, str)
            or id(node) in docstrings
        ):
            continue
        lowered = node.value.casefold()
        found.extend((node.lineno, marker) for marker in CORPUS_MARKERS if marker in lowered)
    return found


#: A module that breaks RS1 both ways, so the two checks below can be shown to bite.
#:
#: **`BRIEF.md` §2 Pass 5 records a control that cannot fail as its own failure mode**, and two
#: checks that scan a tree which happens to be clean are exactly that shape: they would pass
#: identically if the scanning logic returned nothing at all. This fixture is what separates
#: "the package is clean" from "the check is empty".
OFFENDING_MODULE = '''"""A module whose docstring may mention corpora/ freely, and does."""

import corpus_io

SHARD = "research/quality-measurement/corpora/royalroad-03.parquet"
'''


def test_the_package_checks_can_fail():
    tree = ast.parse(OFFENDING_MODULE)
    assert _research_imports(tree, frozenset({"corpus_io"})) == ["corpus_io"]
    assert [marker for _, marker in _corpus_strings(tree)] == [
        "corpora/",
        ".parquet",
        "royalroad",
        "quality-measurement",
    ]
    # And the docstring exemption does not swallow the literal that matters.
    assert ast.get_docstring(tree) is not None


def test_nothing_under_the_package_imports_a_research_module():
    """RS1's generation-side half, **which four places in this repository said was checked here
    and which nothing checked until now.**

    `CLAUDE.md`, `plan/dossier-voice-direction.md`, `research/quality-measurement/rival_pool.py`
    and `domain/rivals.py` each say some version of *"nothing under `src/litharness/` references
    a corpus; `tests/test_corpus_leak_audit.py` checks"*. It did not: every test in this file
    pins the telemetry exemption, and `corpus_leak_audit.py` never opens a `.py` file at all —
    its scan set is `.json`, `.jsonl`, `.csv` and `.txt`. So the rail was a claim in prose the
    code did not keep, which is §146.7's own shape, found the same way.

    **The import half is derived rather than listed**, so it cannot rot: the forbidden names are
    whatever modules exist under `research/quality-measurement/` today. A research module added
    tomorrow is covered without anybody remembering to add it.

    Why it matters more now than it did: `domain/voice.py` computes the arithmetic the
    measurement side distils a market voice with, and the two sides deliberately share one
    implementation so a descriptor is a target our own prose can be read against. That makes the
    package a place where somebody could reasonably reach for the corpus, and it is exactly the
    reach RS1 forbids — the numbers cross, the text does not.
    """
    forbidden = {path.stem for path in RESEARCH.glob("*.py")}
    assert forbidden, "no research modules found; this check would pass vacuously"
    offenders: list[str] = []
    for path, tree in _package_sources():
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            for name in names:
                if name.split(".")[0] in forbidden:
                    offenders.append(f"{path.relative_to(REPO).as_posix()}: imports {name}")
    assert not offenders, "the package imports the measurement side:\n" + "\n".join(offenders)


def test_no_package_code_names_a_corpus_source():
    """The string half: no corpus path, shard, or source name in package **code**.

    Docstrings are exempt and the exemption is the point — see `_docstring_nodes`. What is left
    is every string literal a running process could use: a path it opens, a filename it builds,
    a marker it matches on.

    Stated with the check rather than after it: this catches a source *named*, not a source
    *reached*. A package module handed an open file object by a caller passes, and so it should
    — RS1 is a rule about what the package may know, and the composition root is `cli.py`.
    """
    offenders: list[str] = []
    for path, tree in _package_sources():
        docstrings = _docstring_nodes(tree)
        for node in ast.walk(tree):
            if (
                not isinstance(node, ast.Constant)
                or not isinstance(node.value, str)
                or id(node) in docstrings
            ):
                continue
            lowered = node.value.casefold()
            for marker in CORPUS_MARKERS:
                if marker in lowered:
                    offenders.append(
                        f"{path.relative_to(REPO).as_posix()}:{node.lineno} names {marker!r}"
                    )
    assert not offenders, "package code names a corpus source:\n" + "\n".join(offenders)
