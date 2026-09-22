"""Amendment 1 of the milder-dose arm (`rebuy.py`, arm `milder-v4a`), checked without a call.

What this file pins: the re-buy's profile differs from the registered one only in its labels, and
its registration equals milder-v4's field by field except `elicit.py`, which must be the fixed
transport; the four contaminated files are content-addressed, so a change or a missing commit
refuses; `prepare` refuses while the transport is unfixed, once milder-v4 was read, while it may
still be running, without its pinned binary, on a failed or different request identity, on a
moved design, and once milder-v4a has bought a cell; `verify` refuses a registration without its
amendment or with a hand-edited design; a milder-v4 record copied into the new cache is refused;
the run asks four probes as four fresh calls (the git probe three times) with the process
standing in the marker directories and the CLI in its own empty directory, and a leak on the
third git probe buys nothing; a bought run keeps a failed call's envelope in the failure log and
never in the cache; the claim has its own id; and the frozen runner can no longer verify
milder-v4 now that `elicit.py` is fixed.

What it does not establish: anything about any reader. `claude -p` is a scripted
`subprocess.run`, and `git` is the real one.
"""

from __future__ import annotations

import dataclasses
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

milder = pytest.importorskip(
    "cost_that_bites_milder",
    reason="research module; imported by path, skipped where research/ is unavailable",
)
ctb = pytest.importorskip("cost_that_bites")
elicit = pytest.importorskip("elicit")
governance = pytest.importorskip("epistemic_governance")

ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "research" / "quality-measurement" / "cost-that-bites-milder-20260922" / "rebuy.py"


