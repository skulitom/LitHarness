# Pre-registration: a cost that bites, milder (arm `milder-v4`). Does the costed reader read a book less when two thirds of its paragraphs are reordered?

**Written 2026-09-22, before any cell of this arm is bought.** Stage-0 §230 licenses "one
further experiment, a milder manipulation" for `fcr.v0`, and no production authority. The
operator approved registering it on 2026-09-22 with **six sessions per version on the existing
twenty-book fitness shelf**. v1's, v2's and v3's registrations and findings under
`cost-that-bites/` are not edited, and no number crosses from them into this arm's reading.
What this arm takes from them is v2's design and decision table, the reader properties v2 and
v3 measured to size it, and v2's committed cache and result as the read-only inputs of one
precondition and one diagnostic (below). This file owns the design and the reading.
`ATTAINABILITY.md` owns the sizing. `RUNBOOK.md` owns the commands. The frozen constants are in
`research/quality-measurement/cost_that_bites_milder.py`.

## The claim, and its state

> **A reader whose continuing costs it something (`fcr.v0`, `claude-haiku-4-5` over `claude
> -p`) reads a fitness book in slot A less when a seeded partial shuffle reorders 65% of its
> paragraphs among themselves, beyond a whitespace sham. Tested at twenty books with six
> sessions per version.**

State: **REGISTERED** (`claim.json`). By `EPISTEMIC_GOVERNANCE.md` that state means committed
before observing, so it becomes true at the commit and push the RUNBOOK requires before `run`,
and `run` refuses until then. The arm can move it to OBSERVED. Promotion past that is a
reviewed act against the table below, never the runner's.

## Why a milder dose, and why this one

v2 and v3 found the reader pays less for a book whose paragraph order is **destroyed**, and the
effect survived a redraw of the permutation (+0.1640 and +0.1890). That result is a floor: a
whole-book shuffle is the most violent order damage the house owns. The distance between
noticing it and noticing a book that is merely worse is where every dead proxy in `BRIEF.md`
fell. This arm moves one step along that distance and no further.

**The dose is a new seeded partial shuffle at s = 0.65.** Pick `round(0.65 n)` paragraph
positions by a draw seeded from the text and the salt `cost-that-bites/shuffle/partial/0.65/<seed>`,
and give their contents a uniformly random non-identity permutation among themselves. Every
other paragraph stays in place. On the shelf this moves 64.4% of paragraphs and breaks 87.3% of
adjacent pairs, at a Kendall distance of 0.361 against the full shuffle's 0.499. It keeps every
paragraph and every word.

**How much milder it is where the reader meets it, stated before spend.** The dose is clearly
milder by paragraphs displaced (64% against 99%) and by Kendall distance (0.36 against 0.50).
Inside the reader's window it is only modestly milder: it breaks **87.4%** of the adjacent pairs
a session can see, against the full shuffle's **99.3%**, a ratio of **0.88**. So a
MOVES_WITH_ORDER here carries §230's reading a short step toward "merely worse", not most of the
way. The licence row below says so.

**The candidates weighed** (BRIEF.md §6 item 4). Every operator and strength below was computed
call-free on the shelf by the power record, and one was registered. No candidate was tried
against a reader.

| candidate | displaced | adjacencies broken in the window | why not registered |
| --- | --- | --- | --- |
| partial, s = 0.15 | 0.143 | 0.263 | milder than 0.35, which is already not attainable; not powered separately |
| partial, s = 0.35 | 0.343 | 0.567 | power 0.45 to 0.68 in the linear case even at six per version; 28 to 53 books needed for 0.8 |
| **partial, s = 0.65** | **0.644** | **0.874** | **registered** |
| partial, s = 1.0 | 0.993 | 0.993 | the full shuffle again: v2 and v3's dose, no step |
| `ablate.paragraph_shuffle`, s = 0.15 to 1.0 | 0.15 to 1.0 | 0.276, 0.524, 0.616, 0.007 | refused as an operator (next paragraph) |

- **`ablate.paragraph_shuffle` is refused as the operator.** It rotates the picked set by one
  offset, its damage is not monotone in its strength (0.61 of adjacencies broken at 0.65, 0.007
  at 1.0), and it gives one fixed variant per text, so no seed can be redrawn.
