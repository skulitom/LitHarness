"""A book trial must cross arcs, stop at its boundary and preserve every earlier chapter."""

from __future__ import annotations

import importlib.util
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

PATH = Path(__file__).resolve().parents[1] / (
    "research/quality-measurement/full-book-trial-20260919/run.py"
)


@pytest.fixture
def trial(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("full_book_test", PATH)
    run = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(run)
    run.configure()
    monkeypatch.setattr(run, "LOCAL", tmp_path / "trial")
    monkeypatch.setattr(run.base, "LOCAL", run.LOCAL)
    monkeypatch.setattr(run.base, "lock", lambda: None)
    monkeypatch.setattr(run.base, "verify_frozen", dict)
    root = run.base.book_root("A1")
    root.mkdir(parents=True)
    (root / "brief.txt").write_text(run.base.INPUTS["1"]["premise"], encoding="utf-8")
    run.base.write(root / "seed.json", {"label": "123456789012345678901234567890"})
    return run


def meta(accepted=0, total=0, pending=0):
    return {"accepted": accepted, "total": total, "pending": pending, "terminal": 0,
            "exceptions": 0, "scene_ids": [f"actual-id-{i}" for i in range(1, total + 1)],
            "scene_hashes": {f"actual-id-{i}": f"hash-{i}" for i in range(1, accepted + 1)}}


def state(run):
    return {"started_at": run.base.now(), "status": "running", "calls": [],
            "books": {"A1": {"status": "running", "accepted": 0}}}


def test_real_cli_invention_retains_author_volume_boundary_without_spending(trial):
    trial.preflight("A1")
    row = trial.base.read(trial.LOCAL / "preflight.json")
    assert row["provider_calls"] == 0
    assert trial.base.INPUTS["1"]["premise"] in row["request"]["prompt"]
    assert row["request"]["profile"] == "writer.concept.material.v1"


def test_cli_growth_uses_actual_ids_even_after_first_arc(trial, monkeypatch):
    from litharness import cli

    monkeypatch.setattr(trial, "metadata", lambda book: meta(21, 24))
    for number in (3, 6, 9, 12, 15, 18, 21):
        args = cli.build_parser().parse_args(
            trial.base_args("A1") + trial.command("A1", f"grow{number}"),
        )
        assert args.scene == f"actual-id-{number}"
    for phase in ("grow24", "chapter25", "extend24"):
        with pytest.raises(ValueError, match="Unregistered"):
            trial.command("A1", phase)


def test_scheduler_crosses_three_arcs_drains_and_never_drafts_chapter_25(trial, monkeypatch):
    current, dispatched = meta(), []
    base = trial.base
    base.write(trial.LOCAL / "progress.json", state(trial))
    monkeypatch.setattr(trial, "metadata", lambda book: deepcopy(current))

    def dispatch(argv, **kwargs):
        book, phase, iteration = argv[-3:]
        before = deepcopy(current)
        dispatched.append(phase)
        if phase == "new":
            current.update(meta(0, 6))
        elif phase.startswith("chapter"):
            current.update(meta(current["accepted"] + 1, current["total"], 2))
        elif phase.startswith("drain"):
            current["pending"] -= 1
        elif phase.startswith("extend"):
            current.update(meta(current["accepted"], current["total"] + 6))
        base.write(trial.LOCAL / "steps" / f"{phase}-{book}-{iteration}.json",
                   {"returncode": 0, "stdout": "", "before": before, "after": deepcopy(current)})

    monkeypatch.setattr(trial.subprocess, "run", dispatch)
    for phase in trial.PHASES:
        trial.execute("A1", phase)
    trial.execute("A1", "drain24")
    final = base.read(trial.LOCAL / "progress.json")
    assert not final.get("stop")
    assert final["books"]["A1"]["status"] == "running"
    assert current == meta(24, 24)
    assert [p for p in dispatched if p.startswith("extend")] == ["extend6", "extend12", "extend18"]
    assert len([p for p in dispatched if p.startswith("chapter")]) == 24
    assert dispatched[-2:] == ["drain24", "drain24"]


@pytest.mark.parametrize("fault", ["partial", "undrained", "budget"])
def test_refuses_extension_before_dispatch_when_not_admissible(trial, monkeypatch, fault):
    before = meta(5 if fault == "partial" else 6, 6, int(fault == "undrained"))
    record = state(trial)
    if fault == "budget":
        record["calls"] = [{"book": "A1", "status": "completed", "tokens": trial.LIMITS["tokens"]}]
    trial.base.write(trial.LOCAL / "progress.json", record)
    monkeypatch.setattr(trial, "metadata", lambda book: before)
    monkeypatch.setattr(trial.subprocess, "run", lambda *a, **k: pytest.fail("dispatched"))
    trial.execute("A1", "extend6")
    assert trial.base.read(trial.LOCAL / "progress.json")["stop"]


@pytest.mark.parametrize("fault", ["changed", "lost", "overshot", "terminal", "exception"])
def test_transition_refuses_corruption_or_unfinished_work(trial, fault):
    before, after = meta(6, 12), meta(7, 12)
    if fault == "changed":
        after["scene_hashes"]["actual-id-1"] = "different"
    elif fault == "lost":
        del after["scene_hashes"]["actual-id-1"]
    elif fault == "overshot":
        after = meta(8, 12)
    elif fault == "terminal":
        after["terminal"] = 1
    else:
        after["exceptions"] = 1
    assert trial.transition_error("chapter7", before, after)


def test_test_mode_and_existing_progress_cannot_launch(trial):
    with pytest.raises(RuntimeError, match="test-mode"):
        trial.run()


def test_metadata_reads_real_new_and_extended_stores(trial):
    from litharness import cli

    arguments = trial.base_args("A1")
    assert cli.main([*arguments, "new", "Metadata probe", "--premise", "A journey.",
                     "--scenes", "6"]) == 0
    initial = trial.metadata("A1")
    assert initial["total"] == 6 and initial["accepted"] == 0
    assert len(set(initial["scene_ids"])) == 6
    assert all(isinstance(identity, str) for identity in initial["scene_ids"])
    assert cli.main([*arguments, "extend", "--arcs", "1"]) == 0
    extended = trial.metadata("A1")
    assert extended["total"] == 12 and extended["accepted"] == 0
    assert extended["scene_ids"][:6] == initial["scene_ids"]
    assert len(set(extended["scene_ids"])) == 12


def test_registered_recovery_keeps_old_steps_and_remaining_phase_ceiling(trial, monkeypatch):
    current, dispatched = meta(6, 12), []
    trial.base.write(trial.LOCAL / "progress.json", state(trial))
    original = {"preserved": "three refused outlines"}
    for iteration in range(1, 4):
        trial.base.write(trial.LOCAL / "steps" / f"chapter7-A1-{iteration}.json", original)
    monkeypatch.setattr(trial, "metadata", lambda book: deepcopy(current))

    def dispatch(argv, **kwargs):
        book, phase, iteration = argv[-3:]
        dispatched.append(int(iteration))
        trial.base.write(trial.LOCAL / "steps" / f"{phase}-{book}-{iteration}.json",
                         {"returncode": 0, "stdout": "", "before": current, "after": current})

    monkeypatch.setattr(trial.subprocess, "run", dispatch)
    trial.execute("A1", "chapter7", start_iteration=4)
    assert dispatched == list(range(4, trial.LIMITS["ticks_per_phase"] + 1))
    assert trial.base.read(trial.LOCAL / "progress.json")["books"]["A1"]["reason"].endswith(
        "phase ceiling")
    for iteration in range(1, 4):
        assert trial.base.read(trial.LOCAL / "steps" / f"chapter7-A1-{iteration}.json") == original


@pytest.mark.parametrize("fault", [None, "missing", "attempts", "epoch"])
def test_recovery_retires_only_registered_poison_after_epoch_advances(trial, monkeypatch, fault):
    from litharness.adapters.sqlite_store import SqliteStore

    recovery = trial.module("tested_recovery", PATH.with_name("recover.py"))
    monkeypatch.setattr(recovery, "LOCAL", trial.LOCAL)
    monkeypatch.setattr(recovery.base, "LOCAL", trial.LOCAL)
    monkeypatch.setattr(recovery, "original_metadata", lambda book: {"terminal": 2})
    recovery.base.write(trial.LOCAL / "progress.json", {"recovery_ready": True})

    class Store:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def jobs_by_status(self, status, **kwargs):
            return [SimpleNamespace(job_id="other" if fault == "missing" else recovery.JOB,
                                    attempts=2 if fault == "attempts" else 3,
                                    payload={"plan_epoch": 0})]

        def plan_epoch(self, *args):
            return 0 if fault == "epoch" else 1

    monkeypatch.setattr(SqliteStore, "open_read_only", lambda path: Store())
    if fault:
        with pytest.raises(RuntimeError, match="Historical failure"):
            recovery.metadata("A1")
    else:
        assert recovery.metadata("A1") == {"terminal": 1,
                                           "historical_terminal_ids": [recovery.JOB]}
