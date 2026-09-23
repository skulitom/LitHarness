# Pre-registration: may scene summaries move tier on Codex? (`model-tiers.v1`)

**Written 2026-09-22, before any call of this comparison; revised the same day after review,
before `prepare`.** `docs/model-policy.md` ("Rules") and stage-0 §256 route every role to the
strong tier and name three candidates: scene summaries and title availability checks on `basic`,
the Architect's world keeping on `standard`. A candidate moves only after "a registered
comparison passes and the operator agrees", and the comparison is to "replay recorded requests
from a recent run on the candidate model and compare in code". This is that comparison for what
the full-book trial recorded. This file owns the design and the reading. `RUNBOOK.md` owns the
commands. The frozen constants and every computation are in
`research/quality-measurement/model_tiers_comparison.py`; its tests are
`tests/test_model_tiers_comparison.py`.

## The claim, and its state

> **On the Codex provider only, against fresh `gpt-6-astra` controls on one pinned binary and one
> pinned source, `gpt-6-luna` at medium or high effort summarises the full-book trial's 24 scenes,
> under the recorded wording and under the current (§255) wording, with validator outcomes,
> settled-promise sets and structured-field agreement no worse than the control beyond the
> registered margins. One book, computed in code. Two `gpt-6-sol` seeds of that trial's world
> are a screen for gross failure and license nothing.**

State: **REGISTERED** (`claim.json`). By `EPISTEMIC_GOVERNANCE.md` that becomes true at the
commit and push the RUNBOOK requires before `run`, and `run` refuses until then. `analyse` can
move it to OBSERVED. SUPPORTED or REFUTED is a reviewed act against the rule below, never the
runner's. **A summary pass licenses proposing `mechanical` on `basic` to the operator, for
`LITHARNESS_PROVIDER=codex` only, and nothing more.** The review recommends; it never changes
routing (the policy's own rule).

## What is compared, and why this way

### Scene summaries (profile `mechanical`, `application/summarize.py`), in two blocks

The trial recorded every call as `runs/full-book-trial-20260919/calls/NNNN-A1.json` with
`profile`, `request` (the `dataclasses.asdict` of the `CompletionRequest`), `result` (text,
parsed answer, usage, wall time and the adapter's raw attempt, including the submitted prompt,
system, schema, native schema and argv) and a receipt chain. Of its 129 calls, 24 are
`mechanical`, one per chapter (`drain1` to `drain24`), all `completed`, all on `gpt-6-astra` at
medium effort, 194,725 recorded tokens in all (mean 8,114; 17.1 s mean wall).

What was checked on 2026-09-22 by reading those files and a scratch copy of the trial store,
before this registration, and what `prepare` re-checks and freezes:

- every recorded request rebuilds through `CompletionRequest` and serialises back
  byte-identically (canonical JSON), 24 of 24;
- the prompt and system the adapter submitted equal the rebuilt request's prompt and
  `effective_system`, 24 of 24;
- the adapter's native schema equals the pinned source's `prepare_codex_schema` of the same
  schema **up to the order of `required` members** only (it sorts them): semantically identical,
  not byte-identical. Disclosed below;
- each prompt is `"The scene:\n\n"` + the accepted scene text (by content hash in the store) +
  the pre-§255 ledger block, and none carries an open-thread block;
- the store's accepted summary row equals `flatten` of the recorded parsed answer, and its
  stored `paid_matched`/`paid_unmatched` equal the handler rule recomputed from that answer and
  the subjects the prompt listed, 24 of 24. The accepted record is therefore available, and it
  is the recorded parsed answer;
- every subject a recorded ledger lists has one row in the trial's `promises` table (stored
  normalised, one row per subject; the final store holds 52, none with a payoff window), and
  those rows, rendered in the pre-§255 line format, reproduce all 204 recorded ledger lines of
  the 23 requests that carry one exactly (a string check on 2026-09-22; a window set and later
  cleared would not show in the final store, which is one thing the rebuild below proves
  instead).

