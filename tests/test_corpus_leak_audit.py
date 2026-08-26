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

from pathlib import Path

import pytest

RESEARCH = Path(__file__).resolve().parents[1] / "research" / "quality-measurement"

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
