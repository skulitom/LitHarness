# Amendment 1: arm `milder-v4` is re-bought in full as `milder-v4a`, through a transport that runs outside the repository

**Written 2026-09-22, about 22:30, after milder-v4's second invocation bought nothing and before
any cell of `milder-v4a` is bought.** `PREREG.md`, `RUNBOOK.md`, `ATTAINABILITY.md`, the power
record, `cost_that_bites_milder.py` and `tests/test_cost_that_bites_milder.py` are not edited.
This file, `rebuy.py` beside it and `tests/test_cost_that_bites_milder_rebuy.py` are the
amendment. `registration-v4a.json` records it as data, and `claim-v4a.json` is its claim.

## What happened

| | when | what the ledger records |
| --- | --- | --- |
| invocation 1 | 21:29 to 22:10 | both probes answered `NONE`; 70 of 360 sessions checkpointed; 544 arm calls plus 2 probe calls, 21,417,525 tokens, $19.74 equivalent; stopped by the transport circuit after 5 calls that obtained no answer |
| invocation 2 | 22:11 | the git probe answered `GIT_CONTEXT_LEAKED`; nothing bought; 2 probe calls |
| both | | **548 calls, 21,502,130 tokens, $19.77 equivalent, 2,443.6 s**; 539 cached answers |

The coordinator then measured the leak outside any registered run. The pinned copy
(`claude` 2.1.280) ran with `elicit`'s exact argv from a scratch git repository that held an
untracked file named `GIT_CONTEXT_LEAKED`. The model returned that filename in 2 of 5 calls.
Without `--exclude-dynamic-system-prompt-sections` it returned it in 1 of 5. It returned the
working-directory path in about 2 of 5 calls either way. The CLI's help says that flag moves
the per-machine sections (working directory, environment, memory paths, git status) into the
first user message, and that it is ignored with `--system-prompt`. The measurement says those
sections reach the model regardless.

**The cause is the working directory.** `elicit._call_cli` passed no `cwd`, so every call ran
where the process stood. For this arm that was the repository root: the RUNBOOK runs it from
`C:/DEV/LitHarness`, and the PREREG says so. Each of milder-v4's calls could therefore carry
the repository's git status (branch, changed and untracked paths, recent commit subjects) and
its path, intermittently. Invocation 1's passing probes are no evidence that its calls were
clean. At 1 to 2 leaks in 5, a single probe passes 60% to 80% of the time when the context is
leaking. Whether any of the 539 answers saw the repository's status cannot be known.

**Why the five failures at 22:10 have no cause on record.** `elicit` kept 60 characters of the
first line of the failure. When stderr is empty that line is the JSON envelope, whose leading
keys are the same on every call. So all five reasons read
`cli_error:rc=1:{"duration_api_ms":0,"stop_reason":"stop_sequence","session_`. The truncation
is in `elicit.py` (`_CLI_STDERR_CHARS`), not in the frozen runner. The runner copies elicit's
reason into `failure_reasons` and each session's outcome verbatim. The runner's only 80-character
cut is the probe answer text in the ledger (`cost_that_bites_milder.py`, `run`). That file is
frozen and is not edited; this arm's probe log keeps each probe's full record instead. Invocation
2's two probe calls at 22:11 obtained answers, so the failures were not a lasting outage.

## The fix, in `research/quality-measurement/elicit.py`

- **Every `claude -p` call runs in a fresh, empty temporary directory** (`elicit-cli-*` under
  `%TEMP%`), and the call is refused before any process starts if a `.git` entry sits at that
  directory or any of its ancestors. The directory is removed after the call. This is the
  pattern `src/litharness/providers/cli.py` has used for tool-free completions since 2026-09-08.
- **No git location variable reaches the child.** `GIT_DIR`, `GIT_WORK_TREE` and the other
  variables that name a repository outright would hand the CLI's own `git` a repository from
  the empty directory, so the child's environment goes without them. When none is set, as on
  every run so far, the child inherits the environment unchanged.
- **Nothing sent changes.** The argv, stdin and cache key are byte-identical to the unfixed
  module's. `tests/test_elicit_cli_workdir.py` pins all three against values computed on the
  unfixed module, and a record cached under the old key replays without a call. The request
  identity against v2's cache is re-run at `prepare` (below).
- **What the reader sees does change, so a pre-fix cache is replayed and never extended.** The
  key cannot tell an answer bought in the repository root from one bought after the fix, so a
  partly bought arm resumed through the fixed module would pool the two contexts under the same
  keys. Every answer bought from now on carries `"cli_workdir": "isolated-2026-09-22"` in its
  record (not in its key), and a CLI call is refused before any process starts while its cache
  holds an answer without it. Replaying such a cache, as a finished arm's analysis does, is
  still allowed. This arm's cache is fresh, so every record in it carries the mark; the
  sim-readership backtest's paused stage (c) is the case this closes, since its cache holds
  pre-fix answers.
