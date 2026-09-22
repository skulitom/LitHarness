"""Amendment 1 of arm `milder-v4`: the whole arm re-bought as `milder-v4a`, on the fixed transport.

`AMENDMENT-1.md` beside this file is the amendment. `milder-v4` bought 70 of its 360 sessions
through `elicit`'s `claude -p` transport while that transport ran in the repository root, and a
tool-free call from a git repository was then measured to receive the repository's status
intermittently. Those sessions are preserved on record, marked contaminated in this arm's
registration, and never read. This wrapper re-buys all 360 sessions into a fresh cache and
ledger through the fixed `elicit.py`, which runs every call in a fresh empty temporary directory
outside any git work tree.

**It imports the frozen runner and redirects, as `promise-payoff-challenge-20260922/recover.py`
does.** `cost_that_bites_milder.py`, its test, PREREG, RUNBOOK and ATTAINABILITY record are not
edited. What differs is data passed to the frozen functions:

* a profile that differs from the registered one only in labels: the arm (`milder-v4a`), the
  feed-id tag (`ctbm4a`, so the frozen foreign-record check refuses any contaminated record
  copied into the new cache), and the registration and claim file names;
* a registration built by the frozen `build_registration`, then compared with milder-v4's field
  by field (constants, cells, seeds, texts, stores, reader, request identity, every source hash
  but `elicit.py`, which must differ), and extended with an `amendment` block and the hashes of
  this wrapper, the amendment, its test, the fixed transport's test and the four contaminated
  files, so the frozen `verify` refuses if any of them changes or is uncommitted;
* the reader binary: milder-v4's pinned, hash-checked copy, which the frozen `pin_cli` copies
  again into this arm's own ignored folder;
* the isolation probes: the frozen two plus the git probe twice more (four calls per invocation),
  a regression check of the working-directory fix and no proof about the repository's status
  (`GIT_PROBES`), each probe's full record kept in `probes-milder-v4a.jsonl`;
* a failure log: every call that obtained no answer keeps its first 2,000 characters of stdout
  and stderr in `failures-milder-v4a.jsonl` (the frozen ledger keeps elicit's bounded reason);
* the claim: its own id, `cost-that-bites.milder-v4a.claude`, and the amendment as a
  registration artifact.

    uv run python research/quality-measurement/cost-that-bites-milder-20260922/rebuy.py prepare
    uv run python research/quality-measurement/cost-that-bites-milder-20260922/rebuy.py run
    uv run python research/quality-measurement/cost-that-bites-milder-20260922/rebuy.py close
    uv run python research/quality-measurement/cost-that-bites-milder-20260922/rebuy.py analyse

`close` is for a killed invocation only, as in the frozen RUNBOOK.
"""

from __future__ import annotations

import argparse
import contextlib
import dataclasses
import functools
import json
import os
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Iterator, Sequence
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import cost_that_bites_milder as base  # noqa: E402
import elicit  # noqa: E402

ORIGINAL = base.PROFILES["claude"]
#: The registered profile with four labels changed and nothing else: `design_differences`
#: refuses a registration in which anything else moved.
PROFILE = dataclasses.replace(
    ORIGINAL,
    arm="milder-v4a",
    tag="ctbm4a",
    registration_name="registration-v4a.json",
    claim_name="claim-v4a.json",
)
CLAIM_ID = "cost-that-bites.milder-v4a.claude"

AMENDMENT_NAME = "AMENDMENT-1.md"
WRAPPER_NAME = "rebuy.py"
TEST_NAME = "test_cost_that_bites_milder_rebuy.py"
#: The fixed transport's own test, which pins its argv, stdin and cache key to the unfixed ones.
TRANSPORT_TEST_NAME = "test_elicit_cli_workdir.py"
#: The one registered source this amendment changes, relative to the repository root.
ELICIT = "research/quality-measurement/elicit.py"

