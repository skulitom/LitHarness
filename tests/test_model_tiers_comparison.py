"""The model-tiers comparison (`model-tiers.v1`), checked without a call.

What this file pins: the plan runs, per scene, the recorded block's three cells then the current
block's four, each rotated per scene, and the seeds ABBA; the registered constants are digested;
a recorded request round-trips byte for byte and a changed one does not; the recorded and the
current ledger blocks are read and a thread block refused; the trial's promise rows rebuild the
current-wording request through the summariser's own builder, which differs from the recorded
request in its wording only; the accept step's report is read and must add up; every identity
check on a recorded summary passes on a faithful record and names the one that fails; the
validators, the agreement components, the settlement flag and the field table read the
pipeline's own rules; the exact binomial, settlement and t bounds and the three-way verdicts are
what the PREREG states; a control that did not parse withholds its block's floor tests; the
seed screen proposes nothing; the model's own act is an unusable answer only with evidence of a
model turn, and everything else is transport; the ledger charges reservations for unknown and
interrupted attempts and records halts; `run` buys each unit once, re-dispatches a transport
failure once, never keeps one as an answer, stops before a call past a ceiling, refuses without
this arm's lock and refuses to buy anything after a halt; `prepare` pins, freezes inputs and
registers without a call; `verify` refuses changed, uncommitted or unpushed bytes and a changed
pinned tree, and no longer reads the live `src/`; the interpreter check refuses the live
checkout; the Codex folder is pinned whole and guarded; `claim` rewrites the claim before
registration only; `analyse` refuses while held, before a finished line and on a transport
failure kept as an answer, and reads a complete fake run; the real Codex adapter, driven by a
scripted runner, sends each cell's model and effort.

What it does not establish: anything about any model. No call happens here; every provider is a
fake or the real adapter behind a scripted runner, and neither the frozen nor the pinned runtime
is started (`build_runtime` is exercised only by `prepare`, which refuses loudly before spend).
"""

from __future__ import annotations

import ast
import dataclasses
import json
import os
import sys
from pathlib import Path
from typing import Any

import pytest

mt = pytest.importorskip(
    "model_tiers_comparison",
    reason="research module; imported by path, skipped where research/ is unavailable",
)
governance = pytest.importorskip("epistemic_governance")

from litharness.adapters.sqlite_store import SqliteStore  # noqa: E402
from litharness.application.summarize import (  # noqa: E402
    SUMMARY_SCHEMA,
    flatten,
    render_summary_prompt,
)
from litharness.domain.generation import (  # noqa: E402
    PROFILES,
    CompletionRequest,
    CompletionResult,
    Usage,
)
from litharness.domain.promises import Promise  # noqa: E402
from litharness.domain.text import content_hash  # noqa: E402
from litharness.providers.base import ProviderError, ProviderFailureKind  # noqa: E402
from litharness.providers.cli import CommandResult  # noqa: E402
from litharness.providers.codex_schema import prepare_codex_schema  # noqa: E402

VERSION_STRING = "codex-cli 9.9.9"
LEDGER_BLOCK = (
    mt.LEDGER_HEADING_RECORDED
    + " These are the book's own record of what it owes rather than established fact; each "
    "line is the name a debt is filed under, then what is owed:\n"
    "- old_debt owes: Settle the old debt. (due by s000006)"
)
OLD_DEBT_ROW: dict[str, Any] = {
    "promise_id": "promise-old-debt", "subject": "old_debt",
    "description": "Settle the old debt.", "opened_at_key": "s000001", "due_key": "s000006",
    "opened_by_revision": "rev-1", "model": "gpt-6-astra", "kind": None,
    "window_start_key": None, "window_end_key": None, "scheduled_by_plan_revision": None,
}
SHAPE = {
    "protagonists": ["mara"], "systems": ["joinery"], "grant_counts": [7], "ladder_lengths": [5],
    "cast": ["tavi"], "status_sheet": True, "protagonist_standing": False, "records": 10,
    "by_predicate": {"is_a": 3},
}
ACCEPT_STDOUT = (
    "accepted 196 of 200 proposal(s) into canon\n"
    "  2 record(s) minted to finish a drawn system\n"
    "  4 left proposed: a later declaration filled the same slot\n"
)


def scene_text(index: int) -> str:
    return f'Mara held door {index}. "Not yet," Tavi said. Rank {index % 3 + 1} came at dawn.'


def answer_for(text: str) -> dict[str, Any]:
    first = text.split(". ")[0] + "."
    return {
        "setting": "A washhouse at dawn.",
        "characters": "Mara, Tavi.",
        "events": f"Mara holds a door. {text.split('. ')[-1]}",
        "open": "Nothing is left open.",
        "delta": {"who": "Mara", "what_changed": "rank", "from": "none", "to": "Rank 1"},
        "promises_opened": [
            {"subject": "The door", "description": "Whether the door holds.", "kind": "plot",
             "due_hint": None, "evidence_quote": first},
        ],
        "promises_paid": [{"subject": "old_debt", "evidence_quote": '"Not yet," Tavi said.'}],
    }


def summary_request(text: str, ledger: str = "") -> CompletionRequest:
    """A recorded-style request: the scene plus the pre-§255 ledger block, typed out."""
    system, prompt = render_summary_prompt(text)
    return CompletionRequest(
        prompt=prompt + ledger, system=system, schema=SUMMARY_SCHEMA, profile="mechanical",
        call_class="mechanical", sampler=PROFILES["mechanical"], max_output_tokens=512,
    )


def current_request(text: str, rows: list[dict[str, Any]]) -> CompletionRequest:
    """The request HEAD's summariser builds for this scene and these ledger rows."""
    names = {field.name for field in dataclasses.fields(Promise)}
    promises = tuple(Promise(**{k: v for k, v in row.items() if k in names}) for row in rows)
    system, prompt = render_summary_prompt(text, open_promises=promises)
    return CompletionRequest(
        prompt=prompt, system=system, schema=SUMMARY_SCHEMA, profile="mechanical",
        call_class="mechanical", sampler=PROFILES["mechanical"], max_output_tokens=512,
    )


def seed_request() -> CompletionRequest:
    return CompletionRequest(
        prompt="Reader-facing listing:\n\nA stranded town.", system="Build the supplied world.",
        max_output_tokens=16000, profile="architect.seed.v9", call_class="generation",
        timeout_seconds=3600.0, allowed_tools=("Bash(litharness world summary:*)",),
    )


def make_paths(root: Path) -> Any:
    return mt.Paths(
        root=root, arm_dir=root / "arm", local=root / "local", trial=root / "trial",
        trial_here=root / "trial_here", lock_holder=root / "box.lock" / "holder",
        runner_file=root / "runner.py", test_file=root / "test_runner.py",
    )


def fake_raw(cell: Any, mode: str, **extra: Any) -> dict[str, Any]:
    raw: dict[str, Any] = {
        "requested_model": cell.model, "reasoning_effort": cell.effort,
        "cli_version": VERSION_STRING, "mode": mode,
        "argv": ["codex", "exec", *mt.ISOLATION_FLAGS, "--model", cell.model, "-c",
                 f"model_reasoning_effort={json.dumps(cell.effort)}", "-c",
                 "project_doc_max_bytes=0", "-"],
        **extra,
    }
    if mode == "bridge":
        raw["settings"] = {"mcp_servers.litharness.command": sys.executable}
    return raw


def unit_input(index: int) -> dict[str, Any]:
    text = scene_text(index)
    ledger = LEDGER_BLOCK if index > 1 else ""
    rows = [mt.ledger_row(OLD_DEBT_ROW)] if index > 1 else []
    payload = mt.serial(summary_request(text, ledger))
    current = mt.serial(current_request(text, rows))
    shown = mt.ledger_subjects(ledger)
    answer = answer_for(text)
    matched, unmatched = mt.paid_split(answer, shown)
    return {
        "scene": f"scene-{index}", "call": f"{100 + index:04d}-A1.json",
        "call_sha256": "0" * 64, "request": payload, "request_sha256": mt.digest(payload),
        "current_request": current, "current_request_sha256": mt.digest(current),
        "ledger_rows": rows,
        "scene_text": text, "scene_sha256": mt.sha_text(text), "suffix_empty": not ledger,
        "shown": shown,
        "record": {"parsed": answer, "text_sha256": "0" * 64,
                   "usage": {"input_tokens": 700, "output_tokens": 40, "cache_read_tokens": 0,
                             "cache_write_tokens": 0, "reasoning_tokens": 0},
                   "wall_ms": 1000, "cli_version": "codex-cli 0.155.0",
                   "paid_matched": matched, "paid_unmatched": unmatched},
        "required_names": ["Mara", "Tavi"], "quantities": [str(index % 3 + 1)],
        "native_schema_bytes_equal": True,
    }


def build_arm(tmp_path: Path, scenes: int = mt.EXPECTED_SCENES) -> tuple[Any, dict[str, Any]]:
    """A registered arm in a scratch root: inputs, template, registration, lock, PREREG."""
    paths = make_paths(tmp_path)
    units = [unit_input(index) for index in range(1, scenes + 1)]
    mt.write_json(paths.summary_inputs, {"version": mt.VERSION, "units": units})
    request = mt.serial(seed_request())
    paths.seed_template.parent.mkdir(parents=True, exist_ok=True)
    paths.seed_template.write_bytes(b"template store")
    seed = {"request": request, "request_sha256": mt.digest(request),
            "recorded_request_sha256": "0" * 64, "profile": "architect.seed.v9",
            "recorded_profile": "architect.seed.v8", "record": SHAPE,
            "template_sha256": mt.sha_file(paths.seed_template)}
    mt.write_json(paths.seed_inputs, {"version": mt.VERSION, **seed})
    registration = {
        "registration_digest": mt.registration_digest(),
        "binary": {"path": "codex.exe", "sha256": "0" * 64, "version": VERSION_STRING,
                   "folder": "codex", "folder_hashes": {}},
        "runtime": {"files": {}, "trees": {}},
        "inputs": {"scenes": [unit["scene"] for unit in units],
                   "summary_requests": [{"scene": unit["scene"],
                                         "request_sha256": unit["request_sha256"],
                                         "current_request_sha256":
                                         unit["current_request_sha256"]}
                                        for unit in units],
                   "seed_request_sha256": seed["request_sha256"]},
        "input_hashes": {}, "source_hashes": {},
    }
    mt.write_json(paths.registration, registration)
    for path in (paths.prereg, paths.runbook):
        path.write_text("registered\n", encoding="utf-8")
    take_lock(paths)
    return paths, registration