- **A failed call keeps its cause.** The reason is still a bounded `cli_error:...` Counter key,
  and when stderr is silent it now carries the envelope's own cause (its API status, a subtype
  other than success, its `error` or `errors` text, and its `result` text only when the envelope
  is an error, so a success envelope's answer never lands in the ledger or the live log)
  instead of its first keys. The first 2,000 characters of stdout and of stderr are kept in the
  reader's `failure_details`, and in `failures-milder-v4a.jsonl` for this arm. A failure is
  still never cached (§235).

Because `elicit.py` is content-addressed in milder-v4's registration, the frozen runner now
refuses to verify milder-v4. Its `run` and `analyse` stop at `verify` with
`changed frozen file: research/quality-measurement/elicit.py`. Its `prepare` already refuses,
because cells were bought, and its `close` refuses because its last invocation finished. That
is the mechanical form of "never read".

## What this amendment decides

**(a) milder-v4's purchase is contaminated, preserved and never read.** Its `registration.json`,
`claim.json`, `raw-milder-v4.jsonl` and `runs-milder-v4.jsonl` are committed exactly as they
stand. `registration-v4a.json` content-addresses all four and records the counts above under
`amendment.contaminated`. The frozen `verify` refuses a run or reading of milder-v4a if any of
the four changes. No reading, share or summary of the 539 cached answers is computed, printed
or cited, now or later. milder-v4's claim stays REGISTERED and never moves. `rebuy.py` refuses to
register if a milder-v4 reading exists, or if milder-v4's last invocation has no finished line.

**(b) The arm is re-bought in full, all 360 sessions, as `milder-v4a`.** It has a fresh cache
(`raw-milder-v4a.jsonl`), a fresh ledger (`runs-milder-v4a.jsonl`), its own result
(`results-milder-v4a.json`) and its own claim (`claim-v4a.json`, id
`cost-that-bites.milder-v4a.claude`). Nothing from milder-v4 is loaded into it.

- **The same design:** dose, statistic, decision table, licence, seeds, texts, sham, seat,
  competitors, replicate-major order, workers, circuit, reservations and ledger rules. `prepare`
  builds the registration with the frozen `build_registration` and refuses unless it equals
  milder-v4's field by field. That covers the pre-registration (arm aside), all 360 cells with
  their targets, seeds and dose metrics, the stores and texts, the reader (model, transport,
  effort, binary hash and version, hardening, disclosed changes), the request-identity result,
  and every registered source's bytes except `elicit.py`, which must differ.
- **The same ceilings, applied to the new run from zero:** 4,400 calls, 190 million reported
  tokens, $150 equivalent and 8 hours. milder-v4 already spent 548 calls, 21.5 million tokens,
  $19.77 and 41 minutes. The combined worst case is therefore 4,948 calls, 211.5 million tokens,
  $169.77 and 8 h 41 min. At the power record's expected rates the new run costs about 2,930
  calls and $100, which makes about $120 across both arms. **That worst case is above the
  envelope the PREREG registered for this question** (4,400 calls, $150 equivalent, 8 hours).
  It is a spend change, and it stands only with the operator's explicit sign-off, recorded when
  this amendment is committed. **Signed off 2026-09-22, about 23:55:** asked whether the
  combined worst case of $169.77 / 4,948 calls / 8 h 41 min could exceed the registered
  envelope, the operator chose "Approve up to $170". Lowering this arm's ceilings to fit the old
  envelope is not offered: the ceilings are part of the registered pre-registration, and
  `prepare` refuses any registration whose design differs from milder-v4's.
- **The same binary.** The reader is milder-v4's pinned, hash-checked copy
  (`runs/cost-that-bites-milder-20260922/milder-v4/bin/0e4195524b73eb77/claude.exe`,
  `2.1.280 (Claude Code)`). `prepare` checks its hash and version. The frozen `pin_cli` copies it
  once into `runs/cost-that-bites-milder-20260922/milder-v4a/bin/0e4195524b73eb77/` and checks it
  on every invocation. **Do not delete milder-v4's copy before milder-v4a's first run has pinned
  its own.**
- **Isolation probes at the start of every invocation, the git probe three times:** `claude_md`
  once, then `git_status`, `git_status_2` and `git_status_3`. That is four calls per invocation,
  counted toward the ceilings. Nothing is bought unless all four answers contain `NONE` and none
  carries its marker, the frozen rule. **What the probes can and cannot show.** With the fix,
  the marker `CLAUDE.md` and the scratch repository are where the *process* stands, and the CLI
  always runs in its own empty directory, so it can never run in a probe directory. The probes
  are therefore a regression check of the pinned transport's working-directory fix, a fix the
  registration already pins by hash and `tests/test_elicit_cli_workdir.py` pins by test. If
  that fix were undone and the CLI inherited the process's directory again, three git probes
  would all still pass 22% to 51% of the time at the measured rate. **They prove nothing about
  the repository's status.** Repository context reaching the reader by any other channel
  would describe the repository root, which the scratch repository's marker cannot detect,
  and with the fix in place a failure can only come from an answer that echoes the probe's own
  `GIT_CONTEXT_` prefix. Each resume runs them again. Every probe's full record is appended to
  `probes-milder-v4a.jsonl`, because the ledger keeps 80 characters.

