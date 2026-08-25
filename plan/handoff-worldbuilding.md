# Handoff: worldbuilding — the world the planner was never told, the share of it that reaches the page, and the one lever that is checkable

You are working in `C:\DEV\LitHarness`, an autonomous fiction-production system whose goal is
superhuman popcorn-genre books (LitRPG, progression fantasy, isekai) with no human in the
production loop. Your task is one bounded piece of the worldbuilding programme: make the world the
Architect forges something the **scene plan** is written against, and measure — with a counter that
has a sham — how much of a forged world reaches the page before and after. Nothing here asks you to
make worlds better, pick worlds, or say whether a book with a world on the page is a better book.
Read the boundaries before you read the tasks.

File names, line numbers and measurements below were verified on 2026-08-22 against `main` at
`83de11c`. If the repo has drifted, the repo wins; re-anchor rather than following this document
into a stale reference. Parallel sessions run on this repository — `git status` before you commit,
commit only your own files, and see "Coordination" below for the worktree that is touching the
system you must not touch.

## Why this exists (context you need, then stop reading context)

**The Architect is built and measured, and it has never been asked whether anyone uses what it
makes.** Stage-0 §107 and [`plan/world-architect.md`](world-architect.md): three live forges, nine
worlds, $4.38; every world cleared the four deterministic gates (collapse, ≥3 consequence domains
per rule, manifestation coverage 1.00, RS1 deny-list). The world Serial Pilot 2 ran on — *First In
Time*, water law literalised — is 329 records, 76 edges, 7 rules, 28 claims with recorded answers,
6 mysteries, 20 hidden claims at scene one. It reaches the writer: a flat 229–231 "established
facts" per drafting prompt, ~46% of a 16,000-token packet, `context_omitted = 0` for the whole
book, and the hidden section drops 20 → 19 → 18 at exactly scenes 4 and 7, the two the world
scheduled ([`plan/serial-pilot-2.md`](serial-pilot-2.md) §6.2). Two eight-scene runs of that book
exist (run A with the iceberg inverted by defect 10; run B corrected — 7,812 words, $5.89, 21 of 21
decisions ACCEPT).

Three facts decide this task. Each was verified in code or in the run record today; verify them
again before you act on them.

1. **Both authors of the scene plan are world-blind.** The sentence at the end of every drafting
   prompt — `This scene: {plan}` (`src/litharness/application/planner.py`, `render_prompt`,
   `plan_line = scene_plan_line(scene_plan)` near line 477) — is written by one of two calls.
   `outline.render_outline_request(premise, beats, *, base, seed, promises)`
   (`src/litharness/application/outline.py:208`) writes the one-sentence statement for every scene
   and is handed the premise, the beat sheet, the starting status sheet, and open promises *as
   owed*. `narrative_planner.render_request(base, directive, scene_ids)`
   (`src/litharness/application/narrative_planner.py:144`) applies a director's or Architect's
   directive and is handed the plan and the directive body. **Neither is handed a state record.**
   The only canon `outline` reads is the `status_snapshot` (line 823), for milestones. So the
   rules, the consequences the design calls "each a plot engine" (`plan/world-architect.md` §4
   item 5), the cast with their wants and ties, the creatures, the criteria, and every hidden
   answer with its reveal scene arrive at the *writer* under "Established facts" — and the plan
   the writer is told to execute was written by a model that never saw any of it. This is §108's
   shape one layer up: there, the rule that reached no prompt; here, the world that reached no
   plan.
2. **What the world did on the page is an observation and not a measurement.** Pilot 2 §6.1, read
   rather than counted: *the ladder appears as two spoken dates, the doctrine is never explained,
   the bestiary shows up as one clause about moths.* Nothing counts how much of a 329-record world
   is ever named in 7,812 words, by which entity role, whether the scene plan named it first or the
   writer improvised it, and how much of that the premise alone already carried. The closest
   instrument is `research/quality-measurement/state_coverage.py` — correspondence, not density,
   with a control that can kill it — and it measures a different thing.
3. **No reader exists to say whether it matters.** The BCR has no seated model (§94.7); the fitness
   books it needs were delivered (20 of 20, `exports/fitness/`) and the seating has not been rerun;
   F3 reads structure and not taste (§98.4). So nothing in this task may claim a world on the page
   is a better book. What *can* be measured is whether the world reaches the plan, whether it
   reaches the page, and whether changing the first changes the second.

Why this is worth doing in the operator's own terms, once: readers come for unique abilities and
their interactions with the world; the reader should feel an iceberg under fast, plain prose; a
palette, never a checklist. A consequence cascade that never reaches the plan can drive a scene
only by the writer's improvisation against a plan written without it — which is what "wallpaper"
means mechanically.

