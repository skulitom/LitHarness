# Pruning inventory — what the tree holds that nothing runs, reads or cites

**Status: INVENTORY, 2026-09-03, deliverable 1 of `plan/handoff-pruning.md`.** Measured on
the tree at `2142d0f` (main `d88114b` plus `tools/replay_books.py`). Every count below is this
inventory's own tally on that snapshot, not a property of the project; the suite owns the test
total, `BRIEF.md` §2 the refutation count, the ledger its entries. Each row carries the evidence
that a thing is dead, what would notice if it were not, a disposition, and a status column that
this file updates as cuts land (`landed` with the commit) or are refused (`refused` with the
reason). Nothing here is a research claim.

**The replay that gates every cut.** `tools/replay_books.py` (commit `2142d0f`) copies each
stored book through SQLite's backup API, hands `extract_state` the records as they stood before
each scene was accepted, and compares what it mints with what the store holds by record id and
then field by field; it also snapshots the derived lines at every scene position. Baseline on
the four stores the generality track replayed (`runs/ab/pilot25/draw1b`, `draw2`, `draw3`,
`runs/ab/pilot24-third/draw3`): **8/8 identical, 0 skipped**, which is §203's own figure. Every
cut below is run against that baseline before its commit.

**How the rows were found.** Category 1: a script over every module-level definition and public
method under `src/litharness/` (function, class, constant), word-boundary grep for each name
across every `.py` under `src/`, `tests/`, `tools/` and `research/` and every `.md` under the
repo root, `plan/` and `research/`; a name is dead when no file outside its module references
it and its own module references it nowhere but the definition. `vulture` 2.16 at 60 percent
confidence was the second opinion: 80 reports, of which all but the nine below are enum
members, dataclass fields, protocol methods, or names the grep finds callers for
(`load_finding` has five test references, `contains_ref` thirteen). Category 2: every `.py`
under `tools/` and `research/quality-measurement/` against `RUNBOOK.md`, `BRIEF.md`, every
`FINDINGS.md` and results `.md`, `README.md`, `plan/`, the ledger, the tests, and the research
import graph. Category 4: `git cherry main <branch>` per branch (patch identity, not commit
count) and `git status` per worktree. Category 5: the helper bodies read, not their names.

## 1. Unreferenced code under `src/litharness/`

### 1a. Nine names with no reference anywhere but their own definition line

| name | where | evidence | what would notice | disposition | status |
| --- | --- | --- | --- | --- | --- |
| `RowFilter` (type alias) | `adapters/sqlite_roster.py:43` | defined, never used; `Callable[[sqlite3.Row], bool]` appears nowhere else | nothing; ruff and mypy pass either way | cut | landed, cut 5 |
| `SqliteStore.finding_counts` | `adapters/sqlite_store.py:1426` | not in `application/ports.py`, no caller, no test | nothing; `tests/test_store.py` covers the store's other finding methods | cut | landed, cut 5 |
| `SqliteStore.exceptions_for_job` | `adapters/sqlite_store.py:2125` | not in `ports.py`, no caller, no test; `exceptions` reads `open_exceptions` | nothing | cut | landed, cut 5 |
| `TickResult.did_work` | `application/conductor.py:71` | property never read; `cli.py` reads `outcome` directly | nothing | cut | landed, cut 5 |
| `Job.renew` | `domain/jobs.py:169` | lease renewal never called; leases are claimed with a duration and reclaimed on expiry, and `assert_held_by` is the check that runs | nothing; `tests/test_domain.py` covers claim, release and expiry | cut | landed, cut 5 |
| `version_map` | `domain/revision.py:418` | one-line alias of `Revision.version_ids` | nothing | cut | landed, cut 5 |
| `excerpt_hash`, `slice_canonical` | `domain/text.py:58`, `:73` | every span site hashes `content_hash(text[start:end])` on node content that is canonical by construction (`Node.__post_init__`) | nothing | cut | landed, cut 5 |
| `FakeProvider.append_responses` | `providers/fake.py:177` | no test or tool appends a response after construction | nothing | cut | landed, cut 5 |

One commit, no ledger entry: none of these is behaviour a reader of a book could notice, and
the commit message says so.

### 1b. The brief's named candidates, examined and not dead

- **`application/variation.py`.** Already gone: `530f40e` (2026-08-24) deleted it with
  `domain/variation.py` and `adapters/sqlite_variation.py`, and §105.5 is the null it
  measured. What survives is `tools/variation_repair_comparison.py`, which still imports both
  deleted modules and cannot run — category 2.
