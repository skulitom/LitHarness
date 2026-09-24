"""The chapter-one lane refuses before it spends, and records rather than decides.

**No test here makes a paid call, and none can.** The lane reaches a provider only through a
child process in a draw's runtime (`run_child`), and every test either never gets that far or
replaces `run_child` with a script. The store tests build their stores with production code
(`init`, the fake `listing`, `world declare`, `import`) so a binding that only ever met a
hand-written dict cannot pass. Ported from the registered draw's tests
(`test_restored_directions_draw.py`), which stay with their frozen runner.
"""

from __future__ import annotations

import ast
import contextlib
import io
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from tools import chapter_one as lane

LINE = "read-21"


@pytest.fixture(autouse=True)
def lane_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(lane, "RUNS", tmp_path / "runs")
    monkeypatch.setattr(lane, "LIBRARY", tmp_path / "library")
    monkeypatch.setattr(lane, "lock", lambda: None)
    return tmp_path


@pytest.fixture
def live(monkeypatch: pytest.MonkeyPatch) -> None:
    """The suite runs with LITHARNESS_ENV=test, which the lane refuses; a scripted stage
    runs without it, since `run_child` is replaced and nothing can reach a provider."""
    monkeypatch.delenv("LITHARNESS_ENV", raising=False)
    monkeypatch.delenv("LITHARNESS_PROVIDER", raising=False)
    monkeypatch.setattr(lane, "verify_runtime", lambda d: None)
    monkeypatch.setattr(lane, "file_register_report", lambda d, cp: {"register_report": None})


def make_draw(n: int = 1, *, status: str = "prepared", writer: str = "vance", **state: Any) -> Path:
    root = lane.line_dir(LINE)
    root.mkdir(parents=True, exist_ok=True)
    (root / "brief.txt").write_text("A brief.\n", encoding="utf-8")
    d = lane.draw_dir(LINE, n)
    d.mkdir(parents=True)
    shutil.copy2(lane.ITEMS, d / "items.json")
    shutil.copy2(root / "brief.txt", d / "brief.txt")
    lane.write(d / "seed.json", {"label": "12345678901234567890"})
    lane.write(
        d / "settings.json",
        {
            "line": LINE,
            "draw": n,
            "revision": "0" * 40,
            "writer": writer,
            "writer_id": "w",
            "dossier_sha256": "s",
            "binary": {"path": "codex.exe"},
            "layout": dict(lane.DEFAULT_LAYOUT),
            "limits": dict(lane.DEFAULT_LIMITS),
            "brief_sha256": lane.sha(d / "brief.txt"),
            "items_sha256": lane.sha(d / "items.json"),
        },
    )
    progress = {
        "draw": n,
        "status": status,
        "stages": {},
        "gates": {},
        "stop": None,
        "retries": {},
        "attempts": [],
    }
    lane.save(d, progress | state)
    return d


def meta(accepted: int = 0, total: int = 24) -> dict[str, Any]:
    return {
        "exists": True,
        "accepted": accepted,
        "total": total,
        "terminal": 0,
        "exceptions": 0,
        "scene_ids": [f"scene-{i}" for i in range(1, total + 1)],
        "scene_hashes": {f"scene-{i}": f"hash-{i}" for i in range(1, accepted + 1)},
        "jobs": {},
    }


def scripted(
    monkeypatch: pytest.MonkeyPatch, script: list[tuple[int, str, int]]
) -> list[tuple[list[str], dict[str, str]]]:
    """Each `_step` child writes the next (returncode, stdout, accepted after) as its record; a
    `_bind` child binds a storeless checkpoint and a `_digest` child reports no store."""
    calls: list[tuple[list[str], dict[str, str]]] = []
    current = {"accepted": 0}

    def run_child(argv: list[str], env: dict[str, str], **_: Any) -> tuple[int | None, str]:
        calls.append((list(argv), dict(env)))
        mode, d = argv[2], Path(argv[3])
        if mode == "_step":
            key = argv[4]
            code, stdout, accepted = script[sum(c[0][2] == "_step" for c in calls) - 1]
            if key.startswith("concept-"):
                lane.write(d / "concept" / "concept.json", {"system": {}})
            before = meta(current["accepted"])
            current["accepted"] = accepted
            lane.write_new(
                d / "steps" / f"{key}.json",
                {
                    "key": key,
                    "returncode": code,
                    "stdout": stdout,
                    "before": before,
                    "after": meta(accepted),
                },
            )
        elif mode == "_bind":
            lane.write_new(
                lane.checkpoint_path(d, argv[4], "binding"),
                {"artifacts": {}, "store_sha256": None, "store_backup": None},
            )
        else:
            return 0, json.dumps({"store_sha256": None})
        return 0, ""

    monkeypatch.setattr(lane, "run_child", run_child)
    return calls


