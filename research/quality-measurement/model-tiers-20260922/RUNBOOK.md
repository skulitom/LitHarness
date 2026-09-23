# Runbook: `model-tiers.v1`, may scene summaries move tier on Codex?

Read `PREREG.md` (the design, the rule, what each outcome licenses and what it cannot establish)
before executing anything here. The box rules are CLAUDE.md's and the guard-and-go section of
`../RUNBOOK.md`. Commands are Git Bash from `C:/DEV/LitHarness`.

**What is bought.** 172 planned Codex calls through `providers/codex_cli.CodexCliProvider`, never
the Claude CLI, on a pinned copy of the registered Codex bin folder and a pinned archive of the
registration commit's source: the full-book trial's 24 scene-summary requests as recorded, on
`gpt-6-astra` (medium, the control), `gpt-6-luna` (medium) and `gpt-6-luna` (high); the same 24
rebuilt in §255's current wording, on two `gpt-6-astra` replicates (reference and floor) and the
two Luna cells; then four Architect seeds (`gpt-6-astra`, `gpt-6-sol`, `gpt-6-sol`,
`gpt-6-astra`) into fresh copies of the trial's pre-seed store, a screen that licenses nothing.
Expected about 2.5 to 5 million recorded tokens and 1.2 to 2 hours; ceilings are 240 calls,
7,000,000 tokens and 14,400 seconds of call time, checked before every call. Codex reports no
price. No GPU, no drafting, no production store is touched: the seeds write only into copies
under `runs/model-tiers-20260922/seeds/`.

## 0. Free checks, no call

Only when the box is free (no arm, suite, type check or corpus pass running):

```bash
uv run pytest tests/test_model_tiers_comparison.py -n 0 -p no:randomly
uv run ruff check research/quality-measurement/model_tiers_comparison.py \
    tests/test_model_tiers_comparison.py
# The plan from the recorded calls alone; opens no store and writes nothing.
uv run python research/quality-measurement/model_tiers_comparison.py plan
```

`plan` must print 24 recorded `mechanical` requests, all 24 opening on the scene, 72
recorded-wording units, 96 current-wording units and 4 seed units, and phases `drain1` to
`drain24`. Anything else means the trial's files are not what was registered against: stop.

After any edit to `PREREG.md` or `RUNBOOK.md` before step 1, rewrite the claim so it cites the
edited bytes (no call, no store; refused once `registration.json` exists):

```bash
uv run python research/quality-measurement/model_tiers_comparison.py claim
```

## 1. Freeze the registration, after review

`src/` and `migrations/` must equal `HEAD` (`git status --porcelain -- src migrations` prints
nothing): `prepare` refuses otherwise, because it archives HEAD and its own reads of the trial
import the live checkout. On 2026-09-22 `src/litharness/application/precision.py` carried
another session's uncommitted change; it must be committed or set aside by its owner first,
never by this arm. Once `prepare` has run, later commits to `src/` change nothing this arm runs.

Pick the native Codex the operator's app currently uses (the newest folder under
`C:/Users/artem/AppData/Local/OpenAI/Codex/bin/` holding `codex.exe`; not the npm `.CMD` shim)
and record it:

```bash
uv run python research/quality-measurement/model_tiers_comparison.py prepare \
    --codex-binary "C:/Users/artem/AppData/Local/OpenAI/Codex/bin/<build>/codex.exe"
uv run python research/quality-measurement/epistemic_governance.py \
    research/quality-measurement/model-tiers-20260922/claim.json
```

`prepare` makes no provider call. It:

1. archives HEAD's `src/`, `migrations/`, `pyproject.toml` and `uv.lock` into
   `runs/model-tiers-20260922/source/` and builds `runs/model-tiers-20260922/runtime/`, a venv
   whose `.pth` points there; a probe must import `litharness` from the archive;
2. copies the Codex bin folder whole into `runs/model-tiers-20260922/codex/<build>/` (about
   0.4 GB), every file hash-checked against the original, and reads the copy's `--version`
   (which makes no model call);