**The input control: every request rebuilt whole.** For each of the 24, `prepare` takes the
scene text and the trial's own `promises` rows under the subjects the recorded ledger listed, in
the order it listed them, marked open as they were at the call, and builds the request through
the summariser's own code (`render_summary_prompt` and the handler's `CompletionRequest`
fields, mode `render-summaries`) under the trial's frozen runtime
(`runs/full-book-trial-20260919/runtimes/A`, source 6c3bda4). **The whole request, as canonical
JSON, must be byte-identical to the record, 24 of 24**, or nothing is registered. That proves the
rows, their order, the scene texts and the builder are what the trial sent.

**Block 1, recorded wording.** Each unit sends the recorded request, model unset; the cell's model
and effort are the adapter's settings
(`CodexCliProvider(model=..., reasoning_effort="medium", model_efforts={model: effort})`), so the
three cells differ only in `--model` and `model_reasoning_effort`, and every request digest
equals the record's. Agreement is read against the accepted record, which exists only for this
wording. Codex does not honour the request's greedy sampler, so the strong model itself does not
reproduce its own record: `gpt-6-astra` at medium, run fresh on the same binary in the same
interleaved order, is the control, and its agreement with the record is the floor every
candidate is read against, scene by scene.

**Block 2, current wording.** Stage-0 §255 rewrote the summary prompt after the trial: OPEN,
PROMISES_OPENED and PROMISES_PAID, the ledger heading and the ledger line format (HEAD's own
comment: "neither branch matches the text summaries used before §255"), and §255 says whether
subjects are still copied cleanly is unmeasured. A licence for production's summariser has to
test the prompt production sends, so the same rows are rendered through the same builder under
the pinned registration source (below), giving the request production would send for that scene
and that ledger today. `prepare` checks each: it opens on the scene, lists exactly the recorded
subjects in HEAD's format, carries no thread block, leaves the model unset, round-trips, and
differs from the recorded request in `system` and `prompt` only. No accepted record exists for
this wording, so the block runs **two** `gpt-6-astra` replicates: the first (`astra-medium`) is
the reference every other answer is scored against, the second (`astra-medium-2`) is the floor,
and each Luna cell's agreement with the reference is read against the second Astra's.

### The Architect's seed (`architect.seed.*`, `application/world_agent.py`): a screen

The trial's seed (call 5, `architect.seed.v8`, 291,247 tokens of which 238k cached, 210 s) ran
through the tool bridge, so replaying it needs the store as it stood before the call.
`runs/full-book-trial-20260919/runner-stop/book.db` is that store: the trial's own preserved
snapshot after `new` and before `seed` (0 state records; 2 plan items, the same premise and
concept as the final store). `prepare` rebuilds the seed request through the production CLI
(`architect seed` with the trial's own global arguments, stopped at the completion boundary with
billing disabled):

- under the frozen runtime, from a copy of that snapshot, it must equal the recorded v8 request
  byte for byte. This is the input control: it proves the snapshot, its concept and listing and
  the arguments are the trial's;
- under the pinned runtime, from a template copy it migrated, it gives the request the screen
  sends (`architect.seed.v9` since §255: `LIVED_WORLD` and the `stands_at` sentence are added).

Both arms send that request. Each replicate runs into its own fresh copy of the template; a store
is never reused. **Two replicates a side can show a gross failure and cannot establish
reliability** (a Sol clean 70% of the time looks clean in both of two tries 49% of the time), so
**no outcome of the seed proposes anything**. A seed tier change needs its own registration with
enough replicates, and grow.

