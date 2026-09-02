"""The A/B redraw harness: its refusals, its recipe, and the folder it leaves behind.

**Not one of these tests makes a paid call, and none of them can.** The harness reaches a
provider only through `subprocess`, and every test here either passes a fake runner or drives
`--dry-run`, which builds the argv and executes nothing. `test_the_dry_run_executes_nothing`
proves the second claim by making `subprocess.run` fail the test if it is reached at all.
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

import pytest

from litharness.adapters.sqlite_store import SqliteStore
from litharness.domain.exceptions import ExceptionKind, ExceptionRecord
from tools import ab_redraw

# ------------------------------------------------------------------------------------ fixtures


def _listing(
    root: Path, *, title: str = "The Station Keeps Score", premise: str = "A hull"
) -> Path:
    directory = root / "listing"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "title.txt").write_text(title, encoding="utf-8")
    (directory / "listing.txt").write_text(premise, encoding="utf-8")
    return directory


def _filled_experiment(runs_root: Path, experiment: str = "reviser-off") -> Path:
    """The template with every marker answered — what a person hands the harness."""
    path = ab_redraw.init_experiment(runs_root, experiment)
    text = path.read_text(encoding="utf-8").replace(ab_redraw.FILL_MARKER, "answered:")
    path.write_text(text, encoding="utf-8")
    return path


def _spec(tmp_path: Path, **overrides: object) -> ab_redraw.ArmSpec:
    # The default listing is built only when the caller did not supply one: `_listing` writes
    # to a fixed path, so building it unconditionally would overwrite an override's own files
    # with the defaults and quietly test the wrong listing.
    defaults: dict[str, object] = {
        "experiment": "reviser-off",
        "arm": "a",
        "listing": overrides.pop("listing", None) or _listing(tmp_path),
        "writer": "ferreira",
        "database": tmp_path / "arm-a" / "serial.db",
        "runs_root": tmp_path / "ab",
        "chapter_scenes": 2,
        "max_ticks": 6,
        "max_cost_usd_per_day": 40.0,
        "max_tokens_per_day": 20_000_000,
        "litharness": ("uv", "run", "litharness"),
    }
    defaults.update(overrides)
    return ab_redraw.ArmSpec(**defaults)  # type: ignore[arg-type]


# ------------------------------------------------------------------------------- the refusals


def test_the_experiment_note_is_required_before_any_arm_runs(tmp_path: Path) -> None:
    """§105's discipline made structural: no named variant, no arm."""
    spec = _spec(tmp_path)
    listing = ab_redraw.read_listing(spec.listing)

    with pytest.raises(ab_redraw.Refusal) as refusal:
        ab_redraw.check_refusals(spec, listing)

    assert ab_redraw.EXPERIMENT_FILENAME in str(refusal.value)
    assert "--init-experiment" in str(refusal.value)


def test_an_unfilled_experiment_note_names_no_variant_and_is_refused(tmp_path: Path) -> None:
    """Writing the template is not filling it in, and the harness can tell the difference."""
    spec = _spec(tmp_path)
    ab_redraw.init_experiment(spec.runs_root, spec.experiment)

    with pytest.raises(ab_redraw.Refusal, match="unfilled"):
        ab_redraw.check_refusals(spec, ab_redraw.read_listing(spec.listing))


