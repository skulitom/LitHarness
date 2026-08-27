"""The feed continuation reader's driver: free legs first, and every refusal it owes.

`feed_battery.py` is the composition root of `fcr.v0`, so its tests are about what it refuses
and what it stamps, not about arithmetic that lives in `feed_core` or `feed_controls`. The
properties pinned here:

1. **The free legs are free.** `--selftest` and `--attainability` complete without an elicitor
   existing at all — a sentinel class stands where `elicit.Elicitor` would stand and fails the
   test the moment anyone constructs one.
2. **Both structural refusals fire with their names.** `--seat` refuses while
   `feed_core.CONTROL_MIN_SESSIONS` is None, before even reading the substrate; and any plan
   above `feed_core.CALL_GUARD` refuses without `--yes`, naming both numbers.
3. **Every result carries the registration and nothing unwinds a stamp.** A result file
   round-trips with `registration_digest` matching `feed_core.registration_digest()`, LF
   endings, one trailing newline — and a session set in which nothing is scorable reports
   `"UNREADABLE"` rather than being substituted, retried, or filled.

No model call anywhere: the one paid-leg exercise runs against a scripted fake whose first
answer is a refusal, so each session costs one ask and comes back unscorable by construction.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

feed_battery = pytest.importorskip(
    "feed_battery",
    reason="research module; imported by path, skipped where research/ is unavailable",
)
feed_core = pytest.importorskip(
    "feed_core",
    reason="research module; imported by path, skipped where research/ is unavailable",
)


# --------------------------------------------------------------------------- fakes and fixtures


_WORDS_PER_PARAGRAPH = feed_core.CHUNK_WORDS + 5


def _member_text(marker: str) -> str:
    """One feed member of exactly `MIN_CHUNKS_FEED` chunks: one paragraph per chunk.

    Each paragraph is just over `CHUNK_WORDS`, so `bcr.chunks` cannot merge them and the count
    is stated by construction, before anything runs.
    """
    return "\n\n".join(
        " ".join(f"{marker}p{paragraph}w{word}" for word in range(_WORDS_PER_PARAGRAPH))
        for paragraph in range(feed_core.MIN_CHUNKS_FEED)
    )


def _pool(size: int = feed_core.FEED_SIZE) -> list[tuple[str, str]]:
    """A synthetic fitness pool: full-length members under plausible names."""
    return [(f"fitness-{index:02d}", _member_text(f"b{index}")) for index in range(size)]


class _SentinelElicitor:
    """Stands where `elicit.Elicitor` would stand; constructing it is itself the failure."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        raise AssertionError("sentinel Elicitor constructed; a free leg tried to buy a call")

    def ask_raw(
        self,
        system: str,
        turns: list[dict[str, Any]],
        *,
        schema: dict[str, object] | None,
        max_tokens: int,
        tag: dict[str, Any],
        sample: int = 0,
        model: str | None = None,
    ) -> dict[str, Any]:
        raise AssertionError("sentinel Elicitor asked for a completion")


class _RefusingElicitor:
    """Answers every action turn with a refusal, so one ask ends each session unscorable.

    Same constructor seam as `elicit.Elicitor` (cache path plus keywords), context-manager
    shape included, because the driver uses both.
    """

    def __init__(self, cache_path: Any, **kwargs: Any) -> None:
        self.cache_path = cache_path
        self.kwargs = kwargs
        self.calls = 0

    def __enter__(self) -> _RefusingElicitor:
        return self

    def __exit__(self, *exc: object) -> bool:
        return False

    def spend(self) -> dict[str, float]:
        return {"calls": float(self.calls), "usd": 0.0}

    def ask_raw(
        self,
        system: str,
        turns: list[dict[str, Any]],
        *,
        schema: dict[str, object] | None,
        max_tokens: int,
        tag: dict[str, Any],
        sample: int = 0,
        model: str | None = None,
    ) -> dict[str, Any]:
        del system, turns, schema, max_tokens, tag, model
        self.calls += 1
        return {"refused": True}


# ----------------------------------------------------------------------------------- free legs


def test_selftest_passes_and_exits_zero() -> None:
    """The leg an operator runs before anything paid must pass here, so CI owns it too."""
    assert feed_battery.main(["--selftest"]) == 0