**Grow is deferred.** It is 7 of the trial's 8 Architect calls and 1,304,412 of its 1,595,659
Architect tokens, and a grow replay needs the store as it stood before each grow call. Neither
`steps/` (step receipts: arguments, stdout, before/after metadata with scene hashes and job
counts) nor `sources/` (the frozen source archives) holds a store. The only snapshots are
`runner-stop/book.db` (pre-seed), `arc2-stop/book.db` (after `accept-grow6` and the arc-2
outline failure, which is no grow's starting point), `readout-frozen/book.db` and the final store.
A follow-up is sketched at the end.

**Title availability checks are deferred.** No `title.availability.v0` request exists in the
trial's calls or in any `runs/*/calls/` folder, and the role searches the web, whose answers
are not stationary, so a replay would not hold its input fixed.

## What runs, and on what

**The source is pinned at registration.** `prepare` requires `src/` and `migrations/` clean
against HEAD, then `git archive`s HEAD's `src/`, `migrations/`, `pyproject.toml` and `uv.lock`
into `runs/model-tiers-20260922/source/` and builds `runs/model-tiers-20260922/runtime/`, a venv
whose `.pth` puts the archived `src/` first and the shared environment's site-packages (the
third-party packages; a plain path entry does not process the editable install's `.pth`) after
it: the full-book trial's `runtimes/A` pattern. A probe must import `litharness` from the archive.
`run` and `analyse` refuse unless they execute under that runtime, so the adapter, the tool
bridge (which starts `sys.executable -m litharness`) and the reading's world CLI all run the
archived source; a seed's answer is kept only when its bridge ran on that interpreter. Before
every call the runner hashes the archive's whole tree, the `litharness_contracts` package the
runtime imports, and the venv's own files, and halts on any change, addition or removal. Nothing
reads the live checkout's `src/` after `prepare`, so commits to `src/`, `migrations/` or
`uv.lock` made after registration (four touched `src/` on 2026-09-22 alone) neither change what
runs nor block a resume or the reading.

**The binary is pinned at registration.** `prepare` copies the registered Codex bin folder
whole (the executable sits beside its helpers, `codex-command-runner.exe`,
`codex-code-mode-host.exe`, `codex-windows-sandbox-setup.exe`) into
`runs/model-tiers-20260922/codex/<folder>/`, requires every file to hash to the original, and
registers the copy: the executable's path, sha256 and `--version`, and every file's hash. `run`
hashes the whole copy at the start of each invocation and checks every file's size and mtime
before every call; an update of the operator's app changes nothing the arm runs.

## Cells, order and transport

| block | cell | model | effort | arm |
| --- | --- | --- | --- | --- |
| recorded | `astra-medium` | `gpt-6-astra` | medium | control (floor against the record) |
| recorded | `luna-medium` | `gpt-6-luna` | medium | candidate |
| recorded | `luna-high` | `gpt-6-luna` | high | candidate (OpenAI's recommended start) |
| current | `astra-medium` | `gpt-6-astra` | medium | reference |
| current | `astra-medium-2` | `gpt-6-astra` | medium | floor |
| current | `luna-medium` | `gpt-6-luna` | medium | candidate |
| current | `luna-high` | `gpt-6-luna` | high | candidate |
| seed | `astra-medium` | `gpt-6-astra` | medium | control (screen) |
| seed | `sol-medium` | `gpt-6-sol` | medium | screened |

Per scene, in scene order, the recorded block's three cells (rotated left by the scene's index
mod 3) then the current block's four (rotated left by the index mod 4), so no cell always goes
first: 72 + 96 = 168 summary units. Then 4 seed units in ABBA order (Astra, Sol, Sol, Astra):
172 planned calls. Every call goes through `providers/codex_cli.CodexCliProvider`, never the
Claude CLI, on the pinned binary. After every answer the runner checks, from the adapter's own
receipt, the requested model, the effort, the CLI version, the argv's `--model` and effort, the
isolation flags (`--ignore-user-config`, `--ignore-rules`, `--ephemeral`,
`--skip-git-repo-check`, `project_doc_max_bytes=0`), the mode (completion for summaries, bridge
for seeds) and, for seeds, that the bridge's MCP server ran on this process's interpreter; any
mismatch halts the run and the answer is not kept.

## Outcomes, computed in code

No model rates, ranks or chooses anything here. No prose field is scored, by a model or for
quality.

### Summaries, per scene and cell

**Validator families** (the pipeline's own functions, `application/summarize.py`,
`domain/promises.py`, `domain/extraction.py`):

- **V1 conformance**: the adapter's parse (`parse_schema_payload`; a failure is what production
  retries), the registered `SUMMARY_SCHEMA` validated in full (Draft 2020-12, `jsonschema`:
  nested required fields, the kind enum, no extra properties), and nothing the handler's
  tolerant reads would silently drop (a delta object `extract_delta` rejects, an opened promise
  without subject or description, a kind `normalise_kind` does not admit, a paid entry without
  a subject).
- **V2 evidence**: every non-empty `evidence_quote` (opened and paid) is located exactly once in
  the scene (`exact_evidence_span`). The record locates 102 of 102.