def cli(db: Path, *args: str) -> tuple[int, str]:
    """One production CLI verb on `db`, in process: (exit code, stdout)."""
    from litharness.cli import main

    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        code = main(["--database", str(db), *args])
    return code, output.getvalue()


class FakeGit:
    def __init__(self, *, ancestors: set[tuple[str, str]], changes: dict[str, list[str]]) -> None:
        self.ancestors, self.changes = ancestors, changes

    def __call__(self, *args: str) -> subprocess.CompletedProcess[bytes]:
        if args[0] == "merge-base":
            known = (args[2], args[3]) in self.ancestors
            return subprocess.CompletedProcess(args, 0 if known else 1, b"", b"")
        if args[0] == "diff-tree":
            listed = "\n".join(self.changes.get(args[-1], []))
            return subprocess.CompletedProcess(args, 0, listed.encode(), b"")
        raise AssertionError(f"unexpected git {args}")


# ------------------------------------------------------------------- recipe and fences


def test_every_lane_step_parses_on_the_production_cli() -> None:
    from litharness import cli as cli_module

    d = make_draw()
    settings = lane.read(d / "settings.json")
    parser = cli_module.build_parser()
    steps = [
        ("concept", "concept"),
        ("listing", "listing"),
        ("seed", "architect-seed"),
        ("seed", "world-check"),
        ("chapter", "world-accept"),
        ("chapter", "tick"),
    ]
    for stage, name in steps:
        argv = lane.base_args(d, settings) + lane.stage_argv(d, settings, stage, name)
        assert lane.argv_refusal(d, argv) is None
        args = parser.parse_args(argv)
        assert args.max_invocations_per_day == lane.DEFAULT_LIMITS["calls"]
        assert args.max_tokens_per_day == lane.DEFAULT_LIMITS["tokens"]
        assert args.exemplars == "" and args.chapter_scenes == 4
    concept = parser.parse_args(
        lane.base_args(d, settings) + lane.stage_argv(d, settings, "concept", "concept")
    )
    assert (concept.person, concept.scenes, concept.planning_material) == ("third", 24, False)
    listing = parser.parse_args(
        lane.base_args(d, settings) + lane.stage_argv(d, settings, "listing", "listing")
    )
    assert listing.no_title_check and not listing.rivals
    assert lane.parse_key("seed-architect-seed-1") == ("seed", "architect-seed", 1)
    with pytest.raises(ValueError, match="no such step"):
        lane.stage_argv(d, settings, "chapter", "extend")


@pytest.mark.parametrize(
    ("extra", "reason"),
    [
        (["--exemplars", "C:/openings"], "not an argument"),
        (["--rivals", "rivals.json"], "not an argument"),
        (["--planning-material"], "not an argument"),
        (["--out=elsewhere"], "not an argument"),
        (["--out", "research/quality-measurement/corpora"], "outside the draw"),
    ],
)
def test_no_corpus_exemplar_or_outside_path_rides_a_step(extra: list[str], reason: str) -> None:
    d = make_draw()
    settings = lane.read(d / "settings.json")
    argv = [*lane.base_args(d, settings), "concept", *extra]
    refusal = lane.argv_refusal(d, argv)
    assert refusal is not None and reason in refusal


def test_each_step_traces_transport_in_its_own_folder_and_inherits_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    d = make_draw()
    for name, value in {
        "LITHARNESS_EXEMPLARS": "C:/openings",
        "ANTHROPIC_API_KEY": "k",
        "OPENAI_API_KEY": "k",
        "LITHARNESS_REVISE": "1",
        "PYTHONPATH": "x",
        "LITHARNESS_CODEX_MODELS": "strong=gpt-x",
    }.items():
        monkeypatch.setenv(name, value)
    env = lane.environment(d, "concept-concept-1")
    assert env["LITHARNESS_CODEX_TRACE_DIR"] == str(d / "transport" / "concept-concept-1")
    assert env["LITHARNESS_PROVIDER"] == "codex" and env["LITHARNESS_DATABASE"] == str(
        d / "book.db"
    )
    for name in (
        "LITHARNESS_EXEMPLARS",
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "LITHARNESS_REVISE",
        "PYTHONPATH",
        "LITHARNESS_CODEX_MODELS",
        "LITHARNESS_ENV",
    ):
        assert name not in env, name
    assert "LITHARNESS_CODEX_TRACE_DIR" not in lane.environment(d)


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("LITHARNESS_ENV", "test"),
        ("LITHARNESS_FAKE_PAD_CHARS", "400"),
        ("LITHARNESS_PROVIDER", "claude"),
    ],
)
def test_a_live_verb_refuses_test_mode_and_another_provider(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, name: str, value: str
) -> None:
    for variable in ("LITHARNESS_ENV", "LITHARNESS_FAKE_PAD_CHARS", "LITHARNESS_PROVIDER"):
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setenv(name, value)
    note = tmp_path / "FAILURE-1.md"
    note.write_text("login expired\n", encoding="utf-8")
    for action in (
        lambda: lane.run_stage(LINE, "concept"),
        lambda: lane.start(LINE, note, "vance"),
        lambda: lane.redraw(LINE, "cause", [], "marsh"),
        lambda: lane.retry(LINE, "concept", note),
    ):
        with pytest.raises(lane.Refusal, match=r"test mode|codex only"):
            action()
    monkeypatch.delenv(name)
    monkeypatch.setenv("LITHARNESS_PROVIDER", "codex")
    lane.refuse_live_environment()