def _load() -> Any:
    spec = importlib.util.spec_from_file_location("ctbm_rebuy_under_test", WRAPPER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    before = sys.dont_write_bytecode
    sys.dont_write_bytecode = True  # no __pycache__ beside a registered file
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = before
    return module


rebuy = _load()
ORIGINAL = milder.PROFILES["claude"]
PROFILE = rebuy.PROFILE
VERSION = "2.1.280 (Claude Code)"
IDENTITY = {"books": 4, "cells": 24, "max_abs_book_mean_diff": 0.0, "missing": [],
            "passed": True, "replayed_complete": 24}


def _books(count: int) -> list[tuple[str, str]]:
    return [(f"book-{index:02d}", ctb._member_text(f"b{index}")) for index in range(count)]


def _identity(profile: Any, planned: Any, paths: Any) -> dict[str, Any]:
    return dict(IDENTITY)


class Scratch:
    """A scratch repository holding milder-v4 as it stands tonight, and the fixed transport.

    milder-v4 is registered by the frozen `prepare`, pinned where the frozen `pin_cli` pins,
    and has a finished two-invocation ledger and a cache. `elicit.py` is then rewritten, which
    is the fix. Git is faked from a dictionary of committed bytes.
    """

    def __init__(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self.root = tmp_path
        self.paths = milder.Paths(
            root=tmp_path, arm_dir=tmp_path / "arm", local=tmp_path / "runs" / "arm",
            fitness_dir=tmp_path / "fit", lock_holder=tmp_path / "runs" / "box.lock" / "holder",
        )
        arm = self.paths.arm_dir
        arm.mkdir(parents=True)
        (arm / "PREREG.md").write_text("the registration\n", encoding="utf-8")
        self.module = tmp_path / "module.py"
        self.module.write_text("frozen = True\n", encoding="utf-8")
        self.elicit = tmp_path / rebuy.ELICIT
        self.elicit.parent.mkdir(parents=True)
        self.elicit.write_text("cwd = None\n", encoding="utf-8")
        monkeypatch.setattr(milder, "sources", lambda profile, paths: [
            self.module, self.elicit, paths.arm_dir / "PREREG.md"])
        install = tmp_path / "install" / "claude.exe"
        install.parent.mkdir()
        install.write_bytes(b"claude 2.1.280\n")
        self.binary = {"binary": str(install), "binary_sha256": milder.file_sha(install),
                       "binary_version": VERSION}
        self.original = milder.prepare(
            ORIGINAL, paths=self.paths,
            texts_loader=lambda d: (_books(4), {"x.db": "b" * 64}),
            binary_reader=lambda profile, codex: dict(self.binary),
            identity_check=_identity,
        )
        self.pinned = self.paths.pin_dir(ORIGINAL, self.binary["binary_sha256"]) / "claude.exe"
        self.pinned.parent.mkdir(parents=True)
        self.pinned.write_bytes(install.read_bytes())
        ledger = self.paths.ledger(ORIGINAL)
        for line in (
            {"event": "started", "invocation": 1, "started_at": "21:29", "prior_usage": {}},
            {"event": "probed", "invocation": 1,
             "probes": {"claude_md": {"passed": True}, "git_status": {"passed": True}}},
            {"event": "session", "invocation": 1, "feed_id": "ctbm4-00-intact-r0",
             "fresh_calls": 8, "used_cumulative": {"calls": 10.0, "tokens": 900.0, "usd": 0.3},
             "seconds_cumulative": 12.0},
            {"event": "finished", "invocation": 1, "finished_at": "22:10",
             "stop": "transport_circuit", "fresh_calls": 8,
             "used_cumulative": {"calls": 10.0, "tokens": 900.0, "usd": 0.3},
             "seconds_cumulative": 12.0},
            {"event": "started", "invocation": 2, "started_at": "22:11"},
            {"event": "finished", "invocation": 2, "finished_at": "22:11",
             "stop": "isolation_probe_failed", "fresh_calls": 0,
             "probes": {"claude_md": {"passed": True}, "git_status": {"passed": False}},
             "used_cumulative": {"calls": 12.0, "tokens": 1000.0, "usd": 0.32},
             "seconds_cumulative": 12.0},
        ):
            milder.append_ledger(ledger, line)
        self.paths.raw(ORIGINAL).write_text(
            json.dumps({"feed": "ctbm4-00-intact-r0", "key": "k:0", "stop_reason": "end_turn",
                        "text": "{}", "usage": {"input": 100, "equivalent_usd": 0.03}}) + "\n",
            encoding="utf-8",
        )
        (arm / rebuy.WRAPPER_NAME).write_text("the wrapper\n", encoding="utf-8")
        (arm / rebuy.AMENDMENT_NAME).write_text("the amendment\n", encoding="utf-8")
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / rebuy.TEST_NAME).write_text("its test\n", encoding="utf-8")
        (tmp_path / "tests" / rebuy.TRANSPORT_TEST_NAME).write_text("pins\n", encoding="utf-8")
        self.elicit.write_text("cwd = 'a fresh empty directory'\n", encoding="utf-8")  # the fix
        self.committed: dict[str, bytes] = {}
        self.pushed = b"  origin/main\n"

    def prepare(self, **kwargs: Any) -> dict[str, Any]:
        options: dict[str, Any] = {
            "texts_loader": lambda d: (_books(4), {"x.db": "b" * 64}),
            "version_reader": lambda path: VERSION,
            "identity_check": _identity,
        }
        registration: dict[str, Any] = rebuy.prepare(paths=self.paths, **{**options, **kwargs})
        return registration

    def registration(self) -> dict[str, Any]:
        loaded: dict[str, Any] = json.loads(
            self.paths.registration(PROFILE).read_text(encoding="utf-8"))
        return loaded

    def commit(self) -> None:
        names = [milder._rel(self.paths.registration(PROFILE), self.root),
                 *self.registration()["source_hashes"]]
        self.committed = {name: (self.root / name).read_bytes() for name in names}

    def git(self, args: list[str], root: Path) -> bytes:
        if args[0] == "show":
            name = args[1].removeprefix("HEAD:")
            if name not in self.committed:
                raise subprocess.CalledProcessError(128, ["git", *args])
            return self.committed[name]
        return self.pushed

    def verify(self, **kwargs: Any) -> Any:
        return rebuy.verify(paths=self.paths, git=self.git, **kwargs)


# ------------------------------------------------------------------------ the registration


def test_the_profile_differs_from_the_registered_one_only_in_labels() -> None:
    before, after = dataclasses.asdict(ORIGINAL), dataclasses.asdict(PROFILE)
    assert {key for key in before if before[key] != after[key]} == {
        "arm", "tag", "registration_name", "claim_name"}
    old, new = milder.pre_registration(ORIGINAL), milder.pre_registration(PROFILE)
    assert {key for key in old if old[key] != new[key]} == {"arm"}
    books = _books(4)
    assert rebuy._relabelled(milder.manifest(milder.plan(books, PROFILE))) == milder.manifest(
        milder.plan(books, ORIGINAL))


def test_a_prepared_committed_pushed_amendment_verifies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scratch = Scratch(tmp_path, monkeypatch)
    registration = scratch.prepare()
    scratch.commit()
    verified, planned = scratch.verify()
    assert verified == json.loads(json.dumps(registration)) and len(planned) == 72
    assert all(item.cell.spec.feed_id.startswith("ctbm4a-") for item in planned)
    assert registration["reader"]["binary"] == str(scratch.pinned)
    assert registration["reader"]["binary_sha256"] == scratch.binary["binary_sha256"]
    hashes = registration["source_hashes"]
    assert hashes[rebuy.ELICIT] == milder.file_sha(scratch.elicit)
    assert hashes[rebuy.ELICIT] != scratch.original["source_hashes"][rebuy.ELICIT]
    for name in ("arm/registration.json", "arm/claim.json", "arm/raw-milder-v4.jsonl",
                 "arm/runs-milder-v4.jsonl", "arm/rebuy.py", "arm/AMENDMENT-1.md",
                 f"tests/{rebuy.TEST_NAME}", f"tests/{rebuy.TRANSPORT_TEST_NAME}"):
        assert name in hashes, name
    amendment = registration["amendment"]
    stained = amendment["contaminated"]
    assert stained["usage"] == {"calls": 12.0, "tokens": 1000.0, "usd": 0.32, "seconds": 12.0}
    assert stained["sessions_checkpointed"] == 1 and stained["raw_records"] == 1
    assert [s["probes_passed"] for s in stained["invocations"]] == [
        {"claude_md": True, "git_status": True}, {"claude_md": True, "git_status": False}]
    assert amendment["probes"]["names"] == ["claude_md", "git_status", "git_status_2",
                                            "git_status_3"]
    assert amendment["ceilings"]["combined_worst_case"]["calls"] == 4_400 + 12
    assert rebuy.design_differences(
        scratch.original, registration,
        extras=frozenset(milder._rel(p, tmp_path) for p in rebuy.extra_sources(scratch.paths)),
    ) == []
    claim = json.loads(scratch.paths.claim(PROFILE).read_text(encoding="utf-8"))
    record = governance.parse_claim(claim)
    assert record.claim_id == "cost-that-bites.milder-v4a.claude"
    assert record.status.value == "registered"
    assert {a["path"] for a in claim["artifacts"]} == {
        "arm/PREREG.md", "arm/AMENDMENT-1.md", "arm/registration-v4a.json"}
    # milder-v4's own claim and registration are untouched.
    assert json.loads(scratch.paths.claim(ORIGINAL).read_text(encoding="utf-8"))["claim_id"] == (
        "cost-that-bites.milder-v4.claude")


def test_prepare_refuses_while_elicit_is_the_unfixed_transport(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scratch = Scratch(tmp_path, monkeypatch)
    scratch.elicit.write_text("cwd = None\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="still the transport milder-v4 registered"):
        scratch.prepare()
    assert not scratch.paths.registration(PROFILE).exists()


def test_prepare_refuses_once_milder_v4_was_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scratch = Scratch(tmp_path, monkeypatch)
    scratch.paths.results(ORIGINAL).write_text("{}\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="the contaminated arm was read"):
        scratch.prepare()


def test_prepare_refuses_while_milder_v4_may_still_be_running(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scratch = Scratch(tmp_path, monkeypatch)
    milder.append_ledger(scratch.paths.ledger(ORIGINAL),
                         {"event": "started", "invocation": 3, "started_at": "23:00"})
    with pytest.raises(RuntimeError, match="no finished line"):
        scratch.prepare()


def test_prepare_refuses_without_milder_v4s_pinned_binary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scratch = Scratch(tmp_path, monkeypatch)
    with pytest.raises(RuntimeError, match="reports"):
        scratch.prepare(version_reader=lambda path: "2.1.281 (Claude Code)")
    scratch.pinned.write_bytes(b"claude 2.1.281, installed in place\n")
    with pytest.raises(RuntimeError, match="no longer hashes"):
        scratch.prepare()
    scratch.pinned.unlink()
    with pytest.raises(RuntimeError, match=r"pinned copy .* is missing"):
        scratch.prepare()


def test_prepare_refuses_a_failed_or_different_request_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scratch = Scratch(tmp_path, monkeypatch)
    with pytest.raises(RuntimeError, match="request identity failed"):
        scratch.prepare(identity_check=lambda profile, planned, paths: {
            **IDENTITY, "replayed_complete": 23, "passed": False})
    with pytest.raises(RuntimeError, match=re.escape("'request_identity'")):
        scratch.prepare(identity_check=lambda profile, planned, paths: {
            **IDENTITY, "max_abs_book_mean_diff": 1e-13})
    assert not scratch.paths.registration(PROFILE).exists()


def test_prepare_refuses_a_design_that_moved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scratch = Scratch(tmp_path, monkeypatch)
    scratch.module.write_text("frozen = 'edited'\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match=re.escape("'source module.py'")):
        scratch.prepare()
    scratch.module.write_text("frozen = True\n", encoding="utf-8")
    monkeypatch.setattr(milder, "WORKERS", 2)
    with pytest.raises(RuntimeError, match=re.escape("'pre_registration.workers'")):
        scratch.prepare()
    monkeypatch.setattr(milder, "WORKERS", 3)
    with pytest.raises(RuntimeError, match=re.escape("'inputs.stores_sha256'")):
        scratch.prepare(texts_loader=lambda d: (_books(4), {"x.db": "c" * 64}))
    assert not scratch.paths.registration(PROFILE).exists()


def test_prepare_is_refused_once_milder_v4a_bought_a_cell(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scratch = Scratch(tmp_path, monkeypatch)
    scratch.prepare()
    ledger = scratch.paths.ledger(PROFILE)
    milder.append_ledger(ledger, {"event": "started", "invocation": 1, "started_at": "t"})
    milder.append_ledger(ledger, {"event": "finished", "invocation": 1, "finished_at": "t",
                                  "stop": "probe_transport_failure", "fresh_calls": 0})
    scratch.prepare()  # a probe-only invocation bought nothing
    milder.append_ledger(ledger, {"event": "session", "invocation": 2, "fresh_calls": 5})
    with pytest.raises(RuntimeError, match="never refreshed after a cell was bought"):
        scratch.prepare()


def test_verify_refuses_a_changed_or_uncommitted_contaminated_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scratch = Scratch(tmp_path, monkeypatch)
    scratch.prepare()
    scratch.commit()
    raw = scratch.paths.raw(ORIGINAL)
    kept = raw.read_bytes()
    raw.write_bytes(kept + b'{"feed": "ctbm4-00-sham-r0", "key": "k:1"}\n')
    changed = re.escape("changed frozen file: arm/raw-milder-v4.jsonl")
    with pytest.raises(RuntimeError, match=changed):
        scratch.verify()
    raw.write_bytes(kept)
    del scratch.committed["arm/runs-milder-v4.jsonl"]
    with pytest.raises(RuntimeError, match=re.escape("not committed: arm/runs-milder-v4.jsonl")):
        scratch.verify()


def test_verify_refuses_a_registration_without_its_amendment_or_with_an_edited_design(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scratch = Scratch(tmp_path, monkeypatch)
    scratch.prepare()
    path = scratch.paths.registration(PROFILE)
    registration = scratch.registration()
    edited = {**registration, "reader": {**registration["reader"], "hardening": ["--bare"]}}
    path.write_text(json.dumps(edited), encoding="utf-8")
    scratch.commit()
    with pytest.raises(RuntimeError, match=re.escape("'reader.hardening'")):
        scratch.verify()
    del registration["amendment"]
    path.write_text(json.dumps(registration), encoding="utf-8")
    scratch.commit()
    with pytest.raises(RuntimeError, match="no amendment block"):
        scratch.verify()


def test_verify_refuses_once_milder_v4_was_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scratch = Scratch(tmp_path, monkeypatch)
    scratch.prepare()
    scratch.commit()
    scratch.paths.results(ORIGINAL).write_text("{}\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="the contaminated arm was read"):
        scratch.verify()


def test_the_frozen_runner_can_no_longer_verify_milder_v4_in_this_repository() -> None:
    """Its registration content-addresses the unfixed `elicit.py`, so `run` and `analyse` of
    milder-v4 stop at the frozen `verify`: the contaminated arm is unreadable by construction,
    not only by instruction."""
    registration = json.loads(
        milder.DEFAULT_PATHS.registration(ORIGINAL).read_text(encoding="utf-8"))
    assert registration["source_hashes"][rebuy.ELICIT] != milder.file_sha(ROOT / rebuy.ELICIT)
    with pytest.raises(RuntimeError, match="changed frozen file"):
        milder.verify(ORIGINAL, binary_reader=None)


# ------------------------------------------------------------------------------- the run


def _envelope(text: str) -> str:
    return json.dumps({
        "type": "result", "subtype": "success", "is_error": False, "result": text,
        "stop_reason": "end_turn", "total_cost_usd": 0.002,
        "modelUsage": {"claude-haiku-4-5": {"inputTokens": 100, "outputTokens": 5}},
    })


class Scripted:
    """`subprocess.run` for the whole process: `git` is real, `claude -p` answers from a script.

    Records, for every CLI call, where the process stood and where the CLI was told to run.
    """

    def __init__(self, real: Any, *, leak_on_git_probe: int | None = None,
                 fail_arm_call: int | None = None) -> None:
        self.real = real
        self.leak_on_git_probe = leak_on_git_probe
        self.fail_arm_call = fail_arm_call
        self.probes: list[dict[str, Any]] = []
        self.arm_cwds: list[Path] = []
        self.failed_stdout = ""

    def __call__(self, argv: list[str], *args: Any, **kwargs: Any) -> Any:
        if argv[0] == "git":
            return self.real(argv, *args, **kwargs)
        assert argv[0] == "claude" and "-p" in argv
        cwd = Path(kwargs["cwd"]).resolve()
        assert cwd.is_dir() and not list(cwd.iterdir())
        assert not any((path / ".git").exists() for path in (cwd, *cwd.parents))
        system = argv[argv.index("--system-prompt") + 1]
        if system in (milder.PROBE_SYSTEM, milder.GIT_PROBE_SYSTEM):
            here = Path.cwd().resolve()
            git_probes = sum(1 for probe in self.probes if probe["git"]) + 1
            is_git = system == milder.GIT_PROBE_SYSTEM
            self.probes.append({"git": is_git, "process_cwd": here, "cli_cwd": cwd,
                                "marker": (here / "CLAUDE.md").is_file()
                                or (here / milder.GIT_PROBE_FILE).is_file()})
            leak = is_git and git_probes == self.leak_on_git_probe
            answer = milder.GIT_PROBE_FILE if leak else "NONE"
            return subprocess.CompletedProcess(argv, 0, _envelope(answer), "")
        self.arm_cwds.append(cwd)
        if len(self.arm_cwds) == self.fail_arm_call:
            self.failed_stdout = json.dumps({
                "duration_api_ms": 0, "stop_reason": "stop_sequence", "session_id": "s" * 36,
                "padding": "p" * 2500, "is_error": True,
                "result": "Claude AI usage limit reached|1758580000",
            })
            return subprocess.CompletedProcess(argv, 1, self.failed_stdout, "")
        return subprocess.CompletedProcess(
            argv, 0, _envelope(json.dumps({"action": "read", "book": "A"})), "")


def _run_harness(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, scripted: Scripted) -> Any:
    monkeypatch.setattr(milder, "REPLICATES", 1)
    monkeypatch.setattr(subprocess, "run", scripted)
    monkeypatch.delenv("DISABLE_AUTOUPDATER", raising=False)
    paths = milder.Paths(root=tmp_path, arm_dir=tmp_path / "arm", local=tmp_path / "local",
                         fitness_dir=tmp_path / "fit", lock_holder=tmp_path / "lock" / "holder")
    paths.arm_dir.mkdir()
    planned = milder.plan(_books(4), PROFILE)
    registration = {"registration_digest": milder.registration_digest(PROFILE),
                    "request_identity": {"passed": True},
                    "reader": {"binary": "claude.exe", "binary_sha256": "0" * 64,
                               "binary_version": VERSION}}
    paths.registration(PROFILE).write_text(json.dumps(registration), encoding="utf-8")

    def verifier(profile: Any, **kwargs: Any) -> Any:
        assert profile == PROFILE
        return registration, planned

    return paths, planned, verifier


def test_every_probe_is_a_fresh_call_and_a_leak_on_the_third_git_probe_buys_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scripted = Scripted(subprocess.run, leak_on_git_probe=3)
    paths, _planned, verifier = _run_harness(tmp_path, monkeypatch, scripted)
    with pytest.raises(RuntimeError, match="isolation probe failed"):
        rebuy.run(paths=paths, verifier=verifier, pinner=lambda *args: None, workers=1,
                  log=lambda _: None)
    assert scripted.arm_cwds == []  # nothing bought
    assert [probe["git"] for probe in scripted.probes] == [False, True, True, True]
    for probe in scripted.probes:
        assert probe["marker"]  # the process stood where the marker is ...
        assert probe["cli_cwd"] != probe["process_cwd"]  # ... and the CLI did not
    assert len({probe["cli_cwd"] for probe in scripted.probes}) == 4
    [_started, finished] = milder.read_ledgers(paths.ledger(PROFILE))
    assert finished["stop"] == "isolation_probe_failed" and finished["fresh_calls"] == 0
    assert {name: probe["passed"] for name, probe in finished["probes"].items()} == {
        "claude_md": True, "git_status": True, "git_status_2": True, "git_status_3": False}
    assert finished["used_cumulative"]["calls"] == 4
    logged = [json.loads(line) for line in
              rebuy.probes_path(paths).read_text(encoding="utf-8").splitlines()]
    assert [entry["probe"] for entry in logged] == list(rebuy.PROBES)
    assert logged[-1]["record"]["text"] == milder.GIT_PROBE_FILE and not logged[-1]["passed"]
    assert "git_status_2" not in milder.PROBE_LEAK_MARKS  # the frozen table is restored
    assert not paths.raw(PROFILE).exists()


def test_a_bought_run_keeps_a_failed_calls_envelope_and_never_caches_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scripted = Scripted(subprocess.run, fail_arm_call=5)
    paths, planned, verifier = _run_harness(tmp_path, monkeypatch, scripted)
    ledger = rebuy.run(paths=paths, verifier=verifier, pinner=lambda *args: None, workers=1,
                       log=lambda _: None)
    assert ledger["sessions_completed"] == len(planned) == 12
    assert ledger["sessions_ended_on_failure"] == 1 and not ledger["complete"]
    [reason] = ledger["failure_reasons"]
    assert reason.startswith("cli_error:rc=1:Claude AI usage limit reached")
    # Five calls in the first session (the fifth failed), eight in each of the other eleven,
    # every one in its own fresh directory.
    assert len(set(scripted.arm_cwds)) == len(scripted.arm_cwds) == 5 + 11 * 8
    [entry] = [json.loads(line) for line in
               rebuy.failures_path(paths).read_text(encoding="utf-8").splitlines()]
    assert entry["stop_reason"] == reason
    assert entry["tag"]["feed"].startswith("ctbm4a-")
    assert entry["detail"]["stdout"] == scripted.failed_stdout[: elicit._CLI_FAILURE_DETAIL_CHARS]
    assert entry["detail"]["stdout_chars"] == len(scripted.failed_stdout)
    records = [json.loads(line)
               for line in paths.raw(PROFILE).read_text(encoding="utf-8").splitlines()]
    assert len(records) == 4 + 11 * 8
    assert milder.cached_failures(paths.raw(PROFILE)) == 0
    assert all(str(record["feed"]).startswith("ctbm4a-") for record in records)


def test_a_milder_v4_record_in_the_new_cache_is_refused_before_anything_is_bought(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scripted = Scripted(subprocess.run)
    paths, _planned, verifier = _run_harness(tmp_path, monkeypatch, scripted)
    paths.raw(PROFILE).write_text(
        json.dumps({"feed": "ctbm4-00-intact-r0", "key": "k:0", "stop_reason": "end_turn"})
        + "\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="no invocation of this arm started"):
        rebuy.run(paths=paths, verifier=verifier, pinner=lambda *args: None, log=lambda _: None)
    milder.append_ledger(paths.ledger(PROFILE),
                         {"event": "started", "invocation": 1, "started_at": "t"})
    with pytest.raises(RuntimeError, match="belong to no session of this arm"):
        rebuy.run(paths=paths, verifier=verifier, pinner=lambda *args: None, log=lambda _: None)
    assert scripted.probes == [] and scripted.arm_cwds == []


def test_the_observed_claim_names_this_arms_records_under_its_own_id(tmp_path: Path) -> None:
    paths = milder.Paths(root=tmp_path, arm_dir=tmp_path / "arm", local=tmp_path / "local",
                         fitness_dir=tmp_path / "fit", lock_holder=tmp_path / "lock" / "holder")
    paths.arm_dir.mkdir()
    for path in (paths.arm_dir / "PREREG.md", paths.arm_dir / rebuy.AMENDMENT_NAME,
                 paths.registration(PROFILE), paths.raw(PROFILE), paths.ledger(PROFILE),
                 paths.results(PROFILE), rebuy.failures_path(paths), rebuy.probes_path(paths)):
        path.write_text(f"{path.name}\n", encoding="utf-8")
    frozen = milder.write_claim
    with rebuy._amended_claims():
        assert milder.write_claim is rebuy.write_claim
        milder.write_claim(PROFILE, paths, "observed")
    assert milder.write_claim is frozen
    claim = json.loads(paths.claim(PROFILE).read_text(encoding="utf-8"))
    record = governance.parse_claim(claim)
    assert record.claim_id == "cost-that-bites.milder-v4a.claude"
    assert {(a["kind"], a["path"]) for a in claim["artifacts"]} >= {
        ("registration", "arm/AMENDMENT-1.md"),
        ("raw_result", "arm/raw-milder-v4a.jsonl"),
        ("raw_result", "arm/failures-milder-v4a.jsonl"),
        ("raw_result", "arm/probes-milder-v4a.jsonl"),
        ("derived_result", "arm/results-milder-v4a.json"),
    }
    with pytest.raises(RuntimeError, match="milder-v4a's claim only"):
        rebuy.write_claim(ORIGINAL, paths, "observed")