That is the whole context. Everything below is the bounded work.

## The hard boundaries

These are not preferences. Work that breaks one of them is worse than work not done.

1. **Naming-uptake is the only thing the counter reads, and every number is labelled so.** A
   coined noun on the page is not the fact being *used* — pilot 2 §4's S2 lesson, and the reason
   `tools/serial_pilot_check.py::_disclosure` (line 295) is a note and never a check. And absence
   of a name is not absence of honouring: the hidden section is *supposed* to go unnamed. Report
   hidden claims in their own row and never count their silence as a defect. Do not write, or
   let a prompt imply, "name the world's features" — a counter that becomes the target is the
   shallow-because-easy failure §1a.1 exists to refuse.
2. **No model ranks anything and nothing here declares a bar.** No judge chooses between arms,
   plans or prose; the comparison is counters plus a sham. No axis admitted, no directive
   authored, no new judge. Distributions before bars — and the only pass/fail outcomes in this
   task are the leak check and the sham, both of which can actually fail (declared-bars rule:
   range, direction, unit, non-emptiness).
3. **The leak rail.** A planner may be told a hidden answer *only* to place its reveal. No plan
   item written for a scene before a claim's reveal window may contain that claim's answer, and an
   arc answer with no in-book scene may never appear in any plan item. Check it deterministically
   with `summarize.check_open_threads` (`src/litharness/application/summarize.py:237`, the
   shipped distinctive-word-majority matcher) against every statement, *and* leave the writer-side
   invariant untouched: the hidden section's packing above the facts and the `disclosure_at`
   coordinate (`src/litharness/domain/context.py`, `SECTION_ORDER` line 102, hidden render
   308–322) are not yours. If the world-aware planner leaks and you cannot close it by *what you
   hand it* (answers only on the window scene's entry; questions and windows for the rest), **stop
   and write that up instead**. A plan that states the answer at scene one is worse than the
   blindness you were sent to fix.
4. **A book that declares no world is byte-identical to before.** `render_outline_request` and
   `render_request` must produce the identical payload when there is no world brief. The pattern
   is `tests/test_worlds.py::test_a_packet_with_no_world_records_is_byte_identical_to_before`;
   the golden fixtures are the proof.
5. **RS1 / C3.** No real work, author, brand, game or system named, quoted or imitated in anything
   you write into a prompt. The Architect's rails are unchanged: it proposes, it locks nothing,
   `forge --pick` is the one exit to canon, and you do not re-forge — the worlds you need exist.
6. **Do not touch** `application/summarize.py`, `domain/promises.py` or anything about why the
   ledger pays nothing (S5 — a parallel session owns it, see Coordination); the personas and the
   panel; retrieval or per-scene selection of world facts for the *writer* (`plan/world-architect.md`
   §5.1 is a design note and stays one); the second extractor family; `plan_search`. New files
   where you can; do not restructure shared planning documents.
7. **Spend.** ≤ $25 API, no GPU needed — every counter here is deterministic and runs under
   `uv run python`. One CLI arm at a time; read `transport_failures` before reading any number
   (`claude -p` fails under box load and still returns). The fake provider first, always.

## Task 0 — pin the blindness, then reproduce it on the pilot's own world

Zero cost. Build the pilot world exactly as `tests/test_architect.py:611`
(`test_the_pilot_package_regenerates_the_world_it_was_run_on`) does — `architect.Candidate(0,
package["world"])` over `plan/serial-pilot-2-world.json`, `architect.records_for(...,
authority=ACCEPTED_CANON, scenes=8)` — and render both planner requests against it:
`render_outline_request(world["premise"], beats, base=...)` with the fixture shape in
`tests/test_outline.py:136` (`new_book`, `beats_for`, `arc_template`, a stub `_Base`), and
`narrative_planner.render_request` with one of the Architect's own directives
(`architect.directives_for(candidate)`, `src/litharness/application/architect.py:1121`).

Then assert, and pin as a test with a docstring that names the date and the fact: the payload's
coined-noun set (`worlds.key_nouns`, `src/litharness/domain/worlds.py:761`, restricted to the
payload text) is exactly the premise's; no `world_rule`, `consequence`, `claim.content` or
`manifests_as` value appears in either payload as a substring. That test **passes on `main` today**
— it pins the blindness. Task 2's twin ("a forged world reaches the outline request") is the one
that must **fail on `main` as it stands**, and you write both.

Write down, in the results note, the full list of what the outline call *was* handed for pilot 2
(premise; beat functions; the six seeded promises as owed with `due_by_scene`; no sheet, because
*First In Time* prints no status line) so that nobody reading the census later thinks the planner
knew nothing at all. It knew the questions and the windows. It did not know the answers, the
rules, or a single name beyond the premise.

## Task 1 — the uptake census, with its two controls built before it is read

Zero provider cost. New module `research/quality-measurement/world_uptake.py`, shaped like
`state_coverage.py` (pre-registration as a frozen constant block copied into its result file;
`--selftest` free leg first).

**Substrate.** The pilot world as above. The prose: run A and run B exports,
`.claude/worktrees/litharness-architect-stage-5ee368/pilot2/runs/first-in-time-run{A,B}.md`
(read-only from there; copy what you need, never commit a `.db`). The scene plans and the frozen
drafting prompts: `serial2.db` (run A) and `serial2b.db` (run B) in the same worktree — plan head
items of kind `SCENE_PLAN` via `plans.scene_plan_for`, and the stored `scene_draft` job payloads
(the `debug-book` skill and `litharness why` are how provenance is read here). Run A is a
different condition (five of six answers handed over as fact from scene one); report it
separately and label it, never pooled with B.

**The counter.** For every declared feature — each subject carrying an `entity_role`
(`worlds.entity_roles`, line 376), each rule, each consequence, each criterion and rank, each
claim — a *name set*: that subject's own id parts and the inner-capital words of its own
name-bearing records, by `key_nouns`' rule applied per subject. A feature is **named** in a text
if any member of its name set appears as a whole word, case-folded. Per scene, report whether each
feature is named in (a) the scene's plan statement and (b) the scene's prose. Aggregate:

- share of declared features ever named on the page across eight scenes, by `entity_role` and
  by record kind (rule / consequence / criterion / `manifests_as` / claim);
- first-named scene per feature;
- of the prose-named features, how many were named in the plan first and how many the writer
  improvised — this is the number the whole direction turns on;
- the share of the packet's 229 facts never named anywhere;
- hidden claims in their own row, per boundary 1.

**Control A — the wrong-world sham.** The same name sets counted against prose that has never
seen this world: the twenty fitness books (`exports/fitness/*.md`, no forged world, same genre).
Expected near zero. *First In Time*'s vocabulary is dangerously ordinary — *date, call, gate,
ditch, book, right* — so expect the first version to fire. If it does, narrow the name sets to
coined forms only (ids and inner capitals; never plain content words) and **report both figures**,
the defect-6 discipline from §107.9.1: fixing a counter after seeing its answer is the failure
`platform_priors.py` freezes its matchers to avoid, and the pre-fix number stays on the record
beside the post-fix one.

**Control B — the premise baseline.** The same counter with name sets drawn from the *premise
alone*, on the same prose. The planner and the writer both saw the premise; the premise is derived
from the world and carries its proper nouns. The reading that matters is **world-beyond-premise
uptake**: what the 329 records put on the page that the premise's paragraph did not already
carry. Without this control, "the world reached the page" and "the premise reached the page" are
the same number wearing two names.

No bar. Report distributions, per run, with the sham beside them. A counter whose sham fires above
its floor after narrowing is dead as built, and nothing else from it is reported.

## Task 2 — the world-aware plan, pre-registered before the first call

This is the one improvement candidate in this prompt, and it is licensed by Task 0's fact and read
by Task 1's counter.

**Build.** An optional world brief handed to both planner calls — threaded from `canon`, which
`make_outline_handler` already reads at `outline.py:823` and the narrative-plan handler can read the
same way at its call site (`narrative_planner.py:489`). The brief is what the packet already knows
how to say: `worlds.project(canon)` sentences (`worlds.py:996`) for rules, consequences, cast with
`wants` and relationship edges, creatures, places, institutions; `worlds.criterion_brief`
(line 908); and the claims — every question with its reveal window (`worlds.questions`,
`worlds.reveal_scenes`, lines 558 and 567), and the **answer attached only to the window scene's
entry**, per boundary 3, with arc answers (no in-book scene) carried as question-and-"not in this
book" and nothing more. Byte-identical payload when the book has no world (boundary 4).

Rules added to the outline prompt, in the register the existing rules already use (instruction to
a writer, never prose, never exposition): a statement should put the world's rules and their
consequences to work — what happens in a scene is something only this world could make happen; the
scene that is a reveal's window is the scene where that answer lands, planned as an event and not
as an explanation; a statement for a scene before a window may carry the question and never the
answer. Nothing about naming things. Nothing about how to write.

**Pre-registered, and the readings written before any call is bought:**

| # | question | how it is read | the null, and what it would mean |
|---|---|---|---|
| **P1** | does a world-aware outline put more of the world into its statements | Task 1's counter on the statements, world-beyond-premise, three forged worlds × two arms, one outline call each | no separation → the planner ignores what it is handed (the §89.1 class: instructed variation arriving inert); then the lever is not a prompt field, P4 is **not run**, and you say so |
| **P2** | does it leak | `check_open_threads` of every answer against every statement before its window, and every arc answer against every statement | any hit is a **stop** (boundary 3) |
| **P3** | is the reveal planned rather than hoped for | the two window scenes' statements name their claim | 0 of 2 with P1 positive → the planner took the world and not the schedule; report |
| **P4** | does more world in the plan put more world on the page | one eight-scene draft of *First In Time* with the world-aware plan, same commands as run B (`plan/serial-pilot-2.md` §3: `--target-words 900 --context-budget 16000 --chapter-scenes 4`), then Task 1's census on run B and this run side by side | plans name more and prose does not move → the writer, not the planner, is where the world is lost, which points at §5.1's per-scene selection note and is not yours to build |

**P1 without canon.** Rendering a request and calling the provider admits nothing; use the three
worlds in `pilot2/direct2/forge.json` (the picked one is on `main` as the JSON above; the other
two are *not* to be `--pick`ed — a pick is a person's act, and pilot 2 §1 records why a stand-in
that exercises judgment is the wrong stand-in). Fake provider first for wiring; then one live
outline call per world per arm.

**P4 is one book against one book.** Report the delta as one book, name what it cannot say, and
declare no bar. Stand the run up with `tools/serial-pilot-2-setup.ps1` against a copy of the forge
directory on a fresh database, and export it under its own name — `library.slugify` names a shelf
from the title alone, so two books called *First In Time* overwrite each other's reading copy
(pilot 2 §6.1). Record tokens and cost per invocation.

**What P4 may not be read as.** Not quality. Not reader effect. Not "the iceberg is felt". If the
world-aware run is *worse* by any counter you happen to look at, that is a finding to report in the
same sentence, not a reason to soften the registered question.

## Out of scope, named so you do not drift into it

- **Whether a brief moves the world** — directed forges against the empty-brief control, the
  cross-forge collapse rate (two forges converged on land surveying and nothing noticed), and the
  between-Architect "two worlds or one world in hats" comparison. That is the next direction and it
  has its own rails; build none of it here.
- **Why the ledger pays nothing** (S5: 47 opened, 0 paid). A parallel worktree owns it.
- **World growth.** The second extractor family is inert on pilot 2 by defect 8 (a malformed
  `graph_line`), so the world grows through nothing; fixing that needs a re-forge. Not here.
- **Retrieval or per-scene selection for the writer.** If P4 points there, say so in the note and
  stop.
- **Domain truth** — whether a world can be *wrong* about the real domain it literalised, "the
  first quality question in this project with an answer outside the text" (`plan/world-architect.md`
  §8 item 1). If you want to leave a sketch for it, the honest control is a sign flip: a rule and
  its negation put as a factual question to a model from the measurement-side family, where a
  checker that accepts both is dead. Sketch it in the note; build nothing.