def take_lock(paths: Any) -> None:
    paths.lock_holder.parent.mkdir(parents=True, exist_ok=True)
    paths.lock_holder.write_text(f"{mt.LOCK_PREFIX} test holder\n", encoding="utf-8")


def release_lock(paths: Any) -> None:
    paths.lock_holder.unlink()


class FakeProvider:
    def __init__(self, cell: Any, script: Any, seen: list[Any]) -> None:
        self.cell = cell
        self.script = script
        self.seen = seen
        self.last_attempt: dict[str, Any] = {}

    def complete(self, request: CompletionRequest) -> CompletionResult:
        self.seen.append((self.cell.name, request.profile, os.environ.get("LITHARNESS_DATABASE")))
        outcome = self.script(self.cell, request)
        if isinstance(outcome, BaseException):
            self.last_attempt = {"stdout": ""}
            raise outcome
        return outcome


def good_result(cell: Any, request: CompletionRequest, parsed: Any = "answer") -> CompletionResult:
    if request.profile.startswith("architect."):
        return CompletionResult(
            text="Built the world.", provider="codex", model=cell.model,
            usage=Usage(input_tokens=5000, output_tokens=300, cache_read_tokens=20000),
            raw=fake_raw(cell, "bridge", commands_jsonl=json.dumps(
                {"phase": "result", "call": 1, "argv": ["py", "-m", "litharness", "world",
                                                        "summary"], "returncode": 0})),
            wall_ms=2000,
        )
    text = request.prompt[len(mt.SCENE_PREFIX):].split("\n\n")[0]
    answer = answer_for(text) if parsed == "answer" else parsed
    return CompletionResult(
        text=json.dumps(answer), provider="codex", model=cell.model,
        usage=Usage(input_tokens=700, output_tokens=40), parsed=answer, schema_requested=True,
        raw=fake_raw(cell, "completion"), wall_ms=900,
    )


def factory(script: Any, seen: list[Any]) -> Any:
    def make(cell: Any, binary: str, trace: Path | None) -> FakeProvider:
        return FakeProvider(cell, script, seen)

    return make


def fake_inspector(store: Path, work: Path) -> dict[str, Any]:
    assert store.is_file()
    return {
        "pre_check": {"exit": 0, "parsed": True, "ok": True, "complaints": 0,
                      "complaint_kinds": {}, "would_not_finish": 0},
        "accept_exit": 0, "accept_refusal_kinds": {},
        "post_check": {"exit": 0, "parsed": True, "ok": True, "complaints": 0,
                       "complaint_kinds": {}, "would_not_finish": 0},
        "shape": {**SHAPE, "basis": "accepted", "authority": {"accepted_canon": 10}},
    }


@pytest.fixture
def paid_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """`run` refuses test mode; these runs only ever reach fakes."""
    monkeypatch.setenv("LITHARNESS_ENV", "development")
    monkeypatch.delenv("LITHARNESS_DATABASE", raising=False)


def registered(reg: dict[str, Any]) -> Any:
    def verifier(paths: Any, **_: Any) -> dict[str, Any]:
        return reg

    return verifier


# =============================================================================== the plan


def test_the_module_imports_only_the_standard_library_at_top_level() -> None:
    tree = ast.parse(Path(mt.__file__).read_text(encoding="utf-8"))
    names = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            names |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module.split(".")[0])
    assert names - {"__future__"} <= set(sys.stdlib_module_names)


def test_the_plan_runs_both_summary_blocks_per_scene_rotated_and_the_seeds_abba() -> None:
    scenes = [f"scene-{index}" for index in range(1, 25)]
    units = mt.plan(scenes)
    recorded = [unit for unit in units if unit.block == "recorded"]
    current = [unit for unit in units if unit.block == "current"]
    seeds = [unit for unit in units if unit.block == "seed"]
    assert len(recorded) == 72 and len(current) == 96 and len(seeds) == 4
    assert len(units) == 172
    assert all(unit.role == "summary" for unit in recorded + current)
    assert all(unit.role == "seed" for unit in seeds)
    assert len({unit.unit_id for unit in units}) == len(units)
    assert [unit.block for unit in units[:7]] == ["recorded"] * 3 + ["current"] * 4
    assert [u.cell.name for u in recorded[:6]] == [
        "astra-medium", "luna-medium", "luna-high", "luna-medium", "luna-high", "astra-medium",
    ]
    assert [u.cell.name for u in current[:8]] == [
        "astra-medium", "astra-medium-2", "luna-medium", "luna-high",
        "astra-medium-2", "luna-medium", "luna-high", "astra-medium",
    ]
    for scene in scenes:
        assert sorted(u.cell.name for u in recorded if u.item == scene) == sorted(
            cell.name for cell in mt.SUMMARY_CELLS
        )
        assert sorted(u.cell.name for u in current if u.item == scene) == sorted(
            cell.name for cell in mt.CURRENT_CELLS
        )
    assert all(unit.unit_id.startswith("summary/") for unit in recorded)
    assert all(unit.unit_id.startswith("current/") for unit in current)
    assert [u.unit_id for u in seeds] == [
        "seed/astra-medium/r0", "seed/sol-medium/r0", "seed/sol-medium/r1", "seed/astra-medium/r1",
    ]
    assert [u.position for u in units] == list(range(len(units)))


def test_the_registration_digest_moves_with_every_margin(monkeypatch: pytest.MonkeyPatch) -> None:
    before = mt.registration_digest()
    for name, value in (("AGREEMENT_MARGIN", 0.2), ("VALIDATOR_MARGIN", 0.1),
                        ("SETTLEMENT_MARGIN", 0.3), ("SEED_AGREEMENT_MARGIN", 0.5),
                        ("MAX_ATTEMPTS", 3), ("COMPOSITE_COMPONENTS", ("delta_who",))):
        with monkeypatch.context() as patch:
            patch.setattr(mt, name, value)
            assert mt.registration_digest() != before
    assert mt.registration_digest() == before


def test_the_candidate_cells_are_the_policys_candidates() -> None:
    from litharness.providers.routing import PROVIDER_TIERS

    for cells in (mt.SUMMARY_CELLS, mt.CURRENT_CELLS):
        assert {cell.model for cell in cells if cell.arm == "candidate"} == {
            PROVIDER_TIERS["codex"]["basic"]
        }
    assert {cell.model for cell in mt.SEED_CELLS if cell.arm == "candidate"} == {
        PROVIDER_TIERS["codex"]["standard"]
    }
    assert mt.ASTRA.model == "gpt-6-astra" and mt.ASTRA.effort == mt.ADAPTER_EFFORT
    assert (mt.ASTRA_FLOOR.model, mt.ASTRA_FLOOR.effort) == (mt.ASTRA.model, mt.ASTRA.effort)
    assert mt.ASTRA_FLOOR.name != mt.ASTRA.name
    assert mt.CANDIDATES == {"summary": 2}
    assert [cell.name for cell in mt.SUMMARY_CANDIDATES] == ["luna-medium", "luna-high"]


# ========================================================================= request identity


def test_a_recorded_request_round_trips_and_a_changed_one_does_not() -> None:
    payload = mt.serial(summary_request(scene_text(1), LEDGER_BLOCK))
    assert mt.round_trips(payload)
    rebuilt = mt.rebuild_request(payload)
    assert rebuilt.sampler == PROFILES["mechanical"]
    changed = {**payload, "sampler": None}
    assert mt.round_trips(changed)  # a different request, but a faithful record of it
    assert mt.digest(changed) != mt.digest(payload)
    assert mt.round_trips(mt.serial(seed_request()))


def test_the_recorded_ledger_block_is_read_and_a_thread_block_refused() -> None:
    assert mt.ledger_subjects("") == []
    assert mt.ledger_subjects(LEDGER_BLOCK) == ["old_debt"]
    assert mt.ledger_subjects(mt.THREAD_HEADING + " as still open:\n- x") is None
    assert mt.ledger_subjects("\n\nThe book's open promises, as it stores them.\n- a: b") is None
    assert mt.ledger_subjects(LEDGER_BLOCK + "\n- a line with no owes") is None


def test_the_current_ledger_block_is_read_in_heads_format() -> None:
    text = scene_text(2)
    prompt = current_request(text, [mt.ledger_row(OLD_DEBT_ROW)]).prompt
    suffix = prompt[len(mt.SCENE_PREFIX + text):]
    assert suffix.startswith(mt.LEDGER_HEADING_CURRENT)
    assert mt.current_ledger_subjects(suffix) == ["old_debt"]
    assert mt.current_ledger_subjects("") == []
    assert mt.current_ledger_subjects(LEDGER_BLOCK) is None
    assert mt.current_ledger_subjects(suffix + mt.THREAD_HEADING + " as still open:\n- x") is None


def test_the_trial_rows_rebuild_the_current_request_through_the_summarisers_builder(
    tmp_path: Path,
) -> None:
    text = scene_text(2)
    rows = [mt.ledger_row({**OLD_DEBT_ROW, "paid_at_key": "s000004"})]
    assert rows[0]["status"] == "open" and "paid_at_key" not in rows[0]
    units_file = tmp_path / "units.json"
    mt.write_json(units_file, {"units": [
        {"scene": "scene-2", "text": text, "promises": rows, "call_class": "mechanical"},
        {"scene": "scene-1", "text": scene_text(1), "promises": [], "call_class": "mechanical"},
    ]})
    assert mt.render_summaries_mode(units_file, tmp_path / "out.json") == 0
    out = mt.read_json(tmp_path / "out.json")
    assert Path(out["source"]).name == "__init__.py"
    assert out["requests"]["scene-2"] == mt.serial(current_request(text, rows))
    assert out["requests"]["scene-1"] == mt.serial(summary_request(scene_text(1)))

    unit = unit_input(2)
    checks = mt.current_request_checks(unit, out["requests"]["scene-2"])
    assert all(checks.values()), checks
    assert unit["current_request"]["system"] != unit["request"]["system"]
    drifted = {**out["requests"]["scene-2"], "max_output_tokens": 1024}
    assert not mt.current_request_checks(unit, drifted)["other_fields"]
    other_scene = {**out["requests"]["scene-2"], "prompt": mt.SCENE_PREFIX + "Another scene."}
    assert not mt.current_request_checks(unit, other_scene)["scene"]
    assert mt.current_request_checks(unit, None) == {"present": False}