3. reads the trial's final store and its pre-seed snapshot from temporary copies (originals are
   never opened), checks every recorded summary request (it round-trips byte for byte, the
   adapter submitted exactly its prompt and system, the native schema matches up to the order of
   `required` members, its prompt is the accepted scene plus the recorded ledger block, and the
   store's accepted summary and paid split are the recorded answer's), and requires the seed
   world's reconstruction to reproduce the accept step's own counts. It refuses on any failure;
4. rebuilds every summary request from the scene and the trial's `promises` rows under the
   frozen runtime (`runs/full-book-trial-20260919/runtimes/A/Scripts/python.exe`), requiring
   each whole request byte-identical to the record, and under the pinned runtime, which gives
   the current-wording requests;
5. rebuilds the seed request through the production CLI with billing disabled and the
   completion call replaced (`render-seed`): under the frozen runtime from the pre-seed snapshot
   it must equal the recorded `architect.seed.v8` request byte for byte; under the pinned runtime,
   from the template copy it migrated (`open-store`), it is the request the screen sends;
6. writes the ignored inputs (`runs/model-tiers-20260922/inputs/`: both blocks' requests, ledger
   rows, scene texts, accepted records, the seed request, the template store), then
   `registration.json` (hashes, commit and trees, the pinned runtime and Codex folder, the
   identity results, the constants' digest) and rewrites `claim.json` to cite it.

It refuses once any call has been dispatched or a reading exists; before that it may be run
again, and rebuilds the archive and the runtime from nothing. If the frozen runtime cannot start
(its shared site-packages changed), nothing is registered: record that and amend this
registration rather than skipping the check.

## 2. Commit and push, before any run

The operator or coordinating session does this. `run` refuses unless this arm's files and
`registration.json` are byte-identical to `HEAD` and `HEAD` is on a remote branch. The claim's
REGISTERED state becomes true at this commit.

```bash
git add research/quality-measurement/model_tiers_comparison.py \
    tests/test_model_tiers_comparison.py research/quality-measurement/model-tiers-20260922/
git commit -m "Register the model-tier comparison (model-tiers.v1)"
git push
```

## 3. Guard and go

`run` executes under the pinned runtime, never `uv run`: the adapter, the tool bridge and the
reading's world CLI import whatever `sys.executable` imports, and `run` refuses any other
interpreter.

```bash
# Nothing of anyone's may be running: no arm, suite, type check, corpus pass, draw or GPU job.
ps -W | grep -E 'ab_redraw|claude -p|litharness|pytest|mypy|MirrorBench'
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { \$_.CommandLine \
    -match 'claude(\.exe)?\"? -p|codex(\.exe)?\"? exec|pytest|mypy|ab_redraw|MirrorBench' } | \
    Select-Object ProcessId, CommandLine"

# Take the lock, run, and release the lock only if it is still this arm's.
(
  set -eu
  cd C:/DEV/LitHarness
  mkdir runs/box.lock || { echo "the box is held: stop"; cat runs/box.lock/holder; exit 1; }
  echo "model-tiers-20260922: 172 Codex calls, <=240 calls/7M tokens/4h, $(date +%H:%M)" \
      > runs/box.lock/holder
  status=0
  runs/model-tiers-20260922/runtime/Scripts/python.exe \
      research/quality-measurement/model_tiers_comparison.py run || status=$?
  if grep -q '^model-tiers-20260922:' runs/box.lock/holder 2>/dev/null; then
    rm -f runs/box.lock/holder && rmdir runs/box.lock
  fi
  exit "$status"
)
```

Announce the start and the end. The holder **must** begin `model-tiers-20260922:` or `run`
refuses, and it re-checks the lock before every call. Do not wrap the run in `timeout`, and run
nothing CPU-heavy beside it. `run` refuses `LITHARNESS_ENV=test`.

`run` verifies the interpreter, every frozen byte and pinned tree, the commit, the push, the
pinned binary (every file hashed) and the lock, and refuses if any earlier call halted; appends a
`started` line to `ledger.jsonl`; then, for each planned unit in order, checks the ceilings (with
that role's worst case), the pinned Codex folder's stat, the lock, the frozen bytes and the whole
pinned source tree, appends a `dispatch` line, makes the call, writes the receipt under
`runs/model-tiers-20260922/calls/` (never overwritten) and appends a `call` line. The live log
names each unit's status, tokens and wall time, never an agreement or a verdict. A transport
failure leaves the unit for a second pass; three in a row stop the run. An answer served on
another model, effort, CLI version, mode or interpreter, or without the isolation flags, halts
it, and **a halted registration buys nothing more**: every later `run` refuses, and a re-run is a
new registration.

| exit | meaning | next |
| --- | --- | --- |
| 0 | every unit answered | step 4 |
| 2 | stopped: a ceiling, the transport circuit, a halt, or units that never answered | read the `finished` line's `stop` and `missing`, then resume (not after a halt) or decide |
| other | refused before buying, or an error (the `finished` line records it) | read the message; fix nothing in the frozen files |

**Resume** by running the same block again: answered units are never bought again, a unit is
dispatched at most twice in all (a second time only after a transport failure or an interrupted
dispatch), and the ceilings are cumulative from the ledger. A usage limit means waiting for the
subscription window and resuming on Codex; it never means switching this arm to Claude.

**If the run process is killed**, the ledger keeps every attempt (a `dispatch` line without its
`call` line is an interrupted attempt, charged its role's reservation). Confirm the PID in the
last `started` line has ended (`powershell -NoProfile -Command "Get-Process -Id <pid>"` must
fail; stop owned processes by PID in PowerShell and verify, `pkill -f` has returned success
without stopping anything), release the lock only if its holder begins `model-tiers-20260922:`,
then resume, or record that no resume will follow:
`uv run python research/quality-measurement/model_tiers_comparison.py close`.

**Nobody computes an agreement or reads a summary before step 4.**

## 4. Analyse, once

```bash
runs/model-tiers-20260922/runtime/Scripts/python.exe \
    research/quality-measurement/model_tiers_comparison.py analyse
uv run python research/quality-measurement/epistemic_governance.py \
    research/quality-measurement/model-tiers-20260922/claim.json
```

`analyse` makes no call and needs no lock, but refuses outside the pinned runtime, while
`runs/box.lock` names this arm, while the last invocation has no finished line, and once
`results.json` exists. It verifies the frozen bytes and the pinned trees and that this arm's
files are committed as registered (not the push: `run` required it before anything was bought),
verifies every answer's receipt (hash, request digest, served model, effort, version, isolation,
the seed bridge's interpreter) and refuses if any kept answer is a transport failure. For each
seed it copies the post-seed store twice and runs the pinned runtime's CLI offline on the
copies: `world check --json`, `world accept`, `world check --json` again; the seed stores
themselves are never modified. It writes, in this order, the transport block, both summary
blocks (validators, settlement, agreement, the field table beside the control, descriptive prose
counts, tokens), the seed screen, the decisions and their licence, into `results.json` (numbers
and counts only, exclusive create), writes the ids and per-unit detail to the ignored
`runs/model-tiers-20260922/analysis/analysis.json`, and moves `claim.json` to **observed**.

Commit `ledger.jsonl`, `results.json` and `claim.json`. Receipts, inputs, stores, the pinned
source, runtime and Codex copy, and the detail file stay under ignored `runs/` (they hold
generated prose or binaries). The findings are written by review against `PREREG.md`, not by the
runner; any promotion past OBSERVED, any proposal to the operator and any stage-0 entry are that
review's acts. A summary proposal covers `LITHARNESS_PROVIDER=codex` only: enacting it needs a
Claude arm on the same requests or a per-provider role map first, then the operator's agreement,
in a separate change that `docs/model-policy.md` records.
