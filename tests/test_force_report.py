"""The reporter's own behaviour, pinned on constructed inputs.

These tests cover the three pure functions of `force_report`: how `_track_row` turns a report
dict (or its absence) into a table row, how `render` lays rows out, and how `reassemble`
recombines a stored artifact through `force_harness` without touching the per-family readings.

What they pin: the refusal to summarise a surveyed-but-unscored track into NOT_RUN, the
fallback chain for a row's status, the `-` placeholders, the rounding of the spend column,
the 16-character cell truncation, and every `reassemble` state (SKIPPED, CURRENT,
WOULD_CHANGE, REWRITTEN) including the two-family minimum and the split-family refusal.

What they do not establish: that any *verdict* is correct — combining and headline logic live
in `force_harness` and are tested there; that the committed files under `results/` are
consistent (`collect` and `main` are out of scope, as is anything reading the real results
directory, the corpus, a database, or a model).

Hermetic: no subprocess, no network, no calls. Every file read happens inside `tmp_path`.
"""

from __future__ import annotations

import json

import pytest

force_report = pytest.importorskip(
    "force_report",
    reason="research module; needs the quality-measurement directory on the path",
)


# ------------------------------------------------------------------------------ _track_row


def test_a_track_with_no_result_file_and_no_survey_is_not_run(tmp_path, monkeypatch):
    monkeypatch.setattr(force_report, "RESULTS", tmp_path)
    assert force_report._track_row("F2", None) == {
        "track": "F2",
        "status": "NOT_RUN",
        "detail": "no result file",
    }


def test_a_surveyed_unscored_track_carries_the_surveys_own_verdict_and_pairs(
    tmp_path, monkeypatch
):
    """A substrate that was surveyed but never scored is a different state from never touched."""
    survey = {"price": {"verdict": "SURVEY_CLEAN"}, "pairs": 42}
    (tmp_path / "force-f1-survey.json").write_text(json.dumps(survey), encoding="utf-8")
    monkeypatch.setattr(force_report, "RESULTS", tmp_path)
    assert force_report._track_row("F1", None) == {
        "track": "F1",
        "status": "SURVEY_ONLY",
        "detail": "SURVEY_CLEAN",
        "pairs": 42,
    }


def test_a_survey_without_a_price_block_falls_back_to_the_default_detail(
    tmp_path, monkeypatch
):
    (tmp_path / "force-fx-survey.json").write_text(json.dumps({"pairs": 7}), encoding="utf-8")
    monkeypatch.setattr(force_report, "RESULTS", tmp_path)
    row = force_report._track_row("FX", None)
    assert row["status"] == "SURVEY_ONLY"
    assert row["detail"] == "surveyed, not scored"
    assert row["pairs"] == 7


def test_the_row_status_prefers_force_verdict_then_status_then_read():
    """Each step of the fallback chain, exercised on the side where it actually decides."""
    with_verdict = {"force_verdict": "PASS", "status": "FAIL"}
    assert force_report._track_row("F1", with_verdict)["status"] == "PASS"
    without_verdict = {"status": "DEGRADED_STRATUM"}
    assert force_report._track_row("F1", without_verdict)["status"] == "DEGRADED_STRATUM"
    with_neither: dict[str, object] = {}
    assert force_report._track_row("F1", with_neither)["status"] == "READ"



def test_the_row_takes_binding_statuses_from_combined_and_marks_missing_strata():
    report = {
        "force_verdict": "PASS",
        "pairs": 30,
        "per_family": {
            "qwen3:14b": {"status": "READ"},
            "gemma3:12b": {"status": "READ"},
        },
        "combined": {"aligned": {"status": "PASS"}},
    }
    row = force_report._track_row("F1", report)
    # Families are sorted whatever order the report stored them in.
    assert row["families"] == ["gemma3:12b", "qwen3:14b"]
    assert row["pairs"] == 30
    assert row["aligned"] == "PASS"
    # `crossed` ran nowhere in this report, and the row says so rather than inventing a state.
    assert row["crossed"] == "-"
    assert row["controls"] == {}
    assert "spent_usd" not in row