def test_the_accept_steps_report_is_read_and_must_add_up() -> None:
    assert mt.accept_counts(ACCEPT_STDOUT) == {
        "accepted": 196, "proposals": 200, "minted": 2, "left": 4,
    }
    assert mt.accept_counts("accepted 3 of 3 proposal(s) into canon\n") == {
        "accepted": 3, "proposals": 3, "minted": 0, "left": 0,
    }
    with pytest.raises(RuntimeError, match="add up"):
        mt.accept_counts("accepted 196 of 200 proposal(s) into canon\n  3 left proposed\n")
    with pytest.raises(RuntimeError, match="does not say"):
        mt.accept_counts("nothing happened")


def test_paid_split_is_the_handlers_rule() -> None:
    answer = {"promises_paid": ["Old Debt", {"subject": "new thing", "evidence_quote": "x"}, 7]}
    assert mt.paid_split(answer, ["old_debt"]) == (["Old Debt"], ["new thing"])
    assert mt.paid_split({"promises_paid": "nope"}, ["old_debt"]) == ([], [])


def _trial_for(index: int, answer: dict[str, Any], shown: list[str]) -> Any:
    text = scene_text(index)
    matched, unmatched = mt.paid_split(answer, shown)
    return mt.TrialView(
        scenes={f"scene-{index}": text, "scene-99": "Another scene entirely."},
        summaries={f"scene-{index}": {"content_hash": content_hash(text),
                                      "summary": flatten(answer),
                                      "promises": {"paid_matched": matched,
                                                   "paid_unmatched": unmatched}}},
        person_names=("Mara", "Tavi", "Esken"), seed_world={}, plan_items=[],
        pre_seed_plan_items=[], pre_seed_state_records=0,
        promise_rows={"old_debt": dict(OLD_DEBT_ROW)},
    )


def _recorded_row(request: CompletionRequest, answer: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "completed", "profile": "mechanical", "number": 11, "phase": "drain2",
        "request": mt.serial(request),
        "result": {
            "model": "gpt-6-astra", "parsed": answer, "text": json.dumps(answer),
            "usage": {"input_tokens": 1}, "wall_ms": 5,
            "raw": {"prompt": request.prompt, "system": request.effective_system,
                    "schema": request.schema, "native_schema": prepare_codex_schema(request.schema),
                    "argv": ["codex", "exec", "--model", "gpt-6-astra", "-c",
                             'model_reasoning_effort="medium"'],
                    "cli_version": "codex-cli 0.155.0"},
        },
    }


def test_every_identity_check_passes_on_a_faithful_record_and_names_the_one_that_fails(
    tmp_path: Path,
) -> None:
    request = summary_request(scene_text(2), LEDGER_BLOCK)
    answer = answer_for(scene_text(2))
    row = _recorded_row(request, answer)
    path = tmp_path / "0011-A1.json"
    mt.write_json(path, row)
    trial = _trial_for(2, answer, ["old_debt"])
    unit, checks = mt.summary_unit_input(path, row, trial)
    assert all(checks.values()), checks
    assert unit["scene"] == "scene-2" and unit["shown"] == ["old_debt"]
    assert unit["record"]["paid_matched"] == ["old_debt"]
    assert unit["required_names"] == ["Mara", "Tavi"]
    assert unit["quantities"] == ["2", "3"]
    assert mt.quantities("Rank 1.5 at 12, then 3.") == ["3", "12"]
    assert unit["request_sha256"] == mt.digest(row["request"])

    tampered = json.loads(json.dumps(row))
    tampered["result"]["raw"]["prompt"] += " "
    assert not mt.summary_unit_input(path, tampered, trial)[1]["sent_prompt"]
    drifted = json.loads(json.dumps(row))
    drifted["result"]["raw"]["argv"][-1] = 'model_reasoning_effort="high"'
    assert not mt.summary_unit_input(path, drifted, trial)[1]["recorded_model"]
    other = _trial_for(2, {**answer, "events": "Something else."}, ["old_debt"])
    assert not mt.summary_unit_input(path, row, other)[1]["accepted_summary"]


def test_the_native_schema_is_compared_up_to_the_order_of_required_members() -> None:
    native = prepare_codex_schema(SUMMARY_SCHEMA)
    reordered = json.loads(json.dumps(native))
    reordered["required"] = list(reversed(reordered["required"]))
    assert mt.canonical(mt.schema_canonical(reordered)) == mt.canonical(
        mt.schema_canonical(native)
    )
    assert mt.canonical(reordered) != mt.canonical(native)


# =============================================================================== outcomes


def test_the_validators_accept_a_conforming_answer_and_name_each_failure() -> None:
    text = scene_text(3)
    good = answer_for(text)
    assert mt.validators(good, text) == {
        "parsed": True, "strict_schema": True, "handler_usable": True, "losses": [],
        "conformance": True, "quotes": 2, "quotes_located": 2, "evidence": True,
    }
    assert not mt.validators(None, text)["conformance"]
    extra = {**good, "mood": "bleak"}
    assert not mt.validators(extra, text)["strict_schema"]
    blank_delta = {**good, "delta": {"who": "Mara", "what_changed": " ", "from": "a", "to": "b"}}
    assert mt.validators(blank_delta, text)["losses"] == ["delta"]
    no_description = {**good, "promises_opened": [{"subject": "x", "description": ""}]}
    assert "opened_fields" in mt.validators(no_description, text)["losses"]
    wrong_kind = {**good, "promises_opened": [{**good["promises_opened"][0], "kind": "vibe"}]}
    checked = mt.validators(wrong_kind, text)
    assert not checked["strict_schema"] and "opened_kind" in checked["losses"]
    paraphrased = {**good, "promises_paid": [{"subject": "old_debt",
                                              "evidence_quote": "Tavi said not yet."}]}
    checked = mt.validators(paraphrased, text)
    assert checked["conformance"] and not checked["evidence"] and checked["quotes_located"] == 1
    assert mt.validators({**good, "delta": None}, text)["conformance"]


def test_the_components_score_agreement_with_the_reference() -> None:
    record = answer_for(scene_text(4))
    shown = ["old_debt"]
    assert mt.components(record, record, shown) == dict.fromkeys(mt.REPORTED_COMPONENTS, 1.0)
    assert mt.components(None, record, shown) == dict.fromkeys(mt.REPORTED_COMPONENTS, 0.0)
    unpaid = {**record, "promises_paid": []}
    assert mt.components(unpaid, record, shown)["paid_matched_set"] == 0.0
    two = {**record, "promises_opened": [*record["promises_opened"],
                                         {"subject": "b", "description": "c", "kind": "mystery"}]}
    parts = mt.components(two, record, shown)
    assert parts["opened_count"] == 0.5 and parts["opened_kinds"] == 0.5
    stasis = {**record, "delta": None}
    parts = mt.components(stasis, record, shown)
    assert parts["delta_presence"] == 0.0 and parts["delta_who"] == 0.0
    renamed = {**record, "delta": {**record["delta"], "who": "  MARA "}}
    assert mt.components(renamed, record, shown)["delta_who"] == 1.0
    empty = {**record, "promises_opened": []}
    assert mt.components(empty, empty, shown)["opened_kinds"] == 1.0
    # The composite is the three components the settlement test does not cover.
    assert set(mt.COMPOSITE_COMPONENTS) == {"delta_who", "opened_count", "opened_kinds"}
    assert mt.composite(mt.components(two, record, shown)) == pytest.approx(2 / 3)
    assert mt.composite(mt.components(unpaid, record, shown)) == 1.0


def test_an_answer_scored_without_a_reference_has_no_agreement() -> None:
    unit = unit_input(3)
    answer = answer_for(unit["scene_text"])
    scored = mt.summary_outcome(unit, answer, "answered", None, None, 5, answer)
    assert scored["composite"] == 1.0 and scored["parsed"] and scored["fields"] is not None
    unscored = mt.summary_outcome(unit, answer, "answered", None, None, 5, None)
    assert unscored["components"] is None and unscored["composite"] is None
    assert unscored["fields"] is None and unscored["validators"]["conformance"]
    aggregate = mt.cell_aggregate([unscored, scored])
    assert aggregate["scored_scenes"] == 1 and aggregate["composite_mean"] == 1.0
    off_list = {**answer, "promises_paid": [{"subject": "Old-Debt!", "evidence_quote": ""}]}
    assert mt.summary_outcome(unit, off_list, "answered", None, None, 5, answer)[
        "paid_unmatched"] == 1


def test_the_field_table_reports_exact_and_normalized_beside_each_other() -> None:
    record = answer_for(scene_text(5))
    fields = mt.field_agreement(record, record, ["old_debt"])
    assert set(fields) == set(mt.STRUCTURED_FIELDS)
    assert all(value == {"exact": 1.0, "normalized": 1.0} for value in fields.values())
    cased = {**record, "delta": {**record["delta"], "to": "rank 1!"},
             "promises_paid": [{"subject": "Old Debt", "evidence_quote": '"Not yet," Tavi said.'}]}
    fields = mt.field_agreement(cased, record, ["old_debt"])
    assert fields["delta.to"] == {"exact": 0.0, "normalized": 1.0}
    assert fields["promises_paid.subject"] == {"exact": 0.0, "normalized": 1.0}
    assert fields["promises_paid.matched"] == {"exact": 0.0, "normalized": 1.0}
    assert mt.field_agreement(None, record, [])["delta.null"] == {"exact": 0.0, "normalized": 0.0}


def test_prose_is_counted_and_never_scored() -> None:
    record = answer_for(scene_text(1))
    counted = mt.prose(record, ["Mara", "Tavi", "Esken"], ["2", "40"])
    assert counted["words_total"] == sum(counted["words"].values())
    assert (counted["names_required"], counted["names_present"]) == (3, 2)
    assert (counted["quantities_required"], counted["quantities_present"]) == (2, 1)
    assert set(counted) == {"words", "words_total", "names_required", "names_present",
                            "quantities_required", "quantities_present"}


# ============================================================================= statistics