- **V3 clean copy** (current block only, over the 23 scenes whose prompt listed a ledger): no
  paid subject off the list the prompt showed (the handler's `paid_unmatched` is empty). This is
  the measure §255 left open: an unmatched payment on a listed ledger is a subject not copied
  as the list writes it, whose payment the ledger then loses, or a promise opened and paid in
  one scene. The record has none in those 23 scenes; scene 1 had no list, so any payment there is
  unmatched by construction and it is left out.

An unusable answer (the model's own act: an unpermitted activity, a refusal) and an unparsed
answer fail every family.

**The settled-promise flag**: whether the set of listed subjects the answer pays (the handler's
`paid_matched`, keyed by `normalise_subject`) equals the reference's. This is which ledger rows
the scene would settle. The reference is the accepted record in the recorded block and the
reference Astra in the current block.

**The composite**: the mean of three agreement components with the reference, each in [0, 1];
an unparsed answer scores 0:

1. `delta_who`: the delta's `who` equal after normalisation (NFKC, casefold, punctuation to
   spaces), or both null; a delta present on one side only scores 0;
2. `opened_count`: 1 - |n - n_ref| / max(n, n_ref, 1) over promises the handler would record;
3. `opened_kinds`: multiset overlap of `normalise_kind` over those promises (1 when both empty).

Two components the first draft averaged in are kept out. `paid_matched_set` writes the ledger, so
it gets its own exact test (the settlement test) rather than a fifth of a mean; averaged, a
candidate could lose the settled set in about 20 to 30 points more scenes than Astra and pass.
`delta_presence` is near-constant (the record has a delta in 24 of 24 scenes) and `delta_who`
already scores a delta present on one side only as 0. Both are still computed and reported.

**Field table, reported and deciding nothing**: for every structured field (delta null-ness,
`who`, `what_changed`, `from`, `to`; opened count, subjects, descriptions, kinds, due hints,
quotes; paid count, subjects, matched set, quotes), exact and normalised agreement with the
reference, each cell beside its block's control, and, in the recorded block, each candidate's
agreement with Astra-fresh.

**Descriptive only**: prose words per field and in total (the prompt asks for about 60); whether
the scene's declared people (protagonist and cast display names from the trial's canon, where
the scene prints them) and its whole numbers appear in the prose fields; paid subjects the
ledger did not list; parse failures that would retry; tokens by kind; wall time.

### The seed screen, per replicate

On copies of the post-seed store, through the pinned runtime's CLI offline: `world check --json`
(ok, complaints by kind with subjects and values masked, `would_not_finish`,
`will_not_resolve`, unmanifested and the rest of its payload), `world accept` without `--force`
(exit and refusal kinds) and `world check` again. On the accepted copy, the domain's own
readers: protagonists, systems, grants each system governs, ladder lengths, cast, whether a
status sheet is declared and whether the protagonist stands on a ladder (reported only: the
trial's pre-§255 concept states no counted start, and v9 declares a `stands_at` only when the
concept does), records by predicate and authority. From the bridge's receipts: commands by verb,
bridge errors by kind, nonzero exits by verb, records declared and declarations refused. Tokens
and wall time.

A replicate is **clean** when it answered, the pre-accept check is ok, `world accept` exits 0,
the post-accept check is ok and nothing would not finish.

**Structural agreement** with the trial's accepted seed world: protagonists equal, system count
equal, ladder lengths equal, grant counts equal, cast Jaccard, status sheet equal; their mean.
The trial's seed world is its canon declared before `accept-seed` finished (acceptance promotes
in place and only upward), and `prepare` refuses unless that reconstruction reproduces the
accept step's own report: canon declared before it equals "accepted 196" plus "2 minted" (198),
and everything declared before it equals the 200 proposals plus the 2 minted (202). A proposal
left pending and promoted by a later accept, or a retracted row, would break one of the two. The
trial's world answered the v8 request and both arms answer v9, so this is read only as
candidate against control.

## The decision rule, fixed before spend

### Summaries, each candidate cell against the controls, paired by scene

