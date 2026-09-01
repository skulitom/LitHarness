"""The exploratory panel column: labelling, containment, the two ceilings, and the arithmetic.

What this file pins: that the provenance sentence exists once, says what the pilot's evidence
actually is, and is stamped on the file and on every block inside it; that a house session is
built by the backtest's own cell builder and carries an arm tag and pair id no registered cell
can collide with; that the file never names a verdict or a score and refuses to be written if it
ever does; that a paid run refuses without BOTH ceilings expressed and refuses again when the
estimate or the session count crosses one, spending nothing on either path; that the ledger is
read after every session and a crossing stops the run and says so on the face of the file; and
that the file-space and slot-space arithmetic are each computed in exactly one direction, so a
positional artifact stays visible instead of being folded away.

No model is called anywhere here: every elicitor is a fake, as `test_bt_arms.py` and
`test_bt_backtest.py` do. What this file does not establish: anything about how ten real
personas answer on real chapters — that is the coordinator's operator-gated read, and this
column's evidence status is exactly what `PROVENANCE` says it is.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(
    0, str(Path(__file__).resolve().parent.parent / "research" / "sim-readership-backtest")
)

module = pytest.importorskip("house_panel", reason="research module; imported by path")
backtest = pytest.importorskip("backtest", reason="research module; imported by path")
population = pytest.importorskip("population", reason="research module; imported by path")

REPO = Path(__file__).resolve().parent.parent


def _chapter(path: Path, *, stem: str, paragraphs: int = 6, words: int = 40) -> Path:
    """A chapter file whose tokens are globally numbered, so two files never collide."""
    body = "\n\n".join(
        " ".join(f"{stem}{index * words + k}" for k in range(words)) for index in range(paragraphs)
    )
    path.write_text(body, encoding="utf-8")
    return path


def _sides(tmp_path: Path) -> tuple[Any, Any]:
    a = module.read_side(
        _chapter(tmp_path / "a.md", stem="alpha"), label="draw 3", title="", author=""
    )
    b = module.read_side(
        _chapter(tmp_path / "b.md", stem="beta"), label="draw 2", title="", author=""
    )
    return a, b


class FakeElicitor:
    """Answers every stage-2 call from a fixed script; charges what it is told to charge."""

    def __init__(self, answers: list[str] | None = None, usd: float = 0.0) -> None:
        self.answers = answers or ['{"continue": "A", "reason": ""}']
        self.usd = usd
        self.calls: list[dict[str, Any]] = []
        self.transport_failures = 0
        self.api_calls = 0
        self.replayed = 0

    def ask_raw(
        self, system: str, turns: list[dict[str, Any]], *, schema: dict[str, object] | None,
        max_tokens: int, tag: dict[str, Any], sample: int = 0, model: str | None = None,
    ) -> dict[str, Any]:
        self.calls.append({"system": system, "turns": turns, "tag": tag, "sample": sample})
        self.api_calls += 1
        if schema is None:
            return {"text": "two openings differed in what happens on the page"}
        return {"text": self.answers[(len(self.calls) - 1) // 2 % len(self.answers)]}

    def spend(self) -> dict[str, float]:
        return {"equivalent_usd": self.usd}


# ------------------------------------------------------------------------------ the labelling


def test_the_provenance_sentence_names_the_pilot_status_it_is_supposed_to_name() -> None:
    """The sentence is the whole containment of an unlicensed instrument; it must say so.

    A softened provenance is exactly how pilot-grade evidence becomes a gate three months
    later, so each clause the direction note required is asserted by substring rather than
    trusted to a reviewer's memory.
    """
    sentence = module.PROVENANCE
    assert sentence.startswith("EXPLORATORY")
    assert "0.789" in sentence, "the descriptive number the panel's only evidence is"
    assert "pilot n" in sentence
    assert "unsettled" in sentence, "the control corners never settled"
    assert "no validity licence" in sentence
    assert "gate nothing" in sentence and "never reach a prompt" in sentence


def test_every_block_of_the_result_carries_the_exploratory_label(tmp_path: Path) -> None:
    """A number lifted out of this file on its own still says what it is."""
    side_a, side_b = _sides(tmp_path)
    planned = module.plan_sessions(side_a, side_b, population.POPULATION[:2])
    result = module.build_result(
        side_a, side_b, planned, [], model="m", ledger={"equivalent_usd": 0.0},
        max_usd=1.0, max_sessions=99, aborted=False,
    )
    assert result[module.LABEL] is True
    assert result["provenance"] == module.PROVENANCE
    for block in ("shares", "positional", "reason_codes"):
        assert result[block][module.LABEL] is True, f"{block} must carry its own label"


# ------------------------------------------------------------------------------ the containment


def test_no_result_field_may_name_a_verdict_or_a_score(tmp_path: Path) -> None:
    """The dual-verdict lesson, enforced on the bytes rather than on a remembered schema."""
    side_a, side_b = _sides(tmp_path)
    planned = module.plan_sessions(side_a, side_b, population.POPULATION[:1])
    result = module.build_result(
        side_a, side_b, planned, [], model="m", ledger={"equivalent_usd": 0.0},
        max_usd=1.0, max_sessions=99, aborted=False,
    )
    assert module.forbidden_keys(result) == []

    out = tmp_path / "panel.json"
    module.write_result(result, out)
    assert json.loads(out.read_text(encoding="utf-8"))[module.LABEL] is True

    for smuggled in ({"verdict": "A"}, {"nested": [{"quality_score": 1}]},
                     {"verdict_registered": "A"}):
        with pytest.raises(module.ForbiddenOutput, match="no verdict and no score"):
            module.write_result({**result, **smuggled}, tmp_path / "smuggled.json")
    assert not (tmp_path / "smuggled.json").exists(), "a refused write leaves no file"


def test_the_result_is_a_json_file_and_never_a_store(tmp_path: Path) -> None:
    for destination in ("serial.db", "roster.sqlite", "panel.txt"):
        with pytest.raises(module.ForbiddenOutput):
            module.check_destination(tmp_path / destination)
    module.check_destination(tmp_path / "panel.json")


def test_nothing_under_src_litharness_references_this_column() -> None:
    """Research side, structurally: the generation package may not import it or name it."""
    offenders = [
        str(path.relative_to(REPO))
        for path in (REPO / "src" / "litharness").rglob("*.py")
        if "house_panel" in path.read_text(encoding="utf-8")
    ]
    assert offenders == [], f"src/litharness must not reference the panel column: {offenders}"


def test_the_column_opens_no_database_and_imports_no_package_code() -> None:
    """It reads two files and writes one json; a store connection would be a new power."""
    source = (
        REPO / "research" / "sim-readership-backtest" / "house_panel.py"
    ).read_text(encoding="utf-8")
    assert "import sqlite3" not in source
    assert "sqlite3.connect" not in source
    assert "import litharness" not in source and "from litharness" not in source


# --------------------------------------------------------------------------------- the sessions


def test_a_house_pair_is_ten_personas_by_two_orders_under_an_unmistakable_tag(
    tmp_path: Path,
) -> None:
    side_a, side_b = _sides(tmp_path)
    planned = module.plan_sessions(side_a, side_b)
    assert len(planned) == len(population.POPULATION) * 2 == 20
    assert {s.spec.arm for s in planned} == {module.ARM}
    assert {s.spec.arm for s in planned}.isdisjoint({"C", "P", *backtest.CONTROL_ARMS})
    pair_ids = {s.spec.pair_id for s in planned}
    assert len(pair_ids) == 1
    assert next(iter(pair_ids)).startswith(module.PAIR_PREFIX)
    assert {s.spec.order for s in planned} == {0, 1}
    assert planned[0].text_a == side_a.text and planned[0].text_b == side_b.text
    swapped = next(s for s in planned if s.spec.order == 1)
    assert swapped.text_a == side_b.text, "order 1 shows file B first and nothing else changes"


def test_a_house_cell_cannot_share_a_cache_key_with_a_registered_cell(tmp_path: Path) -> None:
    """`_sample_index` folds pair_id, persona and order — not the arm — so the prefix is the rail.

    A collision would mean a registered arm's bought draw replaying as ours, or ours polluting
    a registered cache. The prefix makes the fold's first field differ by construction.
    """
    side_a, side_b = _sides(tmp_path)
    house = module.plan_sessions(side_a, side_b)[0]
    registered = backtest.arms.SessionSpec(
        pair_id="0123456789abcdef", arm="C", persona_id=house.spec.persona_id,
        order=house.spec.order, excerpt_a_digest="x", excerpt_b_digest="y",
    )
    assert backtest.arms.build_session(house.spec, "s", "a", "b")["sample"] != (
        backtest.arms.build_session(registered, "s", "a", "b")["sample"]
    )


def test_two_identical_drafts_are_refused_by_name_rather_than_answered(tmp_path: Path) -> None:
    """Draw N and draw N-1 of one listing can come back identical; twenty coins is not a read."""
    _chapter(tmp_path / "same-a.md", stem="same")
    _chapter(tmp_path / "same-b.md", stem="same")
    side_a = module.read_side(tmp_path / "same-a.md", label="a", title="", author="")
    side_b = module.read_side(tmp_path / "same-b.md", label="b", title="", author="")
    with pytest.raises(backtest.DegenerateStimuli, match="byte-identical"):
        module.plan_sessions(side_a, side_b)


def test_an_empty_file_is_refused_at_read_time(tmp_path: Path) -> None:
    (tmp_path / "empty.md").write_text("   \n\n  ", encoding="utf-8")
    with pytest.raises(module.ForbiddenOutput, match="not a stimulus"):
        module.read_side(tmp_path / "empty.md", label="a", title="", author="")


def test_blinding_strips_the_identity_a_house_chapter_carries(tmp_path: Path) -> None:
    """Our exports open with a heading and may name the listing; both must leave the stimulus."""
    path = tmp_path / "ch.md"
    path.write_text(
        "Chapter 7: The Vault\n\n"
        "The Unkillable Exploit was what they called it, by Ana Ferreira.\n\n"
        "He counted the doors again and found one more than yesterday.",
        encoding="utf-8",
    )
    side = module.read_side(
        path, label="draw 3", title="The Unkillable Exploit", author="Ana Ferreira"
    )
    assert "Chapter 7" not in side.text
    assert "Unkillable Exploit" not in side.text
    assert "Ferreira" not in side.text
    assert "counted the doors again" in side.text, "blinding never touches the prose"
    assert side.removed["title"] >= 1 and side.removed["chapter_heading"] >= 1


def test_the_side_labels_are_recorded_and_never_shown_to_a_persona(tmp_path: Path) -> None:
    """"draw 3" in a prompt would tell a reader which text it is supposed to prefer."""
    side_a, side_b = _sides(tmp_path)
    planned = module.plan_sessions(side_a, side_b, population.POPULATION[:2])
    shown = "\n".join(
        s.system + s.text_a + s.text_b for s in planned
    )
    assert "draw 3" not in shown and "draw 2" not in shown
    assert side_a.as_record()["label"] == "draw 3", "the label survives in the result file"
    assert "text" not in side_a.as_record(), "the stimulus text never lands in the result"


# --------------------------------------------------------------------------------- the ceilings


def test_a_paid_run_refuses_without_both_ceilings_and_spends_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv(module.ENV_MAX_USD, raising=False)
    monkeypatch.delenv(module.ENV_MAX_SESSIONS, raising=False)
    _chapter(tmp_path / "a.md", stem="alpha")
    _chapter(tmp_path / "b.md", stem="beta")
    out = tmp_path / "panel.json"

    def refuse_to_construct(cache: Path, model: str) -> Any:
        raise AssertionError("an elicitor was constructed on a refusal path")

    base = ["--a", str(tmp_path / "a.md"), "--b", str(tmp_path / "b.md"), "--out", str(out)]
    for argv in (base, [*base, "--max-usd", "5"], [*base, "--max-sessions", "20"]):
        assert module.main(argv, elicitor_factory=refuse_to_construct) == 1
        err = capsys.readouterr().err
        assert "no " in err and "ceiling" in err
        assert "nothing was spent" in err
    assert not out.exists()


def test_either_ceiling_may_be_expressed_through_the_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(module.ENV_MAX_USD, "5")
    monkeypatch.setenv(module.ENV_MAX_SESSIONS, "20")
    _chapter(tmp_path / "a.md", stem="alpha")
    _chapter(tmp_path / "b.md", stem="beta")
    out = tmp_path / "panel.json"
    fake = FakeElicitor()
    assert module.main(
        ["--a", str(tmp_path / "a.md"), "--b", str(tmp_path / "b.md"), "--out", str(out)],
        elicitor_factory=lambda cache, model: fake,
    ) == 0
    assert out.is_file()


def test_an_estimate_or_a_session_count_over_a_ceiling_refuses_before_the_first_call(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _chapter(tmp_path / "a.md", stem="alpha")
    _chapter(tmp_path / "b.md", stem="beta")
    out = tmp_path / "panel.json"

    def refuse_to_construct(cache: Path, model: str) -> Any:
        raise AssertionError("an elicitor was constructed on a refusal path")

    base = ["--a", str(tmp_path / "a.md"), "--b", str(tmp_path / "b.md"), "--out", str(out)]
    assert module.main(
        [*base, "--max-usd", "5", "--max-sessions", "4"], elicitor_factory=refuse_to_construct
    ) == 1
    assert "exceed the --max-sessions ceiling" in capsys.readouterr().err
    assert module.main(
        [*base, "--max-usd", "0.01", "--max-sessions", "20"],
        elicitor_factory=refuse_to_construct,
    ) == 1
    assert "exceeds the --max-usd ceiling" in capsys.readouterr().err
    assert not out.exists(), "no refusal path leaves a result behind"


def test_a_dry_run_plans_and_prices_and_constructs_no_elicitor(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _chapter(tmp_path / "a.md", stem="alpha")
    _chapter(tmp_path / "b.md", stem="beta")

    def refuse_to_construct(cache: Path, model: str) -> Any:
        raise AssertionError("the dry run constructed an elicitor")

    assert module.main(
        ["--a", str(tmp_path / "a.md"), "--b", str(tmp_path / "b.md"), "--dry-run"],
        elicitor_factory=refuse_to_construct,
    ) == 0
    captured = capsys.readouterr()
    assert "20 session(s)" in captured.out
    assert "$1.49" in captured.out, "20 x $0.0747, the arithmetic a person checks by hand"
    assert module.PROVENANCE in captured.out
    assert "nothing spent" in captured.err


def test_the_ledger_is_read_after_every_session_and_a_crossing_stops_the_run(
    tmp_path: Path,
) -> None:
    side_a, side_b = _sides(tmp_path)
    planned = module.plan_sessions(side_a, side_b)
    fake = FakeElicitor(usd=9.0)
    ledger: dict[str, float] = {}
    answers, aborted = module.run_panel(
        fake, planned, model="m", ledger=ledger, max_usd=2.0
    )
    assert aborted is True
    assert len(answers) == 1, "the ceiling stops further sessions after the current one"
    assert ledger["equivalent_usd"] == 9.0


def test_a_run_stopped_at_the_ceiling_says_so_on_the_face_of_the_file(tmp_path: Path) -> None:
    side_a, side_b = _sides(tmp_path)
    planned = module.plan_sessions(side_a, side_b)
    result = module.build_result(
        side_a, side_b, planned, [], model="m", ledger={"equivalent_usd": 9.0},
        max_usd=2.0, max_sessions=20, aborted=True,
    )
    assert result["sessions"]["aborted_at_ceiling"] is True
    assert result["sessions"]["planned"] == 20 and result["sessions"]["returned"] == 0
    assert result["sessions"]["unanswered"] == 20
    assert result["cost"]["ledger_usd"] == 9.0


# ------------------------------------------------------------------------------- the arithmetic


def _answers(*rows: tuple[str, int, str]) -> list[Any]:
    return [
        module.PanelAnswer(persona_id=pid, order=order, choice=choice, reason="")
        for pid, order, choice in rows
    ]


def test_slot_answers_become_file_answers_by_the_rotation_and_nothing_else() -> None:
    assert module.PanelAnswer("p", 0, "A", "").file_choice == "file_a"
    assert module.PanelAnswer("p", 0, "B", "").file_choice == "file_b"
    assert module.PanelAnswer("p", 1, "A", "").file_choice == "file_b"
    assert module.PanelAnswer("p", 1, "B", "").file_choice == "file_a"
    assert module.PanelAnswer("p", 1, "neither", "").file_choice == "neither"


def test_shares_are_hand_checkable_and_every_persona_appears() -> None:
    answers = _answers(
        ("grinder", 0, "A"), ("grinder", 1, "A"),      # file_a, file_b
        ("numbers", 0, "A"), ("numbers", 1, "B"),      # file_a, file_a
        ("comfort", 0, "neither"), ("comfort", 1, "neither"),
    )
    table = module.shares(answers)
    aggregate = table["aggregate"]
    assert aggregate["returned"] == 6
    assert (aggregate["file_a"], aggregate["file_b"], aggregate["neither"]) == (3, 1, 2)
    assert aggregate["decided"] == 4
    assert aggregate["share_of_returned"] == {"file_a": 0.5, "file_b": 0.1667, "neither": 0.3333}
    assert aggregate["share_of_decided"] == {"file_a": 0.75, "file_b": 0.25}
    assert set(table["by_persona"]) == {p.persona_id for p in population.POPULATION}
    assert table["by_persona"]["numbers"]["share_of_decided"]["file_a"] == 1.0
    assert table["by_persona"]["skimmer"]["returned"] == 0, "a silent persona is reported at zero"
    assert table["by_persona"]["skimmer"]["share_of_decided"]["file_a"] == 0.0


def test_the_positional_split_is_reported_in_slot_space_where_the_artifact_lives() -> None:
    """A panel answering on position must be visible; file space would cancel it away."""
    answers = _answers(
        ("grinder", 0, "A"), ("grinder", 1, "A"),
        ("numbers", 0, "A"), ("numbers", 1, "B"),
        ("comfort", 0, "neither"),
    )
    split = module.positional(answers)
    assert split["decided"] == 4
    assert split["first_slot"] == 3
    assert split["first_slot_share"] == 0.75
    assert split["by_order"]["0"] == {"decided": 2, "first_slot": 2, "first_slot_share": 1.0}
    assert split["by_order"]["1"] == {"decided": 2, "first_slot": 1, "first_slot_share": 0.5}
    file_shares = module.shares(answers)["aggregate"]["share_of_decided"]
    assert file_shares == {"file_a": 0.75, "file_b": 0.25}


def test_reason_codes_are_counted_over_the_closed_list_with_every_code_present() -> None:
    answers = [
        module.PanelAnswer("grinder", 0, "A", "slow-start"),
        module.PanelAnswer("numbers", 1, "B", "slow-start"),
        module.PanelAnswer("comfort", 0, "neither", ""),
    ]
    counts = module.reason_counts(answers)["counts"]
    assert set(counts) == set(backtest.arms.REASON_CODES)
    assert counts["slow-start"] == 2 and counts[""] == 1 and counts["confusing"] == 0


def test_a_whole_run_through_main_writes_one_readable_file_and_no_paid_call(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """End to end on a fake: twenty sessions, forty calls, one json, nothing bought.

    The scripted answer is always slot A, which is the clearest possible positional artifact:
    file space splits 0.5/0.5 while the first-slot share is 1.0, and the file shows both.
    """
    _chapter(tmp_path / "a.md", stem="alpha")
    _chapter(tmp_path / "b.md", stem="beta")
    out = tmp_path / "panel.json"
    fake = FakeElicitor()
    assert module.main(
        [
            "--a", str(tmp_path / "a.md"), "--b", str(tmp_path / "b.md"), "--out", str(out),
            "--label-a", "draw 3", "--label-b", "draw 2",
            "--max-usd", "5", "--max-sessions", "20", "--cache", str(tmp_path / "cache.jsonl"),
        ],
        elicitor_factory=lambda cache, model: fake,
    ) == 0
    assert len(fake.calls) == 40, "twenty sessions, two turns each"
    assert not (tmp_path / "cache.jsonl").exists(), "the fake bought nothing and cached nothing"

    result = json.loads(out.read_text(encoding="utf-8"))
    assert result["provenance"] == module.PROVENANCE
    assert module.forbidden_keys(result) == []
    assert result["panel"]["arm"] == module.ARM
    assert result["panel"]["population_digest"] == population.population_digest()
    assert result["sessions"] == {
        "planned": 20, "returned": 20, "unanswered": 0, "aborted_at_ceiling": False,
        "transport_failures": 0, "fresh_calls": 40, "replayed_calls": 0,
    }
    assert result["shares"]["aggregate"]["share_of_returned"] == {
        "file_a": 0.5, "file_b": 0.5, "neither": 0.0
    }
    assert result["positional"]["first_slot_share"] == 1.0, "the artifact stays visible"
    assert result["inputs"]["file_a"]["label"] == "draw 3"
    assert result["cost"]["estimated_usd"] == 1.494
    assert result["cost"]["max_usd"] == 5.0 and result["cost"]["max_sessions"] == 20
    out_text = capsys.readouterr().out
    assert module.PROVENANCE in out_text
    assert "nothing gates on it" in out_text