- **§104's D1P families are not this arm.** They are generation-dependent manipulations. This
  one is a code-only transformation of the same texts v2 and v3 read, so the only thing that
  moves between those arms and this one is the dose.

## The design

| | v2 / v3 | **milder-v4** |
| --- | --- | --- |
| books | the 20 fitness books | the same 20 |
| competitors | books `i+1..i+3`, intact | the same |
| target's slot | A | A |
| versions | intact / full shuffle / sham | **intact / partial-0.65 / sham** |
| sessions per version per book | 3 | **6** |
| sessions | 180 | **360** |
| dosed seeds | 3 per book, a rule from a start | 6 per book, the same rule from 0, plus one clause (below) |
| sham | `ablate.rewhitespace` at 1.0 | the same |
| reader | `claude-haiku-4-5` over `claude -p`, §109 flags | the same, through `elicit`'s transport unchanged |
| the binary | as found | **a pinned, hash-checked copy of the registered binary** (below) |
| isolation probes | none recorded | **two, before any arm call**: a marker CLAUDE.md and a marker git status |
| workers | 3 | 3 |
| dispatch order | book by book | **replicate by replicate** (below) |
| cache | its own file | its own fresh file, `raw-milder-v4.jsonl` |

Byte-frozen and imported, not restated: `fcr.v0` (its 24-minute budget, reads at three, skims at
one, forced spending, the four-book feed, the mid-stream entry and the deterministic skim, under
the registration digest `4c5f695bd0c16a03` that v2 and v3 ran under), `feed_session`'s loop,
`feed_controls`' `fp5` and slot table, `bcr.chunks` and `bcr.cluster_interval`,
`cost_that_bites`' sham, capacity check, interval block and decision function (v2's design
digest `499efb7c9faea9d3`), and `elicit`'s CLI transport with its cache rules. The registration
records both digests and refuses to verify if either moves. It also content-addresses v2's
committed `raw-v2.jsonl` and `results-arm-v2.json`, which the identity check reads.

**Seeds.** For each book, the six lowest seed indices from 0 upward whose dosed copy chunks to at
least `feed_core.MIN_CHUNKS_FEED` (11). That is v3's amendment-a rule, which reads chunk counts
and never a reader's behaviour. The power record found one book below the floor in seeds 0 to 9,
`fitness-08` at seed 1 with 10 chunks, so `fitness-08` takes **(0, 2, 3, 4, 5, 6)**. The other
nineteen take (0 to 5). The result file names the seeds every book used.

**One clause is added to the rule, before spend: a dosed copy's opening must differ from the
intact copy's.** The replay cache keys on the request, and a request carries the prose revealed
so far, not the book. A partial copy whose moved paragraphs all lay past the opening would send
the intact session's first request byte for byte, at the same sample index. It would then be
served the intact session's first answer from the cache, which couples two versions through the
cache instead of measuring them apart. A full shuffle cannot do this. A partial one can in
principle. On this shelf no dosed seed from 0 to 9 does, so the clause changes no registered
seed. The plan also refuses, as a named fault, any two versions of one book at one replicate
that share an opening.

**Dispatch is replicate-major.** Every book's three versions run at replicate 0, then at
replicate 1, and so on, three sessions in flight. A stopped run then loses replicates evenly
across books and versions, instead of losing whole books the way v1's transport stop lost
`fitness-15` to `fitness-19`. Each book's three versions still run next to each other in time.
This changes no request and no reading.

**The cache is fresh, and that matters more here than it did before.** This arm's intact and sham
requests at replicates 0 to 2 are byte-identical to v2's (same texts, same seat, same sample
indices). A cache shared with `raw-v2.jsonl` would replay v2's sessions as this arm's.
`run` refuses a cache holding answers when no invocation of this arm has a started line, and
both `run` and `analyse` refuse a cache holding any record whose feed id is not one of this
arm's. v2's cache is read only by the identity check, through a replay-only reader that cannot
write, and is never loaded into this arm's reader.

## The reading, fixed before spend