Two candidate cells are tried, so each is tested at one-sided alpha = 0.05 / 2 = **0.025**
(BRIEF.md §6 item 4). A candidate needs an answer for all 24 scenes in both blocks, and so do the
controls (Astra-fresh; the reference and the floor); otherwise its verdict is **INCOMPLETE** and
nothing else is read.

The tests, per block:

| block | test | candidate side | control side |
| --- | --- | --- | --- |
| recorded | V1, V2 | candidate | Astra-fresh |
| recorded | settlement | candidate's settled set equals the record's | Astra-fresh's equals the record's |
| recorded | agreement | candidate's composite with the record | Astra-fresh's composite with the record |
| current | V1, V2 | candidate | reference Astra |
| current | V3 clean copy (23 scenes) | candidate | reference Astra |
| current | settlement | candidate's settled set equals the reference's | the floor Astra's equals the reference's |
| current | agreement | candidate's composite with the reference | the floor's composite with the reference |

- **Validators (V1, V2, V3).** b = scenes the candidate fails and the control passes, c = the
  reverse. The excess failure rate p10 - p01 is at most p10, so **pass** when the exact
  (Clopper-Pearson) one-sided upper bound on b/n at 0.025 is at most the margin **0.15**;
  **fail** when the lower bound on b/n minus the upper bound on c/n, each at 0.0125, exceeds
  0.15; otherwise inconclusive.
- **Settlement (exact, paired).** The flag is noisy on the control side too (Codex does not
  sample greedily), so the bound is on the difference. b = scenes where only the control's set
  agrees, c = where only the candidate's does; with probability at least 0.975, p10 is under the
  exact upper bound on b/24 and p01 over the exact lower bound on c/24, each at 0.0125. **Pass**
  when that upper bound less that lower bound is at most **0.25**; **fail** when the lower bound
  on b/24 less the upper bound on c/24 exceeds 0.25; otherwise inconclusive. In production terms
  the margin is **6 of every 24 scenes**: a pass bounds the candidate at settling a different set
  of listed promises from the reference (leaving open one the reference settled, or settling one
  it left open) in at most 6 more scenes per 24 than the control does.
- **Agreement.** d = candidate composite - control composite per scene. With the one-sided t
  quantile t(0.975, 23) = 2.0687: **pass** when mean(d) - t sd(d)/sqrt(24) >= **-0.10**;
  **fail** when mean(d) + t sd(d)/sqrt(24) < -0.10; otherwise inconclusive. In production terms
  -0.10 on the mean of three components is 0.30 of one component per scene: for example the
  change credited to a different character, or present on one side only, in about 7 more of
  every 24 scenes than the control, with nothing else differing; or the count of recorded opened
  promises off by one of three in every scene.
- **A control that did not parse leaves no floor.** If Astra-fresh (recorded block), or the
  reference or the floor (current block), has no parsed answer in any scene, that block's
  settlement and agreement tests read INCONCLUSIVE rather than scoring the missing control as
  zero agreement in the candidate's favour. The validator tests still run.
- **A candidate PASSES** when all nine tests pass (an intersection-union test: no further
  division of alpha), **FAILS** when any fails, and is otherwise **INCONCLUSIVE**.
- If both candidates pass, the proposal names the one with fewer recorded tokens over both
  blocks (ties: medium, which needs no `LITHARNESS_CODEX_EFFORTS` setting). Tokens are
  reported, not credits.

### The seed screen

**NO GROSS FAILURE SEEN** when both Sol replicates are clean and Sol's mean structural agreement
is at least Astra's minus **0.25**; **FAILURE SEEN** when Sol has fewer clean replicates than
Astra; **INCOMPLETE** when any replicate of either arm has no answer; otherwise **UNCLEAR**.
None of these proposes anything.

### What each outcome licenses