def test_the_exact_binomial_bounds_match_their_closed_forms() -> None:
    assert mt.cp_upper(0, 24, 0.025) == pytest.approx(1 - 0.025 ** (1 / 24), abs=1e-9)
    assert mt.cp_lower(24, 24, 0.025) == pytest.approx(0.025 ** (1 / 24), abs=1e-9)
    assert mt.cp_upper(0, 24, 0.025) < mt.VALIDATOR_MARGIN < mt.cp_upper(1, 24, 0.025)
    # V3 runs over the 23 scenes that listed a ledger; b = 0 still passes there.
    assert mt.cp_upper(0, 23, 0.025) < mt.VALIDATOR_MARGIN < mt.cp_upper(1, 23, 0.025)
    uppers = [mt.cp_upper(k, 24, 0.025) for k in range(25)]
    assert uppers == sorted(uppers) and uppers[-1] == 1.0
    assert mt.cp_lower(0, 24, 0.025) == 0.0


def test_the_validator_test_passes_only_without_excess_failures() -> None:
    clean = [True] * 24
    assert mt.validator_test(clean, clean, 0.025)["verdict"] == "pass"
    one = [False] + [True] * 23
    result = mt.validator_test(one, clean, 0.025)
    assert result["candidate_only_failures"] == 1 and result["verdict"] == "inconclusive"
    assert mt.validator_test(one, one, 0.025)["verdict"] == "pass"
    many = [False] * 14 + [True] * 10
    assert mt.validator_test(many, clean, 0.025)["verdict"] == "fail"
    assert mt.validator_test([False] * 13 + [True] * 11, clean, 0.025)["verdict"] == "inconclusive"
    assert mt.validator_test([True] * 23, [True] * 23, 0.025)["verdict"] == "pass"


def _flags(only_control: int, only_candidate: int, n: int = 24) -> tuple[list[bool], list[bool]]:
    """(candidate, control) agreement flags with that many discordant scenes of each kind."""
    candidate = [False] * only_control + [True] * only_candidate
    control = [True] * only_control + [False] * only_candidate
    rest = n - only_control - only_candidate
    return candidate + [True] * rest, control + [True] * rest


def test_the_settlement_test_bounds_the_difference_of_two_noisy_rates() -> None:
    for b, c, verdict in ((0, 0, "pass"), (1, 0, "pass"), (0, 7, "pass"), (2, 0, "inconclusive"),
                          (2, 5, "pass"), (2, 4, "inconclusive"), (3, 7, "pass"),
                          (15, 0, "inconclusive"), (16, 0, "fail")):
        result = mt.settlement_test(*_flags(b, c), 0.025)
        assert result["verdict"] == verdict, (b, c, result)
        assert (result["control_only_agreements"], result["candidate_only_agreements"]) == (b, c)
    result = mt.settlement_test(*_flags(1, 0), 0.025)
    assert result["margin_scenes"] == pytest.approx(6.0)
    assert result["excess_upper_bound"] == pytest.approx(mt.cp_upper(1, 24, 0.0125))
    with pytest.raises(ValueError, match="paired"):
        mt.settlement_test([True], [True, True], 0.025)


def test_the_agreement_test_reads_three_ways() -> None:
    control = [0.8] * 24
    assert mt.agreement_test(control, control, 0.025)["verdict"] == "pass"
    close = [0.8 + (0.2 if index % 2 else -0.2) for index in range(24)]
    assert mt.agreement_test(close, control, 0.025)["verdict"] == "pass"
    noisy = [0.8 + (0.3 if index % 2 else -0.3) for index in range(24)]
    assert mt.agreement_test(noisy, control, 0.025)["verdict"] == "inconclusive"
    worse = [0.4 + (0.05 if index % 2 else -0.05) for index in range(24)]
    assert mt.agreement_test(worse, control, 0.025)["verdict"] == "fail"
    with pytest.raises(ValueError, match="24"):
        mt.agreement_test(control[:10], control[:10], 0.025)
    with pytest.raises(ValueError, match="alpha"):
        mt.agreement_test(control, control, 0.05)


def _summary_row(conformance: bool = True, evidence: bool = True, value: float = 1.0,
                 tokens: int = 100, parsed: bool = True, settles: bool = True,
                 unmatched: int = 0) -> dict[str, Any]:
    return {"validators": {"conformance": conformance, "evidence": evidence},
            "composite": value, "components": {"paid_matched_set": 1.0 if settles else 0.0},
            "tokens": tokens, "parsed": parsed, "paid_unmatched": unmatched}


def _decision_rows(scenes: list[str]) -> tuple[dict[str, Any], dict[str, Any]]:
    full = {scene: _summary_row() for scene in scenes}
    cheap = {scene: _summary_row(tokens=90) for scene in scenes}
    recorded = {"astra-medium": dict(full), "luna-medium": dict(full), "luna-high": dict(cheap)}
    current = {"astra-medium": dict(full), "astra-medium-2": dict(full),
               "luna-medium": dict(full), "luna-high": dict(cheap)}
    return recorded, current


def test_the_summary_decision_needs_every_test_of_both_blocks_and_proposes_codex_only() -> None:
    scenes = [f"scene-{index}" for index in range(1, 25)]
    ledger_scenes = scenes[1:]
    recorded, current = _decision_rows(scenes)
    decision = mt.summary_decision(recorded, current, scenes, ledger_scenes)
    medium = decision["candidates"]["luna-medium"]
    assert medium["verdict"] == "pass"
    assert set(medium["tests"]["recorded"]) == {"conformance", "evidence", "settlement",
                                                "agreement"}
    assert set(medium["tests"]["current"]) == {"conformance", "evidence", "clean_copy",
                                               "settlement", "agreement"}
    assert medium["tests"]["current"]["clean_copy"]["n"] == 23
    proposal = decision["proposal"]
    assert proposal["cell"] == "luna-high" and proposal["effort"] == "high"
    assert proposal["provider"] == "codex" and proposal["tier"] == "basic"
    assert "settings" not in proposal
    assert "claude-haiku-4-5" in proposal["scope"] and "codex only" in proposal["scope"]

    del current["luna-high"]["scene-7"]
    decision = mt.summary_decision(recorded, current, scenes, ledger_scenes)
    assert decision["candidates"]["luna-high"] == {"verdict": "incomplete",
                                                    "missing": ["current/scene-7"]}
    assert decision["proposal"]["cell"] == "luna-medium"

    recorded["luna-medium"] = {**recorded["luna-medium"],
                               "scene-1": _summary_row(conformance=False)}
    assert mt.summary_decision(recorded, current, scenes, ledger_scenes)["proposal"] is None


def test_a_candidate_that_copies_a_subject_off_the_list_does_not_pass() -> None:
    scenes = [f"scene-{index}" for index in range(1, 25)]
    recorded, current = _decision_rows(scenes)
    current["luna-medium"] = {**current["luna-medium"], "scene-2": _summary_row(unmatched=1)}
    decision = mt.summary_decision(recorded, current, scenes, scenes[1:])
    medium = decision["candidates"]["luna-medium"]
    assert medium["tests"]["current"]["clean_copy"]["candidate_only_failures"] == 1
    assert medium["verdict"] == "inconclusive"
    # Scene 1 listed no ledger, so a payment there is unmatched by construction and not read.
    recorded, current = _decision_rows(scenes)
    current["luna-medium"] = {**current["luna-medium"], "scene-1": _summary_row(unmatched=1)}
    decision = mt.summary_decision(recorded, current, scenes, scenes[1:])
    assert decision["candidates"]["luna-medium"]["verdict"] == "pass"


def test_a_control_that_did_not_parse_withholds_its_blocks_floor_tests() -> None:
    scenes = [f"scene-{index}" for index in range(1, 25)]
    recorded, current = _decision_rows(scenes)
    recorded["astra-medium"] = {**recorded["astra-medium"],
                                "scene-3": _summary_row(parsed=False, value=0.0, settles=False)}
    decision = mt.summary_decision(recorded, current, scenes, scenes[1:])
    tests = decision["candidates"]["luna-medium"]["tests"]["recorded"]
    assert tests["settlement"]["verdict"] == "inconclusive"
    assert tests["agreement"]["scenes"] == ["scene-3"]
    assert decision["candidates"]["luna-medium"]["verdict"] == "inconclusive"
    recorded, current = _decision_rows(scenes)
    current["astra-medium-2"] = {**current["astra-medium-2"],
                                 "scene-9": _summary_row(parsed=False, value=0.0)}
    decision = mt.summary_decision(recorded, current, scenes, scenes[1:])
    tests = decision["candidates"]["luna-high"]["tests"]["current"]
    assert tests["agreement"]["verdict"] == "inconclusive"
    assert tests["conformance"]["verdict"] == "pass"


def test_a_settlement_deficit_is_not_averaged_away() -> None:
    scenes = [f"scene-{index}" for index in range(1, 25)]
    recorded, current = _decision_rows(scenes)
    # Five scenes settle another set; the composite, which does not carry it, stays at 1.
    recorded["luna-medium"] = {**recorded["luna-medium"],
                               **{s: _summary_row(settles=False) for s in scenes[:5]}}
    tests = mt.summary_decision(recorded, current, scenes, scenes[1:])["candidates"][
        "luna-medium"]["tests"]["recorded"]
    assert tests["agreement"]["verdict"] == "pass"
    assert tests["settlement"]["verdict"] == "inconclusive"


def _seed_row(clean: bool = True, agreement: float = 1.0) -> dict[str, Any]:
    check = {"ok": clean, "would_not_finish": 0}
    return {"status": "answered", "pre_check": check, "accept_exit": 0, "post_check": check,
            "agreement": agreement}


def test_the_seed_screen_reads_two_replicates_and_proposes_nothing() -> None:
    both = {"r0": _seed_row(), "r1": _seed_row()}
    half = {"r0": _seed_row(), "r1": _seed_row(clean=False)}
    far = {"r0": _seed_row(agreement=0.5), "r1": _seed_row(agreement=0.5)}
    for rows, verdict in (
        ({"astra-medium": both, "sol-medium": both}, "no_gross_failure_seen"),
        ({"astra-medium": both, "sol-medium": half}, "failure_seen"),
        ({"astra-medium": half, "sol-medium": half}, "unclear"),
        ({"astra-medium": both, "sol-medium": far}, "unclear"),
        ({"astra-medium": both, "sol-medium": {"r0": _seed_row()}}, "incomplete"),
    ):
        screen = mt.seed_screen(rows)
        assert screen["verdict"] == verdict
        assert screen["proposal"] is None and "two replicates" in screen["licence"]
    unusable = {**_seed_row(), "status": "answered_unusable"}
    assert not mt.seed_clean(unusable)


# ============================================================================ transport


