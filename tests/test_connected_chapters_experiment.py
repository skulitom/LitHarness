"""The bounded demonstration must actually reach three chapters without selective retries."""

from __future__ import annotations

import importlib.util
from datetime import UTC, datetime
from pathlib import Path

import pytest

PATH = Path(__file__).resolve().parents[1] / (
    "research/quality-measurement/connected-chapters-20260916/run.py"
)


@pytest.fixture
def experiment(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("connected_chapters_test", PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.configure()
    from litharness.application import concept, discovery

    # run.py:167 checks the labels this arm registered; stage-0 §255 relabels both requests.
    # The boundary under test is stage order, no tools and no spend.
    monkeypatch.setattr(concept, "MATERIAL_CONCEPT_PROFILE", "writer.concept.material.v1")
    monkeypatch.setattr(discovery, "PROFILE", "writer.discovery.v13")
    monkeypatch.setattr(module, "LOCAL", tmp_path / "run")
    monkeypatch.setattr(module.base, "LOCAL", module.LOCAL)
    monkeypatch.setattr(module.base, "lock", lambda: None)
    monkeypatch.setattr(module.base, "verify_frozen", dict)
    for book in module.base.order("concept"):
        root = module.base.book_root(book)
        root.mkdir(parents=True)
        (root / "brief.txt").write_text(module.base.INPUTS[book[1]]["premise"], encoding="utf-8")
        module.base.write(root / "seed.json", {"label": "123456789012345678901234567890"})
    return module


def test_real_concept_cli_reaches_the_registered_invention_boundary(experiment):
    for book in ("A1", "B1", "B2", "A2"):
        experiment.preflight(book)
        result = experiment.base.read(experiment.LOCAL / "preflight" / f"{book}.json")
        assert result["provider_calls"] == 0
        assert experiment.base.INPUTS[book[1]]["premise"] in result["request"]["prompt"]
        assert not result["request"]["allowed_tools"]


def test_actual_cli_accepts_both_logical_continuation_ids(experiment):
    from litharness import cli

    for number in (1, 2):
        args = cli.build_parser().parse_args(
            experiment.base_args("B1") + experiment.command("B1", f"grow{number}")
        )
        assert args.scene == f"scene-{number}"
    with pytest.raises(ValueError, match="Unregistered"):
        experiment.command("B1", "grow3")
    assert experiment.command("B1", "chapter3") == ["tick"]
    assert experiment.command("A1", "drain3") == ["tick"]
    assert experiment.base.REVISIONS["A"] == experiment.base.REVISIONS["B"]


def state(experiment, accepted=2, pending=0):
    return {
        "started_at": datetime.now(UTC).isoformat(),
        "status": "running",
        "calls": [],
        "books": {
            book: {"status": "running", "accepted": accepted, "pending": pending, "terminal": 0}
            for book in experiment.base.order("concept")
        },
    }


def test_scheduler_drafts_third_chapter_and_does_not_trigger_fourth(experiment, monkeypatch):
    base = experiment.base
    base.write(experiment.LOCAL / "progress.json", state(experiment))
    dispatched = []

    def step(argv, **kwargs):
        book, phase, iteration = argv[-3:]
        dispatched.append((book, phase))
        base.write(
            experiment.LOCAL / "steps" / f"{phase}-{book}-{iteration}.json",
            {
                "returncode": 0,
                "stdout": "drafted",
                "after": {
                    "accepted": 3,
                    "pending": 0,
                    "terminal": 0,
                },
            },
        )

    monkeypatch.setattr(experiment.subprocess, "run", step)
    monkeypatch.setattr(base, "metadata", lambda book: {"accepted": 3, "pending": 0, "terminal": 0})
    experiment.execute("B1", "chapter3")
    experiment.execute("B1", "drain3")
    assert dispatched == [("B1", "chapter3")]
    assert base.read(experiment.LOCAL / "progress.json")["books"]["B1"]["accepted"] == 3


@pytest.mark.parametrize("failure", ["provider", "terminal", "no_work", "operational"])
def test_stop_is_preserved_without_continuing_the_affected_book(experiment, monkeypatch, failure):
    base = experiment.base
    base.write(experiment.LOCAL / "progress.json", state(experiment))
    dispatched = []

    def step(argv, **kwargs):
        book, phase, iteration = argv[-3:]
        dispatched.append((book, phase))
        if failure == "provider":
            record = base.read(experiment.LOCAL / "progress.json")
            record["stop"] = "provider failure; preserve unknown usage"
            base.write(experiment.LOCAL / "progress.json", record)
        base.write(
            experiment.LOCAL / "steps" / f"{phase}-{book}-{iteration}.json",
            {
                "returncode": 2 if failure == "operational" else 0,
                "stdout": "no_work tick=1" if failure == "no_work" else "",
                "after": {"accepted": 2, "pending": 1, "terminal": int(failure == "terminal")},
            },
        )

    monkeypatch.setattr(experiment.subprocess, "run", step)
    experiment.execute("A1", "chapter3")
    experiment.execute("A1", "drain3")
    assert dispatched == [("A1", "chapter3")]
    record = base.read(experiment.LOCAL / "progress.json")
    assert record.get("stop") or record["books"]["A1"]["status"] == "stopped"


def test_no_test_mode_dispatch_and_unknown_usage_remains_a_stop(experiment):
    with pytest.raises(RuntimeError, match="test-mode"):
        experiment.run()
    record = state(experiment)
    record["calls"] = [{"book": "B1", "status": "started", "tokens": 0}]
    assert experiment.base.admission(record, "A1", record["started_at"]) == (
        "previous failed or interrupted call"
    )
