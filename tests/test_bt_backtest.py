"""The staged driver's refusals and its one remap, checked without calls or corpora.

What this file pins: the member-space remap (the driver's own arithmetic — a slot-space
aggregate would be positional nonsense), the confirmatory filter, the probe-before-arm
structural rule, the plan arithmetic, the PID lock's named refusal, the dry stage running
with a sentinel elicitor that makes constructing one the failure, and the paid stages'
standing operator-gate refusal. Added after the 2026-08-30 pilot's under-run: distinct pairs
produce distinct stimuli on a synthetic fixture, a degenerate cell is refused by name and
counted, and a probe that came back empty does not make a book `clean`. What it does not
establish: anything about any model — the paid path is exercised only through the refusal
that guards it.

Added with PREREG's post-hoc amendment of 2026-08-31: which arms carry the stage salt at which
stage and an unknown stage refusing rather than defaulting to none, the salt reaching the
sample index and nothing the model sees, the amendment provenance addressing its own
registration text, and the dual verdict's shape — both rules present, differing only in the
sham input, and no key called `verdict`.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(
    0, str(Path(__file__).resolve().parent.parent / "research" / "sim-readership-backtest")
)
import pytest

backtest = pytest.importorskip("backtest", reason="research module; imported by path")
analysis = pytest.importorskip("analysis", reason="research module; imported by path")
corpus = pytest.importorskip("corpus", reason="research module; imported by path")
population = pytest.importorskip("population", reason="research module; imported by path")

_DATES = ("2025-03-01T00:00:00Z", "2025-03-02T00:00:00Z", "2025-03-03T00:00:00Z")


def _vote(choice: str, order: int, pair: str = "p1") -> analysis.Vote:
    return analysis.Vote(
        pair_id=pair, arm="C", persona_id="r1", order=order, choice=choice, reason="",
        high_was="A" if order == 0 else "B",
    )


def _fiction(fiction_id: str, *, stem: str, title: str = "A Borrowed Lantern") -> Any:
    """One synthetic fiction whose chapters 1-3 are identified by their title ordinals.

    Each chapter is three paragraphs of `stem`-prefixed tokens, so two fictions built with
    different stems share no byte and one built with the same stem is byte-identical after
    blinding — which is exactly the two cases the stimulus rail has to tell apart.
    """
    texts = [
        "\n\n".join(" ".join(f"{stem}{chapter}{p}{w}" for w in range(12)) for p in range(3))
        for chapter in range(3)
    ]
    return corpus.fiction_from_rows([
        {
            "fiction_id": fiction_id, "title": title, "author": "Rowan Alder",
            "tags": '["LitRPG"]', "warnings": "[]",
            "description": " ".join(f"blurbword{n}" for n in range(40)),
            "status": None, "followers": 30.0, "total_views": 600.0, "average_views": 200.0,
            "chapter_id": f"{fiction_id}-c{index + 1}",
            "chapter_title": f"Chapter {index + 1}",
            "release_datetime": _DATES[index], "text": text,
        }
        for index, text in enumerate(texts)
    ])


def _pair(pair_id: str, high: str, low: str) -> Any:
    return corpus.Pair(pair_id=pair_id, high=high, low=low,
                       cell=("undeclared_2025", "LitRPG", "short", ""), ratio=3.0)


def test_the_member_space_remap_names_the_high_member_a_in_both_orders() -> None:
    """Order 0: choosing slot A is choosing the high member. Order 1: choosing slot B is."""
    remapped = backtest.to_member_space(
        [_vote("A", 0), _vote("B", 0), _vote("B", 1), _vote("A", 1), _vote("neither", 1)]
    )
    assert [v.choice for v in remapped] == ["A", "B", "A", "B", "neither"]
    assert all(v.high_was == "A" for v in remapped)


def test_a_slot_space_aggregate_would_misread_what_the_remap_fixes() -> None:
    """Four decided votes, all naming the HIGH member, split across orders: slot space sees a
    2-2 tie; member space sees 4-0. The remap is the difference between measuring position
    and measuring the pair."""
    votes = [_vote("A", 0), _vote("A", 0), _vote("B", 1), _vote("B", 1)]
    slot = analysis.aggregate_by_pair(votes, {"r1"})
    member = analysis.aggregate_by_pair(backtest.to_member_space(votes), {"r1"})
    assert slot["pairs"]["p1"]["decided"] is False
    assert member["pairs"]["p1"]["predicted"] == "A"
    assert backtest.outcomes_from(member) == [1]


def test_confirmatory_keeps_only_the_undeclared_2025_cells() -> None:
    pairs = [
        corpus.Pair("a" * 16, "f1", "f2", ("undeclared_2025", "LitRPG", "mid", ""), 3.5),
        corpus.Pair("b" * 16, "f3", "f4", ("human_pre_llm", "LitRPG", "mid", ""), 4.0),
    ]
    kept = backtest.confirmatory(pairs)
    assert [p.pair_id for p in kept] == ["a" * 16]


def test_the_plan_prices_the_pilot_at_a_tenth_of_the_target() -> None:
    full = backtest.plan("full", 963)
    pilot = backtest.plan("pilot", 963)
    assert full["pairs_this_stage"] == backtest.N_TARGET
    assert pilot["pairs_this_stage"] == 20
    assert pilot["sessions"] < full["sessions"]
    # Under the K1a-corrected cost basis (0.012 -> 0.075) the registered full stage priced
    # above the original $180 ceiling; the operator resolved the fork on 2026-08-31 by
    # raising the ceiling to 900 (quota-denominated). Both stages fit again, with margin —
    # which is the fact this test now pins.
    assert full["estimated_usd"] <= backtest.COST_CEILING_USD
    assert pilot["estimated_usd"] <= backtest.COST_CEILING_USD
    with pytest.raises(ValueError, match="unknown stage"):
        backtest.plan("rehearsal", 10)


def test_a_book_without_a_clean_classification_enters_no_session() -> None:
    """Probe-before-arm, structurally: an unprobed or recognised book's pairs are skipped."""
    sessions = backtest.build_sessions(
        [corpus.Pair("c" * 16, "fx", "fy", ("undeclared_2025", "other", "mid", ""), 3.0)],
        fictions={},  # never reached: the classification gate fires first
        classifications={"fx": "clean"},  # fy is unprobed
        personas=(),
    )
    assert sessions["C"] == [] and sessions["P"] == []
    assert sessions["skipped_pairs"] == 1


