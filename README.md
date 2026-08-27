<p align="center">
  <img src="docs/banner.png" width="100%" alt="LitHarness — a constellation dragon rising from an open book in a workshop of one-eyed archive creatures">
</p>

# LitHarness

LitHarness is an autonomous fiction-production system for open-ended serials. Its product
objective is fiction a defined audience voluntarily continues and recommends, with no human in
the production loop. The operator may direct a book and accept or reject it at book grain, but
does not write, rank candidates, label passages, or train the system.

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
operator manual.

## Install

Python 3.11+ and [uv](https://docs.astral.sh/uv/) are required. The contracts package and golden
fixtures are pinned through `uv.lock`, so one checkout is enough.

```bash
git clone https://github.com/skulitom/LitHarness
cd LitHarness
uv sync --extra dev
uv run pytest
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

The listing loop is the normal entry point. It writes the listing a reader sees, revises it from
steering-reader expectations, checks the title for collisions, and creates the empty scenes:

```bash
uv run litharness --database book.db listing \
  --writer halloran \
  --brief "A debt collector discovers every debt is also a spell." \
  --scenes 24 \
  --out runs/listings/debt-book
```

An empty brief is a valid control. Use `new` when title and premise already exist, or `import` for
a contracts fixture or manuscript:

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

`world accept` is a recorded state transition, not a ranking step. After a chapter, `architect
grow` reconciles and extends the same world through the same constrained tool surface.

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
author decisions travel at system authority after lower-authority writing aids; reader reactions
remain audience evidence in user material and cannot override them.

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

The simulated readership can stop part-way through the latest drafted scene, or one named scene:

```bash
uv run litharness --database book.db readers
uv run litharness --database book.db readers --scene 4
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

## Repository map

- `src/litharness/domain/` — rules and value objects; imports only inward.
- `src/litharness/application/` — workflows over structural ports.
- `src/litharness/adapters/` — SQLite persistence and artifact translation.
- `src/litharness/providers/` — pinned model transport and deterministic fake.
- `migrations/` — append-only, checksummed SQLite migrations.
- `tests/` — behavior, architecture, replay, and safety contracts.
- `research/quality-measurement/` — isolated experiments and committed text-free results.
- `plan/` — active designs, experiment registrations, and historical decisions.
- `runs/`, `book-library*/`, `exports/`, and `*.db` — ignored local artifacts.

## Development

Read [CONTRIBUTING.md](CONTRIBUTING.md) before changing code. The required handoff checks are:

```bash
uv run pytest
uv run ruff check .
uv run mypy
git diff --check
```

The architecture suite enforces dependency direction and import-cycle freedom. Tests set
`LITHARNESS_ENV=test`, which makes resolving a billing provider an error; live provider tests are
opt-in through `LITHARNESS_LIVE_PROVIDERS=1`.