| outcome | licence |
| --- | --- |
| summary candidate PASS | propose `mechanical` on `basic` (`gpt-6-luna` at that cell's effort) to the operator, **for `LITHARNESS_PROVIDER=codex` only** |
| summary candidate FAIL | no proposal; a demonstrated deficit beyond a margin, recorded |
| INCONCLUSIVE / INCOMPLETE | no proposal; more scenes or a re-run are a new registration |
| any seed screen outcome | no proposal; FAILURE SEEN is recorded against a later seed registration |

**Why Codex only, and what enacting it needs.** `ModelRouting.from_environ` applies the one
`LITHARNESS_MODEL_TIERS` role map on either provider, so setting `mechanical=basic` would also
move Claude summaries to `claude-haiku-4-5` (committed only until at least 2026-10-15), which
nothing here tested, and the policy requires every tier to stay mapped on both providers. So a
pass carries no settings string: enacting it needs either a Claude arm on these same requests or
a per-provider role map first, and either is its own change. Nothing in production moves on any
outcome. A proposal changes nothing until the operator agrees and a separate change edits
routing.

## Attainability at this n

Twenty-four scenes from one book is small. These numbers are computed from the rule, not from any
answer.

**Validators.** The upper bound for b = 0 is 1 - 0.025^(1/24) = **0.1425** at n = 24 and
**0.1482** at n = 23 (V3), under the 0.15 margin; for b = 1 it is 0.2112 and 0.2195. So a
validator family passes **only with no scene the candidate fails and the control passes**. What
that detects: a candidate whose excess failure rate is p passes a family with probability about
(1 - p)^24: 0.79 at p = 0.01, 0.62 at 0.02, 0.29 at 0.05, 0.08 at 0.10. It cannot tell 0% from
1-2%, and it certifies at most "excess failures under 14.3% at 97.5%". If both models share a
base failure rate q with independent failures, an equivalent candidate passes with probability
about (1 - q(1 - q))^24 (0.31 at q = 0.05). The record passes V1 in 24 of 24 scenes (strict
schema and handler reads, checked with this runner's own functions on 2026-09-22), V2 in 24 of
24 and V3 in 23 of 23, so q is plausibly near zero for Astra under the recorded wording; if it is
not, the outcome is inconclusive rather than a pass. **Fail** needs b >= 14 with c = 0: the
validator rule almost never demonstrates a deficit; it withholds the pass instead.

**Settlement.** Pass needs b <= 1 whatever c is, or b = 2 with c >= 5, b = 3 with c >= 7, b = 4
with c >= 9; fail needs b >= 16 with c = 0. Under a model where the control's set agrees with the
reference in a share a of scenes and the candidate's in a - deficit, independently, the
probability of a pass is:

| a (control agrees) | deficit 0 | deficit 0.10 | deficit 0.20 |
| --- | --- | --- | --- |
| 0.95 | 0.68 | 0.13 | 0.01 |
| 0.90 | 0.37 | 0.06 | 0.01 |
| 0.80 | 0.17 | 0.03 | 0.00 |
| 0.70 | 0.13 | 0.03 | 0.00 |

A deficit of 20 points in settled sets passes about 1% of the time; one of 10 points, up to 13%.
The price is that an equivalent Luna passes this test only when Astra reproduces its own settled
set in most scenes; nobody has measured how often it does on Codex (the record settles at least
one listed promise in 20 of 24 scenes, from 1 to 6 of them). In the current block the candidate
and the floor are both read against one reference, which correlates their flags and narrows the
discordance, so these numbers are if anything low there.

**Agreement.** The pass needs t sd(d)/sqrt(24) = 0.4223 sd(d) of room below the observed mean,
so an equivalent candidate (true mean difference 0) **passes more often than not only if
sd(d) < 0.237**. Probability of each verdict under a normal approximation to the bound:

| sd(d) | pass at true diff 0 | pass at -0.05 | pass at -0.10 | fail at -0.15 | fail at -0.20 | fail at -0.30 |
| --- | --- | --- | --- | --- | --- | --- |
| 0.10 | 0.998 | 0.648 | 0.019 | 0.648 | 0.998 | 1.000 |
| 0.15 | 0.884 | 0.332 | 0.019 | 0.332 | 0.884 | 1.000 |
| 0.20 | 0.648 | 0.199 | 0.019 | 0.199 | 0.648 | 0.998 |
| 0.25 | 0.457 | 0.138 | 0.019 | 0.138 | 0.457 | 0.968 |
| 0.30 | 0.332 | 0.105 | 0.019 | 0.105 | 0.332 | 0.884 |

A candidate at the margin passes about 2% of the time (the registered 2.5%). A deficit of 0.2 or
more on the composite is caught as FAIL at least two times in three when sd(d) <= 0.2; a deficit
of 0.05 is not distinguished from equivalence; and at sd(d) = 0.237 an equivalent Luna passes
half the time. sd(d) is not known before spend: no Codex re-sample of this summariser exists
(`summary_reliability.py` was never run on it).

**All nine together.** A pass needs every test to pass. If they were independent, an
equivalent candidate would pass overall with probability about 0.46 when Astra reproduces its
own settled set in 95% of scenes and sd(d) is 0.10, and about 0.11 at 90% and 0.15. **INCONCLUSIVE
is the expected outcome** and is not a failure; it says 24 scenes cannot tell. A PASS, when it
comes, bounds every deficit above at 97.5% for this book.

**The seed screen.** Two replicates detect only gross failure. A Sol whose seed is clean with
probability s looks clean in both with probability s^2: 0.81 at s = 0.9, 0.49 at 0.7, 0.25 at
0.5. FAILURE SEEN needs Sol to have fewer clean seeds than Astra in the same two tries. Neither
can establish reliability, which is why the screen licenses nothing.

## Transport failures, before any verdict

`analyse` writes the transport block first: dispatches, answers, unusable answers by kind,
transport failures by kind, re-dispatched units, interrupted dispatches, unknown usage, halts and
halted units, missing units, coverage. **A transport failure is never an answer** (stage-0 §224,
§235): a timeout, an unavailable binary, a rate limit, a garbled stream or a bridge fault
(`execution`, `timeout`, `trace`) is recorded with its receipt and the unit stays unanswered;
`analyse` refuses if any receipt kept as an answer carries one. Only the model's own act is an
unusable answer: an unpermitted activity, an architect that ran no successful world command,
bridge arguments it never recovered (`invalid_arguments`, `call_budget`), or a refusal or safety
stop **when the attempt's own JSONL shows a model turn** (a `turn.completed` event or an
`agent_message` item). On a nonzero Codex exit the adapter's refusal and safety kinds come from
matching words in stderr ("safety", "prohibited", "refusal"), which a platform or connection
error can say without any model turn, so without that evidence they are transport
(`platform_refusal`, `platform_safety`).

Each unit is dispatched at most twice. **A second attempt happens only after a transport failure
or an interrupted dispatch** (a kill, whose outcome never reached the ledger and whose paid
answer, if any, is lost), in a second pass over the plan. **A call served otherwise halts the
run, and once one has, `run` refuses**: the registration's premise (this model, effort, binary,
mode, isolation and interpreter) failed, so nothing more is bought under it, the halted unit's
receipt is kept and never read, and a re-run is a new registration. Three consecutive transport
failures stop the run. A seed attempt that failed on transport keeps its partial store as
evidence, and its re-dispatch gets a fresh copy.