@pytest.mark.parametrize(
    ("kind", "message", "expected"),
    [
        (ProviderFailureKind.TIMEOUT, "Codex timed out after 300s", "transport_failure"),
        (ProviderFailureKind.RATE_LIMIT, "usage limit", "transport_failure"),
        (ProviderFailureKind.MALFORMED_RESPONSE,
         "Codex request or response was unusable: Codex attempted an unpermitted activity: "
         "command_execution", "answered_unusable"),
        (ProviderFailureKind.MALFORMED_RESPONSE,
         "Codex request or response was unusable: The architect returned without any "
         "successful scoped world command", "answered_unusable"),
        (ProviderFailureKind.MALFORMED_RESPONSE,
         "Codex request or response was unusable: The scoped command failed "
         "(invalid_arguments): arguments must be an array", "answered_unusable"),
        (ProviderFailureKind.MALFORMED_RESPONSE,
         "Codex request or response was unusable: The scoped command failed (timeout): tool "
         "timeout", "transport_failure"),
        (ProviderFailureKind.MALFORMED_RESPONSE,
         "Codex request or response was unusable: Codex did not report exactly one successful "
         "turn", "transport_failure"),
        # No attempt evidence of a model turn: stderr words alone are transport.
        (ProviderFailureKind.REFUSAL, "refused", "transport_failure"),
        (ProviderFailureKind.SAFETY, "Codex exited with code 1: prohibited", "transport_failure"),
    ],
)
def test_the_models_own_act_is_an_unusable_answer_and_the_rest_is_transport(
    kind: ProviderFailureKind, message: str, expected: str,
) -> None:
    assert mt.classify_failure(ProviderError(message, kind=kind))[0] == expected


def test_a_refusal_is_the_models_act_only_with_a_model_turn_in_the_attempt() -> None:
    error = ProviderError("Codex exited with code 1: refusal", kind=ProviderFailureKind.REFUSAL)
    completed = {"stdout": "\n".join(json.dumps(event) for event in (
        {"type": "thread.started"}, {"type": "turn.started"},
        {"type": "turn.completed", "usage": {"input_tokens": 1, "output_tokens": 1}},
    ))}
    message = {"stdout": json.dumps({"type": "item.completed",
                                     "item": {"type": "agent_message", "text": "I can't."}})}
    platform = {"stdout": json.dumps({"type": "error", "message": "safety system unavailable"})}
    assert mt.classify_failure(error, completed) == ("answered_unusable", "model_refusal")
    assert mt.classify_failure(error, message) == ("answered_unusable", "model_refusal")
    assert mt.classify_failure(error, platform) == ("transport_failure", "platform_refusal")
    assert mt.classify_failure(error, {"stdout": "not json"})[0] == "transport_failure"
    assert mt.classify_failure(error, None)[0] == "transport_failure"
    assert not mt.model_turn_seen("stdout")


def test_served_as_registered_names_the_first_mismatch() -> None:
    unit = next(u for u in mt.plan(["scene-1"]) if u.cell.name == "luna-high")
    raw = fake_raw(unit.cell, "completion")
    assert mt.served_as_registered(raw, unit, VERSION_STRING) is None
    assert mt.served_as_registered({**raw, "requested_model": "gpt-6-astra"}, unit,
                                   VERSION_STRING) == "requested_model"
    assert mt.served_as_registered(raw, unit, "codex-cli 0.1") == "cli_version"
    assert mt.served_as_registered({**raw, "mode": "bridge"}, unit, VERSION_STRING) == "mode"
    lax = {**raw, "argv": [item for item in raw["argv"] if item != "--ephemeral"]}
    assert mt.served_as_registered(lax, unit, VERSION_STRING) == "isolation"
    assert mt.served_as_registered(raw, unit, VERSION_STRING, "elsewhere/python.exe") is None


def test_a_seeds_bridge_must_have_run_on_this_interpreter() -> None:
    seed = next(u for u in mt.plan(["scene-1"]) if u.role == "seed")
    raw = fake_raw(seed.cell, "bridge")
    assert mt.served_as_registered(raw, seed, VERSION_STRING, sys.executable) is None
    elsewhere = {**raw, "settings": {"mcp_servers.litharness.command": "C:/other/python.exe"}}
    assert mt.served_as_registered(elsewhere, seed, VERSION_STRING, sys.executable) == (
        "bridge_interpreter"
    )
    assert mt.served_as_registered({**raw, "settings": None}, seed, VERSION_STRING,
                                   sys.executable) == "bridge_interpreter"


def test_the_ledger_charges_reservations_for_unknown_and_interrupted_attempts() -> None:
    lines = [
        {"event": "started", "invocation": 1},
        {"event": "dispatch", "invocation": 1, "seq": 1, "unit": "summary/a/x", "role": "summary"},
        {"event": "call", "invocation": 1, "seq": 1, "unit": "summary/a/x", "role": "summary",
         "status": "answered", "tokens": 900, "usage_known": True, "wall_ms": 2000},
        {"event": "dispatch", "invocation": 1, "seq": 2, "unit": "summary/b/x", "role": "summary"},
        {"event": "call", "invocation": 1, "seq": 2, "unit": "summary/b/x", "role": "summary",
         "status": "transport_failure", "tokens": None, "usage_known": False, "wall_ms": 1000},
        {"event": "dispatch", "invocation": 1, "seq": 3, "unit": "seed/s/r0", "role": "seed"},
    ]
    state = mt.ledger_state(lines)
    reserve = mt.RESERVE
    assert state.used["calls"] == 3
    assert state.used["tokens"] == 900 + reserve["summary"]["tokens"] + reserve["seed"]["tokens"]
    assert state.used["seconds"] == pytest.approx(3.0 + reserve["seed"]["seconds"])
    assert set(state.answered) == {"summary/a/x"}
    assert state.attempts["summary/b/x"] == 1 and state.unknown_usage == 2
    assert [item["unit"] for item in state.interrupted] == ["seed/s/r0"]
    assert not state.finished and state.next_seq == 4 and state.halted == []
    halted = [*lines, {"event": "dispatch", "invocation": 1, "seq": 4, "unit": "current/a/x",
                       "role": "summary"},
              {"event": "call", "invocation": 1, "seq": 4, "unit": "current/a/x",
               "role": "summary", "status": "halted", "failure_kind": "served_otherwise:mode",
               "tokens": 10, "usage_known": True, "wall_ms": 10}]
    assert [line["unit"] for line in mt.ledger_state(halted).halted] == ["current/a/x"]


def test_admission_refuses_a_call_whose_worst_case_crosses_a_ceiling() -> None:
    empty = {"calls": 0.0, "tokens": 0.0, "seconds": 0.0}
    assert mt.admit("seed", empty) is None
    assert mt.admit("summary", {**empty, "calls": mt.LIMITS["calls"]}) == "ceiling:calls"
    near = mt.LIMITS["tokens"] - mt.RESERVE["seed"]["tokens"] + 1
    assert mt.admit("seed", {**empty, "tokens": near}) == "ceiling:tokens"
    assert mt.admit("summary", {**empty, "tokens": near}) is None
    late = mt.LIMITS["seconds"] - 100
    assert mt.admit("summary", {**empty, "seconds": late}) == "ceiling:seconds"
    assert mt.LIMITS["calls"] >= len(mt.plan([f"s{i}" for i in range(24)]))


# ================================================================================== run


def test_run_buys_each_unit_once_and_redispatches_a_transport_failure_only_once(
    tmp_path: Path, paid_env: None,
) -> None:
    paths, reg = build_arm(tmp_path)
    seen: list[Any] = []
    failed: set[tuple[str, str | None, str]] = set()

    def script(cell: Any, request: CompletionRequest) -> Any:
        key = (cell.name, request.system, request.prompt)
        if cell.name == "luna-high" and "door 3." in request.prompt and key not in failed:
            failed.add(key)
            return ProviderError("Codex timed out after 300s", kind=ProviderFailureKind.TIMEOUT)
        if cell.name == "luna-medium" and "door 4." in request.prompt:
            return ProviderError("Codex timed out", kind=ProviderFailureKind.TIMEOUT)
        return good_result(cell, request)

    line = mt.run(paths=paths, verifier=registered(reg), provider_factory=factory(script, seen),
                  guard=lambda: None, log=lambda _: None)
    assert line["missing"] == ["summary/scene-4/luna-medium", "current/scene-4/luna-medium"]
    assert not line["complete"]
    lines = mt.read_ledger(paths.ledger)
    calls = [item for item in lines if item.get("event") == "call"]
    assert len(calls) == 172 + 4  # two re-dispatches that answered, two that never did
    by_unit: dict[str, list[str]] = {}
    for item in calls:
        by_unit.setdefault(item["unit"], []).append(item["status"])
    for block in ("summary", "current"):
        assert by_unit[f"{block}/scene-3/luna-high"] == ["transport_failure", "answered"]
        assert by_unit[f"{block}/scene-4/luna-medium"] == ["transport_failure"] * 2
    retried = {f"{block}/{scene}" for block in ("summary", "current")
               for scene in ("scene-3/luna-high", "scene-4/luna-medium")}
    assert all(len(statuses) == 1 for unit, statuses in by_unit.items() if unit not in retried)
    failure = next(item for item in calls if item["status"] == "transport_failure")
    receipt = mt.read_json(paths.root / failure["receipt"])
    assert receipt["result"] is None and receipt["failure"]["kind"] == "timeout"
    seeds = [item for item in seen if item[1].startswith("architect.")]
    summaries = [item for item in seen if item[1] == "mechanical"]
    assert len(seeds) == 4 and all(item[2] and item[2].endswith("book.db") for item in seeds)
    assert len({item[2] for item in seeds}) == 4
    assert all(item[2] is None for item in summaries)
    assert os.environ.get("LITHARNESS_DATABASE") is None
    started = next(item for item in lines if item.get("event") == "started")
    assert started["executable"] == sys.executable

    again = mt.run(paths=paths, verifier=registered(reg), provider_factory=factory(script, seen),
                   guard=lambda: None, log=lambda _: None)
    assert again["fresh_calls"] == 0
    assert again["missing"] == ["summary/scene-4/luna-medium", "current/scene-4/luna-medium"]