- **The reviser path.** `--revise` is opt-in since §196; `make_scene_draft_handler(revise=...)`,
  `revise_draft`, the reviser key in the policy digest, `revised_by` on the acceptance event
  and `pre_revision_drafts` in the store are all reachable under it, `tests/test_reviser.py`
  pins them, and §196.1 keeps the arm reachable by decision. `--no-revise` is a deliberate
  no-op kept so a §185 recipe still parses (`cli.py:5764`). One thing is stale rather than
  dead: the docstring of `make_scene_draft_handler` (`application/handlers.py:485-500`) still
  says *"`litharness run` passes `revise=not args.no_revise`, so production has the stage and
  `--no-revise` is the control"*, which §196 reversed (`cli.py:672-676` passes
  `revise=bool(getattr(args, "revise", False))`). Disposition: correct the docstring in the
  category 1a commit (landed, cut 5); refuse the cut.
- **`GAME_SYSTEM_DETECTOR_IDS`** (`application/evaluation.py:29`): the id vocabulary of the
  optional six-rule pack. `live_bundle_for` writes the ids into the ContinuityEvaluation
  bundle, `tests/test_continuity_evaluator.py` pins that bundle, `README.md` documents
  `LITHARNESS_CONTINUITY_EVALUATOR`, and `application/status.py:64` reports the books that
  print system state while no evaluator is configured. "Never run here" is true and is the
  documented default (§30: reported rather than defaulted). Refused.
- **The change roles.** Three readers, three facts: `domain/characters.py:198-233` reads
  `actor`/`performed_by` → `caused_by` → `effect` into `CharacterCause` (the README's
  "explicit reified links"); `domain/salience.py:342-404` reads `participant`, `effect`,
  `precondition`, `consumes`, `produces` as intervention candidates for the evidence audit;
  `gamesystem.changes_of` (§212) reads `participant` plus an integer `effect` on a
  `type change` node into the sheet's arithmetic. One reader per fact holds. Refused.

### 1c. Names referenced only inside their own module