## Resource ceilings

Codex reports tokens and no price, so the ceilings are calls, tokens and seconds:
**240 calls** (172 planned; the rest only re-dispatches), **7,000,000 recorded tokens**
(expected about 1.2 to 2.0 million for the summaries and 1.2 to 3.2 million for the seeds) and
**14,400 seconds** of call wall time (expected about 1.2 to 2 hours). Before every call the
runner admits it only if the used totals plus that role's worst case fit under every ceiling:
40,000 tokens and 300 s for a summary (its timeout), 1,500,000 tokens and 3,600 s for a seed (its
timeout). An attempt whose usage is unknown, or that a kill interrupted, is charged that
reservation. Totals are cumulative across invocations from the ledger.

## The box

The run holds `runs/box.lock` with a holder line starting **`model-tiers-20260922:`**; `run`
refuses otherwise and re-checks the lock before every call. It uses no GPU and runs nothing
beside it (CLAUDE.md). `analyse` and `close` refuse while the lock names this arm.

## Registration and refusal to run uncommitted

`prepare` content-addresses: the 24 recorded summary call files and the recorded seed call, the
trial store and the pre-seed snapshot, the seed and accept-seed step receipts, the frozen
runtime's interpreter, `pyvenv.cfg` and source `.pth`, the local inputs it writes (both blocks'
requests, the ledger rows, scenes and accepted records; the seed request; the migrated template
store), this runner, the PREREG, RUNBOOK and test, and the trial's registration. It records the
production commit and the git tree ids of `src/` and `migrations/` it archived, the pinned
runtime (the archive's hash, the whole archived tree, the `litharness_contracts` tree, the venv's
interpreter, `pyvenv.cfg` and `.pth`, and the probe), the pinned Codex folder (every file's hash;
the executable's path, sha256 and version), the Python and `jsonschema` versions, the
request-identity results, the seed world's counts against the accept step, and the digest of
every constant above. `docs/model-policy.md` is not frozen: the arm reads nothing from it, and
its 14-day review edits it.

`run` refuses unless it executes under the pinned runtime, every registered file and pinned tree
is byte-identical, this arm's files and `registration.json` are committed as registered, HEAD is
on a remote branch, the pinned binary hashes and reports the registered version, no call has
halted, and the lock is this arm's. `analyse` needs the pinned runtime, every registered file and
pinned tree byte-identical and this arm's files committed as registered; not the lock (it
refuses while the lock names this arm), the binary or the push (`run` required the push before
anything was bought). `claim` rewrites `claim.json` after an edit to this file or the RUNBOOK and
refuses once a registration exists (`prepare` rewrites it then).