#: The git probe three times. With the fix the CLI never runs in the probe's directory, so the
#: probes are a regression check of the pinned transport and prove nothing about the
#: repository's status: were the working-directory fix undone, one probe would still pass 60% to
#: 80% of the time at the measured rate (1 to 2 leaks in 5) and three would pass 22% to 51%.
#: Each invocation runs them again.
GIT_PROBES: tuple[str, ...] = ("git_status", "git_status_2", "git_status_3")
PROBES: tuple[str, ...] = ("claude_md", *GIT_PROBES)

#: Fields of the registration that name this arm and so may differ from milder-v4's.
_LABEL_KEYS = frozenset({"arm"})


def failures_path(paths: base.Paths) -> Path:
    return paths.arm_dir / f"failures-{PROFILE.arm}.jsonl"


def probes_path(paths: base.Paths) -> Path:
    return paths.arm_dir / f"probes-{PROFILE.arm}.jsonl"


def contaminated_files(paths: base.Paths) -> list[Path]:
    """milder-v4's registration, claim, raw cache and ledger: preserved, hashed, never read."""
    return [
        paths.registration(ORIGINAL),
        paths.claim(ORIGINAL),
        paths.raw(ORIGINAL),
        paths.ledger(ORIGINAL),
    ]


def extra_sources(paths: base.Paths) -> list[Path]:
    """What this amendment adds to the frozen `sources()`, content-addressed the same way."""
    return [
        paths.arm_dir / WRAPPER_NAME,
        paths.arm_dir / AMENDMENT_NAME,
        paths.root / "tests" / TEST_NAME,
        paths.root / "tests" / TRANSPORT_TEST_NAME,
        *contaminated_files(paths),
    ]


def original_registration(paths: base.Paths) -> dict[str, Any]:
    path = paths.registration(ORIGINAL)
    if not path.is_file():
        raise RuntimeError(f"no milder-v4 registration at {base._rel(path, paths.root)}")
    registration: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return registration


def contamination(paths: base.Paths) -> dict[str, Any]:
    """What milder-v4 bought, in counts, usage and hashes. No answer is read for its content.

    Refused while milder-v4's last invocation has no finished line (a run of it could still be
    buying) and once a milder-v4 reading exists (this amendment presumes it was never read).
    """
    if paths.results(ORIGINAL).exists():
        raise RuntimeError(
            f"{base._rel(paths.results(ORIGINAL), paths.root)} exists: the contaminated arm was "
            "read, and this amendment registers a re-buy only of an arm nobody has read"
        )
    ledgers = base.read_ledgers(paths.ledger(ORIGINAL))
    if not ledgers:
        raise RuntimeError("no milder-v4 ledger: there is nothing to preserve or re-buy")
    if not base.finished(ledgers):
        raise RuntimeError(
            "milder-v4's last invocation has no finished line: it may still be running; confirm "
            "its PID has ended and record it with the frozen runner's close first"
        )
    raw = paths.raw(ORIGINAL)
    used = base.prior_usage(ledgers, raw)
    kept = ("invocation", "started_at", "finished_at", "stop", "complete", "fresh_calls",
            "transport_failures", "sessions_completed", "binary_version")
    return {
        "arm": ORIGINAL.arm,
        "status": (
            "contaminated: bought through elicit's claude -p transport while it ran in the "
            "repository root, which was then measured to pass the repository's git status to a "
            "tool-free call intermittently; preserved on record and never read"
        ),
        "files": {base._rel(path, paths.root): base.file_sha(path)
                  for path in contaminated_files(paths)},
        "invocations": [
            {
                **{key: summary.get(key) for key in kept},
                "probes_passed": {
                    name: bool(probe.get("passed"))
                    for name, probe in (summary.get("probes") or {}).items()
                },
            }
            for summary in base.invocations(ledgers)
        ],
        "sessions_checkpointed": len({
            str(line["feed_id"]) for line in ledgers
            if line.get("event") == "session" and line.get("feed_id")
        }),
        "raw_records": base.raw_totals(raw)["records"],
        "usage": {
            "calls": used.get("calls", 0.0),
            "tokens": used.get("tokens", 0.0),
            "usd": round(float(used.get("usd", 0.0)), 4),
            "seconds": used.get("seconds", 0.0),
        },
    }