**The statistic is v2's, exactly.** `target_read_share` is averaged within each book over its
scorable sessions of each version. Here that is up to six sessions, where v2 had three. It is
paired within book, and the 90% interval comes from `bcr.cluster_interval` over the twenty books
at alpha 0.10: 2,000 resamples, seeded from a content digest of the observations. An interval
lies above zero when its lower bound is strictly greater than 0. A book contributes only if
every version has at least one scorable session, v2's `by_book` rule. The test file checks that
this arm's reading equals `cost_that_bites.reading_v2` on the same rows with the version
relabelled.

**The scorable floor's denominator is v2's: the dispatched sessions.** `run_cells` returned a
row only for a session it ran, so in v2 a session never dispatched was missing coverage, not an
unscorable session. Here a session counts as dispatched when a ledger checkpoint names it or the
cache holds one of its answers. A dispatched session that ended on a call that obtained no
answer counts as unscorable, as it did in v2. A session never dispatched does not enter the
floor, and it stamps the reading **partial**. So a run stopped at, say, 70% coverage is read as
a smaller balanced design (replicate-major dispatch), stamped partial, and not as an unscorable
reader.

**Preconditions, read in this order. Each refuses rather than degrades, and each prints its
measured value beside its floor, pass or fail:**

0. **The transport, before anything else** (the section below). A cache holding a transport
   failure as an answer refuses the reading outright.
1. **Request identity.** At `prepare`, the 120 intact and sham sessions at replicates 0 to 2 are
   replayed from v2's committed cache and must replay completely and reproduce v2's committed
   book means. `prepare` refuses to register otherwise, and the reading reads the registered
   result. This proves the extracted texts, the seat, the competitors, the prompt, the sample
   indices and the transport's key are v2's. It also covers the extraction path
   (`corpus_io` and `src/litharness/application/export.py`), which is not content-addressed and
   which another session was editing while this was written. On the power record's texts it
   replays 120 of 120 with a largest book-mean difference of 0.0.
2. **Scorable floor.** At least 75% of each version's dispatched sessions are scorable. A session
   with any unanswered step is reported and never scored.
3. **`fp5`** over every session: the slot-share vector must move across sessions (floor 0.05).
4. **Capacity.** Slot A's mean read share must be the largest of the four and at least 0.40.
   v2 measured 0.5508 and v3 0.5740. The same conditionality v2 recorded applies here: the check
   is drawn from the sample it gates, and it asks about the reader, not the contrast.
5. **At least ten books** with every version scorable.

Then one decision, from `cost_that_bites.decide`:

| the intervals | reading |
| --- | --- |
| `intact - partial` above zero **and** `sham - partial` above zero | **MOVES_WITH_ORDER** at s = 0.65, for a book in slot A |
| `intact - partial` above zero, `sham - partial` not | **MOVES_WITH_EDITEDNESS** |
| `intact - partial` contains zero | **NULL at the declared target** |
| `intact - partial` below zero | **INVERTED** |
| any precondition fails | **UNREADABLE**, with the failing value printed |

**Declared target: a shift of 0.115.** That is the linear-attenuation expectation, 0.65 x 0.1765,
and the design is powered for it at 0.86 to 0.90, or 0.69 to 0.79 if between-book
heterogeneity does not shrink with the dose. **Underpowered at 0.075**, the s-squared
expectation, at 0.57 to 0.77. A NULL is not evidence against a shift of that size.

Reported beside the decision, and deciding nothing: the point estimate against the power
record's attenuation bracket [0.075, 0.155]; the abandonment step and first read on the target,
paired the same way; the per-slot table; the skim rate; the spread of each book's six partial
permutations, which says whether the number is about disorder or about particular
permutations; each dosed copy's displaced and broken-adjacency fractions, from the manifest; and
the reader-drift diagnostic (next section).

**Deviations from v2's analysis: none in the statistic, and none in the floor's denominator.**
The changes are six replicates in place of three, the dosed version in place of the full
shuffle, the seed rule's opening clause, replicate-major dispatch, the request-identity
precondition, and a live log that prints no target share, so no reading can be watched forming
while the arm is bought. Also added are resource ceilings with per-session reservations, a
transport circuit, a kill-proof ledger, a pinned binary and two isolation probes. Those are
below.

## Is it still §230's reader?