def test_start_refuses_uncommitted_production_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, live: None
) -> None:
    def git(*args: str) -> subprocess.CompletedProcess[bytes]:
        answers = {"rev-parse": b"a" * 40, "status": b" M src/litharness/cli.py\n"}
        return subprocess.CompletedProcess(args, 0, answers[args[0]], b"")

    monkeypatch.setattr(lane, "git", git)
    brief = tmp_path / "brief.txt"
    brief.write_text("System apocalypse.\n", encoding="utf-8")
    with pytest.raises(lane.Refusal, match=r"uncommitted production changes.*src/litharness/cli"):
        lane.start(LINE, brief, "vance")
    assert not lane.draw_dir(LINE, 1).exists()
    # The refused prepare bought nothing: the line starts again, but only with its own brief.
    with pytest.raises(lane.Refusal, match="uncommitted production changes"):
        lane.start(LINE, brief, "vance")
    other = tmp_path / "other.txt"
    other.write_text("Portal fantasy.", encoding="utf-8")
    with pytest.raises(lane.Refusal, match="another brief"):
        lane.start(LINE, other, "vance")
    make_draw()
    with pytest.raises(lane.Refusal, match="its next draw is `redraw`"):
        lane.start(LINE, brief, "vance")


def test_the_lane_imports_nothing_from_research() -> None:
    tree = ast.parse(lane.TOOL.read_text(encoding="utf-8"))
    research = {path.stem for path in (lane.REPO / "research" / "quality-measurement").glob("*.py")}
    imported = {
        name.split(".")[0]
        for node in ast.walk(tree)
        for name in (
            [alias.name for alias in node.names]
            if isinstance(node, ast.Import)
            else [node.module or ""]
            if isinstance(node, ast.ImportFrom)
            else []
        )
    }
    assert research and not imported & research, imported & research


def test_the_items_carry_read_20_s_checkpoint_items() -> None:
    items = lane.load_items(lane.ITEMS)
    ids = {cp: [entry["id"] for entry in entries] for cp, entries in items["checkpoints"].items()}
    assert ids == {
        "concept": ["C1", "C2", "C3", "C4", "C-money"],
        "listing": ["L1", "L2", "L3", "L4", "L5", "L6"],
        "world": ["W1", "W2", "W3", "W-money"],
        "chapter": ["H1", "H2", "H3", "H4", "H5", "H6", "H7", "H8", "H-open", "H-diction"],
    }
    assert "PARTIAL counts as FAIL" in items["rule"]
    assert lane.item_verdicts(["C-money", "C1"], "- C-money: PARTIAL rent\nC1: PASS x\n") == {
        "C-money": "PARTIAL",
        "C1": "PASS",
    }


@pytest.mark.intensive
def test_the_runtime_imports_the_archive_not_the_checkout(tmp_path: Path) -> None:
    """A real `git archive` of HEAD and a real venv: seconds, not a paid call."""
    d = tmp_path / "draw-1"
    d.mkdir()
    lane.write(d / "settings.json", {"binary": {"path": "codex.exe"}})
    origin = lane.build_runtime(d, lane.git_out("rev-parse", "HEAD"))
    assert Path(origin["source"]).resolve().is_relative_to((d / "source").resolve())
    assert origin["model"] and origin["effort"] and origin["distributions"]
    assert (d / "runtime.json").is_file()


# --------------------------------------------------------------------- the stage machine