- **Any reader consultation, any claim that a book got better.** The reader role is an instrument
  you may not touch and it is not seated.

## Coordination

- `.claude/worktrees/handoff-promise-ledger-eab7ed` is checked out at `main`'s head for the S5
  work. Expect it to touch `application/summarize.py`, `domain/promises.py`, the summary call and
  its tests. Stay out of those files.
- `.claude/worktrees/litharness-architect-stage-5ee368` holds the pilot 2 artefacts (`serial2.db`,
  `serial2b.db`, `pilot2/direct2/`, `pilot2/runs/`); its branch is merged to `main` at `4e545bc`.
  Read from it; write nothing into it.
- Stage-0 numbering: the committed entry owns the number. Before claiming one, grep
  `^#{2,3} NN` across `main` **and** every `.claude/worktrees/*/plan/stage-0-decisions.md`, and
  check again at commit time (§86.6 and §108 both record why).

## Deliverables

1. The pinned blindness test (Task 0) and, after Task 2, its twin that fails on today's `main`.
2. `research/quality-measurement/world_uptake.py` with its frozen pre-registration block, its
   result files under `research/quality-measurement/results/`, and a results note — new file,
   `research/quality-measurement/world-uptake.md` — carrying the census, both controls with the
   pre- and post-narrowing sham figures if the sham fired, P1–P4 answered exactly as registered,
   and every null reported as a result (§61's rule).
3. The world brief behind an optional parameter on both planner calls, with byte-identity tests
   for the no-world case; `ruff check .` and `mypy --strict` clean; suite green.
4. A stage-0 entry if code lands, under the next free number checked as above, with corrections
   made in place and never silently.
5. Your own commits. `git status` first. Nothing of anyone else's folded in.

Declare no bar, admit nothing to the registry, author no directive. If Task 0's fact turns out to
be false — if some path you find does hand the planner the world — **stop and write that up
instead**; the rest of this prompt is built on it, and a census run on a wrong premise is worse
than no census.
