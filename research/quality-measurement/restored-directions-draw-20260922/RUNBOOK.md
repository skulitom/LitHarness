# Restored-directions draw: runbook

The registration is [PREREG.md](PREREG.md); this is how to run it. After `prepare`, every
command below is `uv run --no-sync python
research/quality-measurement/restored-directions-draw-20260922/run.py <mode>`, shortened here to
`run.py <mode>`: `--no-sync` keeps the runner from re-syncing the shared environment the draw
froze. Global rule: exit 0 answered, 1 needs a person, 2 refused or an operational fault.

## Before anything: the box

One sustained job at a time ([guard and go](../RUNBOOK.md#guard-and-go-how-several-sessions-share-one-box)).
Check the process list, then take the lock atomically with this draw's prefix, which the runner
checks before prepare, before every stage, before every step and before every provider call:

```bash
ps -W | grep -E 'ab_redraw|claude -p|codex|litharness|pytest|mypy|MirrorBench'
mkdir C:/DEV/LitHarness/runs/box.lock && echo "restored-directions-draw-20260922: <who>, draw N <stage>, $(date +%H:%M)" \
    > C:/DEV/LitHarness/runs/box.lock/holder
```

Release it after each command that needs it (`rm -f .../holder && rmdir .../box.lock`), or hold
it across a checkpoint if nothing else is waiting. Never run tests, mypy or another arm beside a
stage.

## 1. Validate and register (no provider call)

```powershell
uv run pytest tests/test_restored_directions_draw.py -n 0      # box free, lock held
uv run python tools/check.py handoff                            # box free, lock held
uv run python research/quality-measurement/restored-directions-draw-20260922/run.py plan      # writes nothing
uv run python research/quality-measurement/restored-directions-draw-20260922/run.py prepare   # draw 1
uv run python research/quality-measurement/epistemic_governance.py research/quality-measurement/restored-directions-draw-20260922/claim.json
```

`prepare` pins HEAD, which must carry `619c697` (§255), `fd77145` (§256), `1c16fe7` (the
plural-decade precision rule), `60b1d56` (§257) and `d146504` (§258). It archives HEAD into
`runs/restored-directions-draw-20260922/draw-1/source` and builds a runtime that imports only
that source, taking its third-party dependencies from the shared `.venv` with the contracts
package frozen by hash and every installed version recorded. It copies the installation roster
through a read-only connection and checks rowntree's row (writer id
`wtr-43f373dd421c86f46c622872`, dossier SHA-256 `b97a2253…21ffa8`). It writes the brief and a
fresh invention seed, hashes and versions the Codex binary, and runs an offline preflight: the
real `concept` command against a scratch store, with the model boundary replaced, must reach
exactly one `writer.discovery` request carrying the brief and the restored directions. The
preflight records that request's digest; the first live invention request must equal it. It
writes `registration.json` and a `registered` claim.

A failed prepare buys nothing. It leaves a partial `draw-1/` without `progress.json`; move that
folder aside (it is the record of the attempt) and prepare again.

Commit `run.py`, `PREREG.md`, `RUNBOOK.md`, `registration.json`, `claim.json` and the test, then
push. Every stage refuses until those bytes are committed at HEAD and HEAD is on a remote branch.

## 2. The four stages

Each stage runs once, stops at its checkpoint and prints, in this order: the transport summary
(read failures first), what was bound for the gate, the delivery results, the inert
observations, the items the gate read must answer, and the command to record the gate.

```powershell
run.py concept     # checkpoint 1: concept/ (concept.json, concept.txt, traces)
run.py listing     # checkpoint 2: listing/ (title.txt, listing.txt, listing.json); the book stands up
run.py seed        # checkpoint 3: architect seed + world check; the world is NOT accepted
run.py chapter     # checkpoint 4: world accept, ticks until chapter one's four scenes are accepted
```

Everything is under `runs/restored-directions-draw-20260922/draw-N/`. When a stage ends, the
runner binds what the gate reads (`checkpoints/<checkpoint>.binding.json`: the checkpoint's
files by hash and a digest of the store); the next stage refuses to start if any of it changed,
and its first step refuses if the store moved. The chapter checkpoint writes `chapter-one.md`
(the reading copy), the library under `library/`, and the `why`, `status`, `verify` and `plans`
views under `views/`.

A stage refused before it starts buys nothing: an uncommitted registration, a changed frozen
file or installed dependency (restore it), or a gate not yet recorded. The one exception is a
ceiling: a stage's last call may cross one, and the next stage is then refused and the draw
recorded as stopped.

If a stage stops, the draw has ended. Read `progress.json`'s `stop`, the step records in
`steps/` and the call receipts in `calls/` (a failed call's `raw` holds the transport attempt)
before anything else, show the draw to the operator, and record `shown`.

If the observation child fails, the runner records `checkpoints/<checkpoint>.observation-failed.json`
(its exit code and log hash) and the gate proceeds without it. Observations decide nothing. A
rerun before the gate is optional, makes no provider call and touches nothing bound; from the
repository root:

```powershell
runs/restored-directions-draw-20260922/draw-N/runtime/Scripts/python.exe research/quality-measurement/restored-directions-draw-20260922/run.py observe N <checkpoint>
```

A defect in an observer, the binding or the scheduler is fixed for the next draw by a runner fix
(section 5), never inside the draw.

## 3. The gate read, at each checkpoint

The coordinator reads the checkpoint's artifacts and writes the read to a file under the draw
folder, for example `draw-1/GATE-concept.md`. It gives each item (C1-C4, L1-L4, W1-W3, H1-H8)
exactly one verdict line: the id at the start of the line (a `-` or `*` bullet is allowed), a
colon, then `PASS`, `FAIL` or `PARTIAL` and a location, for example
`C2: PASS concept.json system.start_rank 2 of 12`. Residuals follow, never on a line that starts
with an item id and a colon. Pass or fail is decided only on structure, mechanics and the
operator's enumerated items; sentence-level notes are residuals. The browsing readers' answers
in the listing step's output are model verdicts and are not read for the gate.

**The rule.** The checkpoint passes only when every item is `PASS`; `PARTIAL` counts as `FAIL`.

```powershell
run.py gate concept pass --read runs/restored-directions-draw-20260922/draw-1/GATE-concept.md --by coordinator
```

The runner refuses a read that misses an item or answers one twice, a `pass` over any item that
is not `PASS`, a `fail` over a read whose items are all `PASS`, a verdict while any call failed
or never finished, a checkpoint whose bound artifacts changed, and a second verdict. It records
each item's verdict. A `fail` ends the draw. A `pass` opens the next stage; at `chapter` it ends
the series.

## 4. After the draw ends

```powershell
run.py publish                                   # only after a chapter pass: book-library/<slug>/
run.py shown --by coordinator --how "<where the operator saw it>"
```

Every draw is shown to the operator, pass or fail. A failed or stopped draw is shown from its
run folder (`chapter-one.md`, `concept/concept.txt`, `listing/listing.txt`, the gate reads). A
passed draw is published first and shown from `book-library/`.

## 5. A redraw (at most three draws)

Only after the previous draw ended, was shown, and a committed amendment names a located cause.
Write both files in this folder, commit and push them, then prepare the next draw:

`AMENDMENT-N.md`: the located cause (checkpoint, where, what the read found) and the remedy.

`amendment-N.json`:

```json
{
  "schema": "restored-directions-draw.amendment.v1",
  "draw": 2,
  "previous_draw": 1,
  "located_cause": {"checkpoint": "concept", "where": "draw-1/concept/concept.json system.look"},
  "kind": "fix",
  "fix_commits": ["<40-hex commit that changes src/ or migrations/, after draw 1's revision>"],
  "registration_changes": []
}
```

`checkpoint` is a checkpoint name or `operational`. `kind` is one of three:

- `fix`: `fix_commits` (production commits touching `src/` or `migrations/`) and/or
  `runner_fix_commits` (commits that change this folder's `run.py` and nothing but it and
  `tests/test_restored_directions_draw.py`, for a defect in an observer, the binding or the
  scheduler). Every commit must be on HEAD and not in the previous draw's revision.
- `writer`: the dossier located as the cause, and the next writer in the registered sequence
  with his pinned pair. After rowntree that is barlow:
  `"writer": "barlow", "writer_id": "wtr-cd62e2c28595668f856fc116", "dossier_sha256":
  "6cd7d4f16a2a36b0225412b97d4f639e61d3aeac41f4447c04195cb006274409"` (the sequence and every
  pair are `WRITER_SEQUENCE` and `WRITERS` in run.py). `AMENDMENT-N.md` names his watched risks
  from his dossier before his draw.
- `transport`: `"failed_receipt": {"path": "calls/0007-chapter.json", "sha256": "<its sha256>"}`
  from the previous draw.

**`registration_changes`, whatever the kind.** Every registered file (run.py, PREREG.md,
RUNBOOK.md, the test, earlier amendments) whose bytes differ from the previous draw's
registration is listed as `{"path": "<repo-relative path>", "sha256": "<sha256 now>", "commit":
"<40-hex commit that changed it>"}`, and committed as it stands. A list naming a file that did
not change is refused too. `run.py prepare --draw N` prints what it refuses and why.

```powershell
uv run python research/quality-measurement/restored-directions-draw-20260922/run.py prepare --draw 2
```

Prepare checks the new draw's writer against its roster copy: a writer redraw against the
amendment's pair, a fix or transport redraw against the previous draw's. Then commit the new
`registration-draw2.json` and `claim.json`, push, and run the stages again.

## 6. Close and audit

The audit is final. It runs after a shown chapter pass, after three shown ended draws, or after
the operator ends the series early:

```powershell
run.py close --reason "<the operator's reason>"   # only to end early
run.py audit
uv run python research/quality-measurement/epistemic_governance.py research/quality-measurement/restored-directions-draw-20260922/claim.json
```

`audit` recomputes delivery over every recorded request in each draw's frozen runtime, checks
each call's transport controls (isolation flags, the working directory outside the repository
and `--skip-git-repo-check`, model and effort, no memory, no project docs, no search, bridge
children on the frozen runtime, fresh sessions, the receipt chain, the preflight digest), writes
`evidence.json` (counts, flags, codes and hashes only; each gate's item verdicts; stop reasons
as a code and a hash) and moves the claim to `observed`. `RESULTS.md` is written by hand after
it, in PREREG.md's reporting order, and keeps prose, quotes and located readings out of the
committed files: they stay under the run folder.

`run.py status` prints each draw's state at any time and writes nothing.
