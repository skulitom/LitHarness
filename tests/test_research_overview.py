"""`RESEARCH.md` is a map of the research record, and a map whose pointers have stopped
resolving is worse than no map: it reads as current because it sits at the repository root.
These tests run `tools/research_overview.py`'s checks in the suite, so a renumbered ledger
entry, a moved `FINDINGS.md` or a state outside the governance vocabulary fails the build.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

from tools import research_overview as overview

_LEDGER = """
## 12. A job carries its input
### 12.1 The blocker
## 169 A status line printed a machine id
### 112.7a The protagonist's second role
"""

_GOVERNANCE = """
| `CONJECTURE` | a thought |
| `REGISTERED` | committed before the result |
| `OBSERVED` | an artifact exists |
"""


def test_the_overview_cites_only_ledger_entries_that_exist() -> None:
    report = overview.audit()
    assert not report.broken_sections, "RESEARCH.md cites ledger entries that do not exist:\n" + (
        "\n".join(report.broken_sections)
    )


def test_the_overview_cites_only_paths_in_the_repository() -> None:
    report = overview.audit()
    assert not report.broken_paths, "RESEARCH.md cites paths that do not exist:\n" + "\n".join(
        report.broken_paths
    )
    assert not report.local_paths, "RESEARCH.md cites gitignored local artifacts:\n" + "\n".join(
        report.local_paths
    )


def test_the_overview_states_every_claim_in_the_governance_vocabulary() -> None:
    report = overview.audit()
    assert not report.invalid_states, "\n".join(report.invalid_states)


def test_the_overview_carries_its_coverage_marker() -> None:
    report = overview.audit()
    assert report.marker is not None
    assert report.marker.through > 0


def test_the_overview_restates_no_count_another_document_owns() -> None:
    """`BRIEF.md` §2 owns the refutation count, the suite owns the test count and the ledger
    owns the decision count; the page points at them and never carries a number of its own."""
    text = overview.OVERVIEW.read_text(encoding="utf-8")
    restated = re.findall(r"\b\d+\s+(?:proxies|tests|decisions)\b", text)
    assert not restated, f"RESEARCH.md restates a count another document owns: {restated}"


def test_a_section_reference_belongs_to_the_document_named_in_front_of_it() -> None:
    page = "See §12 and §12.1, BRIEF.md §2, (PLAN.md §17), [feasibility.md](x/y.md) §4.3."
    assert overview.section_references(page) == ["12", "12.1"]


def test_ledger_headings_are_read_at_every_depth_and_without_a_trailing_period() -> None:
    entries = overview.ledger_entries(_LEDGER)
    assert set(entries) == {"12", "12.1", "169", "112.7a"}


def test_a_slash_in_prose_is_not_a_path_and_a_local_root_is_flagged() -> None:
    page = "followers 0/16 and/or plan/reader-read-2.md, runs/pilots/x.json, README.md"
    assert overview.path_references(page) == [
        "plan/reader-read-2.md",
        "runs/pilots/x.json",
        "README.md",
    ]


def test_a_state_cell_must_carry_a_governance_state_or_an_em_dash() -> None:
    page = "\n".join(
        [
            "| result | state | home |",
            "| --- | --- | --- |",
            "| a | `OBSERVED` | §12 |",
            "| b | `DEAD` | §12 |",
            "| c | — | §12 |",
            "| d | withdrawn | §12 |",
        ]
    )
    report = overview.audit(overview=page, ledger=_LEDGER, governance=_GOVERNANCE)
    assert len(report.invalid_states) == 2
    assert "DEAD" in report.invalid_states[0]
    assert "no state" in report.invalid_states[1]


def test_the_queue_lists_entries_past_the_marker_and_unmentioned_registrations() -> None:
    page = "<!-- research-overview: ledger through §12; checked 2026-09-05 -->\n§12"
    report = overview.audit(overview=page, ledger=_LEDGER, governance=_GOVERNANCE)
    assert report.ok
    assert report.untriaged_entries == ("§169 A status line printed a machine id",)
    assert "research/sim-readership-backtest/PREREG.md" in report.unmentioned_registrations


@pytest.mark.parametrize("record", ["RUNBOOK.md", "registration.json", "RESULTS.md", "REPORT.md"])
def test_an_experiment_folder_without_findings_or_prereg_is_a_registration(
    tmp_path: Path, record: str
) -> None:
    """An experiment folder that registers and reports only in these files was invisible to the
    queue while it read `FINDINGS*.md` and `PREREG*.md` alone. Such a folder is listed once, by
    its path, until the page mentions the folder or a file in it."""
    for name in ("unread-20260915", "indexed-20260916", "cited-20260917"):
        folder = tmp_path / "research" / "quality-measurement" / name
        folder.mkdir(parents=True)
        (folder / record).write_text("x", encoding="utf-8")
    page = (
        "research/quality-measurement/indexed-20260916/ and "
        f"research/quality-measurement/cited-20260917/{record}"
    )
    report = overview.audit(overview=page, ledger=_LEDGER, governance=_GOVERNANCE, repo=tmp_path)
    assert report.unmentioned_registrations == ("research/quality-measurement/unread-20260915/",)


def test_a_folder_with_a_prereg_is_listed_by_its_files_and_a_nested_run_by_its_own_path(
    tmp_path: Path,
) -> None:
    """A folder holding `PREREG.md` beside `RUNBOOK.md` and `RESULTS.md` stays one entry per
    `PREREG`/`FINDINGS` file, as before. A retry registered in its own folder inside an
    experiment is its own registration, so a page citing only the outer folder leaves it queued."""
    research = tmp_path / "research" / "quality-measurement"
    both = research / "prose-order"
    both.mkdir(parents=True)
    for name in ("PREREG.md", "RUNBOOK.md", "RESULTS.md"):
        (both / name).write_text("x", encoding="utf-8")
    nested = research / "challenge-20260922" / "recovery"
    nested.mkdir(parents=True)
    for folder in (nested.parent, nested):
        (folder / "registration.json").write_text("{}", encoding="utf-8")
    page = "research/quality-measurement/challenge-20260922/"
    report = overview.audit(overview=page, ledger=_LEDGER, governance=_GOVERNANCE, repo=tmp_path)
    assert report.unmentioned_registrations == (
        "research/quality-measurement/challenge-20260922/recovery/",
        "research/quality-measurement/prose-order/PREREG.md",
    )


def test_a_nested_run_does_not_mention_its_parent_and_the_roots_are_not_experiments(
    tmp_path: Path,
) -> None:
    """Citing only a retry's file inside an experiment mentions the retry, not the experiment
    around it; and the research roots, which hold the shared runbooks, are never listed."""
    research = tmp_path / "research" / "quality-measurement"
    nested = research / "seeding-20260910" / "action-followup"
    nested.mkdir(parents=True)
    for folder in (nested.parent, nested, research, research.parent):
        (folder / "RUNBOOK.md").write_text("x", encoding="utf-8")
    page = "(research/quality-measurement/seeding-20260910/action-followup/RUNBOOK.md)"
    report = overview.audit(overview=page, ledger=_LEDGER, governance=_GOVERNANCE, repo=tmp_path)
    assert report.unmentioned_registrations == ("research/quality-measurement/seeding-20260910/",)


def test_a_gitignored_path_under_a_tracked_root_is_local_not_present() -> None:
    """`research/quality-measurement/derived/` is gitignored (excerpt-bearing, `.gitignore`), so
    a file there satisfies `Path.exists` on the box that wrote the page and in no clone. The
    page cited one on 2026-09-05: the suite passed locally and every CI job failed. The audit
    asks git, so the pointer is a local artifact here too, whether or not the file exists."""
    page = "research/quality-measurement/derived/never-written.txt"
    report = overview.audit(overview=page, ledger=_LEDGER, governance=_GOVERNANCE)
    assert report.local_paths == (page,)
    assert report.broken_paths == ()


def test_the_gitignore_question_degrades_to_the_working_tree_without_git(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A tarball export has no git and no repository. The audit then checks the working tree
    as it did before this question was asked, instead of failing to run at all."""

    def no_git(*args: object, **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        raise OSError("git: not found")

    monkeypatch.setattr(overview.subprocess, "run", no_git)
    assert overview.gitignored(overview.REPO, ["runs/x.json"]) == frozenset()

    def no_repository(*args: object, **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess(
            args, 128, stdout=b"", stderr=b"fatal: not a git repository"
        )

    monkeypatch.setattr(overview.subprocess, "run", no_repository)
    assert overview.gitignored(overview.REPO, ["runs/x.json"]) == frozenset()
