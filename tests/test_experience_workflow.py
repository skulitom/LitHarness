"""The workflow trial records normal commands without rerouting stories or spending in tests."""

from __future__ import annotations

import hashlib
import importlib.util
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from litharness import cli
from litharness.domain.generation import CompletionRequest, CompletionResult, Usage
from litharness.providers.base import ProviderUnavailable
from litharness.providers.codex_cli import CodexCliProvider

PATH = Path(__file__).resolve().parents[1] / (
    "research/quality-measurement/experience-workflow-20260915/run.py"
)


@pytest.fixture
def experiment(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("experience_workflow_test", PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "LOCAL", tmp_path / "run")
    monkeypatch.setattr(module, "lock", lambda: None)
    monkeypatch.setattr(module, "verify_frozen", dict)
    return module


def state(experiment):
    return {
        "status": "running",
        "started_at": datetime.now(UTC).isoformat(),
        "calls": [],
        "books": {
            book: {"status": "running", "accepted": 0} for book in experiment.order("concept")
        },
    }


def test_pairs_share_premise_and_seed_and_phases_counterbalance(experiment):
    for index in experiment.INPUTS:
        for arm in "AB":
            experiment.write(experiment.book_root(arm + index) / "seed.json", {"label": index})
        commands = [experiment.command(arm + index, "concept") for arm in "AB"]
        assert commands[0][commands[0].index("--seed") + 1] == index
        assert commands[1][commands[1].index("--seed") + 1] == index
        assert experiment.command("A" + index, "new")[3] == experiment.INPUTS[index]["premise"]
        assert experiment.command("B" + index, "new")[3] == experiment.INPUTS[index]["premise"]
    assert experiment.order("concept") == ("A1", "B1", "B2", "A2", "A3", "B3", "B4", "A4")
    assert experiment.order("new") == ("B1", "A1", "A2", "B2", "B3", "A3", "A4", "B4")
    assert experiment.command("B1", "grow1") == ["architect", "grow", "--scene", "1"]
    assert experiment.command("B1", "accept-seed") == ["world", "accept"]
    assert experiment.command("B1", "chapter2") == ["tick"]
    assert "--no-outline" not in experiment.base_args("A1")
    assert "--revise" not in experiment.base_args("A1")


def test_environment_cannot_inherit_an_exemplar_or_other_book_controls(experiment, monkeypatch):
    for key in (
        "LITHARNESS_EXEMPLARS",
        "LITHARNESS_DIRECTOR",
        "LITHARNESS_READER_CHECKPOINTS",
        "LITHARNESS_ROSTER_DATABASE",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "PYTHONPATH",
    ):
        monkeypatch.setenv(key, "UNRELATED")
    env = experiment.environment("B2")
    assert "UNRELATED" not in env.values()
    assert env["LITHARNESS_DATABASE"] == str(experiment.book_root("B2") / "book.db")
    assert env["LITHARNESS_PROVIDER"] == "codex"
    with pytest.raises(ValueError):
        experiment.book_root("../outside")


def test_resource_admission_preserves_unknown_usage_and_bounds_each_book(experiment):
    record = state(experiment)
    at = record["started_at"]
    assert experiment.admission(record, "A1", at) is None
    record["calls"] = [{"status": "started", "book": "A1", "tokens": 0}]
    assert experiment.admission(record, "A1", at) == "previous failed or interrupted call"
    record["calls"] = [{"status": "completed", "book": "A1", "tokens": 1}] * 45
    assert experiment.admission(record, "A1", at) == "book call ceiling"
    assert experiment.admission(record, "B1", at) is None
    record["calls"] = []
    later = (datetime.fromisoformat(at) + timedelta(seconds=14400)).isoformat()
    assert experiment.admission(record, "B1", later) == "elapsed-time ceiling"
    record["calls"] = [{"status": "completed", "book": "A1", "tokens": 4000000}]
    assert experiment.admission(record, "B1", at) == "global token ceiling"


def test_recorder_passes_the_same_request_and_result_and_links_every_receipt(
    experiment, monkeypatch
):
    experiment.write(experiment.LOCAL / "progress.json", state(experiment))
    request = CompletionRequest(prompt="An original premise.", system="Generate.", profile="test")
    result = CompletionResult(
        text="Raw output.", provider="codex", model="gpt-6-astra", usage=Usage(1, 2, 3, 4, 5)
    )
    seen = []

    def complete(self, supplied):
        seen.append(supplied)
        return result

    monkeypatch.setattr(CodexCliProvider, "complete", complete)
    experiment.install_recorder("A1", "concept")
    provider = CodexCliProvider()
    assert provider.complete(request) is result
    assert provider.complete(request) is result
    assert seen == [request, request]
    first, second = sorted((experiment.LOCAL / "calls").glob("*.json"))
    assert experiment.read(second)["previous_receipt_sha256"] == experiment.sha(first)
    saved = experiment.read(experiment.LOCAL / "progress.json")
    assert [row["tokens"] for row in saved["calls"]] == [15, 15]


def test_failed_provider_receipt_stops_further_generation(experiment, monkeypatch):
    experiment.write(experiment.LOCAL / "progress.json", state(experiment))

    def fail(self, supplied):
        raise ProviderUnavailable("transport interrupted")

    monkeypatch.setattr(CodexCliProvider, "complete", fail)
    experiment.install_recorder("A1", "concept")
    with pytest.raises(ProviderUnavailable):
        CodexCliProvider().complete(CompletionRequest(prompt="Generate."))
    record = experiment.read(experiment.LOCAL / "progress.json")
    assert record["stop"]
    receipt = experiment.read(experiment.LOCAL / record["calls"][0]["path"])
    assert receipt["usage_unknown"]
    assert record["calls"][0]["status"] == "failed"
    with pytest.raises(ProviderUnavailable, match="previous failed"):
        CodexCliProvider().complete(CompletionRequest(prompt="Do not generate."))
    assert len(experiment.read(experiment.LOCAL / "progress.json")["calls"]) == 1


def test_no_live_dispatch_or_step_in_test_mode(experiment):
    with pytest.raises(RuntimeError, match="test-mode"):
        experiment.run()
    with pytest.raises(RuntimeError, match="test mode"):
        experiment.step("A1", "concept", 1)


def test_metadata_uses_canonical_book_and_drain_stops_at_an_empty_queue(experiment):
    root = experiment.book_root("A1")
    root.mkdir(parents=True)
    assert experiment.metadata("A1")["accepted"] == 0
    assert (
        cli.main(
            [
                "--database",
                str(root / "book.db"),
                "--chapter-scenes",
                "1",
                "new",
                "Test",
                "--premise",
                "An original premise.",
                "--scenes",
                "6",
            ]
        )
        == 0
    )
    meta = experiment.metadata("A1")
    assert meta["accepted"] == 0 and meta["pending"] == 0 and meta["terminal"] == 0
    assert experiment.phase_done("drain1", meta)
    assert not experiment.phase_done("chapter1", meta)
    assert experiment.phase_done("chapter1", meta | {"accepted": 1})
    assert not experiment.phase_done("chapter2", meta | {"accepted": 1})


def test_changed_frozen_input_refuses_before_dispatch(experiment, monkeypatch):
    source = experiment.LOCAL / "source.py"
    source.parent.mkdir()
    source.write_text("before", encoding="utf-8")
    experiment.write(
        experiment.LOCAL / "manifest.json", {"files": {str(source): experiment.sha(source)}}
    )
    # Restore the real function, since this check specifically exercises the freeze.
    spec = importlib.util.spec_from_file_location("experience_freeze_test", PATH)
    fresh = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fresh)
    monkeypatch.setattr(fresh, "LOCAL", experiment.LOCAL)
    assert fresh.verify_frozen()["files"]
    source.write_text("after", encoding="utf-8")
    with pytest.raises(RuntimeError, match="Frozen input changed"):
        fresh.verify_frozen()


