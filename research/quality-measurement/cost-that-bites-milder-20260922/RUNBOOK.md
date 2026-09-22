# Runbook: arm `milder-v4`, the costed reader at a partial dose

Read `PREREG.md` (the design, the reading and what each outcome licenses) and
`ATTAINABILITY.md` (the sizing) before executing anything here. The box rules are CLAUDE.md's
and the guard-and-go section of `../RUNBOOK.md`. Commands are Git Bash from `C:/DEV/LitHarness`.

**What is bought, and what is not.** 360 `fcr.v0` sessions on `claude-haiku-4-5` over
`claude -p`: 20 fitness books x (intact, partial-0.65, sham) x 6 replicates, the target in slot
A, three workers. That is about 2,930 calls, 124 million reported tokens, $100 equivalent and 4h10
of wall time, under ceilings of 4,400 calls, 190 million tokens, $150 and 8 hours. The runner
checks the ceilings before each paid call and before each session. It also makes two isolation
probe calls per invocation. The arm uses no GPU, no generation and no production dispatch, and
writes no book.

## 0. Free checks, no call

```bash
uv run pytest tests/test_cost_that_bites_milder.py -n 0 -p no:randomly
uv run ruff check research/quality-measurement/cost_that_bites_milder.py \
    tests/test_cost_that_bites_milder.py research/quality-measurement/cost-that-bites-milder-20260922/
# The plan on the real shelf, read from temporary COPIES of the stores (an open may migrate a
# store, so the originals are never opened). Writes nothing.
uv run python research/quality-measurement/cost_that_bites_milder.py plan
```

`plan` must print 20 books, 360 sessions, the seed deviation
`{'fitness-08': {'partial': [0, 2, 3, 4, 5, 6]}}`, a mean dose near 0.644 displaced and 0.873
broken, and `faults: none`. Any other output means the shelf or the code differs from what was
sized. Stop there and do not prepare.

## 1. Freeze the registration, after review

```bash
uv run python research/quality-measurement/cost_that_bites_milder.py prepare
uv run python research/quality-measurement/epistemic_governance.py \
    research/quality-measurement/cost-that-bites-milder-20260922/claim.json
```

`prepare` first runs the **request-identity check**: it replays this arm's 120 intact and sham
sessions at replicates 0 to 2 from v2's committed `cost-that-bites/raw-v2.jsonl`, through a
replay-only reader that cannot write, and requires all 120 to replay and to reproduce v2's
committed book means. It prints the result and **refuses to register** if the check fails,
because then the extracted texts, the prompt or the transport are not v2's.