def test_the_pid_lock_refuses_a_second_holder_by_name(tmp_path: Path) -> None:
    lock = tmp_path / ".backtest.lock"
    holder = backtest.PidLock(lock).__enter__()
    try:
        with (
            pytest.raises(RuntimeError, match="another backtest instance"),
            backtest.PidLock(lock),
        ):
            pass
    finally:
        holder.__exit__(None, None, None)
    assert not lock.exists(), "the lock must release on exit"


def test_the_dry_stage_builds_the_plan_without_an_elicitor(tmp_path: Path, capsys) -> None:
    pairs_path = tmp_path / "pairs.json"
    pairs_path.write_text(json.dumps({"pairs": []}), encoding="utf-8")
    fictions_path = tmp_path / "fictions.json"
    fictions_path.write_text("{}", encoding="utf-8")
    code = backtest.main(
        ["--stage", "dry", "--pairs", str(pairs_path), "--fictions", str(fictions_path)]
    )
    assert code == 0
    out = capsys.readouterr()
    assert '"stage": "dry"' in out.out
    assert "no elicitor constructed" in out.err


def test_paid_stages_refuse_without_yes_and_stand_on_the_operator_gate(
    tmp_path: Path, capsys
) -> None:
    """Name kept alive (cited in the ledger); the gate it stands on changed hands.

    The blanket operator-gate refusal was removed on 2026-08-30 in the commit citing the
    operator's go (plan/serial-pilot-18.md §8). What stands in its place: --yes is still
    required for any spend, and a paid stage with no excerpt-pass artifact refuses by name
    before constructing an elicitor — which is also what keeps this test spend-free on any
    machine, artifact present or not.
    """
    pairs_path = tmp_path / "pairs.json"
    pairs_path.write_text(json.dumps({"pairs": []}), encoding="utf-8")
    assert backtest.main(["--stage", "pilot", "--pairs", str(pairs_path)]) == 1
    assert "pass --yes" in capsys.readouterr().err
    missing = tmp_path / "no-such-fictions.json"
    assert backtest.main([
        "--stage", "pilot", "--pairs", str(pairs_path),
        "--fictions", str(missing), "--yes",
    ]) == 1
    err = capsys.readouterr().err
    assert "excerpt-pass artifact is absent" in err
    assert "nothing was spent" in err