## Disclosed differences from the trial's calls

- The binary: whichever native Codex the operator registers, pinned; the trial's calls ran
  `codex-cli 0.155.0-alpha.9.2`, and on 2026-09-22 the only installed native build reports that
  version. All cells run the same copy, so the controls absorb any change; the record does not.
- The native schema's `required` members are sorted by the pinned adapter; semantically
  identical.
- The current block's requests carry §255's wording; the recorded block's are the trial's bytes.
- The seed request is v9 (§255), not the recorded v8, in both arms.
- The production source is the registration commit's, archived, not the trial's frozen
  6c3bda4/4b35483; the frozen runtime is used only to prove the inputs rebuild. The shared
  environment's third-party packages are imported by both; `litharness_contracts` is hashed,
  `jsonschema`'s version is recorded.
- The Codex bin folder is pinned; its sibling tool folders (`rg`, `node`) are not, because the
  adapter disables every tool that would start them.
- The adapter records the requested model; Codex JSONL reports no resolved model.

## What it cannot establish

- Anything about quality. Agreement with Astra's record, or with a second Astra, is not
  correctness, and no prose field is judged.
- Any book but this one: 24 scenes and one world, one writer, one generator (BRIEF.md §6 item 5).
- The current wording against an accepted record: none exists, so that block reads a candidate
  against a second Astra, not against what production accepted.
- The ledger's feedback loop: every replayed request lists Astra's own ledger, so whether Luna
  re-copies subjects it coined itself scenes earlier (the §110 failure) is untested.
- Downstream effect: summaries feed evicted drafting context, and no chapter is drafted here.
- The Claude provider, or any role map that moves Claude summaries.
- The Architect's seed on `standard` (a screen only) and its grow, the larger share of its tokens.
- Title availability checks.
- The served model, and credits or dollars.
- Equivalence: a pass bounds a deficit at the registered margins and this n, nothing smaller.

## Follow-up for grow, not registered here

Reconstruct the store as it stood before each of the seven recorded grow calls from the final
store's append-only rows: state records declared before the call started
(`state_record_times`); authority as of then (a record canon now was canon then when it was
declared before the last `world accept` step that finished before the call, since acceptance
promotes in place and only upward); the head revision the call's step receipt names
(`before.head`; revisions are immutable); plan items and promise rows as of then. **That
authority rule holds only when nothing was promoted by a later accept or retracted since**, so
each reconstruction must first reproduce every earlier accept step's own report ("accepted N of
M ... K minted ... L left proposed"), as `read_trial` requires for the seed, and refuse
otherwise. Prove each reconstruction by replaying the recorded read-only bridge commands of that
call (the `commands_jsonl` rows before its first declaration carry exact stdout) against it byte
for byte, under the runtime that served the call (calls after 41 ran the recovery runtime,
4b35483). Then replay the seven grow requests, whose prompts do not depend on world state, on Sol
and Astra into copies, with enough replicates to bound a failure rate. That is its own
registration.