def test_each_block_sends_its_own_registered_bytes(tmp_path: Path, paid_env: None) -> None:
    paths, reg = build_arm(tmp_path)
    sent: dict[str, str] = {}
    headings: dict[str, int] = {"recorded": 0, "current": 0}

    def script(cell: Any, request: CompletionRequest) -> Any:
        headings["recorded"] += mt.LEDGER_HEADING_RECORDED in request.prompt
        headings["current"] += mt.LEDGER_HEADING_CURRENT in request.prompt
        return good_result(cell, request)

    mt.run(paths=paths, verifier=registered(reg), provider_factory=factory(script, []),
           guard=lambda: None, log=lambda _: None)
    for line in mt.read_ledger(paths.ledger):
        if line.get("event") == "call":
            sent[line["unit"]] = mt.read_json(paths.root / line["receipt"])["request_sha256"]
    scene = unit_input(2)
    assert sent["summary/scene-2/luna-high"] == scene["request_sha256"]
    assert sent["current/scene-2/luna-high"] == scene["current_request_sha256"]
    assert scene["request_sha256"] != scene["current_request_sha256"]
    # 23 scenes list a ledger: three recorded cells send the old block, four the new one.
    assert headings == {"recorded": 3 * 23, "current": 4 * 23}


def test_run_stops_before_a_call_past_a_ceiling(
    tmp_path: Path, paid_env: None, monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths, reg = build_arm(tmp_path)
    monkeypatch.setitem(mt.LIMITS, "calls", 5)
    seen: list[Any] = []
    line = mt.run(paths=paths, verifier=registered(reg),
                  provider_factory=factory(good_result, seen), guard=lambda: None,
                  log=lambda _: None)
    assert line["stop"] == "ceiling:calls" and len(seen) == 5 and not line["complete"]
    with pytest.raises(RuntimeError, match="ceiling is already reached"):
        mt.run(paths=paths, verifier=registered(reg), provider_factory=factory(good_result, seen),
               guard=lambda: None, log=lambda _: None)


def test_run_halts_on_a_call_served_otherwise_and_then_buys_nothing_more(
    tmp_path: Path, paid_env: None,
) -> None:
    paths, reg = build_arm(tmp_path)

    def other_version(cell: Any, request: CompletionRequest) -> CompletionResult:
        result = good_result(cell, request)
        result.raw["cli_version"] = "codex-cli 1.0"
        return result

    seen: list[Any] = []
    line = mt.run(paths=paths, verifier=registered(reg),
                  provider_factory=factory(other_version, seen), guard=lambda: None,
                  log=lambda _: None)
    assert line["stop"].startswith("halt:served_otherwise:cli_version")
    assert mt.ledger_state(mt.read_ledger(paths.ledger)).answered == {}
    with pytest.raises(RuntimeError, match="served otherwise"):
        mt.run(paths=paths, verifier=registered(reg),
               provider_factory=factory(good_result, seen), guard=lambda: None,
               log=lambda _: None)
    assert len(seen) == 1

    fresh, reg2 = build_arm(tmp_path / "second")
    seen = []

    def drop_lock(cell: Any, request: CompletionRequest) -> CompletionResult:
        release_lock(fresh)
        return good_result(cell, request)

    line = mt.run(paths=fresh, verifier=registered(reg2), provider_factory=factory(drop_lock, seen),
                  guard=lambda: None, log=lambda _: None)
    assert line["stop"].startswith("halt:") and len(seen) == 1


def test_run_halts_when_the_pinned_source_tree_changes(tmp_path: Path, paid_env: None) -> None:
    paths, reg = build_arm(tmp_path)
    source = paths.source_dir / "src" / "litharness"
    source.mkdir(parents=True)
    (source / "cli.py").write_text("registered = True\n", encoding="utf-8")
    reg["runtime"]["trees"] = {mt.key_for(paths.source_dir, paths.root):
                               mt.tree_hashes(paths.source_dir)}
    seen: list[Any] = []

    def edit_after_first(cell: Any, request: CompletionRequest) -> CompletionResult:
        (source / "added.py").write_text("x = 1\n", encoding="utf-8")
        return good_result(cell, request)

    line = mt.run(paths=paths, verifier=registered(reg),
                  provider_factory=factory(edit_after_first, seen), guard=lambda: None,
                  log=lambda _: None)
    assert line["stop"].startswith("halt:changed pinned runtime tree") and len(seen) == 1
    assert "src/litharness/added.py" in line["stop"]


def test_run_refuses_test_mode_and_a_reading(tmp_path: Path, paid_env: None,
                                             monkeypatch: pytest.MonkeyPatch) -> None:
    paths, reg = build_arm(tmp_path)
    monkeypatch.setenv("LITHARNESS_ENV", "test")
    with pytest.raises(RuntimeError, match="test mode"):
        mt.run(paths=paths, verifier=registered(reg), provider_factory=factory(good_result, []))
    monkeypatch.setenv("LITHARNESS_ENV", "development")
    paths.results.write_text("{}", encoding="utf-8")
    with pytest.raises(RuntimeError, match="reading exists"):
        mt.run(paths=paths, verifier=registered(reg), provider_factory=factory(good_result, []))


def test_the_lock_must_name_this_arm(tmp_path: Path) -> None:
    paths = make_paths(tmp_path)
    with pytest.raises(RuntimeError, match="not held"):
        mt.check_lock(paths)
    paths.lock_holder.parent.mkdir(parents=True)
    paths.lock_holder.write_text("cost-that-bites-milder-20260922: someone\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="someone else"):
        mt.check_lock(paths)
    take_lock(paths)
    mt.check_lock(paths)


# ======================================================================= pinned copies


def test_the_tree_hash_sees_every_file_but_bytecode(tmp_path: Path) -> None:
    folder = tmp_path / "tree"
    (folder / "pkg" / "__pycache__").mkdir(parents=True)
    (folder / "pkg" / "a.py").write_text("a = 1\n", encoding="utf-8")
    (folder / "pkg" / "__pycache__" / "a.cpython-313.pyc").write_bytes(b"\x00")
    first = mt.tree_hashes(folder)
    assert set(first) == {"pkg/a.py"}
    (folder / "pkg" / "__pycache__" / "b.cpython-313.pyc").write_bytes(b"\x01")
    assert mt.tree_hashes(folder) == first
    (folder / "pkg" / "b.py").write_text("b = 2\n", encoding="utf-8")
    assert mt.tree_difference(first, mt.tree_hashes(folder)) == ["pkg/b.py"]
    assert mt.tree_hashes(tmp_path / "absent") == {}
    assert mt.key_for(folder, tmp_path) == "tree"
    outside = mt.key_for(folder, tmp_path / "elsewhere")
    assert Path(outside).is_absolute() and (tmp_path / "elsewhere" / outside) == folder.resolve()


def test_the_interpreter_check_refuses_the_live_checkout(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="pinned runtime"):
        mt.check_interpreter(make_paths(tmp_path))


def _codex_folder(tmp_path: Path) -> Path:
    folder = tmp_path / "bin" / "247581e40ee272fb"
    folder.mkdir(parents=True)
    (folder / "codex.exe").write_bytes(b"codex binary")
    (folder / "codex-command-runner.exe").write_bytes(b"helper")
    return folder / "codex.exe"


def _reader(path: Path) -> dict[str, str]:
    resolved = path.resolve()
    return {"path": str(resolved), "sha256": mt.sha_file(resolved), "version": VERSION_STRING}


def test_the_codex_folder_is_pinned_whole_and_guarded(tmp_path: Path) -> None:
    paths = make_paths(tmp_path)
    original = _codex_folder(tmp_path)
    pinned = mt.pin_codex(paths, original, _reader)
    folder = paths.codex_dir / "247581e40ee272fb"
    assert Path(pinned["path"]) == (folder / "codex.exe").resolve()
    assert pinned["original"] == str(original.resolve())
    assert set(pinned["folder_hashes"]) == {"codex.exe", "codex-command-runner.exe"}
    assert pinned["folder"] == "local/codex/247581e40ee272fb"
    assert mt.pin_codex(paths, original, _reader) == pinned  # the same bytes: kept
    reg = {"binary": pinned}
    mt.check_codex(reg, paths, _reader)
    guard = mt.stat_guard(folder)
    assert guard() is None
    # An update of the operator's app changes nothing the arm runs.
    original.write_bytes(b"a newer codex binary")
    mt.check_codex(reg, paths, _reader)
    assert guard() is None
    (folder / "codex-command-runner.exe").write_bytes(b"a changed helper")
    assert guard() == "binary_changed"
    with pytest.raises(RuntimeError, match="pinned Codex folder changed"):
        mt.check_codex(reg, paths, _reader)


def test_the_claim_is_rewritten_before_registration_only(tmp_path: Path) -> None:
    paths = make_paths(tmp_path)
    for path in (paths.prereg, paths.runbook):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("edited\n", encoding="utf-8")
    claim = mt.refresh_claim(paths=paths)
    assert claim["status"] == "registered"
    assert [item["path"] for item in claim["artifacts"]] == ["arm/PREREG.md", "arm/RUNBOOK.md"]
    assert claim["artifacts"][0]["sha256"] == mt.sha_file(paths.prereg)
    governance.parse_claim(claim)
    mt.write_json(paths.registration, {})
    with pytest.raises(RuntimeError, match="prepare again"):
        mt.refresh_claim(paths=paths)
    paths.registration.unlink()
    mt.append_ledger(paths.ledger, {"event": "dispatch", "seq": 1, "unit": "u", "role": "seed"})
    with pytest.raises(RuntimeError, match="dispatched"):
        mt.refresh_claim(paths=paths)


# ============================================================================= prepare


def _write(path: Path, text: str = "frozen\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _prepared_trial(tmp_path: Path) -> tuple[Any, Any, dict[str, Any], dict[str, Any],
                                            dict[str, Any]]:
    paths = make_paths(tmp_path)
    for path in mt.sources(paths):
        _write(path)
    scenes: dict[str, str] = {}
    summaries: dict[str, dict[str, Any]] = {}
    recorded: dict[str, Any] = {}
    for index in range(1, 25):
        text = scene_text(index)
        ledger = LEDGER_BLOCK if index > 1 else ""
        request = summary_request(text, ledger)
        answer = answer_for(text)
        mt.write_json(paths.trial / "calls" / f"{100 + index:04d}-A1.json",
                      {**_recorded_row(request, answer), "number": 100 + index})
        scenes[f"scene-{index}"] = text
        recorded[f"scene-{index}"] = mt.serial(request)
        matched, unmatched = mt.paid_split(answer, mt.ledger_subjects(ledger))
        summaries[f"scene-{index}"] = {"content_hash": content_hash(text),
                                       "summary": flatten(answer),
                                       "promises": {"paid_matched": matched,
                                                    "paid_unmatched": unmatched}}
    recorded_seed = {**mt.serial(seed_request()), "profile": "architect.seed.v8"}
    head_seed = mt.serial(seed_request())
    mt.write_json(paths.trial / "calls" / mt.TRIAL_SEED_CALL,
                  {"profile": "architect.seed.v8", "status": "completed",
                   "request": recorded_seed})
    paths.pre_seed_store.parent.mkdir(parents=True, exist_ok=True)
    with SqliteStore.open(paths.pre_seed_store):
        pass
    for path in mt.trial_inputs(paths, [{"call": "none"}]):
        if not path.exists() and path.name != "none":
            _write(path)
    trial = mt.TrialView(scenes=scenes, summaries=summaries, person_names=("Mara", "Tavi"),
                         seed_world=SHAPE, plan_items=[["plan-premise", "premise", "{}"]],
                         pre_seed_plan_items=[["plan-premise", "premise", "{}"]],
                         pre_seed_state_records=0, promise_rows={"old_debt": dict(OLD_DEBT_ROW)},
                         seed_counts={"accepted": 196, "proposals": 200, "minted": 2, "left": 4})
    return paths, trial, recorded, recorded_seed, head_seed


def fake_git(paths: Any, *, pushed: bool = True, dirty: bytes = b"",
             committed: dict[str, bytes] | None = None) -> Any:
    def git(args: list[str], root: Path) -> bytes:
        if args[0] == "status":
            return dirty
        if args[0] == "rev-parse":
            return b"0123abcd\n"
        if args[0] == "branch":
            return b"  origin/main\n" if pushed else b""
        if args[0] == "show":
            name = args[1].split(":", 1)[1]
            if committed is not None and name in committed:
                return committed[name]
            return (root / name).read_bytes()
        raise AssertionError(args)

    return git


def fake_runtime(paths: Any, git: Any) -> dict[str, Any]:
    """The pinned runtime's files, without a venv or an archive of anything real."""
    for path in (paths.runtime_python, paths.runtime_dir / "pyvenv.cfg", paths.runtime_pth,
                 paths.source_archive, paths.source_dir / "src" / "litharness" / "__init__.py",
                 paths.local / "contracts" / "litharness_contracts" / "__init__.py"):
        _write(path)
    return {"archive_sha256": mt.sha_file(paths.source_archive), "purelib": "site-packages",
            "probe": {"litharness": str(paths.source_dir / "src" / "litharness" / "__init__.py"),
                      "litharness_contracts": str(paths.local / "contracts"
                                                  / "litharness_contracts" / "__init__.py")}}


def fake_pinner(paths: Any, binary: Path, reader: Any) -> dict[str, Any]:
    return {"path": str(binary), "sha256": "0" * 64, "version": VERSION_STRING,
            "original": str(binary), "folder": "local/codex/build", "folder_hashes": {}}


def fake_renderer(paths: Any, recorded: dict[str, Any], recorded_seed: dict[str, Any],
                  head_seed: dict[str, Any], rendered: list[tuple[str, str]],
                  drift: str | None = None) -> Any:
    def renderer(python: Path, mode: str, arguments: Any, out: Path, binary: Any) -> Any:
        frozen = python == paths.frozen_python
        assert frozen or python == paths.runtime_python
        rendered.append(("frozen" if frozen else "pinned", mode))
        source = str((paths.frozen_source if frozen else paths.source_dir / "src")
                     / "litharness" / "__init__.py")
        if mode == "render-summaries":
            if frozen:
                requests = dict(recorded)
                if drift is not None:
                    requests[drift] = {**requests[drift], "prompt": "drifted"}
                return {"source": source, "requests": requests}
            # The real mode, in process: HEAD's summariser is the pinned source here.
            mt.render_summaries_mode(Path(arguments[1]), out)
            return {**mt.read_json(out), "source": source}
        if mode == "open-store":
            with SqliteStore.open(Path(arguments[1])):
                pass
            return {"source": source}
        return {"source": source, "request": recorded_seed if frozen else head_seed}

    return renderer


def test_prepare_pins_freezes_the_inputs_and_registers_without_a_call(tmp_path: Path) -> None:
    paths, trial, recorded, recorded_seed, head_seed = _prepared_trial(tmp_path)
    rendered: list[tuple[str, str]] = []
    registration = mt.prepare(
        paths=paths, codex_binary=Path("codex.exe"), git=fake_git(paths),
        trial_reader=lambda _: trial,
        renderer=fake_renderer(paths, recorded, recorded_seed, head_seed, rendered),
        runtime_builder=fake_runtime, pinner=fake_pinner,
    )
    assert rendered == [("frozen", "render-summaries"), ("pinned", "render-summaries"),
                        ("frozen", "render-seed"), ("pinned", "open-store"),
                        ("pinned", "render-seed")]
    assert registration["planned_units"] == 172
    assert registration["inputs"]["scenes"] == [f"scene-{index}" for index in range(1, 25)]
    identity = registration["request_identity"]
    assert identity["summaries"]["passed"] and identity["seed"]["passed"]
    assert identity["summaries"]["frozen_rebuild"]["whole_request_byte_identical"] == 24
    assert identity["summaries"]["current"]["system_differs"] == 23
    assert identity["summaries"]["current"]["prompt_differs"] == 23
    assert identity["seed"]["recorded_profile"] == "architect.seed.v8"
    assert identity["seed"]["seed_world_counts"]["accepted"] == 196
    assert all(item["current_request_sha256"] != item["request_sha256"]
               for item in registration["inputs"]["summary_requests"][1:])
    local = {mt.rel(path, paths.root) for path in
             (paths.summary_inputs, paths.seed_inputs, paths.seed_template)}
    assert local <= set(registration["input_hashes"])
    assert set(registration["source_hashes"]) == {
        "runner.py", "arm/PREREG.md", "arm/RUNBOOK.md", "test_runner.py",
        "trial_here/registration.json",
    }
    runtime = registration["runtime"]
    assert set(runtime["trees"]) == {"local/source", "local/contracts/litharness_contracts"}
    assert "local/runtime/Scripts/python.exe" in runtime["files"] or os.name != "nt"
    claim = mt.read_json(paths.claim)
    assert claim["status"] == "registered"
    assert [item["path"] for item in claim["artifacts"]] == [
        "arm/PREREG.md", "arm/RUNBOOK.md", "arm/registration.json"]
    governance.parse_claim(claim)
    assert mt.verify(paths, git=fake_git(paths), interpreter=None)["registration_digest"] == (
        mt.registration_digest()
    )

    with pytest.raises(RuntimeError, match="not committed as registered"):
        mt.verify(paths, git=fake_git(paths, committed={"arm/PREREG.md": b"older\n"}),
                  interpreter=None)
    with pytest.raises(RuntimeError, match="no remote branch"):
        mt.verify(paths, git=fake_git(paths, pushed=False), interpreter=None)
    # The reading needs the registration committed, not pushed: run required the push.
    mt.verify(paths, git=fake_git(paths, pushed=False), interpreter=None, require_pushed=False)
    # A later commit to the live src/ changes nothing the arm runs, so it blocks nothing.
    mt.verify(paths, git=fake_git(paths, dirty=b" M src/litharness/cli.py\n"), interpreter=None)
    with pytest.raises(RuntimeError, match="pinned runtime"):
        mt.verify(paths, git=fake_git(paths))
    added = paths.source_dir / "src" / "litharness" / "added.py"
    added.write_text("x = 1\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="changed pinned runtime tree"):
        mt.verify(paths, git=fake_git(paths), interpreter=None)
    added.unlink()
    paths.prereg.write_text("edited\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="changed frozen file"):
        mt.verify(paths, git=fake_git(paths), interpreter=None)


def test_prepare_refuses_a_summary_request_the_trials_rows_do_not_rebuild(
    tmp_path: Path,
) -> None:
    paths, trial, recorded, recorded_seed, head_seed = _prepared_trial(tmp_path)
    with pytest.raises(RuntimeError, match=r"not byte-identical \['scene-5'\]"):
        mt.prepare(paths=paths, codex_binary=Path("codex.exe"), git=fake_git(paths),
                   trial_reader=lambda _: trial,
                   renderer=fake_renderer(paths, recorded, recorded_seed, head_seed, [],
                                          drift="scene-5"),
                   runtime_builder=fake_runtime, pinner=fake_pinner)
    assert not paths.registration.exists()
    rowless = dataclasses.replace(trial, promise_rows={})
    with pytest.raises(RuntimeError, match="no row in the trial's promises"):
        mt.prepare(paths=paths, codex_binary=Path("codex.exe"), git=fake_git(paths),
                   trial_reader=lambda _: rowless,
                   renderer=fake_renderer(paths, recorded, recorded_seed, head_seed, []),
                   runtime_builder=fake_runtime, pinner=fake_pinner)


def test_prepare_refuses_dirty_production_code_and_any_spend(tmp_path: Path) -> None:
    paths = make_paths(tmp_path)
    with pytest.raises(RuntimeError, match="differ from HEAD"):
        mt.prepare(paths=paths, codex_binary=Path("codex.exe"),
                   git=fake_git(paths, dirty=b" M src/x.py\n"))
    mt.append_ledger(paths.ledger, {"event": "dispatch", "seq": 1, "unit": "u", "role": "seed"})
    with pytest.raises(RuntimeError, match="never refreshed"):
        mt.prepare(paths=paths, codex_binary=Path("codex.exe"), git=fake_git(paths))


def test_a_seed_request_that_does_not_rebuild_is_never_registered(tmp_path: Path) -> None:
    paths, trial, _recorded, recorded_seed, _head_seed = _prepared_trial(tmp_path)

    def renderer(python: Path, mode: str, arguments: Any, out: Path, binary: Any) -> Any:
        frozen = python == paths.frozen_python
        source = (paths.frozen_source if frozen else paths.source_dir / "src") / "litharness"
        return {"source": str(source / "x.py"), "request": {**recorded_seed, "prompt": "drifted"}}

    with pytest.raises(RuntimeError, match="frozen_identical"):
        mt.build_seed_inputs(paths, trial, "codex.exe", renderer)
    assert not paths.registration.exists()


# ============================================================================== analyse


def test_analyse_reads_a_complete_fake_run_transport_first(tmp_path: Path, paid_env: None) -> None:
    paths, reg = build_arm(tmp_path)

    def script(cell: Any, request: CompletionRequest) -> Any:
        if cell.name == "luna-high" and "door 5." in request.prompt:
            return good_result(cell, request, parsed=None)
        return good_result(cell, request)

    line = mt.run(paths=paths, verifier=registered(reg), provider_factory=factory(script, []),
                  guard=lambda: None, log=lambda _: None)
    assert line["complete"]
    with pytest.raises(RuntimeError, match="names this arm"):
        mt.analyse(paths=paths, verifier=registered(reg), inspector=fake_inspector)
    release_lock(paths)
    result = mt.analyse(paths=paths, verifier=registered(reg), inspector=fake_inspector)
    assert result["transport"]["coverage"] == "complete"
    assert result["transport"]["transport_failures_by_kind"] == {}
    assert result["transport"]["halted_units"] == []
    assert set(result["transport"]["by_cell_status"]) >= {"summary/astra-medium",
                                                          "current/astra-medium",
                                                          "current/astra-medium-2",
                                                          "seed/sol-medium"}
    decision = result["summaries"]["decision"]
    assert decision["candidates"]["luna-medium"]["verdict"] == "pass"
    high = decision["candidates"]["luna-high"]
    assert high["verdict"] == "inconclusive"
    for block in ("recorded", "current"):
        assert high["tests"][block]["conformance"]["candidate_only_failures"] == 1
    assert high["tests"]["current"]["clean_copy"]["candidate_only_failures"] == 1
    assert high["tests"]["recorded"]["settlement"]["verdict"] == "pass"
    assert decision["proposal"]["cell"] == "luna-medium"
    assert decision["proposal"]["provider"] == "codex" and "settings" not in decision["proposal"]
    recorded = result["summaries"]["recorded"]
    assert recorded["cells"]["astra-medium"]["composite_mean"] == pytest.approx(1.0)
    assert recorded["cells"]["luna-high"]["parse_failures_would_retry"] == 1
    assert recorded["record"]["conformance_passes"] == 24
    current = result["summaries"]["current"]
    assert current["ledger_scenes"] == 23
    assert current["cells"]["astra-medium"]["scored_scenes"] == 0
    assert current["cells"]["astra-medium-2"]["composite_mean"] == pytest.approx(1.0)
    assert current["cells"]["luna-medium"]["paid_unmatched"] == 1  # scene 1: no list shown
    seeds = result["seeds"]["decision"]
    assert seeds["verdict"] == "no_gross_failure_seen" and seeds["proposal"] is None
    assert result["seeds"]["cells"]["sol-medium"]["r0"]["bridge"]["commands"] == 1
    assert mt.read_json(paths.claim)["status"] == "observed"
    text = paths.results.read_text(encoding="utf-8")
    assert "Mara holds a door" not in text and "washhouse" not in text
    with pytest.raises(RuntimeError, match="written once"):
        mt.analyse(paths=paths, verifier=registered(reg), inspector=fake_inspector)


def test_analyse_refuses_before_a_finished_line(tmp_path: Path) -> None:
    paths, reg = build_arm(tmp_path)
    release_lock(paths)
    mt.append_ledger(paths.ledger, {"event": "started", "invocation": 1, "started_at": "t"})
    with pytest.raises(RuntimeError, match="no finished line"):
        mt.analyse(paths=paths, verifier=registered(reg), inspector=fake_inspector)


@pytest.mark.parametrize(
    ("provider_kind", "attempt_raw"),
    [("timeout", None), ("refusal", {"stdout": ""}), ("safety", None)],
)
def test_analyse_refuses_a_transport_failure_kept_as_an_answer(
    tmp_path: Path, provider_kind: str, attempt_raw: Any,
) -> None:
    paths, reg = build_arm(tmp_path)
    release_lock(paths)
    unit = mt.plan(reg["inputs"]["scenes"])[0]
    inputs = mt.load_inputs(paths, reg)
    receipt = paths.calls_dir / "0001-bad.json"
    mt.write_new(receipt, {
        "unit": unit.unit_id, "status": "answered_unusable",
        "request_sha256": mt.request_digest_for(unit, inputs), "result": None,
        "failure": {"kind": provider_kind, "provider_kind": provider_kind,
                    "message": "stopped"},
        "attempt_raw": attempt_raw,
    })
    for line in (
        {"event": "started", "invocation": 1},
        {"event": "dispatch", "invocation": 1, "seq": 1, "unit": unit.unit_id, "role": "summary"},
        {"event": "call", "invocation": 1, "seq": 1, "unit": unit.unit_id, "role": "summary",
         "cell": unit.cell.name, "status": "answered_unusable", "tokens": None,
         "usage_known": False, "wall_ms": 10, "receipt": mt.rel(receipt, paths.root),
         "receipt_sha256": mt.sha_file(receipt)},
        {"event": "finished", "invocation": 1, "finished_at": "t", "stop": None},
    ):
        mt.append_ledger(paths.ledger, line)
    with pytest.raises(RuntimeError, match="§235"):
        mt.analyse(paths=paths, verifier=registered(reg), inspector=fake_inspector)
    assert not paths.results.exists()


def test_close_records_an_interrupted_invocation_only(tmp_path: Path) -> None:
    paths, _ = build_arm(tmp_path)
    mt.append_ledger(paths.ledger, {"event": "started", "invocation": 1})
    mt.append_ledger(paths.ledger, {"event": "dispatch", "invocation": 1, "seq": 1,
                                    "unit": "seed/sol-medium/r0", "role": "seed"})
    with pytest.raises(RuntimeError, match="names this arm"):
        mt.close(paths=paths)
    release_lock(paths)
    line = mt.close(paths=paths)
    assert line["interrupted"] == ["seed/sol-medium/r0"]
    with pytest.raises(RuntimeError, match="nothing to close"):
        mt.close(paths=paths)


def test_the_bridge_receipts_and_the_world_check_are_read_by_code() -> None:
    rows = [
        {"phase": "request", "call": 1},
        {"phase": "result", "call": 1, "argv": None, "error_kind": "invalid_arguments"},
        {"phase": "result", "call": 2, "argv": ["py", "-m", "litharness", "world", "vocabulary"],
         "returncode": 0},
        {"phase": "result", "call": 3,
         "argv": ["py", "-m", "litharness", "world", "declare-batch", "--records", "[]"],
         "returncode": 1, "stdout": json.dumps({"declared": 20, "refused": 2})},
        {"phase": "result", "call": 4, "argv": ["py", "-m", "litharness", "world", "check"],
         "returncode": 1},
    ]
    stats = mt.bridge_stats({"commands_jsonl": "\n".join(json.dumps(row) for row in rows)})
    assert stats["commands"] == 4
    assert stats["bridge_errors_by_kind"] == {"invalid_arguments": 1}
    assert stats["nonzero_exit_by_verb"] == {"world check": 1, "world declare-batch": 1}
    assert (stats["declared"], stats["declaration_refusals"]) == (20, 2)
    assert mt.bridge_stats(None)["commands"] == 0
    check = mt.parse_check(1, json.dumps({
        "ok": False, "complaints": ["mara claims the role 'hero', which is not one of a, b",
                                    "tavi claims the role 'x', which is not one of a, b"],
        "would_not_finish": ["joinery: 9 grants"], "unmanifested": [],
    }))
    assert check["complaints"] == 2 and check["would_not_finish"] == 1
    assert check["complaint_kinds"] == {"claims the role ..., which is not one": 2}
    assert mt.parse_check(2, "Traceback")["parsed"] is False


def test_a_seed_store_is_a_fresh_copy_per_attempt(tmp_path: Path) -> None:
    paths, _ = build_arm(tmp_path)
    unit = next(u for u in mt.plan(["scene-1"]) if u.role == "seed")
    first = mt.fresh_seed_store(paths, unit, 1)
    assert first.read_bytes() == paths.seed_template.read_bytes()
    assert mt.fresh_seed_store(paths, unit, 2) != first
    with pytest.raises(RuntimeError, match="never reuses"):
        mt.fresh_seed_store(paths, unit, 1)


# ================================================================ the real Codex adapter


def test_the_real_adapter_sends_each_cells_model_and_effort(tmp_path: Path) -> None:
    cell = next(c for c in mt.SUMMARY_CELLS if c.name == "luna-high")
    unit = next(u for u in mt.plan(["scene-1"]) if u.cell == cell)
    request = summary_request(scene_text(1))
    answer = answer_for(scene_text(1))
    text = json.dumps(answer)
    calls: list[list[str]] = []

    def runner(argv: Any, *, timeout: float, cwd: str, env: dict[str, str],
               stdin: str = "") -> CommandResult:
        calls.append(list(argv))
        if "login" in argv:
            return CommandResult(0, "Logged in using ChatGPT\n", "")
        if "--version" in argv:
            return CommandResult(0, VERSION_STRING + "\n", "")
        Path(argv[argv.index("--output-last-message") + 1]).write_text(text, encoding="utf-8")
        events = [
            {"type": "thread.started"}, {"type": "turn.started"},
            {"type": "item.completed", "item": {"type": "agent_message", "text": text}},
            {"type": "turn.completed", "usage": {"input_tokens": 10, "cached_input_tokens": 0,
                                                 "output_tokens": 5,
                                                 "reasoning_output_tokens": 0}},
        ]
        return CommandResult(0, "\n".join(json.dumps(event) for event in events), "")

    provider = mt.codex_provider(cell, "codex.exe", None)
    provider.runner = runner
    result = provider.complete(request)
    exec_argv = calls[-1]
    assert exec_argv[exec_argv.index("--model") + 1] == "gpt-6-luna"
    assert 'model_reasoning_effort="high"' in exec_argv
    assert mt.served_as_registered(result.raw, unit, VERSION_STRING, sys.executable) is None
    assert request.model is None  # the recorded bytes carry no model; the adapter does
    assert result.parsed is not None


# ================================================================ the committed claim


def test_the_committed_claim_is_a_valid_registered_record() -> None:
    path = mt.DEFAULT_PATHS.claim
    record = governance.load_and_verify(path)
    assert record.status.value in {"registered", "observed"}
    assert record.claim_id == mt.VERSION
    assert mt.read_json(path)["statement"] == mt.CLAIM_STATEMENT


def test_the_render_boundary_refuses_outside_test_mode(tmp_path: Path,
                                                       monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LITHARNESS_ENV", "development")
    with pytest.raises(RuntimeError, match="billing disabled"):
        mt.render_seed_mode(tmp_path / "book.db", tmp_path / "library", tmp_path / "out.json")
    assert not (tmp_path / "out.json").exists()
