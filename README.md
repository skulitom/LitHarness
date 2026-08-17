# LitHarness

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

- **A template planner plus a bounded directive planner, not a full narrative
  generator.** `tick` does decide what to write next: a
  fixed six-beat sheet (`domain/beats.py`) is zipped against the book's live scenes and the
  next undrafted one is enqueued, least-progressed book first. Separately, immutable plan
  proposals are validated and accepted against a baseline, interpret directives atomically,
  detect concurrent changes, preserve rationale/model provenance, and roll back through a
  new forward revision. A model now produces one bounded proposal for each premise, arc,
  tone, or chapter note. The book-level outline writes one statement per scene plus a
  progression schedule; the promise/payoff ledger tracks what each scene opens, pays,
  and still owes with due positions surfacing into the drafting context; and under
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
  the **pairwise preference engine** (`corpus-add`, `protocol`, `pair-draw`, `pairs`,
  `pair-judge`, `pair-export`, `pair-import`, `win-rate`) runs blinded,
  position-swapped comparisons against matched published-human prose under a
  pre-registered protocol, with a reader-by-pair clustered lower bound on the win
  rate; [plan/preference-runbook.md](plan/preference-runbook.md) is the operating
  procedure. `litharness audit` remains as the smoke-check queue whose deterministic
  draw the engine inherited. Structural instrumentation aimed at what moves readers —
  overdue promises and zero-delta scenes — is recorded per accepted scene, advisory
  until calibrated.
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