def test_controls_are_keyed_by_family_and_only_named_where_they_ran():
    report = {
        "per_family": {
            "qwen3:14b": {
                "placebo_identical": {"status": "READ"},
                "rewhitespace_sham": {"status": "READ"},
            },
            "gemma3:12b": {"placebo_identical": {"status": "READ"}},
        },
    }
    row = force_report._track_row("F1", report)
    # The sham did not run on the second family, and no row pretends it did.
    assert row["controls"] == {
        "qwen3:14b/placebo_identical": "READ",
        "qwen3:14b/rewhitespace_sham": "READ",
        "gemma3:12b/placebo_identical": "READ",
    }


def test_spent_usd_sums_every_readable_family_ledger_and_rounds_to_cents():
    report = {
        "per_family": {
            "qwen3:14b": {"ledger": {"spent_usd": 1.004}},
            "gemma3:12b": {"ledger": {"spent_usd": 0.003}},
        },
    }
    assert force_report._track_row("F1", report)["spent_usd"] == 1.01


def test_a_ledger_without_a_spend_contributes_nothing_and_no_key_when_none_do():
    report = {
        "per_family": {
            "qwen3:14b": {"ledger": {"spent_usd": None}},
            "gemma3:12b": {},
        },
    }
    row = force_report._track_row("F1", report)
    assert "spent_usd" not in row


# ---------------------------------------------------------------------------------- render


def test_render_draws_the_header_one_line_per_track_and_the_reading_last():
    summary = {
        "tracks": [
            {
                "track": "F1",
                "status": "PASS",
                "aligned": "PASS",
                "crossed": "FAIL",
                "families": ["gemma3:12b", "qwen3:14b"],
            },
            {"track": "F2", "status": "NOT_RUN"},
        ],
        "reading": "the reading",
    }
    # Both data rows derived by hand from the format widths: track in 5, every other cell in 17.
    expected = "\n".join([
        "track status            aligned           crossed           families",
        "-" * 86,
        "F1    PASS              PASS              FAIL              gemma3:12b, qwen3:14b",
        "F2    NOT_RUN           -                 -                 -",
        "",
        "the reading",
    ])
    assert force_report.render(summary) == expected

def test_render_puts_each_control_on_an_indented_line_under_its_own_row():
    summary = {
        "tracks": [
            {
                "track": "F1",
                "status": "READ",
                "controls": {"qwen3:14b/placebo_identical": "READ"},
                "families": [],
            },
            {"track": "F2", "status": "READ", "controls": {}, "families": []},
        ],
        "reading": "r",
    }
    lines = force_report.render(summary).splitlines()
    f1_index = lines.index(next(line for line in lines if line.startswith("F1")))
    assert lines[f1_index + 1] == "      control qwen3:14b/placebo_identical: READ"
    # A row with no controls adds no control lines: F1's control line is followed by F2's row,
    # and the blank spacer comes only before the reading.
    assert lines[f1_index + 2] == "F2    READ              -                 -                 -"
    assert lines[-2] == ""
    assert lines[-1] == "r"


def test_render_prints_spend_as_equivalent_quota():
    summary = {
        "tracks": [{"track": "F3", "status": "READ", "spent_usd": 1.26, "families": []}],
        "reading": "r",
    }
    assert "      spend: $1.26 equivalent quota" in force_report.render(summary).splitlines()


def test_render_truncates_cells_longer_than_sixteen_characters():
    """A 16-character status fits whole; a 17th character is cut, not wrapped."""
    sixteen = "ABCDEFGHIJKLMNOP"
    summary = {
        "tracks": [
            {"track": "F1", "status": sixteen, "families": []},
            {"track": "F2", "status": sixteen + "Q", "families": []},
        ],
        "reading": "r",
    }
    lines = force_report.render(summary).splitlines()
    assert lines[2].startswith("F1    " + sixteen)
    # The truncated cell keeps its column width, so the families column stays aligned.
    assert lines[3].startswith("F2    " + sixteen.ljust(17))