def pinned_source(paths: base.Paths, original: dict[str, Any]) -> Path:
    """milder-v4's pinned copy of the registered binary, where its frozen `pin_cli` put it."""
    reader = original["reader"]
    folder = paths.pin_dir(ORIGINAL, str(reader["binary_sha256"]))
    return folder / Path(str(reader["binary"])).name


def source_binary(
    paths: base.Paths, original: dict[str, Any], version_reader: Callable[[Path], str]
) -> dict[str, Any]:
    """The reader binary this arm registers: milder-v4's pinned copy, checked, never the install.

    The install at `~/.local/bin/claude.exe` is updated in place by interactive sessions; the
    copy is the binary milder-v4 registered, hash and version checked here and again by the
    frozen `pin_cli` when it copies it into this arm's own folder.
    """
    reader = original["reader"]
    pinned = pinned_source(paths, original)
    if not pinned.is_file():
        raise RuntimeError(
            f"milder-v4's pinned copy {pinned} is missing: the same binary cannot be registered"
        )
    if base.file_sha(pinned) != reader["binary_sha256"]:
        raise RuntimeError(f"milder-v4's pinned copy {pinned} no longer hashes to its registration")
    version = version_reader(pinned)
    if version != reader["binary_version"]:
        raise RuntimeError(f"milder-v4's pinned copy {pinned} reports {version!r}")
    return {"binary": str(pinned), "binary_sha256": reader["binary_sha256"],
            "binary_version": version}