def test_stages_run_in_order_behind_a_recorded_pass() -> None:
    d = make_draw()
    state = lane.progress(d)
    assert lane.stage_refusal(d, state, "concept") is None
    assert "waits for a recorded pass at the concept" in str(
        lane.stage_refusal(d, state, "listing")
    )
    state["stages"]["concept"] = {"status": "done", "seconds": 1.0, "steps": []}
    assert "already ran" in str(lane.stage_refusal(d, state, "concept"))
    state["gates"]["concept"] = {"result": "fail"}
    assert "waits for a recorded pass" in str(lane.stage_refusal(d, state, "listing"))
    state["gates"]["concept"] = {"result": "pass"}
    assert lane.stage_refusal(d, state, "listing") is None
    state["active"] = "listing-listing-1"
    assert "active" in str(lane.stage_refusal(d, state, "listing"))
    state.pop("active")
    state["status"] = "failed"
    assert "has ended" in str(lane.stage_refusal(d, state, "listing"))


def test_a_ceiling_counts_every_attempt_s_calls() -> None:
    d = make_draw(
        stages={"concept": {"status": "done", "seconds": 1.0, "steps": []}},
        gates={"concept": {"result": "pass"}},
        status="ready",
    )
    settings = lane.read(d / "settings.json")
    settings["limits"]["calls"] = 3
    lane.write(d / "settings.json", settings)
    usage = {"type": "turn.completed", "usage": {"input_tokens": 5, "output_tokens": 2}}
    for index, folder in enumerate(
        ("transport/concept-concept-1", "attempts/listing-1/transport/listing-listing-1")
    ):
        lane.write(d / folder / f"attempt-{index}.json", {"events": [usage]})
    lane.write(
        d / "attempts/listing-1/transport/listing-listing-1/attempt-9.json", {"failure": "x"}
    )
    assert lane.spend(d) == {"calls": 3, "tokens": 14, "usage_unknown": 1}
    with pytest.raises(lane.Refusal, match="ceiling:calls"):
        lane.refuse_stage(d, lane.progress(d), "listing")
    assert lane.progress(d)["status"] == "stopped"


def test_the_chapter_stage_stops_once_chapter_one_is_accepted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    d = make_draw(stages={"chapter": {"status": "running", "started_at": lane.now(), "steps": []}})
    ticks = [(0, "ran_job tick=1", 0), *[(0, "ran_job tick=x", k) for k in range(1, 5)]]
    calls = scripted(monkeypatch, [(0, "", 0), *ticks, (0, "ran_job", 5)])
    assert lane.drive_chapter(d) is None
    assert [argv[4] for argv, _ in calls] == [
        "chapter-world-accept-1",
        *(f"chapter-tick-{i}" for i in range(1, 6)),
    ]


@pytest.mark.parametrize(
    ("script", "reason"),
    [
        ([(1, "", 0)], "world accept refused"),
        ([(0, "", 0), (0, "no_work tick=1", 0)], "idle tick"),
        ([(0, "", 0), (0, "ran_job", 5)], "past chapter one"),
        (
            [(0, "", 0), (1, "job_failed", 0), (1, "job_failed", 0), (1, "job_failed", 0)],
            "3 consecutive failed ticks",
        ),
        ([(0, "", 0), (2, "", 0)], "operational fault"),
    ],
)
def test_the_chapter_stage_stops_for_a_person(
    monkeypatch: pytest.MonkeyPatch, script: list[tuple[int, str, int]], reason: str
) -> None:
    d = make_draw(stages={"chapter": {"status": "running", "started_at": lane.now(), "steps": []}})
    scripted(monkeypatch, script)
    assert reason in str(lane.drive_chapter(d))


def test_the_operator_read_and_the_items_never_reach_a_step(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, live: None
) -> None:
    sentinel = "SENTINEL-7f3a"
    d = make_draw()
    items = lane.read(d / "items.json")
    items["checkpoints"]["concept"][0]["text"] += f" {sentinel}"
    lane.write(d / "items.json", items)
    calls = scripted(monkeypatch, [(0, "", 0)])
    assert lane.run_stage(LINE, "concept") == 0
    settings = lane.read(d / "settings.json")
    steps = [
        lane.base_args(d, settings) + lane.stage_argv(d, settings, stage, name)
        for stage, name in [
            ("concept", "concept"),
            ("listing", "listing"),
            ("seed", "architect-seed"),
            ("chapter", "tick"),
        ]
    ]
    seen = json.dumps([calls, steps])
    assert calls and sentinel not in seen
    assert sentinel not in (d / "brief.txt").read_text(encoding="utf-8")
    harvest = tmp_path / "reader-read-21.md"
    harvest.write_text(f"The operator's read. {sentinel}\n", encoding="utf-8")
    state = lane.progress(d)
    state["status"], state["sent"] = "failed", {"how": "chat"}
    lane.save(d, state)
    lane.record_read(LINE, harvest)
    recorded = lane.progress(d)["read"]
    assert recorded["sha256"] == lane.sha(harvest)
    assert sentinel not in json.dumps(lane.progress(d))
    assert sentinel not in (d.parent / "ledger.jsonl").read_text(encoding="utf-8")