**(c) The request-identity check against v2's cache still holds, and is re-run.** `prepare`
replays this arm's 120 intact and sham sessions at replicates 0 to 2 from v2's committed
`raw-v2.jsonl` through the frozen replay-only reader. It refuses unless all 120 replay and
reproduce v2's committed book means, and unless the result equals milder-v4's (120 of 120, a
largest difference of 0.0). The fix changes no request byte, so this is the expected outcome.

**(d) Nothing else changes.** The differences are labels and records:

- the labels: the arm id, the feed-id tag `ctbm4a` (so the frozen foreign-record check refuses
  any milder-v4 record copied into the new cache), and the registration, claim and claim-id
  names;
- the three records added: the probe log, the failure log and the amendment block;
- the probe schedule above.

The live log still prints no target share, and `analyse` remains the only reader of the cache.

## Disclosed, and not controlled by this amendment

- **v2 and v3 ran through the same unfixed transport from the repository root.** Their readers
  may therefore have seen the repository's git status intermittently too. That was never
  probed, and it cannot be now. The request-identity check proves this arm's requests are v2's,
  byte for byte. It cannot prove v2's reader context was free of repository status. So
  milder-v4a's reader context is, if anything, cleaner than §230's. This adds a clause to
  "Is it still §230's reader?": each §230 clause stays conditional, and the drift diagnostic
  still decides nothing.
- **The CLI still adds per-machine sections and tool definitions.** The sections now describe
  an empty temporary directory that is not a repository. Removing the tool definitions
  (`--tools ""`) or the flag would change the reader's argv, so neither is done here.
- **The CLAUDE.md probe no longer tests the §109 flags directly.** The CLI's own directory is
  now always empty, so a marker `CLAUDE.md` can only stand where the process stands. The flags
  are unchanged. What they exclude from the CLI's own directory and its ancestors is exercised
  by the opt-in live test in `tests/test_providers.py`, on the production argv, not by this arm.
- **The child inherits the rest of the launching process's environment.** That includes the
  `CLAUDE_CODE_*` and `CLAUDECODE` variables a run carries when it is launched from inside a
  Claude Code session. Some of them concern authentication and session plumbing, so stripping
  them would change how the reader is reached, with no call to show what else it changes. The
  RUNBOOK launches the arm from Git Bash; what else those variables do to a `-p` call is
  unmeasured.
- **Auto memory is not switched off in the hardening.** The CLI names its project memory folder
  after the working directory, so a fresh temporary directory selects no existing folder. This
  is read from the record and was not measured by a call.
- The served snapshot is still unobserved, as in the PREREG.

## Runbook

Git Bash from `C:/DEV/LitHarness`. The box rules are the frozen RUNBOOK's.

```bash
# 0. Free checks, no call.
uv run pytest tests/test_cost_that_bites_milder_rebuy.py tests/test_cost_that_bites_milder.py \
    tests/test_elicit_cli_workdir.py tests/test_elicit_failures.py -n 0 -p no:randomly
uv run python research/quality-measurement/cost_that_bites_milder.py plan   # the same plan

# 1. Register (no model call; it runs the pinned copy's --version).
uv run python research/quality-measurement/cost-that-bites-milder-20260922/rebuy.py prepare
uv run python research/quality-measurement/epistemic_governance.py \
    research/quality-measurement/cost-that-bites-milder-20260922/claim-v4a.json

# 2. Commit and push, together: elicit.py and its test, this file, rebuy.py and its test,
#    registration-v4a.json, claim-v4a.json, and milder-v4's raw-milder-v4.jsonl and
#    runs-milder-v4.jsonl exactly as they stand. `run` refuses until all are at a pushed HEAD.
```

**3. Guard and go** with the frozen RUNBOOK's step-3 block, changed in two lines. The holder
reads `cost-that-bites-milder-20260922: milder-v4a, 360 sessions, <=4400 calls/190M tokens/$150/8h, HH:MM`,
and the run line is
`uv run python research/quality-measurement/cost-that-bites-milder-20260922/rebuy.py run`.
Exit codes, resume, kill and `close` are as in the frozen RUNBOOK, with `rebuy.py` in place of
the runner.

**4. Analyse, once:**
`uv run python research/quality-measurement/cost-that-bites-milder-20260922/rebuy.py analyse`.
Then commit `raw-milder-v4a.jsonl`, `runs-milder-v4a.jsonl`, `results-milder-v4a.json`,
`claim-v4a.json`, and `failures-milder-v4a.jsonl` and `probes-milder-v4a.jsonl`. The findings
and any promotion are review's act, against the PREREG's table.