def test_run_sessions_stops_at_the_ceiling_and_says_so() -> None:
    class ChargingElicitor:
        def __init__(self) -> None:
            self.calls = 0

        def ask_raw(self, system, turns, *, schema, max_tokens, tag, sample=0, model=None):
            self.calls += 1
            return {"text": '{"continue": "A", "reason": ""}'}

        def spend(self):
            return {"equivalent_usd": 999.0}

    spec = backtest.arms.SessionSpec(
        pair_id="p1", arm="C", persona_id="r1", order=0,
        excerpt_a_digest="d1", excerpt_b_digest="d2",
    )
    planned = [backtest.PlannedSession(spec, "system", "text a", "text b")] * 3
    ledger: dict[str, float] = {}
    votes, aborted = backtest.run_sessions(
        ChargingElicitor(), planned, model="m", ledger=ledger
    )
    assert aborted is True
    assert len(votes) == 1, "the ceiling stops further sessions after the current one"
    assert ledger["equivalent_usd"] == 999.0


def test_registration_digests_cover_prereg_population_and_pairs(tmp_path: Path) -> None:
    pairs_path = tmp_path / "pairs.json"
    pairs_path.write_text(json.dumps({"pairs": []}), encoding="utf-8")
    digests = backtest.registration_digests(pairs_path)
    assert set(digests) == {"prereg_sha256", "population_digest", "pairs_digest"}
    assert len(digests["prereg_sha256"]) == 64


def test_distinct_pairs_produce_distinct_stimuli_and_a_whole_plan() -> None:
    """Four books, two pairs: every planned C cell carries its own bytes and none is lost.

    The 2026-08-30 pilot's under-run was first hypothesised to be stimulus collapse — pairs
    resolving to the same or empty excerpts, so their requests replayed instead of buying.
    The census refuted that on the real artifact (40 of 40 stimuli distinct and non-empty),
    and this pins the property the hypothesis assumed, so a future collapse has a test that
    fails rather than a cache to be reconstructed from.
    """
    personas = population.POPULATION[:2]
    fictions = {f"f{i}": _fiction(f"f{i}", stem=f"stem{i}") for i in range(4)}
    pairs = [_pair("a" * 16, "f0", "f1"), _pair("b" * 16, "f2", "f3")]
    sessions = backtest.build_sessions(
        pairs, fictions, dict.fromkeys(fictions, "clean"), personas
    )
    assert sessions["degenerate_stimuli"] == [], "a whole plan refuses nothing"
    assert len(sessions["C"]) == len(pairs) * len(personas) * 2 == 8
    assert len(sessions["P"]) == 8
    cells = {(s.spec.excerpt_a_digest, s.spec.excerpt_b_digest) for s in sessions["C"]}
    assert len(cells) == 4, "two pairs x two orders, each its own (A, B) pair of digests"
    assert len({digest for cell in cells for digest in cell}) == 4, "four books, four stimuli"


def test_byte_identical_or_empty_stimuli_are_refused_by_name_and_counted() -> None:
    """A cell that cannot pose its question leaves the plan loudly, with a count.

    Two books whose prose is byte-identical blind to the same excerpt: both orders would ask
    the same question and any answer would be counted as a preference. Both main arms refuse
    the pair, and `build_sessions` reports the refusals rather than returning a quietly
    shorter plan — the shape that let a twentieth-of-plan arm read as a finished one.
    """
    personas = population.POPULATION[:2]
    twins = {"f0": _fiction("f0", stem="same"), "f1": _fiction("f1", stem="same")}
    sessions = backtest.build_sessions(
        [_pair("c" * 16, "f0", "f1")], twins, dict.fromkeys(twins, "clean"), personas
    )
    assert sessions["C"] == [] and sessions["P"] == []
    refusals = sessions["degenerate_stimuli"]
    assert len(refusals) == 2, "the C and P cells each refuse, each counted"
    assert [r.split("/")[0] for r in refusals] == ["C", "P"]
    assert all("byte-identical stimuli are not a comparison" in r for r in refusals)
    assert all("c" * 16 in r for r in refusals), "the refusal names the cell"
    with pytest.raises(backtest.DegenerateStimuli, match="an empty stimulus is not a stimulus"):
        backtest._sessions_for_pair("p1", "C", "some text", "   ", personas)


# ------------------------------------- the post-hoc amendment (2026-08-31): salt and verdicts