@pytest.mark.intensive
def test_attainability_prints_every_candidate_count_and_the_none_refusal_paragraph(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The sizing table names every candidate batch size as a row, models as columns, and says
    in its own output that CONTROL_MIN_SESSIONS is read off it and paid runs refuse while None.

    The seed and trial count are fixed module constants and the leg prints the count it ran;
    the test shrinks only the constant, so what is asserted is still exactly what was run.
    """
    monkeypatch.setattr(feed_battery, "_ATTAINABILITY_TRIALS", 4)
    assert feed_battery.main(["--attainability"]) == 0
    out = capsys.readouterr().out
    assert "trials=4" in out
    # feed_controls' candidate ladder, hand-restated: 16 through 96.
    for size in (16, 24, 32, 48, 64, 96):
        assert str(size) in out, f"the table never named the candidate size {size}"
    assert "mixture" in out and "dirichlet" in out
    assert "CONTROL_MIN_SESSIONS" in out
    assert "None" in out
    assert "refuses" in out


def test_dry_run_prints_fault_free_feeds_and_the_planned_call_count_without_an_elicitor(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Dry-run builds the seating from synthetic full-length members and touches no elicitor.

    Counts derived by hand from the registered shape: a four-book pool seats FEED_SIZE intact
    feeds + 3 controls; each runs across all four rotations, doubled for fp6's flat-price
    block; worst case one call per skim, MAX_STEPS per session.
    """
    monkeypatch.setattr(feed_battery.feed_substrate, "fitness_texts", lambda directory: _pool())
    monkeypatch.setattr(feed_battery, "Elicitor", _SentinelElicitor)
    code = feed_battery.main(["--dry-run", "--yes", "--replicates", "1"])
    assert code == 0
    out = capsys.readouterr().out
    assert out.count("[ok]") == feed_core.FEED_SIZE + 3
    assert "FAULT" not in out
    assert "fitness-00" in out and "fitness-03" in out
    assert str(feed_core.MIN_CHUNKS_FEED) in out
    feeds = feed_core.FEED_SIZE + 3
    sessions = feeds * feed_core.FEED_SIZE * 1 * 2
    assert str(sessions * feed_core.MAX_STEPS) in out


def test_seating_plan_refuses_a_pool_smaller_than_the_registered_feed() -> None:
    """Three books cannot seat an intact feed of four; the plan builder says so up front."""
    with pytest.raises(ValueError, match=f"needs {feed_core.FEED_SIZE}"):
        feed_battery.seating_plan(_pool(feed_core.FEED_SIZE - 1))


# ------------------------------------------------------------------------------- the refusals


def test_seat_refuses_while_control_min_sessions_is_unset_with_the_named_message(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The refusal precedes everything: even the substrate is not read while unsized.

    The registered constant is table-set now; the unset state it guards against is
    restored here so the structural refusal stays pinned."""
    monkeypatch.setattr(feed_core, "CONTROL_MIN_SESSIONS", None)

    def _unread(directory: object) -> list[tuple[str, str]]:
        raise AssertionError("fitness_texts read before the sizing gate refused the run")

    monkeypatch.setattr(feed_battery.feed_substrate, "fitness_texts", _unread)
    monkeypatch.setattr(feed_battery, "Elicitor", _SentinelElicitor)
    assert feed_battery.main(["--seat", "--yes"]) == 1
    err = capsys.readouterr().err
    assert "CONTROL_MIN_SESSIONS" in err
    assert "None" in err


def test_the_call_guard_refuses_an_over_guard_plan_without_yes_and_names_both_numbers(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """With sizing set, a seat over CALL_GUARD still refuses without --yes, naming both numbers."""
    monkeypatch.setattr(feed_core, "CONTROL_MIN_SESSIONS", 48)
    monkeypatch.setattr(feed_battery.feed_substrate, "fitness_texts", lambda directory: _pool())
    monkeypatch.setattr(feed_battery, "Elicitor", _SentinelElicitor)
    feeds = feed_core.FEED_SIZE + 3
    calls = feeds * feed_core.FEED_SIZE * 1 * 2 * feed_core.MAX_STEPS  # 7 x 4 x 2 x 27 = 1512
    assert calls > feed_core.CALL_GUARD, "the planned seat must really be over the guard"
    assert feed_battery.main(["--seat", "--replicates", "1"]) == 1
    err = capsys.readouterr().err
    assert str(calls) in err
    assert str(feed_core.CALL_GUARD) in err
    assert "--yes" in err


def test_planned_calls_straddle_the_guard_at_its_two_sides() -> None:
    """One feed x one replicate stays under the guard; the full pool over it — same arithmetic."""
    under = feed_battery.planned_counts(1, 1)
    assert under["max_calls"] == 2 * feed_core.FEED_SIZE * feed_core.MAX_STEPS
    assert under["max_calls"] <= feed_core.CALL_GUARD
    over = feed_battery.planned_counts(feed_core.FEED_SIZE + 3, 3)
    assert over["max_calls"] > feed_core.CALL_GUARD
    assert over["flat_sessions"] == over["cheap_sessions"]
    assert over["max_calls"] == over["sessions"] * feed_core.MAX_STEPS


def test_main_without_a_mode_is_a_usage_error() -> None:
    """No leg selected is argparse's error, not a silent zero-call success."""
    with pytest.raises(SystemExit) as excinfo:
        feed_battery.main([])
    assert excinfo.value.code != 0


# ------------------------------------------------------- stamps, registration, and no fallback


def test_published_stamps_a_warning_into_a_result_that_round_trips_with_the_matching_digest(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    """A full seat against the refusing fake writes one result file; the stamp and the
    registration survive the round trip byte-exactly, LF, one trailing newline."""
    monkeypatch.setattr(feed_core, "CONTROL_MIN_SESSIONS", 48)
    monkeypatch.setattr(feed_battery.feed_substrate, "fitness_texts", lambda directory: _pool())
    monkeypatch.setattr(feed_battery, "Elicitor", _RefusingElicitor)
    out = tmp_path / "seat.json"
    code = feed_battery.main(
        [
            "--seat",
            "--yes",
            "--published",
            "--replicates",
            "1",
            "--cache",
            str(tmp_path / "raw.jsonl"),
            "--out",
            str(out),
        ]
    )
    assert code == 0
    raw = out.read_bytes()
    assert b"\r" not in raw, "the result file carries CR bytes; results are LF"
    assert raw.endswith(b"\n") and not raw.endswith(b"\n\n")
    stored = json.loads(raw.decode("utf-8"))
    assert stored["warnings"] == [feed_core.PUBLISHED_WARNING]
    assert stored["registration"] == feed_core.PRE_REGISTRATION
    assert stored["registration_digest"] == feed_core.registration_digest()


def test_nothing_scorable_reads_unreadable_across_every_verdict_field() -> None:
    """A session set with only unscorable sessions verdicts UNREADABLE — including empty input —
    and the driver substitutes nothing."""
    dead = [
        feed_core.FeedSession(
            feed_id="f",
            arm="intact",
            model="m",
            rotation=rotation,
            replicate=0,
            dose=0.0,
            actions=(("read", "A"),),
            unanswered=1,
        )
        for rotation in range(4)
    ]
    for block in (feed_battery.controls_block(dead, dead), feed_battery.controls_block([], [])):
        for name, entry in block.items():
            assert entry["verdict"] == "UNREADABLE", f"{name} did not read UNREADABLE"
# ------------------------------------------------------------------------------ the screen cap


def test_a_feeds_cap_turns_the_run_into_a_screen_and_stamps_the_cap(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    """§89's no-silent-caps rail: a capped plan names its cap in the result and in the study
    field, so a screen can never read as a covered pool. Counts derived by hand: 2 feeds x 4
    rotations x 1 replicate x 2 price blocks = 16 sessions."""
    monkeypatch.setattr(feed_core, "CONTROL_MIN_SESSIONS", 48)
    monkeypatch.setattr(feed_battery.feed_substrate, "fitness_texts", lambda directory: _pool())
    monkeypatch.setattr(feed_battery, "Elicitor", _RefusingElicitor)
    out = tmp_path / "screen.json"
    code = feed_battery.main(
        [
            "--seat",
            "--yes",
            "--feeds",
            "2",
            "--replicates",
            "1",
            "--cache",
            str(tmp_path / "raw.jsonl"),
            "--out",
            str(out),
        ]
    )
    assert code == 0
    stored = json.loads(out.read_text(encoding="utf-8"))
    assert stored["study"] == "fcr_screen"
    assert stored["plan_cap"] == {"feeds": 2, "of_pool": feed_core.FEED_SIZE + 3}
    assert len(stored["sessions_cheap"]) + len(stored["sessions_flat"]) == 16


def test_an_uncapped_seat_stamps_no_cap_and_stays_a_seat(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    """Without --feeds the study is the seat and plan_cap is None — the stamp never lies in
    either direction."""
    monkeypatch.setattr(feed_core, "CONTROL_MIN_SESSIONS", 48)
    monkeypatch.setattr(feed_battery.feed_substrate, "fitness_texts", lambda directory: _pool())
    monkeypatch.setattr(feed_battery, "Elicitor", _RefusingElicitor)
    out = tmp_path / "seat.json"
    code = feed_battery.main(
        [
            "--seat",
            "--yes",
            "--replicates",
            "1",
            "--cache",
            str(tmp_path / "raw.jsonl"),
            "--out",
            str(out),
        ]
    )
    assert code == 0
    stored = json.loads(out.read_text(encoding="utf-8"))
    assert stored["study"] == "fcr_seat"
    assert stored["plan_cap"] is None


def test_a_zero_feed_cap_is_a_usage_error_before_the_substrate_is_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--feeds 0 is not an empty screen: argparse's own exit, before any corpus read."""

    def _unread(directory: object) -> list[tuple[str, str]]:
        raise AssertionError("fitness_texts read before the zero-cap refusal")

    monkeypatch.setattr(feed_battery.feed_substrate, "fitness_texts", _unread)
    with pytest.raises(SystemExit) as excinfo:
        feed_battery.main(["--seat", "--yes", "--feeds", "0", "--replicates", "1"])
    assert excinfo.value.code != 0