Three consequences in the table below reach back to §230: MOVES says §230's claim extends, NULL
says its licence narrows, and INVERTED says its order reading is put in question. Each assumes
this run's reader is the one §230 measured. The CLI is a disclosed, uncontrolled change (below),
and the snapshot that answers is not observed. So what the arm can say about that assumption is
registered here, before spend.

- **The requests are proven v2's** by precondition 1, at no cost.
- **The reader is compared with v2's on those same requests, and the comparison decides
  nothing.** Reported: this arm's per-book intact and sham means over replicates 0 to 2, minus
  v2's committed means, with v2's interval; and how many of those sessions repeat v2's action
  sequence exactly. They are printed beside the same reader measured against itself, v3 against
  v2 on the same requests, computed call-free from the committed results:

  | v3 - v2 (the same reader, twice) | point | 90% interval | identical sequences |
  | --- | --- | --- | --- |
  | intact | +0.068 | [+0.013, +0.126] | 7 of 60 |
  | sham | -0.041 | [-0.125, +0.044] | 8 of 60 |
  | (full shuffle, different texts in each arm) | | | 2 of 60 |

- **No drift rule is registered, and the reason is computed, not argued.** The obvious rule,
  "both drift intervals contain zero", would have called v3 a different reader: its intact
  interval against v2 excludes zero. Run-to-run variation of the same reader on the same
  requests is already that large, and no level rule this record could write would separate a
  changed snapshot from a second run of the same one. A rule on the identical-sequence rate has
  one same-reader data point and no measured alternative, so it cannot be calibrated either.
  A gate that the known replication fails is not a bar this reader can be held to.
- **So the three §230 clauses are conditional, in the words of the licence itself.** Each reads
  "if this run's reader is the one §230 measured". The claim's own state, about the reader
  seated on this run's date and binary, is decided by the table as written. Whether it carries
  back to §230 rests on the proven requests plus an unobservable snapshot, with the diagnostic
  on the record for review.
- **The one design that would make those clauses unconditional is not this registration's to
  add.** A full-shuffle positive control on today's reader (120 more sessions, about $34
  equivalent) would re-establish §230's effect on the reader actually seated. It is also a third
  full-shuffle measurement, which §230 refused as a tie-breaker, so it needs the operator's
  approval and its own entry. It is not run.

## Attainability: the four checks, with numbers from the power record

| check | here |
| --- | --- |
| **range** | a paired difference of book means of read shares, in [-1, 1] |
| **direction** | positive means the reader paid less for the dosed copy |
| **unit** | the book: twenty clusters, none empty, each a mean over up to six sessions per version |
| **non-emptiness** | on the shelf's texts the plan builds 360 cells with no fault, every dosed copy at 11 chunks or more, the only seed deviation `fitness-08` |

Power at twenty books and six per version (`ATTAINABILITY.md` has the full tables):

| assumption | primary | MOVES_WITH_ORDER |
| --- | --- | --- |
| s squared, 0.075 | 0.57 to 0.77 | 0.41 |
| **linear, 0.115 (declared)** | **0.86 to 0.90** | **0.77** |
| adjacency, 0.155 | 0.94 to 0.97 | 0.95 |

**Calibration at no effect is measured at three per version only**: 0.056 to 0.062 false
positives on the primary and 0.016 to 0.018 on MOVES_WITH_ORDER, from the k = 3 grid. The
six-per-version simulation has no row at f = 0, so calibration at six per version is
**unmeasured**. The statistic and interval are v2's, and the k = 3 rate is the evidence that
they are calibrated on this reader's variance.

These are parametric and analytic figures, and they are optimistic. At three per version the
resampled model ran 0.04 to 0.11 below them, and no resampled model can exist at six. With
between-book heterogeneity held constant rather than shrinking with the dose, the linear case
falls to 0.69 to 0.79. That is this registration's sensitivity, labelled as such in
`ATTAINABILITY.md`. At three per version the linear case would have been 0.60 to 0.80 with
MOVES_WITH_ORDER near 0.5, which is why the approval is for six.

## What each outcome licenses, and what kills the claim

"If §230's reader" below means: if this run's reader is the one §230 measured, as the previous
section registers.