# ----------------------------------------------------------------------------- the gate


def reach(checkpoint: str = "concept") -> tuple[Path, Path]:
    d = make_draw(
        status="at_checkpoint",
        stages={lane.STAGE_OF[checkpoint]: {"status": "done", "seconds": 1.0, "steps": []}},
    )
    artifact = d / "concept" / "concept.json"
    artifact.parent.mkdir(exist_ok=True)
    artifact.write_bytes(b"{}\n")
    lane.write(
        lane.checkpoint_path(d, checkpoint, "binding"),
        {"artifacts": {"concept/concept.json": lane.sha(artifact)}, "store_sha256": None},
    )
    return d, artifact


def gate_read(tmp_path: Path, verdicts: dict[str, str] | list[str], name: str) -> Path:
    if not isinstance(verdicts, dict):
        verdicts = dict.fromkeys(verdicts, "PASS")
    path = tmp_path / name
    path.write_text(
        "".join(f"{item}: {verdict} at concept.json\n" for item, verdict in verdicts.items())
        + "\nResiduals: none.\n",
        encoding="utf-8",
    )
    return path


CONCEPT_IDS = ["C1", "C2", "C3", "C4", "C-money"]


def test_a_gate_records_one_verdict_per_item_and_follows_them(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(lane, "file_register_report", lambda d, cp: {"register_report": None})
    _, artifact = reach()
    read = gate_read(tmp_path, CONCEPT_IDS, "GATE-concept.md")
    with pytest.raises(lane.Refusal, match="not reached"):
        lane.gate(LINE, "chapter", "pass", read, "coordinator")
    with pytest.raises(lane.Refusal, match=r"\['C-money'\]"):
        lane.gate(LINE, "concept", "pass", gate_read(tmp_path, CONCEPT_IDS[:4], "p.md"), "c")
    mixed = {"C1": "PASS", "C2": "FAIL", "C3": "PASS", "C4": "PASS", "C-money": "PARTIAL"}
    with pytest.raises(lane.Refusal, match=r"not PASS: \['C-money', 'C2'\]"):
        lane.gate(LINE, "concept", "pass", gate_read(tmp_path, mixed, "mixed.md"), "c")
    with pytest.raises(lane.Refusal, match="records a pass, not a fail"):
        lane.gate(LINE, "concept", "fail", read, "coordinator")
    doubled = tmp_path / "doubled.md"
    doubled.write_text(read.read_text(encoding="utf-8") + "C1: FAIL on reflection\n", "utf-8")
    with pytest.raises(lane.Refusal, match=r"\['C1'\] more than once"):
        lane.gate(LINE, "concept", "pass", doubled, "coordinator")
    artifact.write_bytes(b'{"edited": true}\n')
    with pytest.raises(lane.Refusal, match="changed since they were bound"):
        lane.gate(LINE, "concept", "pass", read, "coordinator")
    artifact.write_bytes(b"{}\n")
    entry = lane.gate(LINE, "concept", "pass", read, "coordinator")
    assert entry["items"] == dict.fromkeys(CONCEPT_IDS, "PASS")
    assert entry["read_sha256"] == lane.sha(read)
    assert lane.progress(lane.current(LINE))["status"] == "ready"
    with pytest.raises(lane.Refusal, match="already recorded"):
        lane.gate(LINE, "concept", "fail", read, "coordinator")


def test_a_gate_reads_the_items_its_draw_snapshotted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Tightening the lane's items between draws never moves a draw already under way."""
    monkeypatch.setattr(lane, "file_register_report", lambda d, cp: {"register_report": None})
    reach()
    tightened = tmp_path / "items.json"
    items = lane.read(lane.ITEMS)
    items["checkpoints"]["concept"].append({"id": "C9", "text": "a later item"})
    lane.write(tightened, items)
    monkeypatch.setattr(lane, "ITEMS", tightened)
    entry = lane.gate(LINE, "concept", "pass", gate_read(tmp_path, CONCEPT_IDS, "g.md"), "c")
    assert set(entry["items"]) == set(CONCEPT_IDS)


def test_the_register_report_is_filed_beside_the_gate_and_decides_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    d, _ = reach()
    failing = tmp_path / "report_fails.py"
    failing.write_text("import sys\nsys.exit(3)\n", encoding="utf-8")
    monkeypatch.setattr(lane, "REGISTER_REPORT", failing)
    entry = lane.gate(LINE, "concept", "pass", gate_read(tmp_path, CONCEPT_IDS, "g.md"), "c")
    assert entry["result"] == "pass" and entry["register_report"] is None
    assert lane.read(lane.checkpoint_path(d, "concept", "register-failed"))["returncode"] == 3
    printing = tmp_path / "report_prints.py"
    printing.write_text("print('register report: describes; decides nothing')\n", "utf-8")
    monkeypatch.setattr(lane, "REGISTER_REPORT", printing)
    d2 = tmp_path / "other"
    (d2 / "checkpoints").mkdir(parents=True)
    filed = lane.file_register_report(d2, "listing")
    assert filed["register_report"] == "checkpoints/listing.register.txt"
    assert "decides nothing" in (d2 / filed["register_report"]).read_text(encoding="utf-8")


def test_the_transport_checks_find_a_call_run_inside_the_repository(tmp_path: Path) -> None:
    raw = {
        "provider": "codex",
        "mode": "completion",
        "argv": [
            "codex",
            "exec",
            "--ignore-user-config",
            "--ignore-rules",
            "--ephemeral",
            "--skip-git-repo-check",
        ],
        "settings": {
            "features.memories": False,
            "project_doc_max_bytes": 0,
            "web_search": "disabled",
        },
        "working_directory": str(tmp_path / "litharness-codex-x" / "working"),
    }
    assert all(lane.trace_checks(raw, Path("python.exe")).values())
    inside = raw | {"working_directory": str(lane.REPO / "runs")}
    assert not lane.trace_checks(inside, Path("python.exe"))["outside_repository"]
    searching = raw | {"settings": raw["settings"] | {"web_search": "live"}}
    assert not lane.trace_checks(searching, Path("python.exe"))["no_search"]


def test_a_gate_refuses_a_pass_over_a_call_without_its_isolation_controls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(lane, "file_register_report", lambda d, cp: {"register_report": None})
    d, _ = reach()
    lane.write(
        d / "transport" / "concept-concept-1" / "attempt-a.json",
        {
            "provider": "codex",
            "argv": ["codex", "exec"],
            "settings": {},
            "final_text": "{}",
            "returncode": 0,
            "working_directory": str(lane.REPO),
        },
    )
    summary = lane.transport_summary(d, "concept", "concept")
    assert (
        "outside_repository"
        in summary["isolation_failures"]["transport/concept-concept-1/attempt-a.json"]
    )
    with pytest.raises(lane.Refusal, match="isolation controls"):
        lane.gate(LINE, "concept", "pass", gate_read(tmp_path, CONCEPT_IDS, "g.md"), "c")
    fail = gate_read(tmp_path, dict.fromkeys(CONCEPT_IDS, "FAIL"), "f.md")
    assert lane.gate(LINE, "concept", "fail", fail, "c")["result"] == "fail"


# ------------------------------------------------------------------- retries and redraws


def test_an_operational_retry_keeps_the_failed_attempt_and_restores_the_bound_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, live: None
) -> None:
    d = make_draw()
    db = d / "book.db"
    assert cli(db, "import", "--fixture", "litrpg", "--keep-content")[0] == 0
    (d / "listing").mkdir()
    (d / "listing" / "title.txt").write_text("The Slot\n", encoding="utf-8")
    lane.bind(d, "listing")
    bound = lane.read(lane.checkpoint_path(d, "listing", "binding"))
    assert bound["store_backup"] == "checkpoints/listing.book.db"
    assert cli(db, "world", "declare", "kell", "wants", "--value", "a way home")[0] == 0
    assert lane.store_digest(d) != bound["store_sha256"]
    lane.write(d / "steps" / "seed-architect-seed-1.json", {"returncode": 2})
    lane.write(d / "transport" / "seed-architect-seed-1" / "attempt-a.json", {"failure": "x"})
    state = lane.progress(d)
    state.update(
        status="stopped",
        stop="architect-seed exited 2 (operational fault)",
        gates={"concept": {"result": "pass"}, "listing": {"result": "pass"}},
        stages={
            "seed": {
                "status": "stopped",
                "seconds": 9.0,
                "steps": [],
                "reason": "architect-seed exited 2 (operational fault)",
            }
        },
    )
    lane.save(d, state)
    monkeypatch.setattr(lane, "child_digest", lane.store_digest)
    rerun: list[tuple[str, str]] = []
    monkeypatch.setattr(lane, "run_stage", lambda line, stage: rerun.append((line, stage)) or 0)
    note = tmp_path / "FAILURE-1.md"
    note.write_text("The Codex login expired; no answer was read.\n", encoding="utf-8")
    assert lane.retry(LINE, "seed", note) == 0
    assert rerun == [(LINE, "seed")]
    folder = d / "attempts" / "seed-1"
    assert (folder / "steps" / "seed-architect-seed-1.json").is_file()
    assert (folder / "transport" / "seed-architect-seed-1" / "attempt-a.json").is_file()
    assert (folder / "book.db").is_file()
    assert lane.store_digest(d) == bound["store_sha256"]
    state = lane.progress(d)
    assert "seed" not in state["stages"] and state["stop"] is None and state["status"] == "ready"
    assert state["retries"]["seed"][0]["failure_note"]["sha256"] == lane.sha(note)
    events = [
        json.loads(line)
        for line in (d.parent / "ledger.jsonl").read_text("utf-8").split("\n")
        if line
    ]
    assert events[-1]["event"] == "retry" and events[-1]["failure_note"]["sha256"] == lane.sha(note)
    assert lane.spend(d)["calls"] == 1, "the failed attempt's call still counts"