# ------------------------------------------------------------------------------ reassemble


def _two_family_artifact() -> dict:
    return {
        "per_family": {
            "qwen3:14b": {
                "status": "READ",
                "aligned": {"stratum": "aligned", "status": "PASS"},
                "crossed": {"stratum": "crossed", "status": "PASS"},
                "crossed_loose": {"stratum": "crossed_loose", "status": "DEGRADED_STRATUM"},
            },
            "gemma3:12b": {
                "status": "READ",
                "aligned": {"stratum": "aligned", "status": "PASS"},
                "crossed": {"stratum": "crossed", "status": "PASS"},
            },
        },
    }


def test_reassemble_would_change_a_stale_headline_without_touching_the_file(tmp_path):
    report = _two_family_artifact()
    report["force_verdict"] = "FAIL"
    report["combined"] = {"aligned": {"status": "FAIL"}, "crossed": {"status": "FAIL"}}
    path = tmp_path / "force-f1-haiku.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    row = force_report.reassemble(path, apply=False)
    assert row["file"] == "force-f1-haiku.json"
    assert row["changed"] is True
    assert row["status"] == "WOULD_CHANGE"
    # Derived by hand: both families PASS both binding strata, while the diagnostic stratum --
    # unread by the second family -- refuses rather than joining the pass.
    assert row["now"] == {
        "force_verdict": "PASS",
        "combined": {
            "aligned": "PASS",
            "crossed": "PASS",
            "crossed_loose": "NOT_SCREENABLE",
        },
    }
    assert row["was"] == {
        "force_verdict": "FAIL",
        "combined": {"aligned": "FAIL", "crossed": "FAIL"},
    }
    assert json.loads(path.read_text(encoding="utf-8")) == report


def test_reassemble_apply_rewrites_the_headline_and_records_the_before_and_after(tmp_path):
    report = _two_family_artifact()
    report["force_verdict"] = "FAIL"
    report["combined"] = {"aligned": {"status": "FAIL"}}
    path = tmp_path / "force-f1-haiku.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    row = force_report.reassemble(path, apply=True)
    assert row["status"] == "REWRITTEN"
    rewritten = json.loads(path.read_text(encoding="utf-8"))
    assert rewritten["force_verdict"] == "PASS"
    assert rewritten["combined"]["aligned"]["status"] == "PASS"
    assert rewritten["combined"]["crossed"]["status"] == "PASS"
    # The per-family readings stay exactly as the track wrote them.
    assert rewritten["per_family"] == report["per_family"]
    assert rewritten["per_family"]["qwen3:14b"]["crossed_loose"]["status"] == "DEGRADED_STRATUM"
    (history,) = rewritten["reassembled"]
    assert history["why"] == (
        "combining rules changed after this run was scored; per-family readings untouched"
    )
    assert history["was"] == {"force_verdict": "FAIL", "combined": {"aligned": "FAIL"}}
    assert history["now"]["force_verdict"] == "PASS"


def test_reassemble_apply_appends_to_history_that_was_written_as_a_single_object(tmp_path):
    report = _two_family_artifact()
    report["force_verdict"] = "FAIL"
    report["combined"] = {}
    report["reassembled"] = {"why": "older correction"}
    path = tmp_path / "force-f1-haiku.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    force_report.reassemble(path, apply=True)
    history = json.loads(path.read_text(encoding="utf-8"))["reassembled"]
    assert [entry["why"] for entry in history] == [
        "older correction",
        "combining rules changed after this run was scored; per-family readings untouched",
    ]


