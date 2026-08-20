<p align="center">
  <img src="docs/banner.png" width="100%" alt="LitHarness — a constellation dragon rising from an open book in a workshop of one-eyed archive creatures, six green stars joined along its body, one refused star sealed alone in a vault at the lower right">
</p>

<p align="center"><em>The lines are what the gate can prove; the dragon is what the reader sees.<br>
Six scenes along its spine; one candidate refused, sealed in its vault, joined to nothing.</em></p>

An autonomous book-production system with a human director, refounded on one goal:
**superhuman literary quality**, operationalised as a pre-registered pairwise bar —
the lower bound of a 95% CI on blinded, position-swapped win rate against matched
published-human prose exceeds 0.5, judged by paid genre readers
([stage-0 §61](plan/stage-0-decisions.md)). Throughput, uptime, and publication
cadence are not goals. See [PLAN.md](PLAN.md) for the
master plan and [plan/](plan/) for companion design documents — in particular
[plan/stage-0-decisions.md](plan/stage-0-decisions.md), which records the load-bearing
design decisions and why each went the way it did, and
[plan/craft-corpus.md](plan/craft-corpus.md), which sets out how prose quality gets measured
without a human in the loop.

**Status: Stages 0, 1 and 2 met against their exit clauses** — with two caveats that travel
with the claim: Stage 0's endurance clause is *evidenced rather than met* (2,016 simulated
ticks, not a week of real scheduling), and Stage 2's propagation number is a **dev-set** one
measured on four in-sample cases, which rules out an engine that is obviously wrong and rules
in nothing. Both are recorded in [PLAN.md](PLAN.md) §17 beside the claims they qualify.

The manuscript spine, the Conductor loop, the pinned frontier provider plus a
deterministic fake, recorded acceptance
decisions, a direction inbox whose explicit instructions and model-interpreted notes reach an
immutable plan revision before prose, a way to get a book in, a reading copy to get it out, a
template planner that takes a six-scene fixture book from premise to six accepted scenes with
no human in the loop, an objective-story-state layer and the context packet each scene is
drafted against, a blocking integrity gate that refuses a candidate a planted defect stands
against, and a detect-repair-propagate chain in which a repair that changes a fact re-checks
the scenes that state it.