@pytest.mark.parametrize(
    ("state", "reason"),
    [
        ({"gates": {"concept": {"result": "fail"}}}, "never follows a read"),
        ({"stop": "ceiling:tokens"}, "not an operational stop"),
        ({"stop": "world accept refused (exit 1)"}, "not an operational stop"),
        ({"retries": {"concept": [{}, {}]}}, "retried 2 times"),
    ],
)
def test_a_retry_is_refused_after_a_read_a_content_stop_or_two_retries(
    tmp_path: Path, live: None, state: dict[str, Any], reason: str
) -> None:
    stop = state.pop("stop", "concept exited 2 (operational fault)")
    make_draw(
        status="stopped",
        stop=stop,
        stages={"concept": {"status": "stopped", "reason": stop, "steps": []}},
        **state,
    )
    note = tmp_path / "FAILURE-1.md"
    note.write_text("transport\n", encoding="utf-8")
    with pytest.raises(lane.Refusal, match=reason):
        lane.retry(LINE, "concept", note)


def test_a_retry_needs_a_failure_note_and_a_verified_dead_runner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, live: None
) -> None:
    started = "2026-09-23T10:00:00+00:00"
    d = make_draw(
        status="running",
        active="concept-concept-1",
        stages={
            "concept": {
                "status": "running",
                "runner_pid": 4242,
                "started_at": started,
                "steps": ["concept-concept-1"],
            }
        },
    )
    note = tmp_path / "FAILURE-1.md"
    with pytest.raises(lane.Refusal, match="verify in PowerShell"):
        lane.retry(LINE, "concept", note)
    with pytest.raises(lane.Refusal, match="failure note"):
        lane.retry(LINE, "concept", note, verified_dead_pid=4242)
    note.write_text("The machine shut down mid-stage; no answer was read.", encoding="utf-8")
    monkeypatch.setattr(lane, "run_stage", lambda line, stage: 0)
    assert lane.retry(LINE, "concept", note, verified_dead_pid=4242) == 0
    state = lane.progress(d)
    assert state["attempts"][0]["record"]["status"] == "abandoned"
    # The crashed attempt's wall time is closed, so it cannot fill the ceiling while it waits.
    assert lane.draw_seconds(state, lane.now()) == state["attempts"][0]["record"]["seconds"]