| reading | consequence | claim state |
| --- | --- | --- |
| **MOVES_WITH_ORDER** | the reader reads less at 64% of paragraphs moved, beyond the sham, a book in slot A, this shelf. Inside the window that is 87% of adjacencies broken against the full shuffle's 99%, **a ratio of 0.88: a short step from destroyed order, not a book that is merely worse**. If §230's reader, §230's claim extends that step. It is still not a quality instrument and not a qualification, and no editorial intervention follows | eligible for SUPPORTED on review |
| **MOVES_WITH_EDITEDNESS** | the reader moved, but no further than the sham lets an order claim be read at this dose. No extension of §230 | OBSERVED, not supported |
| **NULL** | **not detected at 0.115, with power 0.69 to 0.90 by heterogeneity model** (and optimistic by the resampling margin). Not evidence against a shift of 0.075 or less. If §230's reader, **the licence narrows** and §230's claim stays at destroyed order. **No further dose, and no further reader, is run on this question to find one that moves**: a second dose or a second reader chosen after a null is the rejection sampling `BRIEF.md` §6 item 6 prices. A finer resolution needs more books, which is a generation spend and the operator's call | OBSERVED, not supported |
| **INVERTED** | the partially disordered book drew more reads. **This is the kill condition.** The registered claim is refuted. If §230's reader, §230's order reading is put in question, because a monotone dose-response is what "the reader reads order" predicts. It is not reversed into a preference for disorder. The mechanism class goes to `BRIEF.md`'s ledger | REFUTED |
| **UNREADABLE** | the failing precondition's measured value is the finding. No interval is read | OBSERVED |

**Nothing is pooled.** This arm is reported beside v2 and v3, never combined with them. It
decides one thing, and no third arm, second dose, second reader or re-run breaks a tie.

## Transport failures, before any verdict

The rules §224 and §235 paid for, applied here:

- **A call that obtained no answer is not an answer.** `elicit` counts it under a reason that
  names the exit code and the first line of stderr (§224), never writes it to the cache (§235),
  and leaves any old one aside on load. The reading **refuses to run** if the cache holds even
  one such record.
- **The transport block is read first.** It covers every invocation (calls, failures by reason,
  undispatched calls, the stop, whether it finished), each session's status (scorable, answered
  but unusable, or never answered, and whether it was dispatched), the missing sessions by name,
  and whether they form a tail block. Only after that are the preconditions and the decision
  read.
- **A contiguous tail of missing sessions is a stopped transport**, v2's amendment, and is named
  as one. A reading over missing sessions is stamped **partial** and is never reported as a
  covered shelf.
- **The circuit.** After three consecutive sessions end on a failed or undispatched call, no new
  session starts and the ones in flight finish. That is one per worker, and a usage limit fails
  every session in flight at once. **Any exception drains the run the same way**: a worker that
  raises, or an interrupt, stops every other worker from admitting a new session.
- **The ledger survives a kill.** Each invocation appends a `started` line before the probes, a
  `probed` line, a checkpoint after every session (its outcome and the meter's cumulative
  totals, failure reasons included) and a `finished` line. A process killed by PID, or a
  workstation shutdown, loses at most the sessions in flight from the ledger, and none of their
  cached answers. A torn last line is skipped on read and closed before the next append.
- **A resume buys only what never answered, and only before a reading exists.** Every bought
  call is in the cache, so a second `run` replays those free and re-issues exactly the calls that
  obtained no answer. A cached answer, including an unusable one, replays identically, so a
  resume cannot re-roll a measurement. `run` resumes after a kill as well as after a stop.
  `run` refuses once `results-milder-v4.json` exists: as §222 recorded, no cell is bought after
  a number has been seen.
- **No reading while a run could still buy.** `analyse` refuses while `runs/box.lock` names this
  arm and while the last invocation has no finished line. A run halts between sessions if a
  reading appears. After a kill, the operator either resumes with `run` or records with `close`
  that the killed invocation will not be resumed. `close` refuses while the lock names this arm.

## Resource ceilings

Each ceiling is checked **before every call** that would be paid, since replays are free. A
refused call ends its session unscorable and halts the run. Each is also checked **before every
session**. A session starts only if every used total, plus a worst-case reservation for every
session in flight including this one, stays under its ceiling. Otherwise the run drains. The
totals are cumulative across resumes, and the isolation probes count toward them. A resume
starts from the **larger of the ledger's totals and the raw cache's**. After a kill that can
undercount by the killed invocation's probe calls and by calls that failed after its last
checkpoint, a few calls against a ceiling of 4,400.