def test_only_the_control_arms_carry_the_stage_salt_and_only_after_the_pilot() -> None:
    """PREREG §A.3 in one table: the primary arms never salt, the controls salt at (c) only.

    Stage (b) keeps the empty salt so the pilot's committed control numbers keep replaying
    free — the RUNBOOK's standing guarantee — and stage (c) salts its controls so they draw
    fresh at the stage that has to certify them.
    """
    assert backtest.CONTROL_ARMS == ("sham", "damage", "surface")
    for arm in ("C", "P"):
        assert backtest.control_stage_salt("full", arm) == ""
        assert backtest.control_stage_salt("pilot", arm) == ""
    for arm in backtest.CONTROL_ARMS:
        assert backtest.control_stage_salt("full", arm) == "full"
        assert backtest.control_stage_salt("pilot", arm) == ""
        assert backtest.control_stage_salt("dry", arm) == ""


def test_an_unknown_stage_refuses_rather_than_silently_returning_no_salt() -> None:
    """A typo that fell through to "" would put stage (c)'s controls back on the pilot's
    cached answers — the exact defect the amendment removes — and would do it silently."""
    with pytest.raises(ValueError, match="unknown stage"):
        backtest.control_stage_salt("rehearsal", "sham")


def test_run_sessions_passes_the_salt_into_the_sample_and_into_nothing_else() -> None:
    """The salt reaches the cache key and stops there: same system, same turns, same schema,
    different `sample`. Checked through the driver's own loop rather than the builder, because
    the loop is what a paid stage actually runs."""
    seen: list[dict[str, Any]] = []

    class Recording:
        def ask_raw(self, system, turns, *, schema, max_tokens, tag, sample=0, model=None):
            seen.append({"system": system, "turns": turns, "schema": schema,
                         "sample": sample, "tag": tag})
            return {"text": '{"continue": "A", "reason": ""}'}

        def spend(self) -> dict[str, float]:
            return {"equivalent_usd": 0.0}

    spec = backtest.arms.SessionSpec(
        pair_id="sham-f0", arm="sham", persona_id="r1", order=0,
        excerpt_a_digest="d1", excerpt_b_digest="d2",
    )
    planned = [backtest.PlannedSession(spec, "SYSTEM", "window one", "window two")]
    for salt in ("", "full"):
        votes, aborted = backtest.run_sessions(
            Recording(), planned, model="m", ledger={}, stage_salt=salt
        )
        assert aborted is False and len(votes) == 1

    unsalted, salted = seen[0], seen[2]  # each session makes two calls; take stage 1 of each
    assert unsalted["sample"] != salted["sample"], "the salted cell re-draws"
    assert unsalted["system"] == salted["system"]
    assert unsalted["turns"] == salted["turns"]
    assert unsalted["tag"] == salted["tag"]
    assert all(record["sample"] == seen[0]["sample"] for record in seen[:2]), (
        "both stages of one session share the cell's sample index"
    )


def test_the_amendment_provenance_carries_the_directive_and_addresses_its_own_text() -> None:
    """The result file must say, on its own face, that `verdict_amended` is post-hoc and
    which change it came from. The section digest is content-addressed against PREREG.md, so
    the code and the registration text cannot drift apart unnoticed."""
    got = backtest.amendment_provenance()
    assert got["present"] is True
    assert got["operator_directive"] == "draft the amendment, run the full after reset"
    assert got["date"] == "2026-08-31"
    assert got["sham_min_decided"] == backtest.analysis.SHAM_MIN_DECIDED
    assert got["control_arms_stage_salted"] == list(backtest.CONTROL_ARMS)
    assert got["primary_arms_stage_salted"] == []
    assert len(got["section_sha256"]) == 64
    assert "first 10%" in got["disclosure"], "the replay disclosure travels with the run"
    prereg = (backtest.HERE / "PREREG.md").read_text(encoding="utf-8")
    index = prereg.find(backtest.AMENDMENT_SECTION)
    assert index > 0, "the amendment is appended, never replacing the registration"
    assert got["section_sha256"] == hashlib.sha256(
        prereg[index:].encode("utf-8")
    ).hexdigest()