Roughly ninety module-level names are referenced only within their module (constants,
helper classes, `cli.py`'s `cmd_*` functions bound through `set_defaults`). They are internal,
not dead, and no module under `src/litharness/` is imported by nothing (`domain/salience.py`
has one importer, the `reader-evidence-audit` command, and its own test). Nothing to cut.

## 2. Scripts with no runbook line

### 2a. `tools/` (the runbook is `README.md`, `AGENTS.md`, `CONTRIBUTING.md`)

| script | named by | disposition | status |
| --- | --- | --- | --- |
| `ab_redraw.py` | README, `tests/test_ab_redraw.py`, §201 to §212 | keep | — |
| `check.py` | README, AGENTS, CONTRIBUTING, CI | keep | — |
| `dashboard.py`, `dashboard.cmd` | PLAN.md, §149, `tests/test_dashboard.py` | keep | — |
| `interiority_packet_proof.py` | imported by `tests/test_context_cutoff.py:553`; `plan/interiority-packet-results.md` | keep | — |
| `run-loop.ps1` | README | keep | — |
| `schedule-library.ps1` | the ledger only (§63's entry, line 7085); its own header says when it is for and that you probably do not need it | keep; a README line would advertise what the header argues against | refused |
| `sentence_census.py`, `tells_census.py` | §199's *Measured (`tools/sentence_census.py` …)* and §199.6; they import `exemplars.load_shelf` and `domain.tells` and run | keep: the instruments behind recorded numbers | refused |
| `serial-pilot-setup.ps1`, `serial_pilot_check.py` | `plan/serial-pilot-1..6.md`, three ledger entries; `serial_pilot_check` imports only live modules and `setup` uses only live verbs | keep | refused |
| `variation_repair_comparison.py` | `plan/variation-session.md` only; imports `litharness.application.variation` and `litharness.domain.variation`, both deleted in `530f40e`, so it cannot run; its numbers are `plan/variation-comparison.json`, cited by §105.5 | cut, with a ledger entry (a research surface, dead since 2026-08-24) | landed, cut 4 (§214) |

### 2b. `research/quality-measurement/` (90 modules including the census subdirectories)

Seventy-six are named in `RUNBOOK.md`, `BRIEF.md`, a `FINDINGS.md` or a results `.md`. Of the
rest:

| module | evidence | disposition | status |
| --- | --- | --- | --- |
| `blurb_gradient`, `blurb_readers`, `chapter_measures`, `listing_arena`, `listing_arms`, `reader_transport`, `system-displays/system_displays.py` | libraries imported by named modules (`blurb_rewrite`, `blurb_perception`, `scorecard`, the blurb trio, `brief_capability`, `blurb_rewrite`/`blurb_shelf`, the four census scripts) | keep with their importers | — |
| `blurb_rewrite`, `blurb_shelf`, `blurb_tribunal`, `brief_capability`, `causal_salience`, `voice_descriptors`, `architect_register` | registered arms: `plan/blurb-rewrite-validity.md`, `blurb-shelf-validity.md`, `blurb-tribunal-validity.md` (RUN), `brief-capability-validity.md`, `causal-salience-interventions.md`, §150.6 (registered, unscheduled), three ledger citations; each has a test module | keep: a registered arm with no result is a promise, not bloat | refused |
| `number_context_run.py`, `register_census_run.py` | the ledger names each as *the driver* behind `results/number-context.json` and the register census (lines 16795 and 16043) | keep: the entry is the runbook line | refused |
| `idiom_fit.py` | §143.3's counter; the entry's table is its output and nothing else records the method | keep | refused |
| `rival_pool.py` | builds the `--rivals` pool README's `ab_redraw` recipe reads | keep | — |
| `scorecard.py` | `ab_redraw`'s scorecard; three test modules | keep | — |
| `blurb_perception.py` | the three quote-a-span probes §143.2 records as blind; `results/blurb-perception.json`; named by `plan/blurb-shelf-validity.md:32` (its transport class is reused) and `blurb_shelf.py:97` | keep: cited, and the brief refuses deleting a refuted arm's code | refused |
| `blurb_defects.py` | ran once (`results/blurb-defects.json`, 2026-08-26); cited by no document, test, entry or module; nobody read the result | cut, with the ledger entry of 2a; the result file stays as the record of the run | landed, cut 4 (§214) |

The sibling research directories are outside the brief's category (`research/loop/` four
modules and no `.md`, `progression-clause/` two, `structural-instrumentation/` one,
`certified-bounded-revision/`, `frontier-arm/`, `proof-carrying-prose/` one file each,
`plan-search/` and `sim-readership-backtest/` with runbooks, `preference-power/` and
`opening-parity/` with findings, `market/` two notes). Listed; not touched.

## 3. Handoffs whose work landed

| file | what it asked for | where that lives now | pointers into it | disposition | status |
| --- | --- | --- | --- | --- | --- |
| `handoff-listing-loop.md` (2026-08-25, header: historical, superseded 2026-08-27) | chapter output read, titles, a title-availability check | §139 (the loop wired, `application/titles.py`), `plan/reader-architecture-program.md` for the appetite path | §139, §142, `domain/voice.py:6`, `plan/dossier-voice-direction.md:20`, `plan/reader-read-5.md:219`, `plan/serial-pilot-7.md:7` | **keep**: its eleven-round listing table (genre nouns, number tokens, em dashes, words, second person; round 1 against the market) has no other home, and `voice.py` says the file owns it | refused |
| `handoff-reader-perception.md` (2026-08-26, header: historical, superseded 2026-08-27) | make the reader produce not judge; surprisal; show the shelf; four counters | every table row is in the ledger: 15/16 (§140), 16/16 without taste and 24/24 against the summits (§143, lines 14340-14341), uncashable terms 5.75 against 12.5-13.8 (§142/§143), the blind quote-a-span probes (§143.2), bigrams 0.302 against 0.101 (§143.3); tasks 1 and 3 became `plan/blurb-rewrite-validity.md` and `plan/blurb-shelf-validity.md`; the surprisal task is `plan/force-program.md`'s GPU-only note | `plan/blurb-rewrite-validity.md:4`, `plan/reader-architecture-program.md:18` | cut; repoint the two pointers to §143.2 | landed, cut 2 |
| `handoff-writer-recruiter.md` (2026-08-28, "Status: OPEN") | store-backed roster, `recruit` agent and `roster` suite, the twelve-shelf run | §146 (with §146.8 the run), §151 (one roster home); the rails are `plan/writer-roster.md` §5, which the handoff itself names as their owner | `src/litharness/adapters/sqlite_roster.py:12`, `application/roster.py:13,19`, `cli.py:471`, `domain/writers.py:61`, `tests/test_recruiter.py:3`, `tests/test_writer_roster.py:3`, `plan/reader-read-5.md:272` | cut; repoint the eight pointers to `plan/writer-roster.md` §5 and §146 (docstrings and one plan line, no behaviour) | landed, cut 2 |
| `handoff-maintainability.md`, `handoff-market-fit.md`, `handoff-reader-sims.md`, `handoff-pruning.md` (2026-09-03) | this week's briefs | in progress in their worktrees | — | not candidates; the pruning brief goes in this track's last commit | — |

## 4. Worktrees and branches (report only; nothing here is deleted by this track)

Registered worktrees (`git worktree list`):

| path | branch / head | state | note for the operator |
| --- | --- | --- | --- |
| `C:/DEV/LitHarness` | `main` at `d88114b` | — | the primary checkout |
| `.claude/worktrees/handoff-maintainability-plan-f1de79`, `…market-fit-plan-6f4026`, `…reader-sims-plan-420e53`, `…intelligent-feynman-119bfa` | the four 2026-09-03 briefs | active this week | — |
| `.claude/worktrees/pensive-hopper-c37de1` | `claude/festive-dijkstra-4b7cfa` at `ff623e0` | clean; `ff623e0` is on `main`; 0 unmerged patches | stale: removable once no session sits in it |
| `C:/Users/artem/.cline/worktrees/2be3b/LitHarness`, `…/fa55a/LitHarness` | detached at `a26d811` (2026-08-26) | clean; `a26d811` is on `main` | stale (the Ox Alpha trial's checkouts, §-recorded and merged) |

Not a worktree: `.claude/worktrees/github-ci-issue-28f539/` is an empty directory with no
`.git` file; removable.

Local branches, by patch identity against `main`:

- **On `main` by content, 0 unmerged patches** (25): `agitated-boyd-0dd39f`, `brave-bose-6f90ea`,
  `chapter-endings-108`, `clarity-t3t4-split`, `comic-beat-census-handoff-de1ce4`,
  `cranky-cerf-b9cbb9`, `fervent-pare-74177c`, `festive-dijkstra-4b7cfa`,
  `handoff-interiority-164412`, `handoff-numbers-go-up-40f3e3`, `handoff-promise-ledger-eab7ed`,
  `handoff-protagonist-plan-29c957`, `handoff-worldbuilding-plan-ae1861`,
  `judge-validity-pricing-9ea30a`, `latent-taste-perception-e0da96`,
  `litharness-architect-stage-5ee368`, `litharness-provenance-read-5d1a95`,
  `musing-satoshi-a2b90b`, `persona-reader-feedback-6f4365`, `persona-reader-feedback-ca03cd`,
  `royal-road-api-litharness-8e4104`, `royalroad-platform-priors-16e717`,
  `codex/maintainability-stage-2`, `worktree-agent-ad68d5b9b8487b690` (all `claude/` unless
  shown). Deletable by the operator.
- **Holding work nobody merged** (1): `claude/ox-alpha-trial-7f3a21`, one patch, `c8ef116`
  (2026-08-22): *thermal_watch's trip decision extracted into TripJudge, with tests* (+252/−21
  over `research/quality-measurement/thermal_watch.py` and `tests/test_thermal_watch.py`). The
  trial's other tasks landed in `8882a89`; whether this one was left out on purpose is the
  operator's to say.
- **This week's** (5): the four brief branches and `claude/intelligent-feynman-119bfa`.

Remote branches on `origin`: 14 merged by ancestry (`agitated-boyd`, `chapter-endings-108`,
`festive-dijkstra`, `handoff-numbers-go-up`, `handoff-promise-ledger`,
`handoff-worldbuilding-plan`, `litharness-architect-stage`, `litharness-provenance-read`,
`musing-satoshi`, `peaceful-cray-e02a5b`, `youthful-volhard-4bb21d`, `zen-carson-41952b`,
`zen-poincare-bed6c0`, `codex/maintainability-stage-2`); one holding a patch:
`claude/adoring-chatterjee-b5f092`, `24845e0` (2026-08-30), *Quiet ruff on the reviser-impact
counters without moving a number* (`plan/agent-impact/reviser-impact.md` and its script);
and this track's branch.

## 5. Duplicate test helpers

The census read bodies, not names, and the brief's premise holds for one family and not for
the homonyms it listed beside it.

- **The make-canon helper** — `dataclasses.replace(record, authority=ACCEPTED_CANON)` — is
  defined eleven times under six names: over one record in `test_integrity._accepted`,
  `test_two_systems._accepted`, `test_choice_points._accepted` (a field-by-field
  reconstruction with the same result), `test_world_slots.accepted`,
  `test_world_supersession.accepted`, `test_worlds.canon`; over a list in
  `test_gamesystem._canon`, `test_progression_gate._canonical`,
  `test_progression_prompt._accepted`; and inline in `test_genre_floor` (four sites),
  `test_outline`, `test_page_contract`. Disposition: `tests/helpers.py` with `accepted` and
  `accepted_all`, the local definitions replaced by imports. Status: landed, cut 3.
- **The canon `world_record` shorthand** — `world_record(subject, predicate, authority=canon,
  **kwargs)` — in `test_packet_register.canon`, `test_display_names._canon`,
  `test_extraction._canon`. Same helper file, `canon`. Status: landed, cut 3.
- **Homonyms that are different fixtures, refused:** `_canon` in `test_gamesystem` (a list),
  `test_progression_gate` and `test_two_systems` (whole seeds); `_record` in six modules (a
  dict, a relationship record, a snapshot with foreign evidence, a keyed snapshot, an event
  with a located span, a proposal); `_seed` in two; and `_system(**overrides)` in
  `test_choice_points`, `test_gamesystem` and `test_progression_gate`, three different systems
  of the same shape, where `test_gamesystem`'s docstring already gives the reason it is not
  shared: *a definition that could drift with somebody else's golden book would make these
  assertions about that book instead*. `rec` (`test_world_slots`) and `_record`
  (`test_schema_words`) are one-line aliases of `world_record` at its default authority and are
  left alone.
- No ledger-cited test name is a helper; none changes.

## 6. Documentation that restates a count

| where | what it says | canonical home | disposition | status |
| --- | --- | --- | --- | --- |
| `PLAN.md:659` | *787 tests passing + 8 opt-in live (2026-08-17 …)* in the current-state table for this repository | the suite | cut: strike in place, keep the pointer to the suite | landed, cut 1 |
| `PLAN.md:1964` | *the refutation ledger … canonical for the count, now stands at twenty dead* | `BRIEF.md` §2, which says twenty-one: the restatement has already drifted | cut: strike the number, keep the pointer | landed, cut 1 |
| `PLAN.md:1338`, `:2095`, `:2152` | *268 tests*, *119 passing tests*, *271 collected, 268 passing + 3 opt-in live* in the Stage 0 exit records | the suite, at those dates | refused: dated records of an exit, not current claims | refused |
| `PLAN.md:660-665`, `:2101`, `:2108`; `plan/litrpg-rules-pack.md:3` | sibling repositories' test totals (BookWorldState, RevisionBench, MirrorBench, ContinuityEvaluation) in a dated inspection table and a build spec's status line | those repositories' suites | refused: not this repository's to keep current, and `test_architecture` deliberately does not resolve them | refused |
| `PLAN.md:891`, `plan/promise-payoff-development.md:79` | *twenty-one proxies* in prose | `BRIEF.md` §2 | refused: prose in dated text, and the number matches the home today | refused |
| `research/quality-measurement/BRIEF.md:31` | *21 proxies dead* | it is the home | — | — |
| `plan/handoff-writer-recruiter.md:3` | *Status: OPEN* while §146 and §151 shipped it | the ledger | goes with category 3 | landed, cut 2 |

## Order of the cuts

Lowest risk first, one commit each, each after `uv run pytest`, `uv run ruff check .`,
`uv run mypy`, `git diff --check` and the replay against the baseline above; `git status` and
`git diff` on every shared document immediately before it is edited:

1. Documentation counts (6): `PLAN.md` lines 659 and 1964. No ledger entry.
2. Handoffs landed (3): delete `handoff-reader-perception.md` and
   `handoff-writer-recruiter.md`, repoint their ten pointers. No ledger entry.
3. Duplicate test helpers (5): `tests/helpers.py`. No ledger entry.
4. Scripts (2): `tools/variation_repair_comparison.py`, `research/quality-measurement/blurb_defects.py`.
   One ledger entry, since a research surface goes.
5. Unreferenced code (1a) and the stale reviser docstring (1b). No ledger entry.
6. This brief's own file, deleted in the last commit, with the ledger entry of step 4
   pointing at this inventory as the record.
