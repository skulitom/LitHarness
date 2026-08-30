"""The staged driver's refusals and its one remap, checked without calls or corpora.

What this file pins: the member-space remap (the driver's own arithmetic — a slot-space
aggregate would be positional nonsense), the confirmatory filter, the probe-before-arm
structural rule, the plan arithmetic, the PID lock's named refusal, the dry stage running
with a sentinel elicitor that makes constructing one the failure, and the paid stages'
standing operator-gate refusal. What it does not establish: anything about any model — the
paid path is exercised only through the refusal that guards it.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(
    0, str(Path(__file__).resolve().parent.parent / "research" / "sim-readership-backtest")
)
import pytest

backtest = pytest.importorskip("backtest", reason="research module; imported by path")
analysis = pytest.importorskip("analysis", reason="research module; imported by path")
corpus = pytest.importorskip("corpus", reason="research module; imported by path")


def _vote(choice: str, order: int, pair: str = "p1") -> analysis.Vote:
    return analysis.Vote(
        pair_id=pair, arm="C", persona_id="r1", order=order, choice=choice, reason="",
        high_was="A" if order == 0 else "B",
    )


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
    assert full["estimated_usd"] <= backtest.COST_CEILING_USD
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
