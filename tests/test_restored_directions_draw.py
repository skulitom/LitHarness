"""The restored-directions draw refuses before it spends, and records rather than decides.

Every test here is offline: the padded fake provider (`LITHARNESS_FAKE_PAD_CHARS`) is the only
provider any of them reaches, the box lock is patched, and git is a fake where a test needs one.
The observer tests build their stores with production code (`init`, the fake `listing`,
`world declare`, `import`) so an observer that only ever met a hand-written dict cannot pass.
"""

from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import itertools
import json
import sqlite3
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

PATH = Path(__file__).resolve().parents[1] / (
    "research/quality-measurement/restored-directions-draw-20260922/run.py"
)
ROSTER = Path(__file__).resolve().parents[1] / "runs" / "roster" / "roster.db"


def load():
    spec = importlib.util.spec_from_file_location("restored_directions_draw_test", PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def run(tmp_path, monkeypatch):
    module = load()
    monkeypatch.setattr(module, "LOCAL", tmp_path / "local")
    monkeypatch.setattr(module, "LIBRARY", tmp_path / "library")
    monkeypatch.setattr(module, "lock", lambda: None)
    return module


@pytest.fixture
def fake(monkeypatch):
    """The padded fake, selected the one way production selects it."""
    from litharness.providers import build_default_registry
    from litharness.providers.fake import FakeProvider

    monkeypatch.setenv("LITHARNESS_FAKE_PAD_CHARS", "400")
    # Recorded so the recorder's wrapper is undone after the test.
    monkeypatch.setattr(FakeProvider, "complete", FakeProvider.complete)
    return build_default_registry()


@pytest.fixture
def observing(monkeypatch):
    """`bind` and `observe` forbid provider calls by patching both provider classes; these
    records undo that after the test, so no other test meets a refusing provider."""
    from litharness.providers.codex_cli import CodexCliProvider
    from litharness.providers.fake import FakeProvider

    monkeypatch.setattr(CodexCliProvider, "complete", CodexCliProvider.complete)
    monkeypatch.setattr(FakeProvider, "complete", FakeProvider.complete)


def make_draw(run, n=1, *, writer="halloran", status="registered", **state):
    d = run.draw_dir(n)
    d.mkdir(parents=True)
    (d / "brief.txt").write_bytes(run.BRIEF.encode("utf-8"))
    run.write(d / "seed.json", {"label": "12345678901234567890", "index": 0})
    run.write(d / "settings.json", {
        "draw": n, "revision": "0" * 40, "writer": writer, "roster": None, "writer_id": "",
        "dossier_sha256": "", "binary": {"path": "codex.exe", "size": 0, "mtime_ns": 0},
    })
    # The offline preflight's record: the first live concept request must equal it.
    run.write(d / "preflight.json", {"request_sha256": run.digest(run.serial(request()))})
    progress = {"draw": n, "status": status, "calls": [], "stages": {}, "gates": {},
                "stop": None}
    run.write(run.progress_path(n), progress | state)
    return d


def call(number, *, tokens=1, status="completed"):
    return {"number": number, "stage": "concept", "profile": "default", "status": status,
            "tokens": tokens, "path": f"calls/{number:04d}-concept.json"}


def cli(db, *args):
    """One production CLI verb on `db`, in process: (exit code, stdout)."""
    from litharness.cli import main

    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        code = main(["--database", str(db), *args])
    return code, output.getvalue()


class FakeGit:
    def __init__(self, committed=None, *, ancestors=(), changes=None, remote=b"  origin/main\n"):
        self.committed = committed or {}
        self.ancestors = set(ancestors)
        self.changes = changes or {}
        self.remote = remote

    def __call__(self, *args):
        if args[0] == "show":
            data = self.committed.get(args[1].removeprefix("HEAD:"))
            return subprocess.CompletedProcess(args, 0 if data is not None else 128,
                                               data or b"", b"")
        if args[:2] == ("branch", "-r"):
            return subprocess.CompletedProcess(args, 0, self.remote, b"")
        if args[0] == "merge-base":
            known = (args[2], args[3]) in self.ancestors
            return subprocess.CompletedProcess(args, 0 if known else 1, b"", b"")
        if args[0] == "diff-tree":
            listed = "\n".join(self.changes.get(args[-1], []))
            return subprocess.CompletedProcess(args, 0, listed.encode(), b"")
        raise AssertionError(f"unexpected git {args}")


def request(**fields):
    from litharness.domain.generation import CompletionRequest

    return CompletionRequest(prompt="hello", **fields)


def production_concept(run):
    """A concept built by production code the way `concept` builds one after discovery."""
    from litharness.application import concept, discovery

    payload = {
        "person_before": "a twenty-six-year-old bike courier three modules short of a degree",
        "exception": "the one Slot on Earth that holds as many skills as he can take",
        "first_use": "he slots a second skill during the first night and outruns the swarm",
        "want": "to get his sister out of the flooded city before the second wave",
        "system": {
            "name": "the Slots", "manner": "in a plain voice that states numbers",
            "look": "a blue pane at the edge of sight, white type on glass",
            "steps": 12, "strongest_known": "rank 7, held by two people in Europe",
            "pays": "a rank up is a skill that lands harder", "start_rank": 2,
        },
        "threat": {"what": "the swarm that came with the System",
                   "first_reach": "the underpass on the first night"},
        "turn": {"event": "the System arrives", "when": "before chapter one"},
        "first_arc": {"opens": "replaced by the treatment", "middle": "he learns to stack",
                      "closes": "he reaches the river"},
        "debts": [
            {"subject": "the second Slot", "owed": "why his Slot has no limit", "due_scene": 5},
            {"subject": "the swarm", "owed": "where the swarm comes from", "due_scene": 6},
        ],
    }
    treatment = discovery.Discovery(
        world="Cities flood with light when the System arrives.",
        opening="He wakes to a pane that offers one Slot and then a second.",
        growth="He can stack skills nobody else can hold together.",
    )
    return concept.Concept.from_development(payload, treatment, author_brief=run.BRIEF)


# ------------------------------------------------------------------- the fixed registration


def test_the_registered_brief_writer_layout_and_ceilings(run):
    assert hashlib.sha256(run.BRIEF.encode("utf-8")).hexdigest() == run.BRIEF_SHA256
    assert run.WRITER_SEQUENCE[0] == "rowntree"
    assert run.WRITERS["rowntree"] == (run.WRITER_ID, run.WRITER_DOSSIER_SHA256) == (
        "wtr-43f373dd421c86f46c622872",
        "b97a225325e883c55c5fe18a04fa6cd48ba6ce638e1d98a48efcf33d9221ffa8",
    )
    assert set(run.WRITER_SEQUENCE) == set(run.WRITERS)
    # Passed over for located reasons (PREREG.md, "Writer"): never a redraw writer either.
    assert not {"draycott", "mabry", "trevelyan", "calloway"} & set(run.WRITER_SEQUENCE)
    assert run.CHAPTER_SCENES * run.ARC_CHAPTERS == run.SCENES == 24
    assert run.PERSON == "third"
    assert run.MAX_DRAWS == 3
    assert {name: 3 * value for name, value in run.LIMITS.items()} == run.TOTAL_LIMITS
    assert "LITHARNESS_CODEX_MODELS" in run.UNSET


def test_the_writer_rule_is_stated_in_the_recruiter_s_own_shelves(run):
    from litharness.application import recruiter

    slugs = [slug for slug, _ in (*recruiter.SLATE, *recruiter.SUPPLEMENTARY)]
    assert set(run.DEFAULT_GENRE_SHELVES) <= set(slugs)
    # draycott and mabry come before rowntree's isekai shelf and are not on a default shelf;
    # calloway and trevelyan are supplementary, after it, and not on one either.
    for shelf in ("dark-fantasy", "supernatural"):
        assert slugs.index(shelf) < slugs.index("isekai")
    for shelf in ("mystery", "historical-portal-fantasy"):
        assert slugs.index(shelf) > slugs.index("isekai")
    assert not {"dark-fantasy", "supernatural", "mystery",
                "historical-portal-fantasy"} & set(run.DEFAULT_GENRE_SHELVES)


@pytest.mark.skipif(not ROSTER.is_file(), reason="the installation roster is local only")
def test_the_pinned_writers_are_the_installation_roster_s_accepted_rows(run):
    """Read through a mode=ro connection, exactly as prepare reads its copy."""
    uri = f"{ROSTER.resolve().as_uri()}?mode=ro"
    with contextlib.closing(sqlite3.connect(uri, uri=True)) as connection:
        shelves = dict(connection.execute(
            "SELECT name, specialization FROM roster_writers WHERE status = 'accepted'"
        ).fetchall())
    for name, pinned in run.WRITERS.items():
        row = run.roster_writer(ROSTER, name)
        assert (row["writer_id"], row["dossier_sha256"]) == pinned, name
        assert shelves[name] in run.DEFAULT_GENRE_SHELVES, name


def test_plan_reads_and_writes_nothing(run, capsys):
    body = run.plan()
    assert not run.LOCAL.exists()
    assert body["stages"]["seed"]["checkpoint"] == "world"
    assert body["writer_rule"]["draw_1"]["name"] == "rowntree"
    assert run.LOCK_PREFIX in capsys.readouterr().out


def test_every_checkpoint_has_items_of_its_own(run):
    ids = [item for items in run.CHECKPOINT_ITEMS.values() for item, _ in items]
    assert len(ids) == len(set(ids))
    assert all(run.VERDICT_LINE.match(f"{item}: PASS") for item in ids)
    assert set(run.CHECKPOINT_ITEMS) == set(run.CHECKPOINTS)
    assert run.STAGE_OF == {"concept": "concept", "listing": "listing", "world": "seed",
                            "chapter": "chapter"}
    assert run.FIRST_STEP == {"concept": "concept", "listing": "listing",
                              "seed": "architect-seed", "chapter": "world-accept"}


def test_every_registered_step_parses_on_the_production_cli(run):
    from litharness import cli as cli_module

    make_draw(run)
    parser = cli_module.build_parser()
    steps = [("concept", "concept"), ("listing", "listing"), ("seed", "architect-seed"),
             ("seed", "world-check"), ("chapter", "world-accept"), ("chapter", "tick")]
    for stage, name in steps:
        args = parser.parse_args(run.base_args(1) + run.stage_argv(1, stage, name))
        assert args.chapter_scenes == run.CHAPTER_SCENES
        assert args.max_invocations_per_day == run.LIMITS["calls"]
        assert args.max_tokens_per_day == run.LIMITS["tokens"]
    concept = parser.parse_args(run.base_args(1) + run.stage_argv(1, "concept", "concept"))
    assert (concept.person, concept.scenes, concept.planning_material) == ("third", 24, False)
    listing = parser.parse_args(run.base_args(1) + run.stage_argv(1, "listing", "listing"))
    assert listing.no_title_check and listing.scenes == 24
    assert run.parse_key("seed-architect-seed-1") == ("seed", "architect-seed", 1)
    with pytest.raises(ValueError, match="unregistered"):
        run.stage_argv(1, "chapter", "extend")


# ---------------------------------------------------------------------- refusals before spend


def test_the_box_lock_must_name_this_draw(tmp_path, monkeypatch):
    module = load()
    holder = tmp_path / "box.lock" / "holder"
    monkeypatch.setattr(module, "LOCK_HOLDER", holder)
    with pytest.raises(module.Refusal, match="not held"):
        module.lock()
    holder.parent.mkdir()
    holder.write_text("cost-that-bites-milder-20260922: arm", encoding="utf-8")
    with pytest.raises(module.Refusal, match="someone else"):
        module.lock()
    holder.write_text(module.LOCK_PREFIX + " draw 1", encoding="utf-8")
    module.lock()


@pytest.mark.parametrize("variable", ["LITHARNESS_ENV", "LITHARNESS_FAKE_PAD_CHARS"])
def test_nothing_live_runs_in_test_mode_or_on_the_fake(run, monkeypatch, variable):
    monkeypatch.delenv("LITHARNESS_ENV", raising=False)
    monkeypatch.setenv(variable, "test" if variable == "LITHARNESS_ENV" else "400")
    for action in (lambda: run.run_stage("concept"), run.prepare,
                   lambda: run.step(1, "concept-concept-1")):
        with pytest.raises(run.Refusal, match="test mode"):
            action()


def test_draws_are_prepared_in_order_and_never_past_three(run):
    assert run.next_draw_refusal(1) is None
    assert "at most 3" in run.next_draw_refusal(4)
    assert "next draw to prepare is 1" in run.next_draw_refusal(2)
    make_draw(run, 1, status="passed")
    assert "passed chapter one" in run.next_draw_refusal(2)
    run.write(run.LOCAL / "closed.json", {"reason": "operator"})
    assert "closed" in run.next_draw_refusal(2)


def test_a_stage_refuses_an_uncommitted_or_unpushed_registration(run, tmp_path, monkeypatch):
    here = tmp_path / "here"
    here.mkdir()
    monkeypatch.setattr(run, "ROOT", tmp_path)
    monkeypatch.setattr(run, "HERE", here)
    files = {name: here / name
             for name in ("PREREG.md", "RUNBOOK.md", "registration.json", "claim.json")}
    for path in files.values():
        path.write_bytes(b"registered\n")
    run.write(files["registration.json"], {"revision": "a" * 40})
    monkeypatch.setattr(run, "registered_files",
                        lambda n: [files["PREREG.md"], files["RUNBOOK.md"]])
    committed = {f"here/{name}": path.read_bytes() for name, path in files.items()}
    committed["here/RUNBOOK.md"] = b"an older runbook\n"
    git = FakeGit(committed, ancestors={("a" * 40, "HEAD")})
    monkeypatch.setattr(run, "git", git)
    with pytest.raises(run.Refusal, match=r"not committed as it stands: RUNBOOK\.md"):
        run.verify_committed(1)
    committed["here/RUNBOOK.md"] = files["RUNBOOK.md"].read_bytes()
    git.remote = b""
    with pytest.raises(run.Refusal, match="push it first"):
        run.verify_committed(1)
    git.remote = b"  origin/main\n"
    git.ancestors = set()
    with pytest.raises(run.Refusal, match="not an ancestor"):
        run.verify_committed(1)
    git.ancestors = {("a" * 40, "HEAD")}
    run.verify_committed(1)


def test_a_redraw_sees_every_registered_file_that_changed(run, tmp_path, monkeypatch):
    here = tmp_path / "here"
    here.mkdir()
    monkeypatch.setattr(run, "ROOT", tmp_path)
    monkeypatch.setattr(run, "HERE", here)
    files = [here / "run.py", here / "PREREG.md"]
    for path in files:
        path.write_bytes(b"as registered\n")
    monkeypatch.setattr(run, "registered_files", lambda n: files)
    run.write(run.registration_path(1), {"files": {str(p): run.sha(p) for p in files}})
    assert run.registration_drift(2) == {}
    files[0].write_bytes(b"a loosened gate\n")
    assert run.registration_drift(2) == {"here/run.py": run.sha(files[0])}


def test_stages_run_once_in_order_behind_a_recorded_pass(run):
    make_draw(run)
    state = run.read(run.progress_path(1))
    assert run.stage_refusal(1, state, "concept") is None
    assert "waits for a recorded pass at the concept" in run.stage_refusal(1, state, "listing")
    state["stages"]["concept"] = {"status": "done", "seconds": 1.0, "steps": []}
    assert "never runs twice" in run.stage_refusal(1, state, "concept")
    state["gates"]["concept"] = {"result": "fail"}
    assert "waits for a recorded pass" in run.stage_refusal(1, state, "listing")
    state["gates"]["concept"] = {"result": "pass"}
    assert run.stage_refusal(1, state, "listing") is None
    state["active"] = "listing-listing-1"
    assert "active" in run.stage_refusal(1, state, "listing")
    state.pop("active")
    state["status"] = "failed"
    assert "has ended" in run.stage_refusal(1, state, "listing")


def test_a_ceiling_reached_at_a_stage_boundary_ends_the_draw(run):
    """The last call of a stage may cross a ceiling; the next stage is then never admitted,
    so the draw is recorded as stopped rather than left `ready` with no way to end it."""
    make_draw(run, status="ready", calls=[call(i + 1) for i in range(run.LIMITS["calls"])],
              stages={"concept": {"status": "done", "seconds": 1.0, "steps": []}},
              gates={"concept": {"result": "pass"}})
    with pytest.raises(run.Refusal, match="ceiling:calls"):
        run.refuse_stage(1, run.read(run.progress_path(1)), "listing")
    state = run.read(run.progress_path(1))
    assert (state["status"], state["stop"]) == ("stopped", "ceiling:calls")
    run.shown("coordinator", "runs/restored-directions-draw-20260922/draw-1")
    # A refusal a person can clear (here: the gate not yet recorded) ends nothing.
    make_draw(run, 2, status="at_checkpoint",
              stages={"concept": {"status": "done", "seconds": 1.0, "steps": []}})
    with pytest.raises(run.Refusal, match="waits for a recorded pass"):
        run.refuse_stage(2, run.read(run.progress_path(2)), "listing")
    assert run.read(run.progress_path(2))["status"] == "at_checkpoint"


# --------------------------------------------------------- the recorder on the padded fake


@pytest.mark.parametrize("ceiling", ["calls", "tokens", "seconds", "total_tokens"])
def test_the_recorder_refuses_before_dispatch_at_each_ceiling(run, fake, ceiling):
    from litharness.providers.base import ProviderUnavailable
    from litharness.providers.fake import FakeProvider

    n = 1
    if ceiling == "calls":
        make_draw(run, calls=[call(i + 1) for i in range(run.LIMITS["calls"])])
    elif ceiling == "tokens":
        make_draw(run, calls=[call(1, tokens=run.LIMITS["tokens"])])
    elif ceiling == "seconds":
        started = datetime.now(UTC) - timedelta(seconds=run.LIMITS["seconds"] + 5)
        make_draw(run, stages={"concept": {"status": "running",
                                           "started_at": started.isoformat(), "steps": []}})
    else:
        over = run.LIMITS["tokens"] + run.LIMITS["tokens"] // 4
        make_draw(run, 1, status="stopped", calls=[call(1, tokens=over)])
        make_draw(run, 2, status="stopped", calls=[call(1, tokens=over)])
        make_draw(run, 3, calls=[call(1, tokens=run.LIMITS["tokens"] // 2 + 10)])
        n = 3
    run.install_recorder(n, "concept", FakeProvider)
    with pytest.raises(ProviderUnavailable, match=f"ceiling:{ceiling}"):
        fake.complete(request())
    assert fake.provider.calls == 0
    assert run.read(run.progress_path(n))["stop"] == f"ceiling:{ceiling}"
    assert not (run.draw_dir(n) / "calls").exists()


def test_completed_calls_are_receipted_and_chained(run, fake):
    from litharness.providers.fake import FakeProvider

    make_draw(run)
    run.install_recorder(1, "concept", FakeProvider)
    fake.complete(request())
    fake.complete(request())
    state = run.read(run.progress_path(1))
    assert [c["status"] for c in state["calls"]] == ["completed", "completed"]
    first, second = (run.read(run.draw_dir(1) / c["path"]) for c in state["calls"])
    assert first["previous_receipt_sha256"] is None
    assert second["previous_receipt_sha256"] == run.sha(run.draw_dir(1) / state["calls"][0]["path"])
    assert first["provider"] == "fake" and first["request"]["prompt"] == "hello"


def test_the_first_live_invention_request_must_be_the_preflight_s(run, fake):
    """PREREG's "must equal", enforced before dispatch rather than found at the audit."""
    from litharness.domain.generation import CompletionRequest
    from litharness.providers.base import ProviderUnavailable
    from litharness.providers.fake import FakeProvider

    make_draw(run)
    run.install_recorder(1, "concept", FakeProvider)
    fake.complete(CompletionRequest(prompt=run.PROBE_PROMPT))  # a health probe is not compared
    with pytest.raises(ProviderUnavailable, match="preflight registered"):
        fake.complete(request(system="an invention request the preflight never saw"))
    assert fake.provider.calls == 1
    state = run.read(run.progress_path(1))
    assert [c["probe"] for c in state["calls"]] == [True]
    assert "preflight" in state["stop"]


def test_a_failed_call_is_kept_failed_stops_the_draw_and_is_never_replayed(run, fake):
    from litharness.providers.base import ProviderError, ProviderUnavailable
    from litharness.providers.fake import FakeProvider

    make_draw(run)
    run.install_recorder(1, "concept", FakeProvider)
    fake.provider.fail_with = ProviderError("transport dropped")
    with pytest.raises(ProviderError, match="transport dropped"):
        fake.complete(request())
    fake.provider.fail_with = None
    with pytest.raises(ProviderUnavailable, match="stopped"):
        fake.complete(request())
    assert fake.provider.calls == 1
    state = run.read(run.progress_path(1))
    assert [c["status"] for c in state["calls"]] == ["failed"]
    receipt = run.read(run.draw_dir(1) / state["calls"][0]["path"])
    assert receipt["status"] == "failed" and receipt["usage_unknown"] is True
    assert "result" not in receipt
    assert "never replayed" in state["stop"]


@pytest.mark.parametrize(("fields", "reason"), [
    ({"allowed_tools": ("WebSearch",)}, "outside the world bridge"),
    ({"model": "gpt-6-sol"}, "registered strong"),
])
def test_the_recorder_refuses_unscoped_tools_and_a_named_model(run, fake, fields, reason):
    from litharness.providers.base import ProviderUnavailable
    from litharness.providers.fake import FakeProvider

    make_draw(run)
    run.install_recorder(1, "listing", FakeProvider)
    with pytest.raises(ProviderUnavailable, match=reason):
        fake.complete(request(**fields))
    assert fake.provider.calls == 0


def test_a_concept_step_on_the_padded_fake_records_every_call(run, fake):
    """The preflight registers the invention request offline, and the live step's first
    request must equal it: the recorder refuses before dispatch otherwise."""
    from litharness.application import discovery
    from litharness.providers.fake import FakeProvider

    key = "concept-concept-1"
    make_draw(run)
    run.preflight(1)
    registered = run.read(run.draw_dir(1) / "preflight.json")["request_sha256"]
    with pytest.raises(run.Refusal, match="not admitted"):
        run.execute_step(1, key, provider_class=FakeProvider)
    state = run.read(run.progress_path(1))
    state.update(status="running", active=key,
                 stages={"concept": {"status": "running", "started_at": run.now(),
                                     "steps": [key]}})
    run.write(run.progress_path(1), state)
    record = run.execute_step(1, key, provider_class=FakeProvider)
    state = run.read(run.progress_path(1))
    assert "preflight" not in str(state.get("stop")), state.get("stop")
    rows = run.receipts(1)
    assert record["returncode"] in (0, 1, 2)
    assert (run.draw_dir(1) / "steps" / f"{key}.json").is_file()
    assert rows and len(rows) == len(state["calls"])
    assert all(row["status"] == "completed" and row["provider"] == "fake" for row in rows)
    first = next(row for row in rows if not run.is_probe(row["request"]))
    assert first["profile"] == discovery.PROFILE
    assert run.digest(first["request"]) == registered
    for earlier, later in itertools.pairwise(state["calls"]):
        receipt = run.read(run.draw_dir(1) / later["path"])
        assert receipt["previous_receipt_sha256"] == run.sha(run.draw_dir(1) / earlier["path"])


def test_the_concept_command_reaches_one_invention_request_offline(run):
    from litharness.application import discovery

    make_draw(run)
    run.preflight(1)
    record = run.read(run.draw_dir(1) / "preflight.json")
    assert record["provider_calls"] == 0
    assert record["profile"] == discovery.PROFILE
    assert run.carries(record["request"], run.BRIEF)
    assert record["request_sha256"] == run.digest(record["request"])
    assert not record["request"]["allowed_tools"]
    assert set(record["delivery_table"]) == {"discovery", "development", "seed", "outline"}


# ------------------------------------------------------------------- the chapter scheduler


def meta(accepted=0, total=24):
    return {"exists": True, "accepted": accepted, "total": total, "pending": 0, "terminal": 0,
            "exceptions": 0, "scene_ids": [f"scene-{i}" for i in range(1, total + 1)],
            "scene_hashes": {f"scene-{i}": f"hash-{i}" for i in range(1, accepted + 1)},
            "head": "revision", "jobs": {}}


def scripted(run, monkeypatch, script):
    """Each dispatched step returns the next (returncode, stdout, accepted after) in order."""
    dispatched, current = [], {"accepted": 0}

    def dispatch(argv, **kwargs):
        n, key = int(argv[-2]), argv[-1]
        code, stdout, accepted = script[len(dispatched)]
        dispatched.append(key)
        before = meta(current["accepted"])
        current["accepted"] = accepted
        run.write(run.draw_dir(n) / "steps" / f"{key}.json",
                  {"key": key, "returncode": code, "stdout": stdout, "before": before,
                   "after": meta(accepted)})

    monkeypatch.setattr(run.subprocess, "run", dispatch)
    monkeypatch.setattr(run, "environment", lambda n, **_: {})
    return dispatched


def test_the_chapter_stage_stops_once_chapter_one_is_accepted(run, monkeypatch):
    make_draw(run, stages={"chapter": {"status": "running", "started_at": run.now(),
                                       "steps": []}})
    ticks = [(0, "ran_job tick=1", 0), *[(0, "ran_job tick=x", k) for k in range(1, 5)]]
    dispatched = scripted(run, monkeypatch, [(0, "", 0), *ticks, (0, "ran_job", 5)])
    assert run.drive_chapter(1) is None
    assert dispatched == ["chapter-world-accept-1", *(f"chapter-tick-{i}" for i in range(1, 6))]


@pytest.mark.parametrize(("script", "reason"), [
    ([(1, "", 0)], "world accept refused"),
    ([(0, "", 0), (0, "no_work tick=1", 0)], "idle tick"),
    ([(0, "", 0), (0, "ran_job", 5)], "past chapter one"),
    ([(0, "", 0), (1, "job_failed", 0), (1, "job_failed", 0), (1, "job_failed", 0)],
     "3 consecutive failed ticks"),
    ([(0, "", 0), (2, "", 0)], "operational fault"),
])
def test_the_chapter_stage_stops_for_a_person(run, monkeypatch, script, reason):
    make_draw(run, stages={"chapter": {"status": "running", "started_at": run.now(),
                                       "steps": []}})
    scripted(run, monkeypatch, script)
    assert reason in run.drive_chapter(1)


# ---------------------------------------------------------------------- a person's records


def reach(run, checkpoint="concept"):
    d = make_draw(run, status="at_checkpoint",
                  stages={run.STAGE_OF[checkpoint]: {"status": "done", "seconds": 1.0,
                                                     "steps": []}})
    artifact = d / "concept" / "concept.json"
    artifact.parent.mkdir()
    artifact.write_bytes(b"{}\n")
    bound = {"concept/concept.json": run.sha(artifact)}
    run.write(run.checkpoint_path(1, checkpoint, "binding"),
              {"artifacts": bound, "store_sha256": None})
    run.write(run.checkpoint_path(1, checkpoint),
              {"artifacts": bound, "observations": {}, "delivery": {}})
    return d, artifact


def gate_read(tmp_path, verdicts, name):
    """A read with one verdict line per item: a list of ids (all PASS) or {id: verdict}."""
    if not isinstance(verdicts, dict):
        verdicts = dict.fromkeys(verdicts, "PASS")
    path = tmp_path / name
    path.write_text("".join(f"{item}: {verdict} at concept.json\n"
                            for item, verdict in verdicts.items()) + "\nResiduals: none.\n",
                    encoding="utf-8")
    return path


def test_a_gate_records_a_complete_read_of_unchanged_artifacts_once(run, tmp_path):
    _, artifact = reach(run)
    items = [item for item, _ in run.CHECKPOINT_ITEMS["concept"]]
    read = gate_read(tmp_path, items, "GATE-concept.md")
    with pytest.raises(run.Refusal, match="pass or fail"):
        run.gate("concept", "maybe", read, "coordinator")
    chapter_items = [item for item, _ in run.CHECKPOINT_ITEMS["chapter"]]
    with pytest.raises(run.Refusal, match="not reached"):
        run.gate("chapter", "pass", gate_read(tmp_path, chapter_items, "GATE-chapter.md"),
                 "coordinator")
    with pytest.raises(run.Refusal, match=r"\['C3'\]"):
        run.gate("concept", "pass", gate_read(tmp_path, ["C1", "C2", "C4"], "partial.md"),
                 "coordinator")
    state = run.read(run.progress_path(1))
    state["calls"] = [call(1, status="failed")]
    run.write(run.progress_path(1), state)
    with pytest.raises(run.Refusal, match="transport failures are read before any verdict"):
        run.gate("concept", "pass", read, "coordinator")
    state["calls"] = []
    run.write(run.progress_path(1), state)
    artifact.write_bytes(b'{"edited": true}\n')
    with pytest.raises(run.Refusal, match="changed"):
        run.gate("concept", "pass", read, "coordinator")
    artifact.write_bytes(b"{}\n")
    entry = run.gate("concept", "pass", read, "coordinator")
    assert entry["result"] == "pass" and entry["read_sha256"] == run.sha(read)
    assert entry["items"] == dict.fromkeys(items, "PASS")
    assert entry["binding_sha256"] == run.sha(run.checkpoint_path(1, "concept", "binding"))
    assert run.read(run.progress_path(1))["status"] == "ready"
    with pytest.raises(run.Refusal, match="already recorded"):
        run.gate("concept", "fail", read, "coordinator")


def test_the_recorded_result_follows_the_item_verdicts(run, tmp_path):
    """Pass only when every item is PASS; PARTIAL counts as FAIL; one line per item."""
    reach(run)
    verdicts = {"C1": "PASS", "C2": "FAIL", "C3": "PASS", "C4": "PARTIAL"}
    mixed = gate_read(tmp_path, verdicts, "mixed.md")
    with pytest.raises(run.Refusal, match=r"not PASS: \['C2', 'C4'\]"):
        run.gate("concept", "pass", mixed, "coordinator")
    clean = gate_read(tmp_path, dict.fromkeys(verdicts, "PASS"), "clean.md")
    with pytest.raises(run.Refusal, match="records a pass, not a fail"):
        run.gate("concept", "fail", clean, "coordinator")
    doubled = tmp_path / "doubled.md"
    doubled.write_text(clean.read_text(encoding="utf-8") + "C1: FAIL on reflection\n",
                       encoding="utf-8")
    with pytest.raises(run.Refusal, match=r"\['C1'\] more than once"):
        run.gate("concept", "pass", doubled, "coordinator")
    mentioned = tmp_path / "mentioned.md"
    mentioned.write_text("- C1: PASS\n* C2: PASS\nC4: PASS\nC3 was not assessed.\n",
                         encoding="utf-8")
    with pytest.raises(run.Refusal, match=r"does not answer \['C3'\]"):
        run.gate("concept", "pass", mentioned, "coordinator")
    entry = run.gate("concept", "fail", mixed, "coordinator")
    assert entry["items"] == verdicts
    assert run.read(run.progress_path(1))["status"] == "failed"
    assert run.item_verdicts("concept", "- C1: PASS\n* C2: PARTIAL\nC3: FAIL x\nC4: PASS\n") == {
        "C1": "PASS", "C2": "PARTIAL", "C3": "FAIL", "C4": "PASS"}


def test_a_recorded_observation_failure_does_not_block_the_gate(run, tmp_path):
    reach(run)
    run.checkpoint_path(1, "concept").unlink()
    items = [item for item, _ in run.CHECKPOINT_ITEMS["concept"]]
    read = gate_read(tmp_path, items, "GATE-concept.md")
    with pytest.raises(run.Refusal, match="neither recorded nor recorded as failed"):
        run.gate("concept", "pass", read, "coordinator")
    run.write(run.checkpoint_path(1, "concept", "observation-failed"),
              {"checkpoint": "concept", "returncode": 1, "log": "checkpoints/x.log"})
    entry = run.gate("concept", "pass", read, "coordinator")
    assert entry["observation"] == "failed" and entry["checkpoint_sha256"] is None


def test_an_unbound_checkpoint_is_never_gated(run, tmp_path):
    reach(run)
    run.checkpoint_path(1, "concept", "binding").unlink()
    items = [item for item, _ in run.CHECKPOINT_ITEMS["concept"]]
    with pytest.raises(run.Refusal, match="never bound"):
        run.gate("concept", "pass", gate_read(tmp_path, items, "GATE.md"), "coordinator")


def test_a_redraw_needs_the_previous_draw_shown_and_a_committed_amendment(run):
    make_draw(run, 1, status="failed")
    with pytest.raises(run.Refusal, match="shown to the operator"):
        run.validate_redraw(2)
    run.shown("coordinator", "runs/restored-directions-draw-20260922/draw-1")
    with pytest.raises(run.Refusal, match="already recorded as shown"):
        run.shown("coordinator", "again")
    with pytest.raises(run.Refusal, match="must exist and be committed"):
        run.validate_redraw(2)


def test_an_amendment_names_a_located_cause_and_a_new_fix(run, monkeypatch):
    old, new, docs, runner, mixed = "1" * 40, "2" * 40, "3" * 40, "5" * 40, "6" * 40
    runner_path, test_path = run.RUNNER_FIX_PATHS
    previous = {"revision": "0" * 40, "writer": "rowntree"}
    monkeypatch.setattr(run, "git", FakeGit(
        ancestors={(old, "HEAD"), (old, "0" * 40), (new, "HEAD"), (docs, "HEAD"),
                   (runner, "HEAD"), (mixed, "HEAD")},
        changes={new: ["src/litharness/application/concept.py"], docs: ["research/notes.md"],
                 runner: [runner_path, test_path],
                 mixed: [runner_path, "research/quality-measurement/"
                                      "restored-directions-draw-20260922/PREREG.md"]},
    ))
    base = {"schema": run.AMENDMENT_SCHEMA, "draw": 2, "previous_draw": 1, "kind": "fix",
            "located_cause": {"checkpoint": "concept", "where": "concept.json exception"}}

    def problems(drift=None, **fields):
        return " ".join(run.amendment_problems(2, base | fields, previous, drift))

    assert problems(fix_commits=[new]) == ""
    assert "already in draw 1" in problems(fix_commits=[old])
    assert "no production path" in problems(fix_commits=[docs])
    assert "not on HEAD" in problems(fix_commits=["4" * 40])
    assert "full commit id" in problems(fix_commits=["abc"])
    assert "names its fix commits" in problems()
    assert "located_cause" in problems(fix_commits=[new], located_cause={})
    assert "draw 2 after draw 1" in problems(fix_commits=[new], draw=3)
    # A runner fix is a fix of this folder's run.py (and its test), named as one, and any
    # changed registered file is listed with its bytes' hash and the commit that changed it.
    drift = {runner_path: "a" * 64}
    change = {"path": runner_path, "sha256": "a" * 64, "commit": runner}
    assert problems(drift, runner_fix_commits=[runner], registration_changes=[change]) == ""
    assert "changed since draw 1" in problems(drift, runner_fix_commits=[runner])
    assert "sha256 its bytes do not have" in problems(
        drift, runner_fix_commits=[runner], registration_changes=[change | {"sha256": "b" * 64}])
    assert f"{new} does not change" in problems(
        drift, fix_commits=[new], registration_changes=[change | {"commit": new}])
    assert "which did not change" in problems(fix_commits=[new], registration_changes=[change])
    assert "not a runner fix" in problems(runner_fix_commits=[mixed])
    assert "not a runner fix" in problems(runner_fix_commits=[new])
    # A writer redraw names the next writer in the sequence and his registered row.
    barlow_id, barlow_dossier = run.WRITERS["barlow"]
    writer = {"kind": "writer", "writer": "barlow", "writer_id": barlow_id,
              "dossier_sha256": barlow_dossier}
    assert problems(**writer) == ""
    assert "barlow" in problems(**writer | {"writer": "carver"})
    assert "registered writer_id" in problems(**writer | {"dossier_sha256": "0" * 64})
    assert "kind is fix, transport or writer" in problems(kind="retry")


def test_every_draw_s_writer_is_the_one_its_registration_names(run):
    barlow = {"kind": "writer", "writer": "barlow", "writer_id": run.WRITERS["barlow"][0],
              "dossier_sha256": run.WRITERS["barlow"][1]}
    previous = {"writer": "rowntree", "writer_id": run.WRITER_ID,
                "dossier_sha256": run.WRITER_DOSSIER_SHA256}
    assert run.expected_writer(1, None, None) == ("rowntree", run.WRITER_ID,
                                                  run.WRITER_DOSSIER_SHA256)
    assert run.expected_writer(2, barlow, previous) == ("barlow", *run.WRITERS["barlow"])
    assert run.expected_writer(2, {"kind": "fix"}, previous) == (
        "rowntree", run.WRITER_ID, run.WRITER_DOSSIER_SHA256)


def test_a_transport_amendment_cites_the_failed_receipt(run):
    d = make_draw(run, 1, status="stopped")
    receipt = d / "calls" / "0003-chapter.json"
    run.write(receipt, {"status": "failed", "error": "transport"})
    base = {"schema": run.AMENDMENT_SCHEMA, "draw": 2, "previous_draw": 1, "kind": "transport",
            "located_cause": {"checkpoint": "operational", "where": "call 3 of draw 1"}}
    cited = {"path": "calls/0003-chapter.json", "sha256": run.sha(receipt)}
    previous = {"revision": "0" * 40, "writer": "rowntree"}
    assert run.amendment_problems(2, base | {"failed_receipt": cited}, previous) == []
    wrong = cited | {"sha256": "0" * 64}
    assert run.amendment_problems(2, base | {"failed_receipt": wrong}, previous)


def test_only_a_chapter_pass_reaches_the_library_and_never_over_a_shelf(run):
    d = make_draw(run, status="failed")
    with pytest.raises(run.Refusal, match="only a draw that passed"):
        run.publish()
    state = run.read(run.progress_path(1))
    state["status"] = "passed"
    run.write(run.progress_path(1), state)
    shelf = d / "library" / "the-slot"
    shelf.mkdir(parents=True)
    (shelf / run.SHELF_MARKER).write_bytes(b"{}\n")
    (shelf / "the-slot.md").write_bytes(b"# The Slot\n")
    (d / "chapter-one.md").write_bytes(b"# The Slot\n")
    with pytest.raises(run.Refusal, match="publish the reading edition"):
        run.shown("coordinator", "book-library")
    (run.LIBRARY / "the-slot").mkdir(parents=True)
    with pytest.raises(run.Refusal, match="never overwritten"):
        run.publish()
    (run.LIBRARY / "the-slot").rmdir()
    destination = run.publish()
    assert (destination / "chapter-one.md").is_file()
    run.shown("coordinator", "book-library")
    assert run.read(run.progress_path(1))["shown"]["by"] == "coordinator"


def test_a_passed_draw_with_no_exported_shelf_is_shown_from_its_run_folder(run):
    make_draw(run, status="passed")
    with pytest.raises(run.Refusal, match="found 0"):
        run.publish()
    run.shown("coordinator", "runs/restored-directions-draw-20260922/draw-1")
    assert run.read(run.progress_path(1))["shown"]


def test_the_audit_is_final_and_follows_every_showing(run):
    make_draw(run, status="failed")
    with pytest.raises(run.Refusal, match="final"):
        run.audit()
    run.close("the operator ends the series after one draw")
    with pytest.raises(run.Refusal, match="every ended draw is shown"):
        run.audit()


# ------------------------------------------------------------------------ the audit's checks


def test_the_transport_audit_checks_the_codex_call_ran_outside_the_repository(run, tmp_path):
    raw = {
        "provider": "codex", "requested_model": run.MODEL, "mode": "completion",
        "argv": ["codex", "exec", "--ignore-user-config", "--ignore-rules", "--ephemeral",
                 "--skip-git-repo-check"],
        "settings": {"model_reasoning_effort": run.EFFORT, "features.memories": False,
                     "project_doc_max_bytes": 0, "web_search": "disabled"},
        "prompt": "hello", "working_directory": str(tmp_path / "litharness-codex-x" / "working"),
    }

    def checks(**changed):
        row = {"status": "completed", "request": {"prompt": "hello", "model": None},
               "result": {"raw": raw | changed, "usage": {"input_tokens": 3}}}
        return run.transport_checks(row, Path("python.exe"))

    assert all(checks().values()), checks()
    assert not checks(working_directory=str(run.ROOT / "runs"))["outside_repository"]
    assert not checks(argv=raw["argv"][:-1])["skip_git_repo_check"]


def test_evidence_keeps_codes_and_hashes_and_never_a_reason_s_text(run):
    assert run.reason_code("ceiling:tokens") == "ceiling:tokens"
    assert run.reason_code("provider failure; usage unknown; the receipt is kept") == (
        "provider_failure")
    assert run.reason_code("the first live request is not the one the offline preflight "
                           "registered") == "preflight_mismatch"
    assert run.reason_code("the store changed after the world checkpoint was bound") == (
        "store_changed")
    assert run.reason_code("something nobody registered") == "other"
    assert run.reason_code(None) is None


# --------------------------------------------------------------- observations and delivery


def test_observations_are_counts_beside_the_gate_not_verdicts(run):
    text = "The ledger held two debts. A claimant filed 12 claims in court for 345 coins."
    body = run.text_observations(text)
    words = len(text.split())
    assert body["words"] == words
    assert body["admin_lexicon"]["counts"] == {"ledger": 1, "debt": 1, "claim": 2}
    assert body["admin_lexicon"]["per_1k_words"] == round(1000 * 4 / words, 2)
    assert body["frame_lexicon"]["counts"] == {"court": 1}
    assert (body["numbers"], body["digit_characters"]) == (2, 5)
    assert not any("pass" in key or "verdict" in key for key in body)


def test_prose_observations_count_the_sheet_and_the_tells(run):
    text = "Dan woke.\n\n[STATUS] Dan — Slots 3 | Rank 1\n\nNobody else had one."
    body = run.prose_observations(text)
    assert (body["status_lines"], body["status_cells"]) == (1, 2)
    assert body["tells"]["located"].get("absence") == 1


def test_evidence_keeps_counts_and_flags_and_drops_text(run):
    value = {"a": 1, "b": "prose", "c": [1, 2], "d": {"e": True, "f": "x"}, "g": None}
    assert run.numeric(value) == {"a": 1, "c": 2, "d": {"e": True}, "g": None}


def test_delivery_finds_the_restored_directions_in_real_requests(run):
    from litharness.application import concept, discovery

    table = run.delivery_table()
    invention = run.serial(discovery.render_request(run.BRIEF, None, person="third"))
    result = run.delivery_result([{"request": invention}], table["discovery"])
    assert result == {"profile": discovery.PROFILE, "requests": 1,
                      "carrying": {"direction": 1, "world_direction": 1}, "delivered": True}
    assert run.carries(invention, run.BRIEF)
    stripped = invention | {"system": invention["system"].replace(discovery.WORLD_DIRECTION, "")}
    assert run.delivery_result([{"request": stripped}], table["discovery"])["delivered"] is False
    treatment = discovery.Discovery(world="w", opening="o", growth="g")
    development = run.serial(concept.render_concept_request(
        run.BRIEF, None, scenes=24, person="third", discovery=treatment))
    developed = run.delivery_result([{"request": development}], table["development"])
    assert developed["delivered"] and developed["schema_requires_start_rank"]
    assert run.delivery_result([], table["outline"])["delivered"] is False


def test_the_concept_observer_and_the_outline_row_read_a_production_concept(run):
    """The outline row needs the book's own first use and start rank, not only the rules."""
    from litharness.application import concept, outline

    d = make_draw(run)
    drawn = production_concept(run)
    (d / "concept").mkdir()
    (d / "concept" / "concept.json").write_text(drawn.to_text() + "\n", encoding="utf-8")
    body = run.observe_concept(1, [], run.delivery_table(1))
    seen = body["observations"]
    assert seen["author_brief_retained"] and seen["discovery_version_is_current"]
    assert (seen["system_steps"], seen["start_rank"], seen["start_rank_in_range"]) == (12, 2, True)
    assert "concept/concept.json" in body["artifacts"]
    row = run.delivery_table(1)["outline"]
    assert row["needles"]["concept_first_use"] == drawn.first_use
    assert row["needles"]["start_rank_label"] == "rank 2 of 12"
    assert set(run.delivery_table()["outline"]["needles"]) == {"first_use_rule",
                                                                "early_magic_rule"}
    rules = f"{concept.FIRST_USE_RULE}\n{concept.EARLY_MAGIC_RULE}"
    bare = {"request": {"profile": outline.CONCEPT_PROFILE, "prompt": rules}}
    assert run.delivery_result([bare], row)["delivered"] is False
    placed = json.dumps({"book_concept": drawn.for_outline()})
    full = {"request": {"profile": outline.CONCEPT_PROFILE, "prompt": f"{placed}\n{rules}"}}
    assert run.delivery_result([full], row)["delivered"] is True


def test_the_listing_and_world_observers_read_a_store_production_built(run, fake, observing):
    """The world observer reads what the world says (a replaced proposal is not part of it)
    and reads the protagonist's place off proposals, which `ladder_for` cannot before accept.
    The binding then refuses a stage whose store moved after the gate read it."""
    d = make_draw(run)
    db = d / "book.db"
    assert cli(db, "init")[0] == 0
    code, _ = cli(db, "listing", "--writer", "vance", "--scenes", "24", "--no-title-check",
                  "--out", str(d / "listing"))
    assert code == 0
    listing = run.observe_listing(1, [], run.delivery_table())
    assert listing["observations"]["book_scenes"] == 24
    assert listing["observations"]["book_stood_up"] is True
    assert "listing/title.txt" in listing["artifacts"]
    declarations = [
        ("kell", "entity_role", "--value", "cast"),
        ("kell", "entity_role", "--value", "protagonist"),
        ("r_one", "precedes", "--object", "r_two", "--value", "crit_rank"),
        ("r_two", "precedes", "--object", "r_three", "--value", "crit_rank"),
        # A first standing, then the Architect's correction of the same slot.
        ("kell", "stands_at", "--object", "r_two", "--value", "crit_wrong"),
        ("kell", "stands_at", "--object", "r_two", "--value", "crit_rank"),
    ]
    for subject, predicate, *flags in declarations:
        assert cli(db, "world", "declare", subject, predicate, *flags)[0] == 0
    code, out = cli(db, "world", "check")
    run.write(d / "steps" / "seed-world-check-1.json", {"returncode": code, "stdout": out})
    (d / "concept").mkdir()
    run.write(d / "concept" / "concept.json", {"system": {"steps": 3, "start_rank": 2}})
    body = run.observe_world(1, [], run.delivery_table())
    seen = body["observations"]
    assert seen["protagonists"] == 1
    assert seen["replaced"] >= 1
    assert (seen["protagonist_stands_at"], seen["protagonist_opening_standings"]) == (1, 1)
    assert seen["declared_start_rank"] == 2
    assert seen["declared_start_matches_concept"] is True
    assert seen["world_check"]["returncode"] == code and "ok" in seen["world_check"]
    assert {"views/world-check.json", "views/world-show.json",
            "views/world-ladders.json"} <= set(body["artifacts"])
    run.bind(1, "world")
    binding = run.read(run.checkpoint_path(1, "world", "binding"))
    assert binding["store_sha256"] == run.store_digest(1)
    assert "steps/seed-world-check-1.json" in binding["artifacts"]
    assert run.binding_changes(1, "world") == []
    assert run.bound_store_refusal(1, "chapter-world-accept-1") is None
    assert run.bound_store_refusal(1, "chapter-tick-1") is None
    assert cli(db, "world", "declare", "kell", "wants", "--value", "a way home")[0] == 0
    assert "store changed" in run.bound_store_refusal(1, "chapter-world-accept-1")


def test_the_chapter_binding_and_observer_read_an_imported_book(run, observing):
    d = make_draw(run)
    assert cli(d / "book.db", "import", "--fixture", "litrpg", "--keep-content")[0] == 0
    run.bind(1, "chapter")
    binding = run.read(run.checkpoint_path(1, "chapter", "binding"))
    assert "## Chapter 1" in (d / "chapter-one.md").read_text(encoding="utf-8")
    assert {"chapter-one.md", "views/library.json"} <= set(binding["artifacts"])
    assert binding["store_sha256"] == run.store_digest(1)
    body = run.observe_chapter(1, [], run.delivery_table())
    seen = body["observations"]
    assert 1 <= seen["scenes"] <= run.CHAPTER_SCENES
    assert seen["chapter"]["words"] > 0 and "status_lines" in seen["chapter"]
    assert all(path.startswith("views/") for path in body["artifacts"])
    assert run.binding_changes(1, "chapter") == [], "the observer rewrote what the gate reads"
