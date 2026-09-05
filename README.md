<p align="center">
  <img src="docs/banner.png" width="100%" alt="LitHarness — a constellation dragon rising from an open book in a workshop of one-eyed archive creatures">
</p>

# LitHarness

[![CI](https://github.com/skulitom/LitHarness/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/skulitom/LitHarness/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![MIT License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

LitHarness is an open-source Python system for autonomous, open-ended serial fiction. It
coordinates specialised LLM agents across listing, world design, planning, scene drafting,
continuity, repair, covers, and release packaging while preserving content-addressed manuscript
history and scene-grounded narrative state.

Its product objective is fiction a defined audience voluntarily continues and recommends, with
no human in the production loop. The operator may direct a book and accept or reject it at book
grain, but does not write, rank candidates, label passages, or train the system.

The hard unsolved problem is perception, not prose plumbing: LitHarness needs an **LLM-based
cognitive system that perceives literary quality well enough to behave as a readership**. A
reader prompt is only one possible interface to that capacity. The current mechanism families
and their evidence live in
[the reader-architecture programme](plan/reader-architecture-program.md); failed approaches and
their controls live in the
[quality-measurement brief](research/quality-measurement/BRIEF.md).

The production loop is real: it can create a listing and title, build and evolve a world through
the Architect, plan and draft scenes against recorded context, reject integrity failures, repair
located defects, preserve immutable revisions, and export a book and cover set. **No simulated
reader mechanism has yet earned the right to certify literary quality.** That distinction is the
project's most important status line.

For the full objective and roadmap, see [PLAN.md](PLAN.md) §1a and §17. Historical decisions and
reversals are preserved in [plan/stage-0-decisions.md](plan/stage-0-decisions.md); they are not an
operator manual. What the research has established so far, by question and with a pointer for
every result, is [RESEARCH.md](RESEARCH.md).

## Install

Python 3.11+ and [uv](https://docs.astral.sh/uv/) are required. The contracts package and golden
fixtures are pinned through `uv.lock`, so one checkout is enough.

```bash
git clone https://github.com/skulitom/LitHarness
cd LitHarness
uv sync --extra dev
uv run python tools/check.py smoke
```

Production generation uses the signed-in local Claude Code CLI, pinned to the frontier model in
`src/litharness/providers/cli.py`. There is no automatic weaker fallback: if the provider is
unavailable, work waits rather than silently degrading. Tests cannot reach a billing provider;
for an explicit model-free local run, set `LITHARNESS_FAKE_PAD_CHARS=400`.

Cover generation is separate. It uses signed-in Codex image-generation sessions, followed by
deterministic local typography, and needs the `cover` extra:

```bash
uv sync --extra cover
```

## Start a serial

The concept comes first (stage-0 §197 to §199). One writer invents the book before its
listing — who the person was, the one power nobody else has and the first time it works in
chapter one, what they want in their own words, the system's manner and look, how far the
ladder goes and what a step buys, what kills people in the first days, the turn and where it
falls, the first arc in three events, and two to four debts with the scene each is due by.
It is written to disk so the listing, the world seed and the outline are all drawn from the
same settled concept, and a concept that names its system with one of this house's own
machinery words is redrawn:

```bash
uv run litharness --database book.db --writer halloran \
  --exemplars book-library --exemplars-limit 3 \
  concept --scenes 24 --out runs/pilots/my-book
```

`--exemplars` names the shelf: openings and blurbs the operator places by hand under
`book-library/<Name>/Chapter1.txt` and `blurb.txt` (gitignored, never committed, never quoted
— an eight-word run lifted from one refuses the draft). The shelf is shown to the concept,
listing and scene writers as how this shelf sounds and sets the listing's sentence-length
ceiling. On scene drafts, tells counts are observations only: the ladder reports rates
against the shelf without rewriting sentences, blocking acceptance, or making extra model
calls. Removing a surface pattern does not establish that a replacement preserves meaning.
Without a shelf there is no tells observation or exemplar-leak gate.

The listing loop is then the entry point for the book. It writes the listing a reader sees
from the concept, records experimental appetite observations without feeding them back into
revision, checks the title for collisions, and creates the empty scenes carrying the concept
and its debts:

```bash
uv run litharness --database book.db listing \
  --writer halloran \
  --concept runs/pilots/my-book/concept.json \
  --person third \
  --scenes 24 \
  --out runs/pilots/my-book
```

Books carrying a concept receive scene plans before drafting, including six-scene pilots.
The planner sees which scenes share a chapter and chooses their events from the concept.
The writer also receives the concept as planned story, separately from established facts
and author locks. A missing or failed outline holds drafting for that book; `--no-outline`
is the explicit control that permits drafting without one. These are generation and
meaning-preservation safeguards, not evidence of literary quality.
Candidate and acceptance events preserve the exact provider draft and its SHA-256 before
format cleanup or an explicitly requested revision, so changes can be traced afterwards.
Automatic planning also waits for a concept-backed book's first missing scene before
drafting its successors. `status` names the unresolved scene and job; an empty locked scene
does not count as drafted. Other books can continue, and `revive` or `replan` can recover the
missing scene. Existing explicitly queued work keeps its queue order.
New concept-backed scene plans reach the writer without appended stat increases, mandatory
interface readings, cast limits, or a prescribed chapter-one ending. Their events determine
the milestone schedule. Status formatting remains available; a changed state is shown as a
result, while an unchanged panel appears only when the scene needs it. Legacy planning defaults
and explicit author locks remain in place.
The outline receives the complete concept, including what carries over when the story moves
under a second system, so its progression schedule can account for those intentions.
Declared world rules, costs, prerequisites, limits and exceptions are protected context.
The writer receives their existing text as operating constraints above scene-plan guidance,
with author locks retaining precedence; these facts are not duplicated in the ordinary fact
list. Hidden rules retain their disclosure boundary. If required rules or author locks cannot
fit the context budget, drafting refuses rather than omitting them. Planners also receive
explicit instructions to respect payment/activation order and declared quantities. These are
context and instruction safeguards, not a semantic check that certifies the resulting prose.
World facts are also distinguished from character knowledge: passing a fact through the POV
visibility filter makes it available to the writer, not automatically known by the character.

`--person` is a position, not a finding: `first` seeds one locked constraint every scene call
carries, `third` and the default seed nothing. The operator's position since read 19 is third
person. `--brief` still takes a story, a situation, a constraint somebody cares about — never
a shelf label — and an empty brief is a valid control.

`--writer` names a compiled cast writer or any writer the roster has accepted. The roster lives
in the open database unless `--roster-database` (or `LITHARNESS_ROSTER_DATABASE`) names the
installation's roster store, which is what lets a writer accepted once draft on every fresh book
database (stage-0 §151).

Use `new` when title and premise already exist (`--concept` carries a settled concept and
opens its debts on the promise ledger), or `import` for a contracts fixture or manuscript:

```bash
uv run litharness --database book.db new "The Toll Road" \
  --premise "A debtor works off an impossible debt along a System-governed road." \
  --scenes 24

uv run litharness --database fixture.db import --fixture litrpg
```

The default 24 scenes are one structurally closed six-chapter arc. Grow the same canonical
serial—without resetting character state, promises, numbering, or revision history—with:

```bash
uv run litharness --database book.db extend --arcs 1
```

Release “books” are derived packaging windows over that serial, not sequel databases.

Before drafting a new book, let the Architect establish enough world for its opening, inspect the
deterministic checks, then accept the proposals into canon:

```bash
uv run litharness --database book.db --writer halloran architect seed
uv run litharness --database book.db world check
uv run litharness --database book.db world accept
```

`world check` reports, beside the world's own contradictions, what the drafting gate would
refuse on this world before any scene (a declared shape the seed itself breaches), and
`world accept` refuses on that list the way it refuses a machinery name (stage-0 §200).
`world accept` is a recorded state transition, not a ranking step. After a chapter, `architect
grow` reconciles and extends the same world through the same constrained tool surface.

The whole recipe under one settled listing and concept, with a fresh store per arm, both
spend ceilings on every call, the simulated readership on chapter one after the shelf, and a
folder per arm that records the listing's digests, every command, the spend and the reading,
is `tools/ab_redraw.py`. Its experiment note must be written before an arm runs: a variant
comes from a diagnosed defect, never from undirected variation (stage-0 §105).

```bash
uv run python tools/ab_redraw.py --experiment my-book --arm draw1 \
  --listing runs/pilots/my-book --writer halloran \
  --database runs/ab/my-book/draw1/serial.db --library book-library \
  --scenes 6 --chapter-scenes 2 --person third \
  --rivals research/quality-measurement/derived/rivals.json \
  --max-cost-usd-per-day 40 --max-tokens-per-day 20000000 \
  --extra-arg=--exemplars=book-library --extra-arg=--exemplars-limit=3
```

## Run the production loop

One `tick` performs one bounded, restart-safe unit of work. The ordinary operating model is one
foreground process running ticks until interrupted:

```powershell
.\tools\run-loop.ps1 -Database book.db -DelaySeconds 15
```

Or run one unit directly:

```bash
uv run litharness --database book.db tick
```

Accepted scene revisions, policy decisions, state extraction, follow-up evaluation, events, and
library publication are committed through the SQLite store. A killed process leaves a reclaimable
lease; replay converges rather than duplicating accepted work.

`tick` exits `0` after successful work or ordinary idleness, `1` when a unit failed or parked, and
`2` for an operational fault. Budget ceilings are global options and are checked before provider
calls:

```bash
uv run litharness --database book.db \
  --max-invocations-per-day 40 \
  --max-tokens-per-day 500000 \
  tick
```

Useful operating views:

| Command | Purpose |
| --- | --- |
| `status [--json]` | queue depth, attention, daily usage, and spend |
| `jobs [--status parked]` | queued or blocked work |
| `why --scene N` | the prompt, decision, and evidence behind one scene |
| `events` | append-only state-change history |
| `plans` | immutable plan lineage and its proposals |
| `state`, `characters`, `world summary` | current canon and world state |
| `prompts [--role ROLE]` | labelled representative requests: role, material, schema, tools, and effective size |
| `prompts --role scene --scene N` | the exact frozen scene request, provenance, section pressure, omissions, and repeated material |
| `verify` | rebuild revisions and verify hashes and policy coverage |
| `backup PATH` | online SQLite backup, safe while ticking |

Run `uv run litharness COMMAND --help` for the authoritative option list.

## Direct and recover

Direction enters an inbox and becomes a new immutable plan revision before it can affect prose:

```bash
uv run litharness --database book.db directive \
  "No combat in the midpoint." --kind constraint
uv run litharness --database book.db directives
uv run litharness --database book.db plans
```

Explicit constraints and vetoes are preserved verbatim and locked. Interpretive notes receive one
bounded proposal whose scope, locks, and base revision are validated outside the model. Locked
author decisions travel at system authority after lower-authority writing aids. Raw chapter-reader
reactions never enter scene drafting or story planning. A qualified reader mechanism may instead produce an
immutable editorial intervention, and only `satisfy` or `subvert` interventions enter this same
machine-authored directive and plan-revision path; conflicts with locks are surfaced rather than
silently overridden.

Recovery is explicit:

- `revive JOB_ID` returns a parked unit to the queue after its blocker is cleared.
- `replan` issues still-draftable beats under a fresh plan epoch.
- `revert-plan REVISION` restores an earlier plan as a new head; history is never rewritten.
- `revert REVISION --book ... --branch ...` does the same for manuscript revisions.
- `exceptions` and `resolve` record cases policy could not settle; resolving does not requeue.

## Story state and time

State records live at stable scene coordinates and retain the evidence span that established
them. Model-facing views are projections of that ledger: a writer entering a scene sees the
prior boundary; a caller stopped within a scene sees only facts whose evidence has already
ended; a Director may see the latest accepted boundary; POV-restricted knowledge reaches only
the named character. Superseded wants, standings, and other changing assertions are labelled as
history instead of being presented beside their replacements as simultaneously current.
The outline sees this projection at the arc's entry. Interpretive planning sees it through the
furthest accepted scene together with accepted/draftable scene status and current-hash summaries;
that lane cannot revise an accepted scene.

Chapter, arc, and fifty-chapter volume state are therefore derived snapshots, not separate
editable sheets. SQLite revisions and events are authoritative. Git is appropriate for reviewed
checkpoint exports and disaster recovery, but not as a second mutable canon database.

Character sheets expose only explicit reified `actor/performed_by → caused_by → effect` links;
a free-text want is never inferred to have caused an action. Promise rows can carry optional exact
opening and payoff spans when the summary answer supplies uniquely locatable quotes. Historical
or unlocated rows remain usable debts, but cannot become hidden answer keys in a reader battery.

## Integrity and continuity

Every candidate passes deterministic shape and integrity checks. Existing blocking findings park
work before generation; candidate-local findings can trigger bounded, span-limited repair and
independent re-detection. Findings below the blocking threshold annotate rather than spend another
generation.

The in-process contradiction check runs automatically. The optional six-rule LitRPG pack can be
connected through the ContinuityEvaluation executable:

```powershell
$env:LITHARNESS_CONTINUITY_EVALUATOR = \
  "C:\DEV\ContinuityEvaluation\.venv\Scripts\continuity-evaluate.exe"
```

External evaluators enter through a shared `EvaluationArtifact`:

```bash
uv run litharness --database book.db ingest findings.json
uv run litharness --database book.db findings
uv run litharness --database book.db dismiss FINDING_ID
```

`dismiss` records that an intentional device or false positive should no longer block; it does
not delete the finding.

## Simulated readers

The readership is also a port another pipeline can call (stage-0 §221): `application/instrument.py`
takes a passage, an audience (a domain pack, a roster, a population) and a currency, stops the
readers part-way, and returns a content-addressed record — the continue/abandon/return
distribution per reader with each reader's own sentence, a validity block that names every rail
and says what it did and did not do, the transport failures, and the hashes it was computed from.
There is no score and no verdict slot, and the record refuses one added later. `instrument.report`
renders the Markdown a downstream pipeline pastes into its README or model card, from the record
alone. Domains are packs under `src/litharness/packs/`: `litrpg` is the house's readership and
`plain` reads anything with no genre, no rival and no craft essay; the application layer imports
only the seam, never a pack.

The simulated readership can stop part-way through the latest drafted scene, or one named scene:

```bash
uv run litharness --database book.db readers
uv run litharness --database book.db readers --scene 4
uv run litharness --database book.db readers --history
```

The request is no longer a cold scene: it includes earlier scenes in the current chapter, two
recent chapters in full, compact current-hash memories from the preceding four chapters, and that
same reader's previous stopping-point memory. The window stays bounded as the serial grows and
never includes prose after the stop point. Reader output is behavioural—continuation,
anticipation, abandonment—not a literary score. Reader roles are split between steering and
measurement pools so a book shaped by a reader cannot later be certified by that reader. The
architecture is wired, but its ability to perceive quality is still under validation; see the
[reader-architecture programme](plan/reader-architecture-program.md) for current work rather than
inferring validity from the existence of the command.

Automatic chapter checkpoints are opt-in:

```bash
uv run litharness --database book.db --reader-checkpoints tick
```

The four steering requests are frozen as durable jobs when the final scene of a chapter is
accepted. Their observations record the exact mechanism version, source revision and content
hash, persona/prompt/system/schema/context digests, provider, model, and response. The bundled
`reader.anticipation.v0` mechanism is registered as `experimental`, so these records are inert:
they cannot enqueue editorial interpretation or affect planning. A later mechanism version may
be registered as `qualified` only with an evidence digest. Complete qualified panels are reduced
to one decision—`satisfy`, `defer`, `subvert`, `refuse`, or `challenge_lock`—before any direction
can reach the plan. A deterministic fingerprint check refuses directive bodies that repeat a
reader's six-word phrase (or an eight-word span from a longer answer), preventing the old
reader-vocabulary transcription failure from returning through the controller. Experimental and
qualified observations remain separate records even when they read the same scene. Registering a
new `withdrawn` version closes both future panels and already-queued controller work before spend.
Accepted target scenes record a durable realization linking intervention, directive, plan
revision, manuscript revision, and content hash; this proves the intervention reached prose, not
that it improved prose.

The remaining research boundary is executable without a model:

```bash
uv run litharness --database book.db reader-evidence-audit --out generated/reader-audit
uv run litharness --database book.db reader-mechanism status
uv run litharness --database book.db reader-mechanism qualify --evidence qualification.json
uv run litharness --database book.db reader-mechanism withdraw --reason "transfer regressed"
```

The audit validates current-revision evidence spans, counts state, event, progression, character,
and promise candidates independently, classifies their anchor distance from adjacent chapter
through growing serial, and emits a prose-free registration manifest, unlabeled
`battery.public.json` packets, and a physically separate `battery.private.json` scoring key.
Damage and sham siblings must have identical shallow edit fingerprints. Qualification
accepts one closed evidence-artifact shape and requires held-out books and transformations,
memorisation and fingerprint controls, full-volume/cross-volume/growing-prefix results, transfer,
and the fixed operator acceptance test all to have passed. It never runs or trusts a model by
itself. The bundled mechanism remains experimental until such an artifact exists.

Listing appetite answers are likewise experimental evidence only. They remain in `listing.json`
but no longer have a renderer or revision path back into the listing writer.

Real readers are the reason to publish the books, but their behaviour never feeds generation,
planning, selection, calibration, or gating.

## Covers, library, and export

Generate several independent cover options after the book exists:

```bash
uv run litharness --database book.db cover --variants 4
uv run litharness --database book.db cover --volume 2 --variants 4
```

Codex produces text-free 2:3 art; LitHarness adds the exact title and publication author locally
and writes 400×600 PNGs plus a manifest under the book's library shelf. A volume run writes its
own set under `volumes/VolumeN/covers/`, marks that release in the prompt and manifest, and keeps
the same canonical book and revision identity. The default author is `Skulitom`. Use `--art` to
finish existing art without another generation, `--reference` for a layout reference, and
`--art-direction` or `--description-file` for volume-specific visual context. Covers are
generated, not ranked or critiqued.

The derived library is refreshed after each tick and skipped when the book head has not moved:

```bash
uv run litharness --database book.db library
uv run litharness --database book.db export book.md
uv run litharness --database book.db export book.html
```

The library contains a whole-serial reading copy, paste-ready chapter fragments, and derived
release volumes in globally numbered fifty-chapter windows. Change only the packaging with
`--volume-chapters`; state, promises, characters, revision identity, and chapter numbering remain
continuous across every boundary. An incomplete final volume means work in progress, not an
ending. Incomplete chapters are withheld from paste-ready output while reading copies show their
gaps explicitly. The library is a file handoff, not a posting scheduler or publication platform.

The release queue is the operator's, and the tool never posts (stage-0 §221):

```bash
uv run litharness --database book.db --chapter-scenes 1 release stage --chapter 1 --slot 2026-09-10 --tag AI-Generated --tag LitRPG
uv run litharness --database book.db release approve rel-… --by "your name"
uv run litharness --database book.db release record-posted rel-… --by "your name"
uv run litharness --database book.db release show
```

`stage` writes the chapter's pastable copy under its content hash into the shelf's `release/`
folder, which no republish touches; `approve` re-renders the chapter and refuses if the book has
moved under the entry; `record-posted` is the operator saying, afterwards, that the approved copy
went up by hand. The AI-Generated tag is a required field the operator states, not a default, and
the author note carries the disclosure that names this repository. There is no `post`.

## Repository map

- `src/litharness/domain/` — rules and value objects; imports only inward.
- `src/litharness/application/` — workflows over structural ports.
- `src/litharness/packs/` — domain packs behind the evaluator's seam; `litrpg` and `plain`.
- `src/litharness/adapters/` — SQLite persistence and artifact translation.
- `src/litharness/providers/` — pinned model transport and deterministic fake.
- `migrations/` — append-only, checksummed SQLite migrations.
- `tests/` — behavior, architecture, replay, and safety contracts.
- `research/quality-measurement/` — isolated experiments and committed text-free results.
- `plan/` — active designs, experiment registrations, and historical decisions.
- `runs/`, `book-library*/`, `exports/`, and `*.db` — ignored local artifacts.

## Development

Read [AGENTS.md](AGENTS.md) and [CONTRIBUTING.md](CONTRIBUTING.md) before changing code;
[docs/system-model.md](docs/system-model.md) says where each fact the loop reasons about lives,
which function reads it, and which test notices a change. Use the
four-second core loop for immediate feedback, or let the checker select a conservative slice from
the working tree:

```bash
uv run python tools/check.py smoke
uv run python tools/check.py changed
```

The broader lanes are explicit and identical across platforms:

```bash
uv run python tools/check.py quick
uv run python tools/check.py full
```

Before committing or handing off a completed change, run the comprehensive check:

```bash
uv run python tools/check.py handoff
```

Direct pytest commands remain useful while debugging one failure; use `-n 0` when ordering or
captured output matters. The architecture suite enforces dependency direction and import-cycle
freedom. Tests set `LITHARNESS_ENV=test`, which makes resolving a billing provider an error;
live provider tests are opt-in through `LITHARNESS_LIVE_PROVIDERS=1`.