def test_a_filled_experiment_note_lets_the_arm_through(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    _filled_experiment(spec.runs_root, spec.experiment)

    ab_redraw.check_refusals(spec, ab_redraw.read_listing(spec.listing))


@pytest.mark.parametrize(
    ("dropped", "flag"),
    [
        ("max_cost_usd_per_day", "--max-cost-usd-per-day"),
        ("max_tokens_per_day", "--max-tokens-per-day"),
    ],
)
def test_a_missing_spend_ceiling_is_refused(tmp_path: Path, dropped: str, flag: str) -> None:
    spec = _spec(tmp_path, **{dropped: None})
    _filled_experiment(spec.runs_root, spec.experiment)

    with pytest.raises(ab_redraw.Refusal) as refusal:
        ab_redraw.check_refusals(spec, ab_redraw.read_listing(spec.listing))

    assert flag in str(refusal.value)


def test_an_existing_store_is_refused_because_every_arm_draws_fresh(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    _filled_experiment(spec.runs_root, spec.experiment)
    spec.database.parent.mkdir(parents=True, exist_ok=True)
    spec.database.write_text("not really a store", encoding="utf-8")

    with pytest.raises(ab_redraw.Refusal, match="FRESH store"):
        ab_redraw.check_refusals(spec, ab_redraw.read_listing(spec.listing))


def test_a_recorded_arm_is_not_overwritten(tmp_path: Path) -> None:
    """One folder describing two books is the failure this refusal exists to prevent."""
    spec = _spec(tmp_path)
    _filled_experiment(spec.runs_root, spec.experiment)
    spec.arm_dir.mkdir(parents=True, exist_ok=True)
    (spec.arm_dir / "arm.json").write_text("{}", encoding="utf-8")

    with pytest.raises(ab_redraw.Refusal, match="already exists"):
        ab_redraw.check_refusals(spec, ab_redraw.read_listing(spec.listing))


def test_a_second_arm_under_a_different_listing_is_refused(tmp_path: Path) -> None:
    """Byte-for-byte is the only thing an A/B redraw holds constant, so it is checked.

    An assertion nobody can check is not a control. Arm `a` recorded its listing's digests;
    arm `b` arriving under a different listing is two books, not two draws.
    """
    spec_a = _spec(tmp_path, arm="a")
    _filled_experiment(spec_a.runs_root, spec_a.experiment)
    spec_a.arm_dir.mkdir(parents=True, exist_ok=True)
    (spec_a.arm_dir / "arm.json").write_text(
        json.dumps({"listing": {"digest": "aaaa:bbbb"}}), encoding="utf-8"
    )

    spec_b = _spec(tmp_path, arm="b", database=tmp_path / "arm-b" / "serial.db")

    with pytest.raises(ab_redraw.Refusal) as refusal:
        ab_redraw.check_refusals(spec_b, ab_redraw.read_listing(spec_b.listing))

    assert "different listing" in str(refusal.value)


def test_a_second_arm_under_the_same_listing_is_admitted(tmp_path: Path) -> None:
    spec_a = _spec(tmp_path, arm="a")
    _filled_experiment(spec_a.runs_root, spec_a.experiment)
    listing = ab_redraw.read_listing(spec_a.listing)
    spec_a.arm_dir.mkdir(parents=True, exist_ok=True)
    (spec_a.arm_dir / "arm.json").write_text(
        json.dumps({"listing": {"digest": listing.digest}}), encoding="utf-8"
    )

    spec_b = _spec(tmp_path, arm="b", database=tmp_path / "arm-b" / "serial.db")
    ab_redraw.check_refusals(spec_b, listing)


def test_a_listing_directory_missing_its_files_is_refused(tmp_path: Path) -> None:
    empty = tmp_path / "nothing"
    empty.mkdir()

    with pytest.raises(ab_redraw.Refusal) as refusal:
        ab_redraw.read_listing(empty)

    assert "title.txt" in str(refusal.value)
    assert "listing.txt" in str(refusal.value)


def test_an_empty_listing_file_is_refused(tmp_path: Path) -> None:
    directory = _listing(tmp_path, premise="   ")

    with pytest.raises(ab_redraw.Refusal, match="empty"):
        ab_redraw.read_listing(directory)


def test_no_writer_is_refused(tmp_path: Path) -> None:
    """No writer is the pipeline's control arm, which holds nothing constant across a redraw."""
    spec = _spec(tmp_path, writer="")
    _filled_experiment(spec.runs_root, spec.experiment)

    with pytest.raises(ab_redraw.Refusal, match="--writer is required"):
        ab_redraw.check_refusals(spec, ab_redraw.read_listing(spec.listing))


def test_the_lock_refuses_a_second_arm_and_names_the_holder(tmp_path: Path) -> None:
    """One paid arm at a time, CLAUDE.md's box rule as a refusal rather than a comment."""
    path = tmp_path / ab_redraw.LOCK_NAME

    with ab_redraw.PidLock(path):
        assert path.read_text(encoding="utf-8").strip() == str(os.getpid())
        with pytest.raises(ab_redraw.Refusal) as refusal, ab_redraw.PidLock(path):
            pytest.fail("the second lock must not be granted")

    assert str(os.getpid()) in str(refusal.value)
    assert "delete the lock file" in str(refusal.value)
    assert not path.exists()


def test_the_experiment_note_is_never_regenerated_over_a_filled_one(tmp_path: Path) -> None:
    _filled_experiment(tmp_path / "ab", "reviser-off")

    with pytest.raises(ab_redraw.Refusal, match="not regenerated"):
        ab_redraw.init_experiment(tmp_path / "ab", "reviser-off")


# ---------------------------------------------------------------------------------- the recipe


def test_every_invocation_carries_both_spend_ceilings(tmp_path: Path) -> None:
    """Pilot 12 §5's silent failures, pre-empted by a uniform prefix rather than by memory."""
    spec = _spec(tmp_path)
    steps = ab_redraw.plan_steps(spec, ab_redraw.read_listing(spec.listing))

    assert steps, "the recipe is not empty"
    for step in steps:
        assert "--max-cost-usd-per-day" in step.argv, step.label
        assert "--max-tokens-per-day" in step.argv, step.label
        assert step.argv[step.argv.index("--max-cost-usd-per-day") + 1] == "40"
        assert step.argv[step.argv.index("--max-tokens-per-day") + 1] == "20000000"


def test_every_invocation_carries_the_chapter_shape_and_the_writer(tmp_path: Path) -> None:
    """`--chapter-scenes` drives planning, reader context and packaging; one value or none."""
    spec = _spec(tmp_path)

    for step in ab_redraw.plan_steps(spec, ab_redraw.read_listing(spec.listing)):
        assert step.argv[step.argv.index("--chapter-scenes") + 1] == "2", step.label
        assert step.argv[step.argv.index("--writer") + 1] == "ferreira", step.label


def test_the_recipe_is_the_hand_run_sequence_in_order(tmp_path: Path) -> None:
    """Pilot 15b §1: init, new, seed, check, accept, tick x N, library."""
    spec = _spec(tmp_path)
    steps = ab_redraw.plan_steps(spec, ab_redraw.read_listing(spec.listing))

    assert [step.label for step in steps] == [
        "init",
        "new",
        "architect seed",
        "world check",
        "world accept",
        "tick",
        "library",
    ]
    assert next(step for step in steps if step.label == "tick").repeat == spec.max_ticks


def test_world_accept_is_never_forced(tmp_path: Path) -> None:
    """Accepting a world that contradicts itself is a person's call on a named contradiction."""
    spec = _spec(tmp_path)

    for step in ab_redraw.plan_steps(spec, ab_redraw.read_listing(spec.listing)):
        assert "--force" not in step.argv, step.label


def test_the_settled_listing_is_passed_byte_for_byte(tmp_path: Path) -> None:
    directory = _listing(tmp_path, title="What the Kettle Remembers", premise="A mender, keeping")
    spec = _spec(tmp_path, listing=directory)
    listing = ab_redraw.read_listing(directory)

    new = next(step for step in ab_redraw.plan_steps(spec, listing) if step.label == "new")

    assert "What the Kettle Remembers" in new.argv
    assert new.argv[new.argv.index("--premise") + 1] == "A mender, keeping"


def test_a_variant_expressed_as_a_flag_rides_every_invocation(tmp_path: Path) -> None:
    """§185's `--no-revise` is a control arm, so a flag has to be able to BE the variant."""
    spec = _spec(tmp_path, extra_args=("--no-revise",))

    for step in ab_redraw.plan_steps(spec, ab_redraw.read_listing(spec.listing)):
        assert "--no-revise" in step.argv, step.label


def test_a_first_person_arm_creates_its_book_in_that_person_and_nowhere_else(
    tmp_path: Path,
) -> None:
    """Stage-0 §195's position is a flag of `new`, so it rides that step alone; an arm that
    names no person creates the book exactly as every arm before the flag existed."""
    first = _spec(tmp_path, person="first")
    steps = ab_redraw.plan_steps(first, ab_redraw.read_listing(first.listing))
    for step in steps:
        carried = "--person" in step.argv
        assert carried is (step.label == "new"), step.label
    new = next(step for step in steps if step.label == "new")
    assert new.argv[new.argv.index("--person") + 1] == "first"

    plain = _spec(tmp_path)
    for step in ab_redraw.plan_steps(plain, ab_redraw.read_listing(plain.listing)):
        assert "--person" not in step.argv, step.label


# ----------------------------------------------------------------------------------- the arm


class FakeProbe:
    """A store read that answers from a script instead of from SQLite."""

    def __init__(self, states: Sequence[ab_redraw.StoreState]) -> None:
        self.states = list(states)
        self.calls = 0

    def __call__(
        self, database: Path, chapter_scenes: int, library_root: Path
    ) -> ab_redraw.StoreState:
        self.calls += 1
        return self.states[min(self.calls - 1, len(self.states) - 1)]


class FakeRunner:
    """Records every argv and answers with scripted exit codes."""

    def __init__(self, failures: dict[str, int] | None = None, output: str = "") -> None:
        self.failures = failures or {}
        self.output = output
        self.calls: list[tuple[str, tuple[str, ...]]] = []

    def __call__(self, label: str, argv: Sequence[str], cwd: Path) -> ab_redraw.StepResult:
        self.calls.append((label, tuple(argv)))
        return ab_redraw.StepResult(
            label=label,
            argv=tuple(argv),
            returncode=self.failures.get(label, 0),
            seconds=0.0,
            output=self.output,
        )


def test_the_arm_runs_the_recipe_and_stops_when_chapter_one_completes(tmp_path: Path) -> None:
    """Pilot 15b's loop stopped itself; here that is the loop's condition rather than luck."""
    spec = _spec(tmp_path)
    runner = FakeRunner()
    probe = FakeProbe(
        [ab_redraw.StoreState(exists=True)] * 6
        + [ab_redraw.StoreState(exists=True, chapter_complete=True, scenes_drafted=2, shelf="s")]
    )

    run = ab_redraw.run_arm(
        spec, ab_redraw.read_listing(spec.listing), runner=runner, probe=probe, cwd=tmp_path
    )

    assert run.stopped == ""
    assert run.ticks == 2
    assert [label for label, _ in runner.calls] == [
        "init",
        "new",
        "architect seed",
        "world check",
        "world accept",
        "tick 1/6",
        "tick 2/6",
        "library",
    ]


def test_a_failing_world_check_stops_the_arm_and_refuses_to_spend_the_reseed(
    tmp_path: Path,
) -> None:
    """The standing allowance is ONE re-seed on mechanical complaints, and it is a person's."""
    spec = _spec(tmp_path)
    runner = FakeRunner(failures={"world check": 1})

    run = ab_redraw.run_arm(
        spec,
        ab_redraw.read_listing(spec.listing),
        runner=runner,
        probe=FakeProbe([ab_redraw.StoreState(exists=True)]),
        cwd=tmp_path,
    )

    assert "world check` exited 1" in run.stopped
    assert "ONE re-seed" in run.stopped
    assert "world accept" not in [label for label, _ in runner.calls]


def test_an_open_exception_stops_the_arm_after_the_step_that_raised_it(tmp_path: Path) -> None:
    """A call that returned is not a call that worked; the exceptions table is what says so."""
    spec = _spec(tmp_path)
    runner = FakeRunner()
    probe = FakeProbe(
        [
            ab_redraw.StoreState(exists=True),
            ab_redraw.StoreState(exists=True),
            ab_redraw.StoreState(
                exists=True, exceptions=("provider_unavailable exc-1: the transport gave up",)
            ),
        ]
    )

    run = ab_redraw.run_arm(
        spec, ab_redraw.read_listing(spec.listing), runner=runner, probe=probe, cwd=tmp_path
    )

    assert "provider_unavailable" in run.stopped
    assert "architect seed" in run.stopped
    assert [label for label, _ in runner.calls] == ["init", "new", "architect seed"]


def test_a_poisoned_unit_stops_the_arm(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    probe = FakeProbe(
        [ab_redraw.StoreState(exists=True, poisoned=("poisoned scene_draft j-1: out of attempts",))]
    )

    run = ab_redraw.run_arm(
        spec,
        ab_redraw.read_listing(spec.listing),
        runner=FakeRunner(),
        probe=probe,
        cwd=tmp_path,
    )

    assert "poisoned scene_draft j-1" in run.stopped


def test_an_idle_queue_with_chapter_one_unfinished_stops_the_arm(tmp_path: Path) -> None:
    """A loop that ticks NO_WORK forever is a chapter that will never finish, said quietly."""
    spec = _spec(tmp_path)
    runner = FakeRunner(output="tick: no_work")
    probe = FakeProbe([ab_redraw.StoreState(exists=True, scenes_drafted=1)])

    run = ab_redraw.run_arm(
        spec, ab_redraw.read_listing(spec.listing), runner=runner, probe=probe, cwd=tmp_path
    )

    assert "went idle at tick 1" in run.stopped
    assert "1 of 2 scene(s) drafted" in run.stopped


def test_the_tick_cap_stops_the_arm_rather_than_ticking_on(tmp_path: Path) -> None:
    spec = _spec(tmp_path, max_ticks=3)
    runner = FakeRunner()
    probe = FakeProbe([ab_redraw.StoreState(exists=True, scenes_drafted=1)])

    run = ab_redraw.run_arm(
        spec, ab_redraw.read_listing(spec.listing), runner=runner, probe=probe, cwd=tmp_path
    )

    assert "tick cap (3) was reached" in run.stopped
    assert run.ticks == 3


def test_a_stopped_arm_still_writes_its_command_log(tmp_path: Path) -> None:
    """The folder is the deliverable; a stopped arm is the one somebody needs the log of."""
    spec = _spec(tmp_path)
    run = ab_redraw.run_arm(
        spec,
        ab_redraw.read_listing(spec.listing),
        runner=FakeRunner(failures={"architect seed": 2}),
        probe=FakeProbe([ab_redraw.StoreState(exists=True)]),
        cwd=tmp_path,
    )

    directory = ab_redraw.write_folder(
        run, scorecard={"status": "skipped"}, spend={"invocations": 0}
    )

    log = (directory / "commands.log").read_text(encoding="utf-8")
    assert "architect seed" in log
    assert "STOPPED:" in log
    assert json.loads((directory / "arm.json").read_text(encoding="utf-8"))["stopped"]


# ------------------------------------------------------------------------------- the folder


def test_the_folder_convention_records_the_listing_digest_and_the_boundary(
    tmp_path: Path,
) -> None:
    """`runs/ab/<experiment>/<arm>/`, and the two-draws boundary travels with the record."""
    spec = _spec(tmp_path)
    listing = ab_redraw.read_listing(spec.listing)
    run = ab_redraw.run_arm(
        spec,
        listing,
        runner=FakeRunner(),
        probe=FakeProbe(
            [ab_redraw.StoreState(exists=True, chapter_complete=True, scenes_drafted=2)]
        ),
        cwd=tmp_path,
    )

    directory = ab_redraw.write_folder(
        run,
        scorecard={"status": "absent"},
        spend={"invocations": 3, "tokens": 10, "cost_usd": 4.16},
    )

    assert directory == spec.runs_root / "reviser-off" / "a"
    assert {path.name for path in directory.iterdir()} == {
        "arm.json",
        "commands.log",
        "spend.json",
        "shelf.txt",
    }
    record = json.loads((directory / "arm.json").read_text(encoding="utf-8"))
    assert record["listing"]["digest"] == listing.digest
    assert record["listing"]["title_sha256"] == listing.title_sha256
    assert record["ceilings"] == {"max_cost_usd_per_day": 40.0, "max_tokens_per_day": 20_000_000}
    assert record["spend"]["cost_usd"] == 4.16
    assert "never a treatment effect" in record["boundary"]
    assert json.loads((directory / "spend.json").read_text(encoding="utf-8"))["invocations"] == 3


def test_the_recorded_digest_is_what_the_sibling_refusal_reads(tmp_path: Path) -> None:
    """The write side and the refusal side agree, so the control cannot drift apart."""
    spec_a = _spec(tmp_path, arm="a")
    listing = ab_redraw.read_listing(spec_a.listing)
    run = ab_redraw.run_arm(
        spec_a,
        listing,
        runner=FakeRunner(),
        probe=FakeProbe([ab_redraw.StoreState(exists=True, chapter_complete=True)]),
        cwd=tmp_path,
    )
    ab_redraw.write_folder(run, scorecard={}, spend={})

    spec_b = _spec(tmp_path, arm="b", database=tmp_path / "arm-b" / "serial.db")

    assert ab_redraw.sibling_digests(spec_b) == {"a": listing.digest}


# ------------------------------------------------------------------------------- the scorecard

#: What §190's script prints: a table, ending in its own pointer to where the JSON went. The one
#: value is a count, because the card carries counts and nothing else.
TABLE = (
    "scorecard: the-station\n"
    "  path      the-station\n"
    "\n"
    "  row         value  chk  market reference\n"
    "  ----------------------------------------\n"
    "  file_words     12  -    no market reference\n"
    "\n"
    "  json: scorecard.json\n"
)

#: What §190's script writes to `--out`.
CARD = '{"book": "the-station", "rows": [{"key": "file_words", "value": 12}]}\n'

#: A synthetic chapter for the real scorecard to count — written here, transcribed from nowhere.
CHAPTER = """\
Teo counted the crates on the platform twice and got the same number both times.

[STATUS] Teo — Lift 1 | Carried 2/4

The foreman said nothing. The rain said a great deal.
"""


class OutRunner(FakeRunner):
    """`FakeRunner` holding §190's contract: the JSON goes to `--out`, the table to stdout."""

    def __init__(self, written: str, output: str = TABLE) -> None:
        super().__init__(output=output)
        self.written = written

    def __call__(self, label: str, argv: Sequence[str], cwd: Path) -> ab_redraw.StepResult:
        if label == "scorecard" and "--out" in argv:
            out = Path(argv[list(argv).index("--out") + 1])
            out.write_text(self.written, encoding="utf-8", newline="\n")
        return super().__call__(label, argv, cwd)


def _scorecard_script(tmp_path: Path) -> Path:
    """A stand-in at the first probed path, so `find_scorecard` finds it without being told."""
    script = tmp_path / "research" / "quality-measurement" / "scorecard.py"
    script.parent.mkdir(parents=True)
    script.write_text("# build 1", encoding="utf-8")
    return script


def test_the_scorecard_is_absent_rather_than_fatal_when_build_one_has_not_landed(
    tmp_path: Path,
) -> None:
    """This harness shipped before the per-draw scorecard; an arm without one is still an arm."""
    spec = _spec(tmp_path)

    assert ab_redraw.find_scorecard(None, repo=tmp_path) is None

    result = ab_redraw.run_scorecard(
        spec, ab_redraw.StoreState(), tmp_path / "scorecard.json", repo=tmp_path
    )

    assert result["status"] == "absent"
    assert "research/quality-measurement/scorecard.py" in str(result["detail"])


def test_a_scorecard_that_has_landed_is_run_and_its_output_kept(tmp_path: Path) -> None:
    """And the shelf path reaches it WHOLE.

    `shlex.split` is POSIX: splitting a command string that already carries `C:\\DEV\\...` eats
    every backslash and hands the scorecard a path to nothing. The template is split first and
    substituted after, so this assertion is the one that would catch it coming back. The
    template was repointed at §190's real interface after the first live arm (shelf target
    plus --out; the database is no longer an argument), so the whole-path assertion now rides
    the shelf and the destination. "Its output kept" has meant, since pilot 21's draws 2 and
    3, the JSON where the script wrote it — the next test is that defect, pinned.
    """
    script = _scorecard_script(tmp_path)
    spec = _spec(tmp_path)
    runner = OutRunner(written=CARD)

    result = ab_redraw.run_scorecard(
        spec,
        ab_redraw.StoreState(shelf="the-station"),
        tmp_path / "scorecard.json",
        runner=runner,
        repo=tmp_path,
    )

    assert result["status"] == "written"
    assert (tmp_path / "scorecard.json").read_text(encoding="utf-8") == CARD
    argv = runner.calls[0][1]
    assert str(spec.library_root / "the-station") in argv
    assert str(tmp_path / "scorecard.json") in argv
    assert str(script) in argv


def test_a_scorecard_that_refuses_this_invocation_is_recorded_not_swallowed(
    tmp_path: Path,
) -> None:
    """A wrong guess at build 1's CLI must leave a reason behind, never a silent absence."""
    script = tmp_path / "tools" / "scorecard.py"
    script.parent.mkdir(parents=True)
    script.write_text("# build 1", encoding="utf-8")
    spec = _spec(tmp_path)

    result = ab_redraw.run_scorecard(
        spec,
        ab_redraw.StoreState(),
        tmp_path / "scorecard.json",
        runner=FakeRunner(failures={"scorecard": 2}, output="unrecognized arguments: --json"),
        repo=tmp_path,
    )

    assert result["status"] == "failed"
    assert "unrecognized arguments" in str(result["detail"])
    assert not (tmp_path / "scorecard.json").exists()


def test_the_written_scorecard_json_parses_and_the_printed_table_lands_beside_it(
    tmp_path: Path,
) -> None:
    """The defect pilot 21 found on 2026-09-02, pinned.

    `runs/ab/pilot21-loop/draw2/scorecard.json` and `draw3/scorecard.json` were the printed
    table, ending in the script's own `json: ...` pointer, because the harness wrote the
    scorecard's stdout over the file the scorecard had just written to `--out`; `json.load`
    raised on both. Now the JSON is where the script put it and loads, the table is a fenced
    `scorecard.md` beside it, and the record names the two files and nothing else — no bar,
    no verdict, no value read out of either.
    """
    _scorecard_script(tmp_path)
    destination = tmp_path / "ab" / "arm" / "scorecard.json"
    destination.parent.mkdir(parents=True)

    result = ab_redraw.run_scorecard(
        _spec(tmp_path),
        ab_redraw.StoreState(shelf="the-station"),
        destination,
        runner=OutRunner(written=CARD, output=TABLE),
        repo=tmp_path,
    )

    assert result["status"] == "written"
    assert set(result) == {"status", "script", "argv", "path", "table"}
    assert result["path"] == "scorecard.json"
    assert result["table"] == "scorecard.md"
    card = json.loads(destination.read_text(encoding="utf-8"))
    assert card["book"] == "the-station"
    table = destination.with_suffix(".md").read_text(encoding="utf-8")
    assert table == "```text\n" + TABLE.strip("\n") + "\n```\n"


def test_a_scorecard_that_prints_but_writes_no_json_is_unparsed_not_written(
    tmp_path: Path,
) -> None:
    """A template without `--out {destination}` gets a reason, never a `.json` holding a table."""
    _scorecard_script(tmp_path)
    destination = tmp_path / "scorecard.json"

    result = ab_redraw.run_scorecard(
        _spec(tmp_path),
        ab_redraw.StoreState(shelf="the-station"),
        destination,
        runner=FakeRunner(output=TABLE),
        repo=tmp_path,
    )

    assert result["status"] == "unparsed"
    assert "--out {destination}" in str(result["detail"])
    assert not destination.exists()
    assert not destination.with_suffix(".md").exists()


def test_a_scorecard_json_that_does_not_parse_is_moved_aside_and_said_to_be(
    tmp_path: Path,
) -> None:
    """A `scorecard.json` that exists is one that loads; anything else is renamed, not kept."""
    _scorecard_script(tmp_path)
    destination = tmp_path / "scorecard.json"

    result = ab_redraw.run_scorecard(
        _spec(tmp_path),
        ab_redraw.StoreState(shelf="the-station"),
        destination,
        runner=OutRunner(written=TABLE, output=""),
        repo=tmp_path,
    )

    assert result["status"] == "unparsed"
    assert "moved to scorecard.unparsed.txt" in str(result["detail"])
    assert not destination.exists()
    assert not destination.with_suffix(".md").exists()
    assert (tmp_path / "scorecard.unparsed.txt").read_text(encoding="utf-8") == TABLE


def test_a_step_output_is_read_as_utf8_before_the_console_codepage() -> None:
    """The scorecard prints UTF-8 by its own reconfigure; `text=True` read it as the codepage,
    and the first live arms' folders carry the section sign as two characters to show for it."""
    assert ab_redraw.decode_output("§61 — no bar\r\nrow\rvalue\n".encode()) == (
        "§61 — no bar\nrow\nvalue\n"
    )
    fallback = ab_redraw.decode_output(b"\xa7 alone\n")
    assert fallback.endswith(" alone\n")  # decoded and never raised; the character is the box's


def test_the_real_scorecard_through_the_default_template_leaves_json_that_loads(
    tmp_path: Path,
) -> None:
    """§190's script itself, driven the way an arm drives it, `uv run` swapped for this interpreter.

    Both scorecard defects so far were found on paid arms rather than here, because every
    earlier test faked the script: the `--database --json` guess died on the first live arm,
    and the table-over-JSON overwrite on pilot 21's draws 2 and 3. The script is regex and
    arithmetic over a synthetic chapter — no model runs and no corpus is opened — so running
    it is not a paid call; and the section sign in its no-bar paragraph is the check that the
    table is decoded as the script wrote it rather than through the console codepage.
    """
    script = ab_redraw.REPO / ab_redraw.SCORECARD_CANDIDATES[0]
    if not script.is_file():
        pytest.skip("build 1's scorecard is not in this tree")
    assert ab_redraw.DEFAULT_SCORECARD_COMMAND.startswith("uv run python ")
    shelf = tmp_path / "library" / "the-station"
    (shelf / "chapters").mkdir(parents=True)
    (shelf / "chapters" / "Chapter1.txt").write_text(CHAPTER, encoding="utf-8")
    spec = _spec(
        tmp_path,
        library=tmp_path / "library",
        scorecard_command=(
            f'"{Path(sys.executable).as_posix()}" '
            + ab_redraw.DEFAULT_SCORECARD_COMMAND.removeprefix("uv run python ")
        ),
    )
    destination = tmp_path / "ab" / "arm" / "scorecard.json"
    destination.parent.mkdir(parents=True)

    result = ab_redraw.run_scorecard(
        spec, ab_redraw.StoreState(shelf="the-station"), destination, repo=ab_redraw.REPO
    )

    assert result["status"] == "written", result
    card = json.loads(destination.read_text(encoding="utf-8"))
    assert card["book"] == "the-station"
    assert card["chapters"] == ["Chapter1.txt"]
    table = destination.with_suffix(".md").read_text(encoding="utf-8")
    assert "scorecard: the-station" in table
    assert "§61" in table
    assert "json:" in table


# --------------------------------------------------------------------- against a real store


def test_a_missing_store_is_reported_rather_than_raised(tmp_path: Path) -> None:
    """`init` has not run yet at the first probe, and that is not an error."""
    state = ab_redraw.read_store(tmp_path / "nothing.db", 2, tmp_path)

    assert not state.exists
    assert state.trouble == ()


def test_an_exception_in_a_real_store_is_read_back_as_trouble(tmp_path: Path) -> None:
    """The fakes above script the store; this one proves the query against SQLite.

    `PROVIDER_UNAVAILABLE` is the transport failure's name on the book side, and CLAUDE.md's
    standing warning is that the run completes anyway — so this read is the whole reason the
    harness does not trust an exit code.
    """
    database = tmp_path / "serial.db"
    store = SqliteStore.open(database)
    try:
        store.raise_exception(
            ExceptionRecord(
                exception_id="exc-1",
                kind=ExceptionKind.PROVIDER_UNAVAILABLE,
                summary="the transport gave up",
                job_id="draft-1",
                raised_at="2026-09-01T00:00:00Z",
            )
        )
    finally:
        store.close()

    state = ab_redraw.read_store(database, 2, tmp_path / "book-library")

    assert state.exists
    assert state.trouble == ("provider_unavailable exc-1: the transport gave up",)


def test_a_resolved_exception_does_not_stop_a_later_arm(tmp_path: Path) -> None:
    database = tmp_path / "serial.db"
    store = SqliteStore.open(database)
    try:
        store.raise_exception(
            ExceptionRecord(
                exception_id="exc-1",
                kind=ExceptionKind.REPEATED_GATE_FAILURE,
                summary="three refusals",
                job_id="draft-1",
                raised_at="2026-09-01T00:00:00Z",
            )
        )
        store.resolve_exception("exc-1", "looked at it", at="2026-09-01T01:00:00Z")
    finally:
        store.close()

    assert ab_redraw.read_store(database, 2, tmp_path).trouble == ()


def test_spend_is_summed_over_the_days_the_arm_touched(tmp_path: Path) -> None:
    """A run that crosses midnight reports itself whole, not the fraction after the boundary."""
    database = tmp_path / "serial.db"
    SqliteStore.open(database).close()
    started = datetime(2026, 8, 31, 23, 50, tzinfo=UTC)
    ended = datetime(2026, 9, 1, 0, 20, tzinfo=UTC)

    spend = ab_redraw.read_spend(database, started, ended)

    assert list(spend["days"]) == ["2026-08-31", "2026-09-01"]  # type: ignore[call-overload]
    assert spend["cost_usd"] == 0.0


# --------------------------------------------------------------------------------- the dry run


def _dry_run_argv(spec: ab_redraw.ArmSpec) -> list[str]:
    return [
        "--experiment",
        spec.experiment,
        "--arm",
        spec.arm,
        "--listing",
        str(spec.listing),
        "--writer",
        spec.writer,
        "--database",
        str(spec.database),
        "--runs-root",
        str(spec.runs_root),
        "--chapter-scenes",
        "2",
        "--max-cost-usd-per-day",
        "40",
        "--max-tokens-per-day",
        "20000000",
        "--dry-run",
    ]


def test_the_dry_run_executes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The rehearsal spends nothing, and this test is what makes that a fact rather than a hope."""
    spec = _spec(tmp_path)
    _filled_experiment(spec.runs_root, spec.experiment)

    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("a dry run reached subprocess.run")

    monkeypatch.setattr(ab_redraw.subprocess, "run", forbidden)

    assert ab_redraw.main(_dry_run_argv(spec)) == 0

    printed = capsys.readouterr().out
    assert "nothing below was executed" in printed
    assert "uv run litharness" in printed
    assert not spec.arm_dir.exists(), "a dry run leaves no arm folder to collide with the real one"


def test_the_dry_run_prints_the_commands_the_paid_arm_would_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    spec = _spec(tmp_path)
    _filled_experiment(spec.runs_root, spec.experiment)

    ab_redraw.main(_dry_run_argv(spec))
    printed = capsys.readouterr().out

    for fragment in ("init", "architect seed", "world check", "world accept", "tick", "library"):
        assert fragment in printed
    assert printed.count("--max-cost-usd-per-day") == len(
        ab_redraw.plan_steps(spec, ab_redraw.read_listing(spec.listing))
    )
    # The commands only: the `# world accept: no --force, ever` note says the word on purpose.
    commands = [line for line in printed.splitlines() if line and not line.startswith("#")]
    assert commands
    assert not any("--force" in line for line in commands)


def test_a_flag_variant_reaches_the_commands_through_the_equals_form(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`--extra-arg=--no-revise`, and the help says so because the bare form cannot work.

    Argparse reads `--extra-arg --no-revise` as a missing value followed by an unknown option
    and exits 2 — which is the exact invocation somebody reaches for when the variant IS a
    flag, so the help text names the equals form rather than leaving them to find out.
    """
    spec = _spec(tmp_path)
    _filled_experiment(spec.runs_root, spec.experiment)

    assert ab_redraw.main([*_dry_run_argv(spec), "--extra-arg=--no-revise"]) == 0

    commands = [
        line for line in capsys.readouterr().out.splitlines() if line and not line.startswith("#")
    ]
    assert commands
    assert all("--no-revise" in line for line in commands)


def test_the_dry_run_still_refuses_an_unnamed_variant(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Every refusal is rehearsed too, so the first surprise is not on the paid run."""
    spec = _spec(tmp_path)

    assert ab_redraw.main(_dry_run_argv(spec)) == 2
    assert "REFUSED" in capsys.readouterr().err


def test_init_experiment_writes_the_template_and_runs_no_arm(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    argv = [
        "--experiment",
        "reviser-off",
        "--init-experiment",
        "--runs-root",
        str(tmp_path / "ab"),
    ]

    assert ab_redraw.main(argv) == 0

    path = tmp_path / "ab" / "reviser-off" / ab_redraw.EXPERIMENT_FILENAME
    assert path.is_file()
    assert ab_redraw.FILL_MARKER in path.read_text(encoding="utf-8")
    assert "Fill every" in capsys.readouterr().out


# ---------------------------------------------------------------------------- the standing header


def test_the_experiment_template_carries_105s_caution_verbatim(tmp_path: Path) -> None:
    """The caution is quoted, not paraphrased: a paraphrase is how a rule loses its teeth."""
    text = ab_redraw.init_experiment(tmp_path, "x").read_text(encoding="utf-8")

    assert "The agentic path bought nothing on these cases and cost 2.25x the calls." in text
    assert (
        "No general prose hill-climbing, and no selection among mechanically valid candidates "
        "by any\n> quality proxy, score, ranking or preference signal" in text
    )
    assert "never from undirected variation" in text


def test_the_experiment_template_asks_for_the_control_statement_and_the_confound(
    tmp_path: Path,
) -> None:
    """§54's shape: what was held constant, and what moved besides the variant."""
    text = ab_redraw.init_experiment(tmp_path, "x").read_text(encoding="utf-8")

    assert "Same premise, same model, same budget, 30 scenes" in text
    assert "And the confound, which is not small." in text
    assert "Not held constant, and named:" in text
    assert "n is one per arm." in text


def test_the_experiment_template_forbids_a_bar_or_a_rank(tmp_path: Path) -> None:
    text = ab_redraw.init_experiment(tmp_path, "x").read_text(encoding="utf-8")

    assert "may not produce a win, a rank, a score, a bar" in text
    assert "two draws are two draws" in text


def test_a_settled_concept_beside_the_listing_rides_new_and_joins_the_digest(
    tmp_path: Path,
) -> None:
    """Stage-0 §197: `concept.json` beside the listing is part of the settled book, so it is
    passed to `new` byte for byte off disk and its digest joins the listing's; a listing drawn
    before the concept stage existed carries none and the recipe is what it always was."""
    directory = _listing(tmp_path)
    (directory / ab_redraw.CONCEPT_NAME).write_text(
        '{"person_before": "a clerk"}', encoding="utf-8"
    )
    spec = _spec(tmp_path, listing=directory)
    listing = ab_redraw.read_listing(directory)

    assert listing.concept == '{"person_before": "a clerk"}'
    assert listing.concept_sha256 is not None
    assert listing.digest.endswith(listing.concept_sha256)
    new = next(step for step in ab_redraw.plan_steps(spec, listing) if step.label == "new")
    assert new.argv[new.argv.index("--concept") + 1] == str(directory / ab_redraw.CONCEPT_NAME)

    plain_dir = _listing(tmp_path / "plain")
    plain = ab_redraw.read_listing(plain_dir)
    assert plain.concept is None and plain.concept_sha256 is None
    assert plain.digest == f"{plain.title_sha256}:{plain.premise_sha256}"
    plain_new = next(
        step
        for step in ab_redraw.plan_steps(_spec(tmp_path / "plain", listing=plain_dir), plain)
        if step.label == "new"
    )
    assert "--concept" not in plain_new.argv


def test_an_empty_concept_file_is_refused_rather_than_read_as_none(tmp_path: Path) -> None:
    directory = _listing(tmp_path)
    (directory / ab_redraw.CONCEPT_NAME).write_text("", encoding="utf-8")
    with pytest.raises(ab_redraw.Refusal) as refusal:
        ab_redraw.read_listing(directory)
    assert "empty" in str(refusal.value)