It then writes `registration.json`, which content-addresses this module, the PREREG, RUNBOOK,
ATTAINABILITY and every power-record file, the test file, every imported instrument module,
`src/litharness/domain/events.py` (the bootstrap's seed), `uv.lock`, v2's raw cache and result,
the store hashes, the extracted texts, every session's target text, the seeds, the identity
result, the Claude binary's path, sha256 and version, and the ceilings. It also rewrites
`claim.json` to point at `registration.json`, and writes the texts to the ignored
`runs/cost-that-bites-milder-20260922/milder-v4/texts.json`.

It **refuses** once this arm has bought a cell: a cached answer, a fresh arm call in the ledger,
or a reading. A probe-only invocation buys nothing, so after a failed probe, or a binary update
while waiting for a usage window, `prepare` can be re-run after review. It also refuses while the
Codex arm holds the question (see the end of this file).

## 2. Commit and push, before any run

The operator or coordinating session does this. `run` refuses unless every registered file is
byte-identical to `HEAD` and `HEAD` is on a remote branch. The claim's REGISTERED state becomes
true at this commit.

```bash
git add research/quality-measurement/cost_that_bites_milder.py tests/test_cost_that_bites_milder.py \
    research/quality-measurement/cost-that-bites-milder-20260922/
git commit -m "Register the costed reader's milder-dose arm (milder-v4)"
git push
```

## 3. Guard and go

```bash
# Nothing of anyone's may be running: no arm, suite, type check, corpus pass, draw or GPU job.
# The house guard, and the CIM query that sees command lines (interactive Claude sessions are
# not a job; a `claude -p` or `codex exec` child is).
ps -W | grep -E 'ab_redraw|claude -p|litharness|pytest|mypy|MirrorBench'
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { \$_.CommandLine \
    -match 'claude(\.exe)?\"? -p|codex(\.exe)?\"? exec|pytest|mypy|ab_redraw|MirrorBench' } | \
    Select-Object ProcessId, CommandLine"

# Take the lock, run, and release the lock only if it is still this arm's. The subshell stops at
# a held box before anything else runs, so this block can never unlock someone else's job.
(
  set -eu
  cd C:/DEV/LitHarness
  mkdir runs/box.lock || { echo "the box is held: stop"; cat runs/box.lock/holder; exit 1; }
  echo "cost-that-bites-milder-20260922: milder-v4, 360 sessions, <=4400 calls/190M tokens/\$150/8h, $(date +%H:%M)" \
      > runs/box.lock/holder
  status=0
  uv run python research/quality-measurement/cost_that_bites_milder.py run || status=$?
  if grep -q '^cost-that-bites-milder-20260922:' runs/box.lock/holder 2>/dev/null; then
    rm -f runs/box.lock/holder && rmdir runs/box.lock
  fi
  exit "$status"
)
```

Announce the start and the end. The lock holder **must** begin `cost-that-bites-milder-20260922:`
or `run` refuses. Do not wrap the run in `timeout`. Do not run anything CPU-heavy beside it.

`run` does these things in order:

1. It verifies every frozen byte, the commit, the push and the lock, and that the Codex arm has
   bought nothing.
2. It **pins the binary**. On the first invocation it copies the registered `claude.exe`, only if
   it still hashes to the registration, into the ignored
   `runs/cost-that-bites-milder-20260922/milder-v4/bin/<hash>/`. Every invocation checks the
   copy's hash and version, puts its folder first on PATH, and confirms CreateProcess will start
   it. From then on an interactive session updating `~/.local/bin/claude.exe` changes nothing
   this arm runs. If the original changed before the first pin, `run` refuses. Nothing was bought,
   so go back to step 1.
3. It sets `DISABLE_AUTOUPDATER=1` for itself and appends a `started` line to
   `runs-milder-v4.jsonl`, with its PID.
4. It makes **two isolation probes** through the arm's own transport on the pinned copy: one from
   a directory holding a marker `CLAUDE.md`, one from a scratch git repository holding a marker
   file. It buys nothing unless both answers contain `NONE` and neither carries its marker.
5. It buys the plan in replicate-major order, logging each session's outcome and step count and
   **never a target share**. It appends a checkpoint line after every session and a `finished`
   line at the end.

| exit | meaning | next |
| --- | --- | --- |
| 0 | every session dispatched and none ended on a failed call | step 4 |
| 2 | stopped: a ceiling, the transport circuit, unknown usage, a halt, or sessions that ended on a failed call | read the ledger's `stop` and `failure_reasons`, then resume or decide |
| other | refused before buying, or an error (the ledger's finished line records it) | read the message, fix nothing in the frozen files |

**Resume** by running the same block again. Bought calls replay free from `raw-milder-v4.jsonl`,
and only calls that obtained no answer are issued again. Ceilings are cumulative across
invocations. A usage limit (`cli_error:rc=...` reasons in the ledger) means waiting for the
subscription window, then resuming **on Claude**. It never means switching this arm to Codex.

**If the run process is killed** (by PID, a crash, or a shutdown), the ledger keeps every
session up to its last checkpoint and the cache keeps every answer. Then:

1. Confirm the PID in the last `started` line has ended:
   `powershell -NoProfile -Command "Get-Process -Id <pid>"` must fail. On this host, stop an owned
   process by PID in PowerShell and verify it ended; `pkill -f` has returned success without
   stopping anything.
2. If the lock is still held and its holder begins `cost-that-bites-milder-20260922:`, release
   it: `rm -f runs/box.lock/holder && rmdir runs/box.lock`. Never release another holder's lock.
3. Either **resume** with the step-3 block (a resume takes the larger of the ledger's and the
   cache's totals), or, if the operator decides no resume will follow, record that:
   `uv run python research/quality-measurement/cost_that_bites_milder.py close`, then step 4.
   `close` refuses while the lock names this arm.

**Nobody computes a reading from the raw cache before step 4.** The live log prints no share on
purpose, and `analyse` is the only reader of the cache.

## 4. Analyse, once

Run this when the last invocation finished with `"complete": true`, or when the operator decides
that no resume will follow, in which case the reading is stamped partial.

```bash
uv run python research/quality-measurement/cost_that_bites_milder.py analyse
uv run python research/quality-measurement/epistemic_governance.py \
    research/quality-measurement/cost-that-bites-milder-20260922/claim.json
```

`analyse` is call-free and needs no lock, but it **refuses while `runs/box.lock` names this arm**
and **while the last invocation has no finished line** (a run is live, or one was killed and
neither resumed nor closed), so no number is written while a cell could still be bought. It
verifies the frozen bytes and the commit, refuses if the cache holds any transport failure as an
answer (§235), and replays every planned session offline from the cache. It then writes
`results-milder-v4.json` (exclusive create, never overwritten), in this order: the transport
block (invocations, stops, failures by reason, dispatched and never-dispatched sessions, missing
sessions by name, tail block, coverage), the reader-identity block (the registered request
identity, and the drift diagnostic beside its same-reader baseline, which decides nothing), then
the preconditions with their measured values, the decision and its licence, and the
diagnostics. It moves `claim.json` to **observed**. From then on, `run` refuses.

Commit `raw-milder-v4.jsonl`, `runs-milder-v4.jsonl`, `results-milder-v4.json` and `claim.json`.
The findings (`FINDINGS.md` beside this file) are written by review against the PREREG's table,
not by the runner. Any promotion past OBSERVED is that review's act, and so is the stage-0 entry.
The pinned binary under `runs/` is local and is not committed; delete it only after the reading.

## The Codex contingency: not licensed by this arm's approval

This is a different reader, and so its own experiment (`PREREG.md`, "The Codex contingency").
**Whichever reader buys a cell first holds the question.** The Codex arm can substitute only if
no Claude cell has been bought. Once one has, a Codex arm needs its own folder and stage-0 entry,
and it is never run to second-guess a Claude reading. It is never a continuation of a stopped
Claude run.

`prepare --reader codex` refuses until two files exist beside the PREREG, and both are then
content-addressed in the Codex registration:

- `codex-approval.json`: the operator's approval record (who, when, and the stage-0 entry or
  message it cites);
- `ATTAINABILITY-codex.md`: a power record for this reader. None exists today, because no
  Codex session has ever been seated (`BRIEF.md` §5).

```bash
uv run python research/quality-measurement/cost_that_bites_milder.py plan --reader codex
uv run python research/quality-measurement/cost_that_bites_milder.py prepare --reader codex \
    --codex-binary "C:/Users/artem/AppData/Local/OpenAI/Codex/bin/<build>/codex.exe"
# commit and push registration-codex.json and claim-codex.json, take the lock as above with
# `run --reader codex` in place of `run`, then:
uv run python research/quality-measurement/cost_that_bites_milder.py analyse --reader codex
```

`--codex-binary` must be the native executable, not the npm `.CMD` shim. The Codex arm writes
`raw-milder-v4-codex.jsonl`, `runs-milder-v4-codex.jsonl` and `results-milder-v4-codex.json`,
and its ceilings are 5,900 calls, 150 million tokens and 12 hours (no price is reported).