| resource | expected (v2/v3's measured rates) | ceiling | reserved per session |
| --- | --- | --- | --- |
| calls | about 2,930 (8.1 a session) | **4,400** | 24 (every unit on skims) |
| reported tokens | about 124 million (42,400 a call) | **190 million** | 1.5 million |
| equivalent USD | about $100 ($0.28 a session) | **$150** | $1.50 |
| wall time | about 4h10 at three workers | **8 hours** | 30 minutes |

The dollar figure is the subscription-equivalent price the CLI envelope reports, a proxy for
quota burn and not money charged. A fresh call that reports no usage also drains the run,
because a ceiling that cannot be read cannot be enforced.

## The box

`run` refuses unless `runs/box.lock/holder` exists and begins
`cost-that-bites-milder-20260922:`. Take the lock atomically with the RUNBOOK's guard-and-go
block, after checking the process list. That block releases the lock only if the holder is still
this arm's. Run one CLI arm at a time across all sessions, with no validation suite, type
check, corpus pass or GPU job beside it, and three workers at most.

**The binary is pinned.** Interactive Claude sessions on this box update
`~/.local/bin/claude.exe` in place (it was replaced at 17:48 on the day this was written), and a
setting inside the runner cannot stop them. So the first `run` copies the registered binary,
only if it still hashes to the registration, into the ignored
`runs/cost-that-bites-milder-20260922/milder-v4/bin/<hash>/`. Every invocation checks the
copy's hash and version, puts its folder first on PATH, and confirms that CreateProcess will
start the copy and nothing ahead of it. The probes and the arm then run on the copy. The runner
also sets `DISABLE_AUTOUPDATER=1` for its own process, checks the copy's size and mtime before
every session (a change halts the run), and hashes it again at the end. Once pinned, an update
of the original changes nothing this arm runs. If the original changes before the first pin,
`run` refuses and, because nothing was bought, `prepare` may be run again.

**A registration can be refreshed until a cell is bought.** `prepare` refuses once this arm's
cache holds an answer, its ledger records a fresh arm call, or a reading exists. A probe-only
invocation (a probe that failed, or a usage window waited out) buys nothing and does not block
it.

## Disclosed changes since v3

- **The Claude CLI is 2.1.280** (`C:/Users/artem/.local/bin/claude.exe`; `prepare` records the
  version it reads and the binary's sha256). v2 and v3 recorded no CLI version. The nearest
  records are 2.1.236, measured in §109 before them, and 2.1.263, recorded on 2026-09-08 after
  them. So the binary is a disclosed and uncontrolled change of at least seventeen patch
  releases. Before any arm call, `run` makes **two isolation probes** through the arm's own
  transport on the pinned copy. One asks from a directory holding a marker `CLAUDE.md`. The
  other asks from a scratch git repository holding an untracked file named for a marker, because
  the arm runs from the repository root and a git status is the other context the house tests
  (`tests/test_providers.py`). An answer passes on the house's comparison: it contains `NONE`
  and not the probe's marker, so "NONE." passes. Nothing is bought unless both pass.
- **The served model is not observed.** The transport records the requested alias
  `claude-haiku-4-5`, not the snapshot that answered, exactly as v2 and v3 did. A snapshot
  change between 2026-09-04 and this run is possible and cannot be ruled out from the record.
  "Is it still §230's reader?" registers what follows from that.
- The binary is found where CreateProcess finds `claude.exe`. `shutil.which('claude')` names a
  `.CMD` shim on this box that the transport never runs.

## The Codex contingency: a different reader, not licensed here

The operator's direction of 2026-09-22 is that work must adapt to a Claude-only or Codex-only
setup when one account's limits are reached. **Stated plainly: switching readers is one flag,
but only before either reader has bought a cell, and only as a separate experiment.** A Claude
run stopped by its usage window waits and resumes on Claude, or is analysed as partial. It is
never continued on Codex, and a Codex arm is never run after a Claude reading to see whether a
second reader agrees. That would be best-of-two on one question, the rejection sampling
`BRIEF.md` §6 item 6 prices and the tie-breaking §230 refused.

The runner carries the second profile, `--reader codex`: `gpt-6-astra` at low effort through the
Codex CLI's subscription transport (the production `CodexCliProvider`, tool-free, ephemeral, no
project documents). It is sent the system block `claude -p` is sent, schema sentence included,
byte for byte, and the same flattened transcript, and the adapter also passes the schema
natively.

- **Whichever reader buys a cell first holds the question.** `prepare` and `run` for either
  profile refuse once the other profile's arm has bought a cell. Codex can therefore substitute
  only if no Claude cell has been bought. After that, a Codex arm is a new experiment with its
  own folder and its own stage-0 entry.
- **Its reading never reaches §230.** It is a reader §230 never measured, so its licence has its
  own text. None of its outcomes extends, narrows or questions §230's claim. It has its own arm
  `milder-v4-codex`, registration (`registration-codex.json`), cache, ledger, result and claim,
  and it is **never pooled** with this arm.
- **It cannot be registered on this file's sizing.** `prepare --reader codex` refuses until
  `codex-approval.json` (the operator's approval record) and `ATTAINABILITY-codex.md` (its own
  power record) exist beside this file. Both are content-addressed in its registration. That is
  `BRIEF.md` §5's last rule: size the batch against the reader you will actually seat. No such
  record exists today.
- It has never been seated, so v2's full shuffle is added as a **positive control**: a fourth
  version, `shuffled`, at `cost_that_bites.seeds_for` from 0. That makes 480 sessions. If
  `intact - shuffled` and `sham - shuffled` are not both above zero, the reading is **UNSEATED**:
  this reader was not shown to read order at all, and no dose reading exists. The capacity
  precondition decides whether slot A is the slot it attends to.
- **Its own acts are answers.** The adapter reports a `MALFORMED_RESPONSE` both for a garbled or
  incomplete event stream and for a turn in which the model itself attempted an activity the
  tool-free profile forbids. The first stays a transport failure, uncached and re-issued, which
  is §235's rule. The second is the reader's behaviour, so it is cached as an unusable answer
  with the usage the stream reported, and a resume replays it instead of re-rolling it.
- Its transport reports no price, so it has no dollar ceiling. Its limits are 5,900 calls,
  150 million reported tokens and 12 hours. It records the requested model, because the CLI
  reports no resolved one. Its probe asks with marker `AGENTS.md` and `CLAUDE.md` files in the
  adapter's working directory. It has no git-status probe, because the adapter chooses its own
  working directory.

## What it cannot establish

- **Not a quality instrument.** The arm measures how a reader allocates minutes under a cost. It
  makes no claim about any of the twenty books.
- **Not QUALIFIED.** It carries no production authority and licenses no editorial intervention.
  No reader is retuned on it (§89, §97.1), and no book is selected or revised on it (§105).
- **One reader.** It is one model over one transport, and the snapshot that answered is
  unobserved. A different model is a different reader with its own file.
- **An old shelf.** The fitness books are this house's own 2026-08-22-pipeline drafts, about
  3,900 words and 11 to 12 chunks each. Nothing transfers from them to the current pipeline's
  books.
- **Slot A only.** The claim is about a book in the position this reader attends to.
- **The window.** A session reveals at most the first 11 chunks of a book, so what the reader
  can notice is the disorder inside that window.
- **One point of a dose-response.** The power record assumed the attenuation, and this arm
  measures it at s = 0.65 only.

## A located defect, recorded and not fixed

`cost_that_bites.py:1218`, `volume_text`, sorts chapter files by name
(`key=lambda p: p.name`), so `Chapter10.txt` sorts before `Chapter2.txt`. It sits in the code
path of the 2026-09-04 volume screen (`cost-that-bites/PREREG-volume-screen.md`). It is
**latent for the books that screen read**: their result files record 1 to 8 chapters each,
`Chapter1` to `Chapter8`, and for those, name order is reading order. **Any future screen of a
book with ten or more chapters would read it out of order.** Full-book trial A1's library export
has 24 chapters, and the power record's export measured its name order differing from its
reading order. This arm does not use `volume_text`. The frozen file is not edited here, and the
fix, a numeric chapter sort, belongs to whoever next runs a volume screen, as its own entry.