def test_a_redraw_needs_an_ended_draw_a_located_cause_and_a_change(
    monkeypatch: pytest.MonkeyPatch, live: None
) -> None:
    old, new, docs = "1" * 40, "2" * 40, "3" * 40
    monkeypatch.setattr(
        lane,
        "git",
        FakeGit(
            ancestors={(old, "HEAD"), (old, "0" * 40), (new, "HEAD"), (docs, "HEAD")},
            changes={new: ["src/litharness/application/discovery.py"], docs: ["plan/notes.md"]},
        ),
    )
    prepared: list[dict[str, Any]] = []

    def prepare(
        line: str, n: int, *, writer: str, binary: str | None, extra: dict[str, Any]
    ) -> Path:
        prepared.append({"n": n, "writer": writer, **extra})
        return lane.draw_dir(line, n)

    monkeypatch.setattr(lane, "prepare", prepare)
    d = make_draw(status="at_checkpoint")
    with pytest.raises(lane.Refusal, match="has not ended"):
        lane.redraw(LINE, "listing.txt: a list of facts", [new], None)
    state = lane.progress(d)
    state["status"] = "failed"
    lane.save(d, state)
    with pytest.raises(lane.Refusal, match="located cause"):
        lane.redraw(LINE, " ", [new], None)
    with pytest.raises(lane.Refusal, match="same revision and writer"):
        lane.redraw(LINE, "chapter-one.md:5 rent", [], None)
    with pytest.raises(lane.Refusal, match="already in the previous draw"):
        lane.redraw(LINE, "chapter-one.md:5 rent", [old], None)
    with pytest.raises(lane.Refusal, match="no production path"):
        lane.redraw(LINE, "chapter-one.md:5 rent", [docs], None)
    with pytest.raises(lane.Refusal, match="full commit id"):
        lane.redraw(LINE, "chapter-one.md:5 rent", ["abc"], None)
    lane.redraw(LINE, "chapter-one.md:5 rent", [new], None)
    lane.redraw(LINE, "dossier: obligations nobody mentioned", [], "sandoval")
    assert prepared == [
        {
            "n": 2,
            "writer": "vance",
            "after": 1,
            "cause": "chapter-one.md:5 rent",
            "fixes": [new],
            "writer_changed_from": None,
        },
        {
            "n": 2,
            "writer": "sandoval",
            "after": 1,
            "fixes": [],
            "cause": "dossier: obligations nobody mentioned",
            "writer_changed_from": "vance",
        },
    ]
    state["status"] = "passed"
    lane.save(d, state)
    with pytest.raises(lane.Refusal, match="has not ended"):
        lane.redraw(LINE, "read 21", [new], None)