def test_scheduler_never_ticks_an_empty_drain_queue(experiment, monkeypatch):
    monkeypatch.delenv("LITHARNESS_ENV")
    monkeypatch.setattr(experiment.subprocess, "check_output", lambda *a, **k: b"committed")
    monkeypatch.setattr(experiment, "sha", lambda path: hashlib.sha256(b"committed").hexdigest())
    dispatched = []

    def simulate(arguments, **kwargs):
        book, phase, iteration = arguments[-3:]
        dispatched.append(phase)
        record = experiment.read(experiment.LOCAL / "progress.json")
        accepted = record["books"][book]["accepted"]
        if phase.startswith("chapter"):
            accepted = int(phase[-1])
        experiment.write(
            experiment.LOCAL / "steps" / f"{phase}-{book}-{iteration}.json",
            {
                "after": {"accepted": accepted, "pending": 0, "terminal": 0},
                "returncode": 0,
                "stdout": "",
            },
        )

    monkeypatch.setattr(experiment.subprocess, "run", simulate)
    experiment.run()
    assert not any(phase.startswith("drain") for phase in dispatched)
    assert experiment.read(experiment.LOCAL / "progress.json")["status"] == "complete"


def test_transport_audit_detects_changed_system_schema_and_unscoped_tools(experiment):
    from litharness.providers.codex_schema import prepare_codex_schema

    schema = {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}
    request = CompletionRequest(prompt="Original", system="Fixed", schema=schema)
    raw = {
        "system": request.effective_system,
        "schema": schema,
        "native_schema": prepare_codex_schema(schema),
        "argv": ["--output-schema", "path"],
    }
    payload = experiment.serial(request)
    assert all(experiment.transport_details(raw, payload, "A1").values())
    altered = raw | {
        "system": "Different",
        "schema": None,
        "events": [{"item": {"type": "command_execution"}}],
    }
    checks = experiment.transport_details(altered, payload, "A1")
    assert not checks["system"]
    assert not checks["original_schema"]
    assert not checks["no_unscoped_tool_events"]