It writes a book whose scenes know about each other, refuses one that contradicts itself, and
— since it now asks its generator to state game state on the page and reads that back — can
do both on a book with no imported snapshot, which is what makes Stage 3 startable. **Nothing
in it yet measures whether the book is any *good* — but the instrument that could is now
built and waiting on funded judgment**: the pairwise preference engine, whose empty
verdict store is the honest measure of the gap, exactly as the empty `calibrations`
table was before it. See [What is not built](#what-is-not-built).

## Setup

One clone, and nothing has to sit beside it. `litharness-contracts` is a git dependency
pinned to a commit in `uv.lock`, and the golden fixture books ship inside that package, so
`uv sync` fetches everything the suite reads.

```bash
git clone https://github.com/skulitom/LitHarness
cd LitHarness
uv sync --extra dev
uv run pytest
```

The six-rule LitRPG pack is an optional subprocess integration rather than a runtime
dependency. To enable it, install the sibling `../ContinuityEvaluation` checkout and point
LitHarness at its console script:

```powershell
cd ..\ContinuityEvaluation
uv sync --extra dev
$env:LITHARNESS_CONTINUITY_EVALUATOR = "$PWD\.venv\Scripts\continuity-evaluate.exe"
cd ..\LitHarness
```

The equivalent one-shot option is
`--continuity-evaluator-command ..\ContinuityEvaluation\.venv\Scripts\continuity-evaluate.exe`.
Without either setting, LitHarness keeps its existing in-process contradiction check.

## Running it

```bash
uv run litharness --database book.db init
```

Then get a book in. Nothing else works without this — every other command acts on a
revision, and `import` is the only one that creates one. The golden fixtures come from the
sibling contracts checkout:

```bash
uv run litharness --database book.db import --fixture mystery
```

It prints the revision id. Scene prose is **cleared** so each scene can be drafted;
`--keep-content` keeps it and tells you that nothing is draftable, because a draft may only
fill an empty node. Use `--path` for a manuscript of your own — and pass `--plans` with it,
because the premise in the plan snapshot is what beat prompts are rendered from and a book
without one is reported as blocked rather than drafted. `--state` imports objective story
state alongside: open threads and POV-visible knowledge, which the context packet is built
from. It is optional where `--plans` is not — a book with no state records drafts against
its plan and its prose, which is thinner but not blocked, and a regenerating book starts
with none by definition. `--fixture` supplies all three.

A book that does not exist yet starts with `new` instead, which is Stage 3's entry point:

```bash
uv run litharness --database book.db new "The Toll Road" \
  --premise "A debtor works off an impossible debt along a System-governed road." \
  --scenes 24 --state seed.json
```

`import` needs a manuscript file, so before this a book could only exist if someone had
already written one. `new` creates N **empty** scenes — empty is what draftable means here,
since a draft may only fill an empty node — plus the premise the planner requires. The beat
sheet is chosen to fit: six scenes keep `SIX_BEAT`, any other length gets an arc of its own
length with the singular beats kept singular (one inciting incident, one crisis, one
resolution, and everything between them rising). `--state` seeds canon, and for a LitRPG book
it is not optional in practice: a book whose canon holds no status snapshot is never asked for
system voice, writes none, and so has nothing for §12 step 5 to read back.

Then tick — one bounded unit of work, which is what a scheduler invokes:

```bash
uv run litharness --database book.db tick
```

Each tick first materialises plan work for any unambiguously scoped direction, then drains
the queue; when nothing is claimable it plans the next undrafted beat. The beat becomes a
job, is drafted, gated and accepted. With the automatic evaluation pass, a clean six-scene
book takes twelve uninterrupted ticks from premise to a full evaluated draft when no
direction intervenes; each accepted repair adds its own repair and verification ticks.
`enqueue` still exists for drafting one named node by hand with your own prompt, which is now
the exception rather than the way in.

Each beat is drafted against an assembled **context packet** (§12 step 2): the premise, the
director's locked constraints and promises, the book's open threads, the established facts
visible to the scene's POV, and the prose of every scene before it. It is packed by a fixed
priority order under a token ceiling — constraints and threads first, prose dropped
oldest-first — and **everything dropped is recorded** on the job payload with its reason,
because a baseline that packs by priority rather than relevance will drop things a scorer
would have kept and has no way to know it. Relevance scoring is LongRangeContext's, per §12.

One book runs as one foreground session: a single process drives `tick` in a loop until
the book is done. Ctrl+C is the pause — ticks are idempotent, so restarting the session is
safe at any moment, and a job lease left behind by a killed process expires and is
reclaimed on the next tick. **Exit codes are `tick`'s contract with whatever drives it**:
`0` the tick did its job, including finding nothing to do; `1` a unit failed or parked and
a human should eventually look; `2` an operational fault — locked or corrupt database,
missing migrations, full disk, a bad argument — which the driving loop should retry next
iteration rather than escalate.

## Operating it

```bash
uv run litharness --database book.db status
```

Reports queue depth by status, how many units need attention, unread direction, and the
day's digest and spend. `--json` for machine consumption. Always exits `0`: it is a report
for the operator driving the session, not an external monitor.

Everything else the director does:

```bash
uv run litharness --database book.db directive "More dungeon crawling." --kind arc_note
uv run litharness --database book.db directive "No combat in the midpoint." \
  --kind constraint --book <book-id> --branch <branch-id>
```

- `directives` — what has been captured. Explicit `constraint` and `veto` direction is
  converted deterministically into a locked plan item on the next tick, before queued scene
  work. Constraint text stays exact; veto text keeps its original words under an explicit
  veto label. Arc, tone, chapter, and premise notes take a bounded structured-output model
  pass that proposes at most 12 edits; locks, explicit targets, the single-premise invariant,
  and the current plan head are enforced outside the model. Scope may be supplied with
  `--book` / `--branch`; an unscoped directive is applied only when the store has exactly one
  matching branch. Rejected output leaves the original directive in `received`.
- `jobs [--status parked]` — queue depth, or the units in one state.
- `revive <job_id>` — return a parked unit to the queue once you have cleared what parked
  it. Refuses a poisoned unit, whose attempt budget really was spent. A unit stopped by a
  budget ceiling or by a standing finding is parked, not poisoned: the blocker is external
  and the work is still there.
- `state [--subject] [--predicate]` — what this book holds as true, in story order. The layer
  that gates every draft: the integrity gate refuses a candidate contradicting it, the context
  packet hands it to the generator, and propagation reads its changes out of it. Every line
  says whether the record was **given** (imported canon) or **read** (this system's reading of
  prose it generated), and carries any note about how its story position was decided. It is
  also the view that makes a ledger checkable by eye — `state.contradiction.v0` compares
  values at a single story position and cannot see a balance that stops adding up across them,
  so without the ContinuityEvaluation pack configured, a human reading this column is the one
  who notices.
- `propagate <change-set.json> [--enqueue]` — what a change reaches beyond what it edits.
  **An accepted repair does this by itself**: the facts it changed are read out of the
  extraction the acceptance already runs, and the scenes stating them are queued for
  re-evaluation in the same transaction, bounded by the repair-depth ladder and recorded as an
  `ImpactAnalyzed` event. This command is for the changes that have no in-repo producer —
  renames and moved events — and for asking before acting.
  Reads a `ChangeSet` of the shared schema (as `ingest` reads an `EvaluationArtifact`) and
  reports every scene and state record the change touches, with the rule that reached it and
  why. Four rules: a rename reaches wherever the old name is spelled, forwards and back; a
  changed fact reaches forward to what states it after the change; a moved event reaches the
  window between where it was and where it goes; a surface-only edit reaches nothing.
  Anything else **abstains and exits non-zero** — "no rule read this" must not print the same
  as "this reaches nothing". `--enqueue` queues an evaluation for each reached scene; without
  it the command only reports. Scored against the contracts gold impact suites at precision
  1.000 / recall 1.000 versus the base rate of 0.481 — **a dev-set number over four in-sample
  cases**, which is what the command prints under every result.
- `plans` — the plan's lineage, newest first, with the proposal that produced each revision:
  which directive it came from, what it summarised itself as, and whether it was itself a
  rollback. A revision no proposal produced is the plan the book was imported with.
- `revert-plan <plan-revision>` — restore an earlier plan revision as the new plan head.
  Forward, like `revert`: the restored plan is a new revision, so the change and its undoing
  both stay in the lineage and rolling back a rollback composes. It is the one proposal
  permitted to move a **locked** item, which is what lets it undo a director's constraint —
  so it reports how many it moved, and names any applied directive left citing a plan item
  the restored plan does not have. It touches no prose: the plan epoch advances and queued
  scene jobs are cancelled in the same transaction, so the next tick replans the
  still-draftable beats, and scenes already accepted stay accepted.
- `replan` — reissue every still-draftable beat under a fresh plan epoch. The verb for the
  two states `revive` cannot reach: a poisoned unit burned its derived job id forever, and a
  parked unit whose head has since moved would be revived onto a stale base. It does not
  overrule the gate — a beat blocked by a finding blocks again unless the finding is
  dismissed first.
- `exceptions` / `resolve` — what policy could not resolve. Resolving closes your side; it
  deliberately does not requeue the unit, because an escalation may have been *right*.
- `revert <revision> --book --branch` — restore an earlier revision as the new head. Goes
  forward: the mistake and the correction both stay in the record.
- `backup <path>` — online backup, safe while ticking. Uses SQLite's backup API because
  this store runs in WAL mode and a file copy would silently omit everything since the
  last checkpoint.

Every state change writes its event into the store's `events` table in the same
transaction, so the audit trail is always in the database itself — there is no separate
delivery channel to configure or monitor.

**Who writes it.** One pinned frontier provider: the local Claude Code session
(`claude_code`). §1a.5 requires a frontier generator, and a silent mid-book fallback to a
weaker model is a quality defect, not resilience — so there is no fallback chain and no
provider-selection flag. When the provider is unhealthy the unit parks or requeues and the
book waits; it never degrades. The retired plurality design and its measurements stay
recorded in `plan/provider-adapters.md`.

The one alternative is the deterministic fake, and it has to be *asked for*:
`LITHARNESS_FAKE_PAD_CHARS` (e.g. `400`) runs the whole loop model-free, with the fake's
output padded past the shape gate's floor. Setting it is the statement "I am deliberately
running on the fake" — the fake is never a silent generation backstop, because a backstop
that cannot clear the gate it feeds once poisoned six units during an outage.

`LITHARNESS_ENV=test` keeps its one job: a test run provably cannot reach a paid
provider. The registry now enforces it by refusal — resolving a billing provider in test
mode raises rather than quietly substituting.

`--context-budget` sets how much context a scene is drafted against, and **it moves with
`--target-words`**: measured, a 900-word scene binds the 6,000-token default at scene 5 and
leaves the packet holding three prior scenes, against scene 24 at 160-word scenes. When the
packet drops prose it bumps a `context_omitted` counter in the daily digest, so a book being
written blind shows up in `status` rather than only on a job payload.

`--target-words` asks the generator for a scene of a given length. A target, never a gate:
nothing refuses a scene for missing it, and it is recorded in every decision's policy digest
because it shapes every scene in the book. Measured, it moves a capable model about halfway
and a small one not at all — so pick a scene count from what your model actually writes.

Budget ceilings apply to every generating call and are checked **before** it is made:
`--max-tokens-per-day`, `--max-invocations-per-day` (the one tokens cannot express — see
§15's per-call harness tax), `--max-tokens-per-operation`, `--max-cost-usd-per-day`. Pass
`-1` for unbounded on any of them, which has to be asked for rather than being what you get
by forgetting a flag. `status` prints spend against plan.
- `verify` — rebuild every revision from canonical records, check the content hashes, and
  report any revision no policy decision explains. Exits non-zero if it finds one.

## Gating it

The ladder runs shape, then integrity, and integrity runs in two places for one reason.

A finding **already on record** against a node is checked *before* the provider call. It
cannot be caused or cleared by the candidate, so all three attempts would meet the identical
refusal — generating to discover it costs three model calls and then poisons the unit,
leaving nothing to resume when you do the right thing and dismiss the finding. So it parks
revivably, costs no attempt and no tokens, and names the findings that stopped it in
`jobs --status parked`.

A finding about **this candidate** is checked after generation, carries a `continuity_breach`
veto, earns a bounded retry, and after the attempt budget parks the unit and files an
exception. That refusal is about the work, so it is charged like one.

Either way a defect on scene 3 does not stop scene 6: findings are scoped to the node they
land on, because blocking the branch would turn one defect into a dead book.

The detectors themselves live in **ContinuityEvaluation** (PLAN.md §8.4 owns that decision),
and siblings depend on contracts rather than on each other (§13) — so findings arrive as an
`EvaluationArtifact`, a file of a shared schema:

```bash
uv run litharness --database book.db ingest ../litharness-contracts/src/litharness_contracts/fixtures/golden/litrpg/findings.json
```

That path is the file in a contracts *checkout*; the same artifact ships inside the installed
package, so with no checkout at all `python -c "from litharness_contracts.fixtures import
golden_path; print(golden_path('litrpg', 'findings.json'))"` prints the one `uv sync` already
fetched.

```bash
uv run litharness --database book.db findings
```

When `LITHARNESS_CONTINUITY_EVALUATOR` (or the matching CLI option) is configured, every
durable evaluation streams the current manuscript, state and plan snapshots to that executable
as a UTF-8 live bundle. Its six deterministic rules run alongside the in-process contradiction
check; both result sets enter the same repair and re-detection workflow. The executable is
optional so installing and operating LitHarness does not silently depend on a sibling checkout.

`ingest` exits **1** when the artifact records detector errors, and says which stage failed.
An evaluation that did not finish is not a passing one, and until this the two were
indistinguishable: an artifact whose every detector failed reported "0 finding(s), 0 new, 0
blocking" and exited 0 over a book carrying six planted defects. The findings that *did*
arrive are still ingested — dropping them would trade one silent gap for another. This matters
for §17 Stage 2: "repairs verified by re-detection" means re-running an
evaluator over prose a repair just changed, and a repair invalidates the `version_id` every
downstream evidence span cites, so an errored run is the *expected* post-repair state.

Accepted drafts now enqueue a durable evaluation job. A complete run persists its findings
and, when it supplies a deterministic blocking finding with a `primary_span`, schedules one
located repair. The repair call can replace only that cited span; mechanical patch policy
checks the version, hash, scope, length and byte-for-byte preservation outside it. The finding
stays open until a separate evaluation explicitly re-runs its rule and no matching complaint
remains. Detector errors and omitted required rules fail the verification instead of turning
an empty result into a false pass. Repairs are serial and capped at three in one automatic
chain, so changing content cannot manufacture an unbounded stream of fresh job ids.

Re-ingesting the same artifact writes nothing: finding ids are content-derived and a re-run
converges rather than growing the queue, and a status a human already set is not overwritten.

```bash
uv run litharness --database book.db dismiss f-control-motif-rain
```

`dismiss` is the way past a **negative control** — both golden fixtures ship deliberate
devices a *correct* detector flags, like the mystery's repeated rain-on-glass motif and
Julian's intentional lie. Without it the only route past one would be to weaken the detector,
trading a true positive for a quiet queue. `--false-positive` says the detector was wrong
rather than the device deliberate; the distinction is what a later calibration pass reads.

Two things the gate will not do. A finding below `major` **annotates rather than blocks** — a
refusal costs a generation, so a finding not worth a second model call is not worth blocking
on. And an **uncalibrated critic cannot block at all** (§10.4): a finding whose
`confidence_basis` is not `deterministic` is recorded, and the gate says it ran, but it never
refuses. Promotion needs held-out calibration evidence, which is Stage 4.

## Reading it

The prose lives in the database as content-addressed node versions; `backup` produces
another database and `verify` never prints a word. `export` is how you read the book:

```bash
uv run litharness --database book.db export book.md
```

The suffix picks the format — `.md` or `.html`, overridable with `--format`, stdout if you
name no file. Both open with front matter the document derives from itself: revision id,
timestamp, word count, and a table of which scenes are drafted and which are still empty.
**Undrafted scenes are rendered as titled placeholders, never skipped** — the gap is the
most useful thing on the page, and a document that omitted it would read as a finished
short book rather than an unfinished long one. Export twice a day apart and the difference
is the progress.

`--book` / `--branch` are needed only when the store holds more than one; more than one is
ambiguous rather than defaultable, so it lists what it found and asks. `--revision` exports
an older revision instead of the head, which is how two points in time get compared —
revisions are immutable, so an export of revision N is reproducible forever apart from its
timestamp.

There is no PDF writer here, deliberately: owning font metrics and page breaking is not
worth it in a repo whose only runtime dependency is its own contracts package. The HTML
carries print CSS — `@page` margins, chapter page breaks, orphan and widow control — so a
browser's *Save as PDF* gives a readable book, and pandoc is the other one-liner:

```bash
uv run litharness --database book.db export book.html --format html
```

```bash
pandoc book.md -o book.pdf
```

## Judging it

The one input this system cannot generate. §10.5 routes a share of accepted scenes to a
queue as they are drafted, so evidence accumulates as a by-product of operation rather than
requiring a session someone has to schedule:

```bash
uv run litharness --database book.db audit --next
```

It prints the prose, not a reference to it, and with no provenance attached — §10.3 wants
blinded judgments, and RevisionBench measured 43–65% positional artifacts in unblinded
judges. The draw is derived from `(revision, node)` rather than randomly, so a replayed tick
picks the same scene and nobody can re-roll for a kinder sample.

```bash
uv run litharness --database book.db judge aud-… --would-stop --note "nothing changes; all setup"
```

`--keep-reading` / `--would-stop` / `--not-sure`, matching §1a.5's bar rather than a rubric.
Abstention is a real answer and is counted (§10.4). A verdict is recorded once and never
overwritten, because the first reading is the blind one.

```bash
uv run litharness --database book.db craft
uv run litharness --database book.db calibrations
```

`craft` shows the advisory numbers and what they do not measure; `calibrations` shows what
evidence exists that any of them predicts human judgment, and prints nothing today. That
emptiness is the honest state of §19's Quality clause.

```bash
uv run litharness --database book.db calibrate --metric craft.tricolon_rate.v0 --threshold 4.0 --direction above --precision 0.86 --holdout 50 --flagged 21
```

`calibrate` is the write verb, and the only route to a gate that can refuse a scene. It
records; it does not promote. Whether the evidence may block is recomputed at every draft
against the verdict set *as it stands then*, so it is printed here as information rather
than enforced here as a precondition — recording a measurement that cannot yet promote is
how evidence accumulates toward one that can, and the command says which you have.

`--flagged` is the number the metric actually fired on, and it is required because
precision is computed over the flagged set: a metric that flags one scene in fifty and
happens to be right scores 1.00 on a holdout of 50 while having shown nothing. The floor is
17 — the smallest flagged set whose 95% Clopper-Pearson lower bound on a *perfect* score
clears the 0.80 precision floor.

**A scene a promoted craft gate refuses is parked, not escalated and not redrafted.** The
book continues, because findings are node-scoped and a weak scene 3 must not stop scene 6;
`revive` is the way past one, exactly as it is for a standing finding. Retrying instead
would make the accepted candidate the one that beat the metric — best-of-three optimisation
against a craft proxy, which is the coupling [plan/craft-corpus.md](plan/craft-corpus.md)
§4.2 calls non-negotiable to prevent. A craft refusal also files **no exception**: §4.2
reserves those for what policy could not resolve, and a refusal is policy resolving.

What a parked unit is *not*, yet, is an unjudged sample. Craft metrics are recorded and the
§10.5 audit sample is drawn on the acceptance path, after the revision commits; a refused
candidate commits nothing, so its text is discarded and no sample is drawn. The gate does
not fill the audit queue by refusing, which would have been the best argument for parking —
and it is a gap rather than an oversight, because an audit sample is addressed by
`(revision_id, logical_id)` and a refused candidate has no revision id.

**The audit queue is a confirmation sample, not the plan for measuring quality.** A system
whose quality evidence depends on someone deciding to sit down will not produce any — the
measured throughput of that design is two verdicts against 104 exported pairs. The primary
calibration target remains *revealed* judgment: readers who followed, favourited or
abandoned published LitRPG at scale, already collected, with none of the demand
characteristics or positional artifacts that solicited judging has to be blinded against.
What it currently lacks is a surviving label: the measured candidate
(`followers / total_views`) failed its own control at the decile grain a calibration would
use — the deciles are recoverable from follower count alone at AUC 0.814
(`plan/stage-0-decisions.md` §56.3). [plan/craft-corpus.md](plan/craft-corpus.md) has the
refutation, the covariate control any successor label must state before it runs, and what
each remaining research direction is and is not valid for.

To rebuild the published-LitRPG reference profile (optional, needs the `corpus` extra and
downloads shards of a 12.5GB dataset — no prose is stored, only percentiles):

```bash
uv run --extra corpus python research/quality-measurement/build_craft_profile.py --out plan/craft-profile.json
```

## Development

```bash
uv run pytest
```

```bash
uv run ruff check . && uv run mypy
```

The package has executable architecture boundaries in `tests/test_architecture.py`:
`domain` imports only inward, providers and adapters do not import each other, application
code depends on structural capabilities in `application/ports.py` rather than SQLite, and
internal import cycles are rejected. Change that allow-list only as an explicit architecture
decision, not to make a convenient import pass. CI runs the suite on Python 3.11 and 3.13 on
both Linux and Windows, then builds the wheel once — from one checkout, since the contracts
rev in `uv.lock` is the whole of what it needs.

**Co-developing against a local contracts checkout.** `uv pip install -e ../litharness-contracts`
puts your checkout in front of the pinned rev for as long as the venv lasts; the next
`uv sync` reverts it, which is the property that keeps the experiment from becoming the
configuration. For fixture edits that are not yet committed anywhere, `LITHARNESS_CONTRACTS_ROOT`
points at a contracts checkout root and its golden books win over the installed ones. When the
contracts change is ready, advance the pin: bump `rev` in `pyproject.toml`, run `uv lock`, and
land that with the code that needs it in **one commit** — the pin is part of the behaviour,
not part of the infrastructure.

SQLite is composed behind the stable `SqliteStore` facade: durable jobs, controls, and plan
epochs live in `adapters/sqlite_jobs.py`, while immutable plan revisions and proposals live
in `adapters/sqlite_plans.py`. This keeps transaction boundaries explicit without making
application workflows depend on a monolithic concrete store.

The suite is model-free by default. `tests/conftest.py` sets `LITHARNESS_ENV=test` at
import, which makes the provider registry refuse to resolve any billing provider — so a
test run provably cannot reach a paid CLI. The live round-trip tests are skipped unless
`LITHARNESS_LIVE_PROVIDERS=1`.

## What is not built

Stated plainly, because a system that runs is easy to mistake for a system that works:

- **The reader → writer loop is wired and it has no evidence in it.** Until now nothing a
  reader said about prose reached the thing that writes the next prose, by any path. There is
  one now, and it is built as **two roles split by what each is licensed to answer** rather
  than by human-versus-machine: a **reader** owns valence (would I keep reading, which of
  these two would I rather continue) and a **judge** owns location and axis and never valence.
  The split is measured rather than chosen — three independent attempts to get a *verdict*
  about prose out of a machine died (a positional bias of 0.8151 over 568 decided comparisons;
  a VOID precondition at 0.6408 over 142; "keep reading" on 195 of 196 passages), and exactly
  one frame survived: asked to *name the difference* between two passages, the same model on
  the same pairs cleared three of three families.
  What exists: three axes with deterministic counters (`litharness axes`), a measurement
  firewall splitting readers and passages before any verdict is routed (`pools`), a path from
  steering-pool reader verdicts to a **direction** on an axis (`directions`), a judge channel
  that names *which axis and where* over a contrast pair and never which is better
  (`contrast`), composition into a draft prompt with provenance on the resulting scene
  (`feedback`, `blame`), and an ablation harness
  (`research/quality-measurement/feedback_ablation.py`).
  **What does not exist is a single reader verdict.** `audit_samples` is at 0 rows, no reader
  has been paid, no axis has a direction, and with no direction the judge half refuses before
  it spends anything — so the whole loop resolves to an empty feedback set and every book
  drafts exactly as it did before. The ablation's machine side reads `INERT_GENERATOR` on the
  fake provider and its reader side reads `UNDECIDABLE`, which is the honest state of both.
  Neither source can block: nothing on this path can construct a gate, and a reader-derived
  gate would still be a gate (§10.4).
  Designed and deliberately not built, each with its condition:
  a **certified single-axis transform** as a second source of direction pairs, if sibling
  yield or confounding makes siblings unusable; a **paraphrase sham** (same content, different
  surface) to catch a judge or counter firing on surface features carrying no reader-visible
  difference — a register entry rather than a task because certifying "same content" honestly
  is the hard part; and the **promise/payoff ledger** as a candidate counter family, which is
  the right shape (deterministic, span-locating, judge-free) and is strictly a *hypothesis*
  axis: it earns nothing until a human read names it or the discard corpus nominates it, and
  nothing at all until readers give it a direction.
  [plan/reader-judge-loop.md](plan/reader-judge-loop.md) is the design and its
  pre-registration.
- **A library folder, and it is a copy button rather than the publication pillar.**
  `book-library/`, republished after **every tick without being asked** and resolved beside the
  database it is derived from, so nothing writes into whatever directory a command was run from
  and a run against a scratch store takes its output away with it. `--no-library` opts out;
  `litharness library` rebuilds on demand. A book whose head has not moved is skipped, because
  revisions are content-addressed and "the head is what this shelf was built from" is exact —
  so a quiet system rewrites nothing, and the index carries **when it was last checked** beside
  **when each book last changed**, which are different questions and would lie if collapsed.
  It supersedes `exports/`. Two shapes, because they have opposite requirements. The
  **reading copy** is `export`'s document — the whole book, a progress table, and undrafted
  scenes as visible gaps, so two copies a day apart differ in a way you can read at a glance.
  The **pastable copy** is one file per chapter carrying none of that: no progress table, no
  revision id, and no title heading, because a serial platform takes the title in its own
  field and a heading in the body is published twice. Minimal HTML — only `<p>`,
  `<blockquote>` and `<hr>`, no classes or styles — as a fragment rather than a document, so
  "open it and copy" and "paste into an HTML source view" are the same file; a `.txt` sits
  beside each one because **this repository cannot verify how any particular platform's
  editor treats a paste**, and a fallback is the honest response to that rather than a claim.
  **A chapter holding an undrafted scene is withheld and counted, never emitted with a hole
  in it.** One scene is one chapter by default, which asserts nothing: production books hold
  no chapter nodes and no assembly scheme is decided, so `--chapter-scenes N` makes grouping
  an operator act rather than a guess.
  **What this is not is the serial-publication pillar**, which §62 cut after measuring it at
  two inert enum values. Of the seven things that entry found missing, this adds exactly one
  — the per-chapter export, as a file format — and none of the other six: no chapter-release
  unit, no recap generation, no publication policy object, no posting scheduler, no
  publication table. §62 also settled what publishing means here — the export, run when the
  book clears §1a.5's bar — and **no book has cleared it**, which the library's own index says
  where somebody about to paste will read it. Each shelf also carries a `NOTES.md` that is
  written once and never overwritten, because a human read is not only a progress check: a
  named defect is one of only two doors an axis can enter the registry by, and all three the
  system measures came from one read of one book.
  **On "publish it every few hours": the loop already beats that.** §63 cut the cron deployment
  (−1,103 lines, three tables) and named what replaced it — one process running `tick` in a
  loop, which `tools/run-loop.ps1` now writes down. With publishing on every tick the folder is
  as fresh as the book at all times, which no wall-clock schedule can improve on; when the loop
  is off there is nothing new to publish. `tools/schedule-library.ps1` exists for the case the
  loop does not cover and registers a task that runs `library` and **never `tick`**: §63 also
  removed the instance lease that made overlapping invocations safe, so a scheduled tick beside
  a running loop is exactly the case that no longer has a guard — while `library` is read-only
  against the store and safe to fire whenever. It does nothing without `-Install`.
- **A Director role: a personality that says what a book is, and never whether it is good.**
  The third role, and it is safe for a different reason from the other two rather than the same
  one. Every frame this project has buried was *evaluative and downstream* — handed prose that
  existed and asked how good it is. A Director is *generative and upstream*: it says what the
  book should be, before any of it exists, so it makes no measurement and cannot make an invalid
  one. `--director <name>` runs one; off by default, because a director is an arm and no
  director is its control.
  What exists: a content-addressed personality with a brief (`litharness directors`), one
  bounded directive per six accepted scenes, written into the same inbox a person writes into
  and **marked with its author** — and a distinctness control
  (`research/quality-measurement/director_distinctness.py`) that has to pass before two
  directors may be compared at all.
  **Four things it cannot do**, each closing a path that was open: it emits only the
  interpretive directive kinds, so it cannot issue a veto or a constraint — refusal is the human
  director's authority; it cannot produce a **locked** plan item by either lane, so its words
  cannot sit in every context packet wearing a person's standing; its brief may name what the
  book is about and not what good prose is, so it cannot pre-empt an axis the Reader/Judge loop
  is actively measuring; and **it is never shown the prose**, only the plan and the scene
  summaries, which makes "a Director may not evaluate prose" a property of what it was handed
  rather than an instruction it might drift from.
  **What is not established is whether any director is any good.** That is a reader question
  and it waits with every other reader question — and it is not free: §61 pre-registration (5)
  divides the superiority claim's confidence level by the candidate-book count, so **running N
  directors divides §61's alpha by N**. At three directors the headline is made at α/3. The
  distinctness harness prints that price rather than leaving it to be discovered.
  Also not built: directors that read their own books' reception, which would be a second
  steering loop with none of the measurement firewall's discipline.
  [plan/director-role.md](plan/director-role.md) is the design.
- **A template planner plus a bounded directive planner, not a full narrative
  generator.** `tick` does decide what to write next: a
  fixed six-beat sheet (`domain/beats.py`) is zipped against the book's live scenes and the
  next undrafted one is enqueued, least-progressed book first. Separately, immutable plan
  proposals are validated and accepted against a baseline, interpret directives atomically,
  detect concurrent changes, preserve rationale/model provenance, and roll back through a
  new forward revision. A model now produces one bounded proposal for each premise, arc,
  tone, or chapter note. The book-level outline writes one statement per scene plus a
  progression schedule; the promise/payoff ledger tracks what each scene opens, pays,
  and still owes — typed by kind, with due positions and planner-scheduled payoff
  windows surfacing into the drafting context as debts rather than as facts; and under
  `--plan-search`, K alternative beat-plans per span are drafted and selected by
  pairwise judgment (human verdicts first; a judge only when a current
  PREFERENCE-class calibration licenses it on the selection task). What does not exist
  is structural/mechanical plan critics or replacement of the fixed six-beat arc
  template.
- **A context packet with no relevance scoring.** It carries prior prose, locked
  constraints, open threads and POV-filtered state, and it is graded against the contracts
  `GoldContextSuite` — mandatory items present, forbidden POV leak absent. What it does not
  do is *choose*: under a budget that binds, it drops the oldest prose rather than the least
  relevant, because nothing here measures relevance. On six-scene fixtures the budget never
  binds, so that limit is currently invisible and will not stay that way at Book Zero
  length. Only the `draft_scene` operation is served; the suite's `evaluate` and `repair`
  cases have no implementation to grade and the suite says so rather than skipping them.
- **No craft gate, and the reason is measured — but the path to one is now wired end to
  end.** The blocking ladder is shape then integrity: a draft exists, is the right size, did
  not overwrite anything, and nothing unresolved stands against its node. Nothing *blocks* on
  whether the prose is any good (PLAN.md §1a). Two duplicate-detection craft metrics
  (`craft.scene_echo.v1`, `craft.repeated_span.v0`) are logged per accepted
  scene and can only annotate — `craft_gates` has no branch that could set `blocking`, and
  `PolicyDecision` raises on a blocking craft gate with no calibration.
  What changed is that the *other* door is now reachable and has a decided behaviour behind
  it: `calibrate` records evidence, `handlers` consults it on every draft, `promoted_gate`
  builds a blocking gate or refuses to, and a refusal parks the unit under
  `Veto.CRAFT_BELOW_BAR`. **Nothing about the book changes until a calibration exists**, and
  none does — with an empty table the wired path costs one indexed query and cannot construct
  a gate, which is what made it safe to build before the evidence. It is plumbing waiting on
  judgment, and the emptiness of `calibrations` is still the measure of the gap.
  The four line-level proxies this list used to lead with were measured against 13,000
  chapters of published LitRPG and
  **all four failed to separate declared-AI prose from human prose at the same date**; the one
  that looked promising turned out to be detecting the year. They are archived off the accept
  path in `research/quality-measurement/refuted_metrics.py`, with `plan/craft-profile.json`
  kept as the measured record. For how many candidate proxies
  stand refuted, [research/quality-measurement/BRIEF.md](research/quality-measurement/BRIEF.md)
  §2 is canonical — this sentence used to restate a count and the restatement was stale
  within days, which is exactly why the ledger owns the number. The blocker is human
  judgment, not effort — and the instrument for collecting it at scale is now built:
  the **pairwise preference engine** (`corpus-add`, `protocol`, `pools`, `pair-draw`,
  `pairs`, `pair-judge`, `pair-export`, `pair-import`, `win-rate`) runs blinded,
  position-swapped comparisons against matched published-human prose under a
  pre-registered protocol, with a reader-by-pair clustered lower bound on the win
  rate; [plan/preference-runbook.md](plan/preference-runbook.md) is the operating
  procedure. **`pools` is new and now comes first**: readers and passages are split
  into a steering pool and a measurement pool before the first verdict is routed,
  because the superiority claim dies if the prose was shaped by the readers who later
  judge it — and once reader verdicts reach a draft prompt that stops being
  hypothetical. Nothing draws or judges until the split is declared.
  `litharness audit` remains as the smoke-check queue whose deterministic
  draw the engine inherited; its verdict verb is now `read` rather than `judge`, since
  under the Reader/Judge split what it records is a reader's verdict (`judge` still
  works and warns). Structural instrumentation aimed at what moves readers —
  overdue promises and zero-delta scenes — is recorded per accepted scene, advisory
  until calibrated. A second channel is being *tested* rather than operated: asking a
  system-prompted model, in character as a reader, what a passage did to it — untested
  rather than refuted, since every refutation on the books bounds an expert-frame or
  distributional instrument instead. It reaches no gate, mints no row and has no CLI
  surface. Its first form is already dead: asked for an absolute verdict it answered
  "keep reading" to 195 of 196 passages across two model tiers, a constant function that
  no manipulation could move, and the pre-registered positivity floor fired. The successor
  asks the panel to *choose* between a passage and a manipulated copy of it, blinded and
  position-swapped — the shape the pairwise engine above already uses, and the only
  standing this channel could ever earn. It has now run, and **it discriminates without yet
  being a reader.** It clears the detection rung against its sham (0.906 vs 0.783, margin
  0.122), but the sham itself sits at 0.78, so much of what it separates is *edited-ness*;
  positional bias measures 0.587 (z = +4.73), so a real share of the rest is layout; and the
  one pre-registered arm that would have made it reader-specific ran **backwards** — removing
  sentences chosen for stakes hurt less than deleting the same word count at random. The
  battery says why: the panel catches every local manipulation and is near-blind to
  `transplant`, a length-matched graft from a different story, so it reads at
  clause-to-paragraph scale and may not be asked whether a scene belongs in its book. A 4B
  local model fails the positional-bias precondition outright, putting the capability floor
  above it. Nothing here mints a row and the ceiling is unchanged
  ([plan/persona-reader-validity.md](plan/persona-reader-validity.md) §5a,
  `plan/stage-0-decisions.md` §70).
- **The full deterministic pack is opt-in, and its live inputs are still thin.** Every
  accepted draft is automatically evaluated by `state.contradiction.v0`. When the
  ContinuityEvaluation executable is configured, the same durable job also runs all six
  game-system detectors over a live shared-contract bundle and feeds located findings into
  bounded repair and re-detection. Without that explicit configuration, operation remains
  in-process-only. Even with it, detector effectiveness is limited by the state and facts the
  producer can justify: current evidence is re-anchored, stale imported future-state evidence
  is omitted, and the extractor still understands only system voice. The process boundary is
  complete; richer live state production is not.
- **State extraction reads system voice only.** §12 step 5 now exists
  (`domain/extraction.py`): every accepted scene is read for the facts it establishes, the
  records are written in the revision's own transaction, and a candidate contradicting
  established canon is refused before it commits. That is what gives
  `state.contradiction.v0` an in-process producer — until it had one, the detector could not
  fire at all and Stage 2 had no trigger to build on.
  What it reads is the `[STATUS]` line the genre puts on the page, and nothing else. Nothing
  here touches prose-semantic facts like "Brandt knows about the letter", which need a model
  call that is deliberately not built. And it **mints nothing**: the story position is read
  back out of the book's own evidence and abstains where the book is silent. ~~Until
  `render_prompt` asks generators to emit system voice, extraction yields records only for
  prose that already carries it.~~ That change has landed — it is what the opening of this
  file means by "asks its generator to state game state on the page and reads that back",
  and this bullet contradicted the opening for a while by still calling it future. What
  remains true: a book whose scenes carry no `[STATUS]` line extracts nothing, which for a
  book outside the genre is abstention working as designed, not a gap.
- **Operator controls are not narrative plan edits.** A directive whose kind is `control`
  remains visible in the inbox; process control is the session itself — Ctrl+C stops the
  loop, and restarting is safe because ticks are idempotent. The planner does not
  reinterpret words like “stop” as story constraints.