def test_only_a_chapter_pass_publishes_never_over_a_shelf_and_names_its_draw_count() -> None:
    make_draw(1, status="failed", stop=None, gates={"listing": {"result": "fail"}})
    d = make_draw(2, status="failed", writer="sandoval")
    with pytest.raises(lane.Refusal, match="only a draw that passed"):
        lane.publish(LINE)
    state = lane.progress(d)
    state["status"], state["gates"] = "passed", {"chapter": {"result": "pass"}}
    lane.save(d, state)
    shelf = d / "library" / "the-slot"
    shelf.mkdir(parents=True)
    (shelf / lane.SHELF_MARKER).write_bytes(b"{}\n")
    (d / "chapter-one.md").write_bytes(b"# The Slot\n")
    with pytest.raises(lane.Refusal, match="publish the reading edition"):
        lane.sent(LINE, "chat")
    (lane.LIBRARY / "the-slot").mkdir(parents=True)
    with pytest.raises(lane.Refusal, match="never overwritten"):
        lane.publish(LINE)
    (lane.LIBRARY / "the-slot").rmdir()
    destination = lane.publish(LINE)
    record = lane.read(destination / "DRAW.json")
    assert record["label"] == "draw 2 of 2" and record["writer"] == "sandoval"
    assert record["earlier"][0]["draw"] == 1 and record["earlier"][0]["gates"] == {
        "listing": "fail"
    }
    assert (destination / "chapter-one.md").is_file()
    with pytest.raises(lane.Refusal, match="not recorded as sent"):
        lane.record_read(LINE, destination / "chapter-one.md")
    lane.sent(LINE, "chat")
    assert [row["draw"] for row in lane.status(LINE)] == ["1 of 2", "2 of 2"]


# ------------------------------------------------------- stores production built


def test_the_binding_reads_a_store_production_built(monkeypatch: pytest.MonkeyPatch) -> None:
    """The world binding writes the world views, backs the store up, and a later declaration
    moves the digest the next stage checks before `world accept`."""
    monkeypatch.setenv("LITHARNESS_FAKE_PAD_CHARS", "400")
    d = make_draw()
    db = d / "book.db"
    assert cli(db, "init")[0] == 0
    code, _ = cli(
        db,
        "listing",
        "--writer",
        "vance",
        "--scenes",
        "24",
        "--no-title-check",
        "--out",
        str(d / "listing"),
    )
    assert code == 0
    assert lane.metadata(d)["total"] == 24
    assert cli(db, "world", "declare", "kell", "entity_role", "--value", "protagonist")[0] == 0
    lane.write(d / "steps" / "seed-world-check-1.json", {"returncode": 0})
    lane.bind(d, "world")
    binding = lane.read(lane.checkpoint_path(d, "world", "binding"))
    assert binding["store_sha256"] == lane.store_digest(d)
    assert {
        "views/world-show.json",
        "views/world-ladders.json",
        "steps/seed-world-check-1.json",
    } <= set(binding["artifacts"])
    assert lane.read(d / "views" / "world-show.json")["returncode"] == 0
    assert lane.binding_changes(d, "world") == []
    assert cli(db, "world", "declare", "kell", "wants", "--value", "a way home")[0] == 0
    assert lane.store_digest(d) != binding["store_sha256"]


def test_the_chapter_binding_writes_the_reading_copy_of_an_imported_book() -> None:
    d = make_draw()
    assert cli(d / "book.db", "import", "--fixture", "litrpg", "--keep-content")[0] == 0
    lane.bind(d, "chapter")
    binding = lane.read(lane.checkpoint_path(d, "chapter", "binding"))
    assert "## Chapter 1" in (d / "chapter-one.md").read_text(encoding="utf-8")
    assert {"chapter-one.md", "views/library.json", "views/status.json"} <= set(
        binding["artifacts"]
    )
    assert binding["store_sha256"] == lane.store_digest(d)
    assert lane.binding_changes(d, "chapter") == []