def test_the_dual_verdict_writes_both_rules_and_no_key_called_verdict() -> None:
    """PREREG §A.5's output shape, over one set of votes.

    The shams are twelve two-vote cells: under the registered rule they set a floor of 0.5 and
    void the arm; under the amended rule none of them qualifies, so the floor is unmeasured and
    the amended path voids for its own named reason. Both verdicts are present, they differ,
    and neither is called `verdict` — a reader has to name the rule.
    """
    by_sham = {
        f"sham-{i}": [
            analysis.Vote(pair_id=f"sham-{i}", arm="sham", persona_id=p, order=0,
                          choice="A", reason="", high_was="A")
            for p in ("r1", "r2")
        ]
        for i in range(12)
    }
    got = backtest.dual_verdict(
        [1] * 200,
        largest_true_effect=0.3,
        positional=analysis.positional_rate([]),
        votes_by_sham=by_sham,
        damage_outcomes=[1] * 20,
        shuffle={"draws": 200, "clears": 0, "clear_share": 0.0},
    )
    assert set(got) == {"sham", "sham_amended", "verdict_registered", "verdict_amended",
                        "unimplemented_margin_band", "amendment"}
    assert "verdict" not in got, "no default rule: the reader names one"
    # §7's uncoded +0.05 clearance: floor 0.5 sits ABOVE the 0.3 effect here, so the outcome
    # is not in the band where the registered text and the registered code diverge — and the
    # flag must say so rather than fire on every void.
    assert got["unimplemented_margin_band"]["registered"] is False
    assert got["verdict_registered"]["verdict"] == "void_sham"
    assert got["verdict_amended"]["verdict"] == "void_sham_unmeasured"
    assert got["sham"]["floor"] == pytest.approx(0.5)
    assert got["sham_amended"]["floor"] == 0.0
    assert got["sham_amended"]["n_qualifying"] == 0
    assert got["amendment"]["present"] is True


def test_both_verdicts_differ_in_the_sham_input_and_in_nothing_else() -> None:
    """One difference, auditable: every other field of the two records is identical, so a
    disagreement between the rules is attributable to the sham corner alone."""
    by_sham = {  # one two-vote sham (excluded, deviation 0.5) and one eight-vote sham at 0.25
        "sham-thin": [
            analysis.Vote(pair_id="sham-thin", arm="sham", persona_id=p, order=0,
                          choice="A", reason="", high_was="A")
            for p in ("r1", "r2")
        ],
        "sham-thick": [
            analysis.Vote(pair_id="sham-thick", arm="sham", persona_id=f"r{i}", order=0,
                          choice="A" if i < 6 else "B", reason="", high_was="A")
            for i in range(8)
        ],
    }
    got = backtest.dual_verdict(
        [1] * 200,
        largest_true_effect=0.3,
        positional=analysis.positional_rate([]),
        votes_by_sham=by_sham,
        damage_outcomes=[1] * 20,
        shuffle={"draws": 200, "clears": 0, "clear_share": 0.0},
    )
    registered, amended = got["verdict_registered"], got["verdict_amended"]
    assert registered["verdict"] == "void_sham" and registered["sham_floor"] == 0.5
    assert amended["verdict"] == "qualified"
    assert amended["sham_floor"] == pytest.approx(0.25)
    differing = {k for k in registered if registered[k] != amended[k]}
    assert differing == {"verdict", "fired", "sham_floor", "sham_min_decided",
                         "sham_n_qualifying"}


def test_a_probe_that_answered_nothing_does_not_make_a_book_clean() -> None:
    """PREREG §3 says every candidate book is probed; a silent transport probed nothing.

    In the pilot, 12 of 40 books had all three probes fail on the transport and all 12 were
    scored `clean` — the screen carrying the whole memorisation defense certified books it
    never asked about. An unanswered probe now lands the book outside `clean`, where
    `build_sessions` will not let it into an arm.
    """
    class Silent:
        def ask_raw(self, system: str, turns: Any, **kwargs: Any) -> dict[str, Any]:
            return {"text": "", "refused": True, "stop_reason": "transport_error:OSError"}

    class Answering:
        def ask_raw(self, system: str, turns: Any, **kwargs: Any) -> dict[str, Any]:
            return {"text": "I do not recognise this passage.", "refused": False}

    fiction = _fiction("f0", stem="stem0")
    silent = backtest.probe_book(Silent(), fiction, model="m")
    assert silent["classification"] == "unprobed"
    assert silent["unanswered"] == ["title", "author", "continuation"]
    assert "silence is not a miss" in silent["why"]
    answering = backtest.probe_book(Answering(), fiction, model="m")
    assert answering["classification"] == "clean"
    assert "unanswered" not in answering
    skipped = backtest.build_sessions(
        [_pair("d" * 16, "f0", "f1")], {}, {"f0": "unprobed", "f1": "clean"},
        population.POPULATION[:2],
    )
    assert skipped["C"] == [] and skipped["skipped_pairs"] == 1