def test_reassemble_reports_current_and_leaves_a_matching_artifact_alone(tmp_path):
    report = _two_family_artifact()
    report["force_verdict"] = "PASS"
    report["combined"] = {
        "aligned": {"status": "PASS"},
        "crossed": {"status": "PASS"},
        "crossed_loose": {"status": "NOT_SCREENABLE"},
    }
    path = tmp_path / "force-f1-haiku.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    row = force_report.reassemble(path, apply=False)
    assert row["changed"] is False
    assert row["status"] == "CURRENT"
    assert "reassembled" not in json.loads(path.read_text(encoding="utf-8"))


def test_reassemble_skips_an_artifact_with_no_per_family_block_and_leaves_it_alone(tmp_path):
    path = tmp_path / "force-fm-dryrun.json"
    original = {"force_verdict": "PASS", "combined": {"aligned": {"status": "PASS"}}}
    path.write_text(json.dumps(original), encoding="utf-8")
    row = force_report.reassemble(path, apply=True)
    assert row["status"] == "SKIPPED"
    assert row["why"] == "no per_family block to read"
    assert json.loads(path.read_text(encoding="utf-8")) == original


def test_reassemble_skips_a_withdrawn_artifact_whose_headline_is_stale(tmp_path):
    """The retraction is a decision; recomputing over it would soften a VOID into a verdict."""
    report = _two_family_artifact()
    report["WITHDRAWN"] = True
    report["force_verdict"] = "VOID"
    path = tmp_path / "force-f2-partial.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    row = force_report.reassemble(path, apply=True)
    assert row["status"] == "SKIPPED"
    assert "WITHDRAWN" in row["why"]
    assert "reassembled" not in json.loads(path.read_text(encoding="utf-8"))


def test_one_family_passing_a_stratum_alone_still_combines_to_not_screenable(tmp_path):
    """The two-family minimum: one PASS is trivially unanimous, so it certifies nothing."""
    report = {
        "per_family": {
            "qwen3:14b": {
                "status": "READ",
                "aligned": {"stratum": "aligned", "status": "PASS"},
            },
        },
        "force_verdict": "PASS",
        "combined": {"aligned": {"status": "PASS"}},
    }
    path = tmp_path / "force-f1-haiku.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    row = force_report.reassemble(path, apply=False)
    assert row["changed"] is True
    assert row["now"]["combined"] == {"aligned": "NOT_SCREENABLE", "crossed": "NOT_SCREENABLE"}
    assert row["now"]["force_verdict"] == "NOT_SCREENABLE"


def test_a_split_stratum_fails_the_headline_rather_than_passing_either_family(tmp_path):
    """One family reads the force and one does not: neither reading becomes the force's."""
    report = {
        "per_family": {
            "qwen3:14b": {
                "status": "READ",
                "aligned": {"stratum": "aligned", "status": "PASS"},
                "crossed": {"stratum": "crossed", "status": "PASS"},
            },
            "gemma3:12b": {
                "status": "READ",
                "aligned": {"stratum": "aligned", "status": "FAIL"},
                "crossed": {"stratum": "crossed", "status": "FAIL"},
            },
        },
        "force_verdict": "PASS",
        "combined": {"aligned": {"status": "PASS"}},
    }
    path = tmp_path / "force-f1-haiku.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    row = force_report.reassemble(path, apply=False)
    assert row["changed"] is True
    assert row["now"]["combined"]["aligned"] == "SPLIT_FAMILY"
    # The crossed statuses are the same PASS/FAIL split, so that stratum splits too.
    assert row["now"]["combined"]["crossed"] == "SPLIT_FAMILY"
    # A refusal anywhere outranks everything: a split stratum is not a pass, so the headline fails
    # rather than reporting either family's reading as the force's.
    assert row["now"]["force_verdict"] == "FAIL"


def test_render_of_a_summary_with_no_tracks_is_header_and_reading_alone():
    rendered = force_report.render({"tracks": [], "reading": "nothing ran"})
    assert rendered == "\n".join([
        "track status            aligned           crossed           families",
        "-" * 86,
        "",
        "nothing ran",
    ])