def _relabelled(cells: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    prefix, original = f"{PROFILE.tag}-", f"{ORIGINAL.tag}-"
    return [
        {**cell, "feed_id": original + str(cell["feed_id"]).removeprefix(prefix)}
        for cell in cells
    ]


def design_differences(
    original: dict[str, Any], registration: dict[str, Any], *, extras: frozenset[str] = frozenset()
) -> list[str]:
    """Everything in `registration` that is not milder-v4's design, beyond the labels.

    Empty means: the same constants (the pre-registration, arm aside), the same 360 cells in the
    same order with the same targets, seeds and dose metrics (feed ids relabelled), the same
    stores and texts, the same reader, the same request-identity result, and the same bytes in
    every registered source except `elicit.py`, which must be the fixed one. `extras` are the
    amendment's own hashed files, left out of the source comparison. Both sides are compared as
    JSON, which is how the registered one was read.
    """
    original = json.loads(json.dumps(original))
    registration = json.loads(json.dumps(registration))
    problems: list[str] = []
    before, after = original["pre_registration"], registration["pre_registration"]
    for key in sorted(set(before) | set(after)):
        if key not in _LABEL_KEYS and before.get(key) != after.get(key):
            problems.append(f"pre_registration.{key}")
    if after.get("arm") != PROFILE.arm:
        problems.append("pre_registration.arm")
    if registration.get("arm") != PROFILE.arm:
        problems.append("arm")
    if _relabelled(registration["cells"]) != original["cells"]:
        problems.append("cells")
    for key in ("books", "sessions", "max_calls", "seeds", "seed_deviations", "dose_metrics_mean"):
        if original["plan"].get(key) != registration["plan"].get(key):
            problems.append(f"plan.{key}")
    for key in ("fitness_dir", "stores_sha256", "texts_sha256", "books"):
        if original["inputs"].get(key) != registration["inputs"].get(key):
            problems.append(f"inputs.{key}")
    for key in ("model", "transport", "effort", "binary_sha256", "binary_version", "hardening",
                "disclosed_changes"):
        if original["reader"].get(key) != registration["reader"].get(key):
            problems.append(f"reader.{key}")
    if original.get("request_identity") != registration.get("request_identity"):
        problems.append("request_identity")
    if original.get("registration_digest") == registration.get("registration_digest"):
        problems.append("registration_digest (the arm label must be in it)")
    registered = original["source_hashes"]
    now = {k: v for k, v in registration["source_hashes"].items() if k not in extras}
    for name in sorted(set(registered) | set(now)):
        if name == ELICIT:
            if registered.get(name) == now.get(name):
                problems.append(f"{ELICIT} is milder-v4's registered, unfixed transport")
        elif registered.get(name) != now.get(name):
            problems.append(f"source {name}")
    return problems


def amendment_block(
    paths: base.Paths, original: dict[str, Any], stained: dict[str, Any], fixed_sha: str
) -> dict[str, Any]:
    prior = stained["usage"]
    limits = dict(PROFILE.limits)
    return {
        "amendment": base._rel(paths.arm_dir / AMENDMENT_NAME, paths.root),
        "amends": {
            "arm": ORIGINAL.arm,
            "registration": base._rel(paths.registration(ORIGINAL), paths.root),
            "registration_sha256": base.file_sha(paths.registration(ORIGINAL)),
        },
        "contaminated": stained,
        "transport_fix": {
            "file": ELICIT,
            "registered_sha256": original["source_hashes"][ELICIT],
            "fixed_sha256": fixed_sha,
            "change": (
                "every claude -p call runs in a fresh empty temporary directory outside any git "
                "work tree, refused if a work tree contains it, and without git's location "
                "variables in its environment; the argv, stdin and cache key are unchanged; "
                "each bought answer's record carries cli_workdir=isolated-2026-09-22, and a "
                "cache holding an answer without it is replayed, never bought into; a failed "
                "call's first 2,000 characters of stdout and stderr are kept, never in the cache"
            ),
        },
        "labels": {
            "arm": PROFILE.arm,
            "feed_tag": PROFILE.tag,
            "registration": PROFILE.registration_name,
            "claim": PROFILE.claim_name,
            "claim_id": CLAIM_ID,
            "why": "a separate arm, so no file of milder-v4 is written; the feed tag makes the "
            "frozen foreign-record check refuse a contaminated record in the new cache",
        },
        "reader_binary": {
            "source": str(pinned_source(paths, original)),
            "pinned_to": str(paths.pin_dir(PROFILE, str(original["reader"]["binary_sha256"]))),
        },
        "probes": {
            "names": list(PROBES),
            "per_invocation": len(PROBES),
            "rule": "each answer contains NONE and not its leak mark, the frozen rule; any "
            "failure buys nothing",
            "log": base._rel(probes_path(paths), paths.root),
        },
        "failure_log": base._rel(failures_path(paths), paths.root),
        "ceilings": {
            "this_arm": limits,
            "contaminated_spend": prior,
            "combined_worst_case": {
                name: (float(limits[name] or 0.0) + float(prior.get(name, 0.0)))
                for name in ("calls", "tokens", "usd", "seconds")
            },
        },
        "unchanged": [
            "the design, statistic, decision table and licence (the pre-registration, arm aside)",
            "the 360 cells, their order, targets, seeds and dose metrics",
            "the texts and stores, the sham, the reader, its argv and the request bytes",
            "the ceilings, reservations, circuit, workers, ledger and lock rules",
            "every registered source but elicit.py",
        ],
    }


def write_claim(profile: base.Profile, paths: base.Paths, status: str) -> None:
    """The frozen `write_claim` with this arm's own id and the amendment as a registration."""
    if profile != PROFILE:
        raise RuntimeError("this wrapper writes milder-v4a's claim only")
    files: list[tuple[str, Path]] = [
        ("registration", paths.arm_dir / "PREREG.md"),
        ("registration", paths.arm_dir / AMENDMENT_NAME),
    ]
    if paths.registration(profile).is_file():
        files.append(("registration", paths.registration(profile)))
    if status == "observed":
        files += [
            ("raw_result", paths.raw(profile)),
            ("raw_result", paths.ledger(profile)),
            ("derived_result", paths.results(profile)),
            ("control_result", paths.results(profile)),
        ]
        files += [("raw_result", path) for path in (failures_path(paths), probes_path(paths))
                  if path.is_file()]
    base.write_json(
        paths.claim(profile),
        {
            "schema": "litharness.epistemic-claim.v1",
            "claim_id": CLAIM_ID,
            "statement": base.claim_statement(profile) + (
                " Bought as arm milder-v4a under AMENDMENT-1, through the transport that runs "
                "outside the repository; milder-v4's contaminated purchase is not read."
            ),
            "status": status,
            "artifacts": [
                {"kind": kind, "path": base._rel(path, paths.root), "sha256": base.file_sha(path)}
                for kind, path in files
            ],
        },
    )


# -------------------------------------------------------------------------------- prepare


def prepare(
    *,
    paths: base.Paths = base.DEFAULT_PATHS,
    texts_loader: Callable[[Path], tuple[list[tuple[str, str]], dict[str, str]]] = (
        base.extract_texts
    ),
    version_reader: Callable[[Path], str] = base.binary_version,
    identity_check: Callable[..., dict[str, Any] | None] = base.request_identity,
) -> dict[str, Any]:
    """The frozen `prepare`'s steps in its order, then the comparison and the amendment block.

    Refused: without milder-v4's finished ledger, or once it has a reading; while `elicit.py` is
    still the registered transport; once this arm has bought a cell (the frozen rule, so a
    probe-only invocation still allows a fresh registration); while the Codex arm holds the
    question; without milder-v4's pinned binary; when the request identity against v2 fails;
    and when anything but the labels and `elicit.py` differs from milder-v4's registration.
    """
    original = original_registration(paths)
    stained = contamination(paths)
    fixed_sha = base.file_sha(paths.root / ELICIT)
    if fixed_sha == original["source_hashes"][ELICIT] or not hasattr(elicit, "_cli_workdir"):
        raise RuntimeError(
            f"{ELICIT} is still the transport milder-v4 registered: nothing is re-bought through "
            "it, so nothing is registered"
        )
    bought = base.purchases(PROFILE, paths)
    if bought["any"]:
        raise RuntimeError(
            f"{PROFILE.arm} has bought cells ({bought}): a registration is never refreshed "
            "after a cell was bought"
        )
    base.fence(PROFILE, paths)
    binary = source_binary(paths, original, version_reader)
    texts, store_hashes = texts_loader(paths.fitness_dir)
    identity = identity_check(PROFILE, base.plan(texts, PROFILE), paths)
    if identity is None or not identity["passed"]:
        raise RuntimeError(
            f"request identity failed: {identity}; the texts, prompt or transport are not v2's, "
            "so nothing is registered"
        )
    texts_path = paths.texts(PROFILE)
    base.write_json(texts_path, {"fitness": [list(pair) for pair in texts]})
    registration = base.build_registration(
        PROFILE, texts, store_hashes, binary, paths, base.file_sha(texts_path), identity
    )
    problems = design_differences(original, registration)
    if problems:
        raise RuntimeError(
            f"the re-buy is not milder-v4's design: {problems}; nothing is registered"
        )
    extras = {base._rel(path, paths.root): base.file_sha(path) for path in extra_sources(paths)}
    overlap = sorted(set(extras) & set(registration["source_hashes"]))
    if overlap:
        raise RuntimeError(f"the amendment's files collide with registered sources: {overlap}")
    registration["source_hashes"].update(extras)
    registration["amendment"] = amendment_block(paths, original, stained, fixed_sha)
    base.write_json(paths.registration(PROFILE), registration)
    write_claim(PROFILE, paths, "registered")
    return registration


# --------------------------------------------------------------------------------- verify


def verify(
    profile: base.Profile = PROFILE,
    *,
    paths: base.Paths = base.DEFAULT_PATHS,
    git: Callable[[Sequence[str], Path], bytes] = base._git,
    binary_reader: Any = None,
    check_lock: bool = False,
) -> tuple[dict[str, Any], list[base.Planned]]:
    """The frozen `verify`, then the amendment's own checks.

    The frozen checks cover every hashed file, this amendment's included: unchanged, committed
    at HEAD, HEAD pushed, the lock this folder's. `binary_reader` is accepted for the frozen
    runner's call and not used: the binary is milder-v4's pinned copy, checked by hash and
    version when `pin_cli` copies it and at every invocation.
    """
    del binary_reader
    if profile != PROFILE:
        raise RuntimeError("this wrapper verifies milder-v4a only")
    registration, planned = base.verify(
        PROFILE, paths=paths, git=git, binary_reader=None, check_lock=check_lock
    )
    amendment = registration.get("amendment")
    if not isinstance(amendment, dict):
        raise RuntimeError("the registration carries no amendment block")
    original = original_registration(paths)
    if amendment["amends"]["registration_sha256"] != base.file_sha(paths.registration(ORIGINAL)):
        raise RuntimeError("milder-v4's registration changed after the amendment was registered")
    extras = frozenset(base._rel(path, paths.root) for path in extra_sources(paths))
    unaddressed = sorted(extras - set(registration["source_hashes"]))
    if unaddressed:
        raise RuntimeError(f"the registration does not content-address {unaddressed}")
    if paths.results(ORIGINAL).exists():
        raise RuntimeError("a milder-v4 reading exists: the contaminated arm was read")
    problems = design_differences(original, registration, extras=extras)
    if problems:
        raise RuntimeError(f"the registration is not milder-v4's design: {problems}")
    if registration["reader"]["binary"] != str(pinned_source(paths, original)):
        raise RuntimeError("the registered reader binary is not milder-v4's pinned copy")
    return registration, planned


# ------------------------------------------------------------------------------------ run


def open_reader(
    profile: base.Profile, paths: base.Paths, reg: dict[str, Any], *, replay_only: bool
) -> Any:
    """The frozen reader, with elicit's failure log pointed at this arm's file when it buys."""
    reader = base.open_reader(profile, paths, reg, replay_only=replay_only)
    if not replay_only:
        reader.failure_log = failures_path(paths)
    return reader


def _append(path: Path, entry: dict[str, Any]) -> None:
    with base.open_append(path) as handle:
        handle.write(json.dumps(entry, sort_keys=True, ensure_ascii=False) + "\n")
        handle.flush()


def _ask_probe(
    name: str, directory: Path, system: str, model: str, cache: Path, paths: base.Paths
) -> dict[str, Any]:
    """One probe, asked with the process standing in `directory`, as the frozen `_probe_in` does.

    Its own cache file, so the repeated git probe is three calls and never a replay.
    """
    previous = Path.cwd()
    os.chdir(directory)
    try:
        with base.ClaudeReader(cache, model=model) as reader:
            reader.failure_log = failures_path(paths)
            record: dict[str, Any] = reader.ask_raw(
                system, [{"role": "user", "content": base.PROBE_PROMPT}], schema=None,
                max_tokens=16, tag={"stage": "isolation_probe", "probe": name},
            )
    finally:
        os.chdir(previous)
    # The repeated git probes are judged by the git probe's own mark, as `_probe_marks` has the
    # frozen `run` judge them.
    judged_as = "git_status" if name in GIT_PROBES else name
    _append(probes_path(paths), {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "probe": name, "record": record,
        "passed": base.probe_passed(judged_as, record),
    })
    return record


def isolation_probes(
    profile: base.Profile, reg: dict[str, Any], *, paths: base.Paths = base.DEFAULT_PATHS
) -> dict[str, dict[str, Any]]:
    """The frozen probes, with the git probe asked three times.

    The marker `CLAUDE.md` and the scratch repository are where the *process* stands; the fixed
    transport runs the CLI in its own empty directory, so it can never run in either. A pass is
    a regression check that the process's directory still does not reach the reader. It says
    nothing about repository context arriving by another channel, which would describe the
    repository root, where no marker is.
    """
    del reg
    records: dict[str, dict[str, Any]] = {}
    with tempfile.TemporaryDirectory(prefix="ctbm4a-probe-", ignore_cleanup_errors=True) as tmp:
        root = Path(tmp)
        marker = root / "claude_md"
        marker.mkdir()
        (marker / "CLAUDE.md").write_text(base.PROBE_MARKER, encoding="utf-8")
        repository = root / "git_status"
        repository.mkdir()
        subprocess.run(["git", "init", "--quiet", str(repository)], check=True,
                       capture_output=True)
        (repository / base.GIT_PROBE_FILE).write_text("context probe\n", encoding="utf-8")
        records["claude_md"] = _ask_probe(
            "claude_md", marker, base.PROBE_SYSTEM, profile.model, root / "claude_md.jsonl", paths
        )
        for name in GIT_PROBES:
            records[name] = _ask_probe(
                name, repository, base.GIT_PROBE_SYSTEM, profile.model, root / f"{name}.jsonl",
                paths,
            )
    return records


@contextlib.contextmanager
def _probe_marks() -> Iterator[None]:
    """The repeated git probes' leak mark, the git probe's own, for the frozen `probe_passed`."""
    added = [name for name in GIT_PROBES if name not in base.PROBE_LEAK_MARKS]
    for name in added:
        base.PROBE_LEAK_MARKS[name] = base.PROBE_LEAK_MARKS["git_status"]
    try:
        yield
    finally:
        for name in added:
            base.PROBE_LEAK_MARKS.pop(name, None)


def run(
    *,
    paths: base.Paths = base.DEFAULT_PATHS,
    verifier: Callable[..., tuple[dict[str, Any], list[base.Planned]]] = verify,
    reader_factory: Callable[..., Any] = open_reader,
    probe: Callable[[base.Profile, dict[str, Any]], dict[str, dict[str, Any]]] | None = None,
    guard: Callable[[], str | None] | None = None,
    pinner: Callable[[base.Profile, base.Paths, dict[str, Any]], Path] = base.pin_cli,
    workers: int = base.WORKERS,
    log: Callable[[str], None] = print,
) -> dict[str, Any]:
    """The frozen `run` on this arm's profile, verifier, reader, probes and pin."""
    with _probe_marks():
        return base.run(
            PROFILE,
            paths=paths,
            verifier=verifier,
            reader_factory=reader_factory,
            probe=probe or functools.partial(isolation_probes, paths=paths),
            guard=guard,
            pinner=pinner,
            workers=workers,
            log=log,
        )


def close(*, paths: base.Paths = base.DEFAULT_PATHS) -> dict[str, Any]:
    return base.close(PROFILE, paths=paths)


@contextlib.contextmanager
def _amended_claims() -> Iterator[None]:
    frozen = base.write_claim
    base.write_claim = write_claim
    try:
        yield
    finally:
        base.write_claim = frozen


def analyse(
    *,
    paths: base.Paths = base.DEFAULT_PATHS,
    verifier: Callable[..., tuple[dict[str, Any], list[base.Planned]]] = verify,
    reader_factory: Callable[..., Any] = open_reader,
) -> dict[str, Any]:
    """The frozen `analyse` on this arm's files; it reads `raw-milder-v4a.jsonl` and no other."""
    with _amended_claims():
        return base.analyse(PROFILE, paths=paths, verifier=verifier, reader_factory=reader_factory)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "run", "close", "analyse"))
    parser.add_argument("--workers", type=int, default=base.WORKERS)
    args = parser.parse_args(argv)
    if args.workers < 1 or args.workers > base.WORKERS:
        parser.error(f"--workers must be 1..{base.WORKERS}")
    if args.mode == "prepare":
        registration = prepare()
        print(json.dumps({k: registration["plan"][k] for k in ("books", "sessions", "max_calls",
                                                                 "seed_deviations")}, indent=2))
        print(f"request identity: {json.dumps(registration['request_identity'])}")
        print(f"contaminated: {json.dumps(registration['amendment']['contaminated']['usage'])}")
        print(f"wrote {base._rel(base.DEFAULT_PATHS.registration(PROFILE), base.ROOT)} and the "
              "claim; commit and push them with the milder-v4 ledger and cache before run")
        return 0
    if args.mode == "run":
        ledger = run(workers=args.workers)
        return 0 if ledger.get("complete") else 2
    if args.mode == "close":
        print(json.dumps(close(), indent=2))
        return 0
    result = analyse()
    print(json.dumps({"transport": result["transport"],
                      "decision": result["reading"]["decision"],
                      "preconditions": result["reading"]["preconditions"],
                      "target_read_share": result["reading"]["target_read_share"],
                      "warnings": result["warnings"]}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
