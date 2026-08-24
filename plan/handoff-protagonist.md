# Handoff: the protagonist the pipeline never decides — the hook that is an exception, the cast that never reaches the page, and the names a chapter asks a reader to hold

You are working in `C:\DEV\LitHarness`, an autonomous fiction-production system whose objective is
popcorn-genre fiction (LitRPG, progression fantasy, isekai) a defined audience voluntarily
continues and recommends, with no human in the production loop. Superhuman literary
quality is the long-term goal (stage-0 §126). Your task is one bounded piece: make **who a book is about, and what is singular
about them** something the system (1) forges as a declared fact of the world, (2) tells the outline
and the writer, (3) can check an exception against, and (4) can count — and, beside it, close the
two prose gaps the same read named (a name budget at chapter grain; a verb lent to a thing that
cannot perform it). Nothing here asks you to make the system *write* a hook. Read the boundaries
before you read the tasks.

File names, line numbers and measurements below were verified on 2026-08-22 against `main` at
`f947247` (the anchors were taken at `3fbfaf8` and re-checked after the promise-ledger commits
landed; those touched `summarize.py`, tests, tools and docs only). If the repo has drifted, the repo wins; re-anchor rather than following this document
into a stale reference. Parallel sessions run on this repository — `CLAUDE.md` carries the rules;
`git status` before you commit, commit only your own files, and see "Coordination" below.

## Why this exists (context you need, then stop reading context)

The operator read the first two chapters of *What Takes* — Serial Pilot 3, the first book drafted
on a world the Architect forged from a directed brief (`"progression fantasy"`) — and named four
defects. They are recorded verbatim in [`plan/reader-read-3.md`](reader-read-3.md); read it first.
Measured against the machinery, the mechanism is sharper than "the prose was wrong":

- **The forge never asks for a protagonist.** `application/architect.py` `_RULES` (line 350) asks
  for a literalised real domain, two incompatible systems, mysteries with answers, `manifests_as`,
  no levels/HP, and to *"remove or invert exactly one default of the genre"*. The words
  *protagonist*, *main character*, *hero* do not occur in the module. `_WORLD` (line 289) requires
  `title, domain, geometry, progression_means, inversion, premise, systems, cast, creatures,
  mysteries` — a `premise` that is a **world** premise (what is true of everyone). The operator's
  definition of a hook is the opposite shape: *an exception to the world's rule, belonging to one
  person* — "everyone in the world has one cuff, the main character broke the system and can have
  as many as they like". The inversion rule inverts a default for *everyone*; nothing declares an
  exception for *one*.
- **The outline never sees the world.** `application/outline.py` `render_outline_request` (line
  208) is given `premise`, the beat sheet, `open_promises` and `starting_state` (the status-sheet
  seed, absent on this world) — **not one record of canon**: no cast, no rules, no criteria. Its
  system message: *"Given a premise and a beat sheet, say in one sentence what happens in each
  scene."* So it invented a protagonist ("Kell" — **0 occurrences** in `pilot3/direct1/forge.json`)
  and every other named person in the book. Of the forged cast — `hesper_ivane`, `nib_calder`,
  `ossen_wray`, `teoma_shale`, `clerk_amble`, each carrying `wants` and `relationships` rendered
  into every drafting packet — **none appears in the prose** (0 hits each across both chapters).
  The world reached the writer (S1 held: 328 facts, `context_omitted = 0`); its people did not.
- **The packet has a viewpoint seam and nobody uses it.** `planner.packet_for` (line 494) takes
  `pov_character_id: str | None = None` and `context.assemble` (line 350) filters records through
  `state.visible_to` and labels the block *"Established facts known to {pov}"* (`context.py:306`).
  The one production caller (`make_plan_selector`, the `packet_for` call near line 905) never
  passes one. Every packet ever built was built for no one.
- **The premise cannot be redirected after `new`.** `cmd_new` writes the premise as the one
  plan item the planner requires, `locked=True` (`cli.py:3464-3469`). The narrative planner's
  rules include *"Never update or delete a locked item"* and *"exactly one premise"*
  (`narrative_planner.py:168-171`), so a `premise` directive — an interpretive kind
  (`domain/directives.py:79`) — can add items beside it but cannot rewrite it. The hook has to be
  right at the forge, or come in as a locked `constraint`.
- **The name budget is per scene and the reader reads chapters.** C6 (*"in the first three
  hundred words of a scene, name at most three things a reader is expected to remember"*) was in
  every packet and was honoured in every scene — `domain/axes.opening_proper_nouns` (line 396,
  300-word window) scores the eight openings 2, 3, 1, 2, 3, 1, 2, 2 real names. Chapter 1 as a
  reader receives it (four scenes, 3,805 words) introduces nine named people and three unnamed
  roles; the book seventeen named persons in 7,700 words — all invented by the outline or the
  writer, since the forged cast never arrived. Nothing bounds a chapter, and nothing bounds how
  many people an outline blind to the cast invents.
- **C7 was present and did not name the failure.** *"Two rings of bark stood on her wrist."* C7
  (plain words; every phrase survives a second read) enumerates noun stacks, backwards
  comparisons, self-cancelling and restated phrases. A verb lent to an object that cannot perform
  it is not on the list. No counter sees it; the read did.

That is the whole context. Everything below is the bounded work.

## The hard boundaries

These are not preferences. Work that breaks one of them is worse than work not done.

1. **Code carries facts and positions, never taste.** A protagonist is a **declared fact of the
   world** (canon: who, what exception, what it costs, what they want) and a **position** (whose
   scene this is), both the same class as "scene 3 of 8" and the chapter cue (stage-0 §108.4).
   No default instruction about how to *handle* a protagonist — "open on the hero", "make them
   likeable", "show them winning" — may enter any prompt, template, beat function or system
   message. Direction about that is the operator's, and the only place you may write it is as
   **proposed** craft-constraint text in a JSON file the operator issues (Task 5), stamped with
   its source read. The one rule you add to the forge (Task 1) is a rule about what a *world
   declares*, cited to `reader-read-3.md`, beside the other declared-shape rules already there.
2. **No verdict channel.** Do not ask any model whether a hook is good, which premise hooks more,
   whether a protagonist is interesting, or which of K worlds to pick. The forge stops and a person
   chooses (`plan/world-architect.md` §2; `forge --pick` is `VerdictSource.HUMAN`). E6 stays
   byte-frozen (`domain/discrimination.py`). If you find yourself writing a prompt with the word
   "hook" and a question mark, stop.
3. **RS1.** No anchor, corpus or RoyalRoad prose crosses to the generation side — not as an
   example hook, not paraphrased. `tests/test_corpus_leak_audit.py` checks.
4. **Declare no bar.** Every count you produce is descriptive and says so (§81, §85, §87, §89 each
   named a quantity that could not do what it said). A chapter-level name budget, if the operator
   wants one, gets its number from a measured distribution (Task 6) and is the operator's to set.
   Pre-registered questions name outcomes, not thresholds.
5. **Scope axiom (stage-0 §95); LLM-only regime.** No human readers, labels, or solicited
   judgment. The operator's read is a defect harvest and not data; the operator's acceptance read
   is not spent here.
6. **Counts point to canonical homes; corrections in place; the ledger is append-only.** The next
   stage-0 number is **§111 or later** — §110 (the promise ledger) is already in `main`'s
   `plan/stage-0-decisions.md` as this is written, and the highest in any worktree is 110; re-run
   the check in `CLAUDE.md` at commit time, because this number moves daily. Never cite a test name that
   does not exist (`tests/test_architecture.py::test_every_test_cited_as_evidence_exists`).
7. **`serial3.db`, `pilot3/` and `serial.db` are read-only.** Redraft no accepted scene; re-pick
   nothing; do not edit `plan/serial-pilot-2-*.json` or the pilot-2 setup script. A new world is
   forged under Task 4 into a **new** directory and database; the run costs ~$1.50 + ~$5.
8. **Backwards compatibility is a test, not a hope.** A world with no protagonist (every forged
   world to date; `plan/serial-pilot-2-world.json`) must regenerate byte-identically
   (`tests/test_architect.py::test_the_pilot_package_regenerates_the_world_it_was_run_on`, line
   611), and a book whose canon declares no protagonist must render **today's outline request and
   today's drafting prompt byte-for-byte** (the control the chapter cue pinned:
   `tests/test_planner.py::test_the_prompt_is_byte_identical_when_a_chapter_is_one_scene`, line
   565). `input_digest_for` covers the prompt and is the sampler seed — a leak into the control
   path silently re-decodes every new job.
9. **New files where you can.** Do not restructure `plan/world-architect.md`; extend it with
   dated sections.

## Coordination

- Worktrees dirty on 2026-08-22: `busy-spence-0cf6eb` (`domain/calibration.py`,
  `domain/failures.py`, `tests/test_architecture.py`), `ox-alpha-trial-7f3a21`
  (`research/quality-measurement/thermal_watch.py`), `ox-repair_generation-7f3a21`
  (`tests/test_repair_generation.py`), `modest-kalam-94e683` (`py.typed`),
  `scene-book-preference-experiment-ff67a9` (`research/scene-book-grain/`). None touches
  `architect.py`, `outline.py`, `planner.py`, `worlds.py`, `integrity.py` or `context.py`.
- **Two other handoffs touch neighbours.** `plan/handoff-promise-ledger.md` has **landed**
  (`f947247`, stage-0 §110: shown the ledger, the settling call paid 8 of 40). It changed
  `summarize.py` only, and it added `tools/rematerialise_forge_bundle.py`, which rebuilds a
  `seed.json`/`directives.json`/`promises.json` bundle from a committed world JSON — use it,
  not a second `--pick`, if you ever need a bundle re-materialised. Its `plan/serial-pilot-2.md`
  §6.3 is a baseline you may cite.
  `plan/handoff-worldbuilding.md` is **untracked** on `main` and belongs to another session; read
  it before you touch `architect.py` and keep your schema change **additive** (one optional object,
  one rule, one gate complaint) so the two merge. If it has already added a protagonist-shaped
  field, build on it and say so; do not add a second.
- Before the paid run (Task 4): check no other paid arm, pilot loop or forge is running
  (`claude -p` fails silently under box load — `CLAUDE.md`); one CLI arm at a time.

## Task 0 — measure before building (no provider call, all local)

Record these as output in your results note, not as prose claims. `debug-book` (a project skill)
answers provenance questions from stored rows; use it before opening a database by hand.

1. **The outline is blind to canon.** From `render_outline_request`'s signature and its one
   caller (`outline.py:839`): list exactly what it receives. Confirm no `StateRecord` reaches it.
2. **The viewpoint seam is unused.** `grep -n pov_character_id src/litharness/application/planner.py`
   — confirm the only production call passes nothing, and that `context.assemble` would label and
   filter if it did (`context.py:306, 439`).
3. **The premise is locked at `new`.** `cli.py:3464-3469`; `narrative_planner.py:168-171`.
4. **The numbers from the read, re-derived from the store** (if `serial3.db` and
   `book-library/what-takes/` are present; if not, cite `reader-read-3.md` and do not re-run):
   `opening_proper_nouns` per scene; named persons by first appearance per chapter (word offset);
   forged-cast hits in the prose (expect 0 for Ivane/Calder/Wray/Shale); Kell's first-appearance
   offset (17) and scene-1 mention share (9 of 16 vs Ossary); where his role is first stated (word
   804, in reported speech).
5. **The cardinality exception is currently undeclarable, and the detector proves it.** On a
   *copy* of `serial3.db`'s canon (or `records_for` over `pilot3/direct1/forge.json` candidate 2,
   `scenes=8`), take one declared shape (`worlds.cardinality_shapes`; this world declares four,
   e.g. `c_one_owner_per_trait`), plant one extra `object_ref` record on a cast subject that breaks
   its maximum, and run `integrity.detect_cardinality_violations`. Record that it fires. Then read
   `worlds.in_scope` (line 724): *"Scope is an `entity_role`, or `*`. Not a subject id"* — there is
   no way to say *this one person is the exception*. That is Task 1's design problem stated in
   code.
6. **How many of the book's people did the Architect write?** For each own-generated book you can
   reach with a forged world behind it (`serial3.db`; pilot-2 stores if regenerated by the other
   handoff): named persons in the prose ∩ forged cast ids. Expect ∅ on *What Takes*.

## Task 1 — the protagonist as a declared fact of the world (Architect)

The Architect says what a world *is*; add to that one thing a world may declare about *whose* book
this is. All additive; every world forged so far stays valid and regenerates unchanged.

**Schema** (`architect.py`, `_WORLD`): an optional `protagonist` object —
`id` (a declared cast id), `exception` (the one rule or cardinality shape of this world that does
not hold for them or holds differently, **by id**), `edge` (what that lets them do that nobody
else can, as it shows on the page — `manifests_as` register, never an explanation), `wants`,
`price` (what the exception costs them, payable on the page). Require it **in the forge request
only**: add it to `_WORLD["required"]` for `WORLDS_SCHEMA` and refuse in `worlds_from` (line 530)
the way a missing premise is refused — but `records_for` (line 704) must tolerate absence so the
pilot-2 package pin holds. Keep `_TEXT` as it is for old fields; give the new text fields
`minLength: 1`, because the 2026-08-22 forge returned a world with an **empty** premise that
conformed and then failed the shape check, $1.48 gone (`pilot3/forge.db`, `dec-fb00e71c…`).

**One rule** in `_RULES`, cited to `reader-read-3.md` in the comment beside it, in the register of
the rules already there (declared shapes, not taste): the world names one member of its cast as
the protagonist; the exception is the hook — the one rule that does not hold for them, what it lets
them do that nobody else can, what it costs; and the **premise is written as that person's
situation** — who they are, what is singular about them, what is in the way — rather than as a
description of the world. Do not write "progress faster than anyone", "win", or any verb about
outcome into the rule: an exception declared is a fact; who wins is the book's.

**Records** (`records_for`): `protagonist` added to `worlds.ENTITY_ROLES` (line 95) and emitted as
an `entity_role`; `<id> edge <text>`; `<id> wants`; `<id> exception_to <rule-or-shape id>` with
`object_ref` set — it is an edge, and the second extractor family reads edges; `<id> price <text>`.
All `world_record`, all `PROPOSED` until `--pick`, exactly as the rest.

**The exception must reach the gate, or it is decoration.** Extend `CardinalityShape`
(`worlds.py:655`) with `except_subjects: tuple[str, ...] = ()` populated from the shape's own
declaration (add `"except": [ids]` to `_CARDINALITY`, line 232), and make `in_scope` return
`False` for an excepted subject. Scope stays a role — the docstring's reason stands: a shape is a
rule about a *kind* of thing — and the exception is a declared fact about one subject, which is
what an exception is. Pin in `tests/test_worlds.py` / `tests/test_integrity.py`: (a) a shape with
no `except` behaves byte-identically (Task 0.5's planted violation still fires); (b) the same
violation on the excepted subject yields zero findings; (c) the same violation on a *different*
subject still fires (the exception is one person, not a hole in the shape). The Architect's gate
(`gate_candidate`, line 592) complains — non-blocking, like the rest — when `protagonist.id` is not
a declared cast id, when `exception` names no declared rule or shape, and when the premise does not
contain any token of the protagonist's id (snake_case split, casefolded; deterministic, no model).

**`report()`** (line 1198) adds counters, not verdicts: `protagonist_declared`,
`exception_declared`, `premise_names_protagonist`. `plan/world-architect.md` §3 (record patterns),
§5 (change surface), §7 (what the Architect may do) and §9 (anti-scope) get dated additions; §6's
rule that nothing here orders worlds is untouched.

The claim you may make is "a world can now declare its protagonist and the gate can honour their
exception", and only that.

## Task 2 — the outline is told the world's people, and whose book it is

`render_outline_request` gets two new keyword inputs and **renders nothing new when both are
empty** (byte-identical control, pinned beside the existing tests in `tests/test_outline.py`):

- `cast`: the world's cast as the projection layer already phrases it for the packet
  (`worlds.project`, line 996 — sentences, not ids; §107.3 measured why), one entry per cast id
  with `is_a`, `wants`, and its relationships.
- `protagonist`: the id, `edge`, `exception`, `wants`, `price` from canon, or `None`.

Rules added to the request only when the inputs are present, in the register of the rules already
there (*"Use the subject names given in open_promises. Do not invent promises."*): use the cast
given and do not invent named people — an unnamed role is fine; the protagonist is `{id}` and the
book is theirs, so every statement says what they do or what is done to them. **Position and
fact; no adjective, no outcome verb.** Pin a test that the added lines carry none, the way
`test_the_chapter_cue_carries_no_verb_and_no_adjective` (`tests/test_planner.py:624`) does.

The caller (`outline.py:839`) reads cast and protagonist out of the same canon it already reads the
status seed from. `outline_job_id` is epoch-keyed and excludes the prompt (line 181): confirm with a
test that a tick over an already-outlined book mints nothing new.

## Task 3 — the writer is told whose scene it is

Thread the protagonist's id from canon into the one production `packet_for` call
(`planner.py` near line 905) as `pov_character_id`. Two effects, both to be **measured on a stored
book before you rely on either**: the facts block is labelled *"Established facts known to {id}"*
(`context.py:306`), and `visible_to` admits records restricted to that id — which, on a forged world,
is none (`pov_visibility` is packet *access*, not the iceberg: `plan/world-architect.md` §1). Render
scene 1's packet for `serial3.db` with and without and diff it; record the diff. Then add **one
fragment** to the beat line, after the chapter cue and before `Dramatic function:`, of the form
`Point of view: {id}.` — position-class information, no verb, no adjective, rendered only when
canon declares a protagonist, byte-identical otherwise. Do not put it after the scene-plan line
(`plans.scene_plan_line` is rendered last, always; `plan_search` depends on it). Pin the control and
the no-verb test beside the chapter-cue tests.

Nothing here tells the writer to *open* on the protagonist or to *like* them. If the operator wants
that, Task 5 carries the proposed text.

## Task 4 — pre-register, forge once, run once, record

**Pre-register first**, as `plan/serial-pilot-4.md` §4 in the pilot-2 table form, before any paid
call. Every question is structural; none is about whether the prose is good.

| # | question | how it is answered | outcomes named in advance |
|---|---|---|---|
| **P1** | does the forge declare a protagonist and an exception | `report()` fields per candidate; gate complaints | a K-way forge where no candidate names a declared cast id, or where every exception names the same rule, is a failure of the rule text — measure `spread` against pilot 2's 0.93 and pilot 3's 0.90 |
| **P2** | does the protagonist reach the outline and the packet | the stored outline request carries `protagonist`; every scene's stored drafting prompt carries `Point of view:` | a packet without it is a threading defect, not a prose finding |
| **P3** | who acts | per scene statement: does it name the protagonist as actor (count of 8); named persons introduced per chapter, by first-appearance offset; forged-cast ids on the page (count) | *What Takes*: 9 and 8 named persons, 0 forged cast; report the new numbers beside them, no bar |
| **P4** | does the exception survive the gate | `state.cardinality.v0` findings on the protagonist's excepted shape across the run (expect 0) and the planted positive control on a copy (expect ≥1) | a finding on the excepted subject means Task 1's scope change did not reach the live detector |
| **P5** | where does the reader meet the protagonist | word offset of first appearance; share of first-300-word mentions; where their role is first stated | descriptive, beside Kell's 17 / 9-of-16 / 804 |

Then: `litharness --database pilot4/forge.db forge "progression fantasy" --k 3 --shape direct --out
pilot4/direct1 --scenes 8` (same brief as pilot 3, so the only change is the rule), pick by the
**recorded rule** — first candidate clear of every gate whose real domain was not forged in pilots 2
or 3 (water law, transplant immunology, land surveying, grafting) — and write the rule into the run
record beside the decision id; the operator may re-pick later and that is a different row. Stand it
up with `tools/serial-pilot-2-setup.ps1 -Forge pilot4\direct1 -Scenes 8 -Database serial4.db -Craft
plan\serial-pilot-4-craft.json` (Task 5's file), then the two phases exactly as
`plan/serial-pilot-2.md` §3 — budget phase 1 at ~2× the directive count in ticks (pilot 3 needed 26,
not 14: each verbatim constraint bumps the plan epoch and re-mints the interpretive jobs behind it)
— and `serial_pilot_check.py` with **both** `--spec`s. `--context-budget 16000` is a precondition.
Keep the database. Record `plan/serial-pilot-4.md` §6 in §6.2's form: ticks / jobs / decisions /
invocations / tokens / cost / scenes / words / parked / findings / gate, the per-scene packet
table, and P1–P5 as counts.

**The operator's alternative, named and not taken by you:** the cheap test on *What Takes* itself —
a locked `constraint` naming one of its cast as protagonist and their exception, then a re-run on
the same world — requires a person to author the hook. That is authoring, not operating; say it is
available and leave it to them.

## Task 5 — craft constraints from the read, drafted for the operator to issue

The house pattern (`plan/serial-pilot-2-craft.json`): constraints that came from a human read of
real prose belong to the project, travel in a JSON file with their source recorded, and are issued
by the operator through the setup script. Write `plan/serial-pilot-4-craft.json` carrying C3, C4,
C5, C6, C8 **verbatim** from the pilot-2 file, C7 with **one recorded edit**, and two new entries,
each `"source": "plan/reader-read-3.md"`:

- **C7, edited:** add the lent-verb clause — a verb may not be lent to a thing that cannot perform
  it (rings do not stand on a wrist; a room does not wait; light does not decide) — and record the
  edit in `carried` as pilot 2 did.
- **C9, introductions at chapter grain:** a budget on named people a *chapter* may introduce,
  stated the way C6 states its scene budget. **The number comes from Task 6's distribution, not
  from you**: write the constraint with the number left as `N` and the measured own-book and
  RoyalRoad medians beside it in the JSON, and say in the results note that the operator sets `N`.
  Do not issue it with a number you chose.
- **C10, the first person named:** the operator's note 3 remedy in direction form — the first
  sentence of the book, and of each chapter, belongs to the protagonist: they are the first person
  named, and the sentence says what they want or what has just happened to them. This is a craft
  rule like C5 and it is the operator's to issue; write it, do not issue it, and do not put any
  form of it into code.

`tools/serial-pilot-2-setup.ps1 -Craft` already takes a path; no script change is needed.

## Task 6 — the counter: named persons a chapter introduces, no bar

Under `research/quality-measurement/` (never `src/`; read `BRIEF.md` §2 and `CONTRIBUTING.md`
"Before proposing a quality or craft metric" first): `named_persons.py` with a locator and
descriptors that need no model — distinct named persons introduced per chapter (first-appearance
word offset), per 1k words, and the share that are the protagonist's mentions when a protagonist id
is known. Reuse `domain/axes`' tokeniser and `_proven_names` rather than a second regex, and carry
its known false-positive class (`I'll`, `I'd`, `I've` scored as names on *What Takes* — say so).
Run over own books (`corpus_io.generated_scenes`, `by_story`; `book-library/*/chapters/*.txt`)
and over the cached RoyalRoad cohort (`corpus_io.royalroad_chapters` — parquet, so the
**MirrorBench** interpreter, `C:/DEV/MirrorBench/.venv`; if the shards are not on this machine,
record NOT RUN with the reason, in the table, never omitted). Commit numbers beside
`opening-counters-results.md`; label them **descriptive**; state which source ran. Do not classify
who is "major" or "minor" — that is a judgment; count people.

## Out of scope, named so you do not drift into it

- Any instruction to any model about how to write, open, end or pace a protagonist's scene;
  any "hook" beat function; any change to `SIX_BEAT` or the arc template.
- Any judge, reader, persona, BCR, axis admission, pool change, or pre-registration beyond P1–P5.
- The observation that the outline invents answers to forged mysteries (`reader-read-3.md`'s run
  record; scene plans s3/s5/s7 of *What Takes* state explanations that differ from the iceberg's)
  — a separate handoff; note it, do not fix it here. Likewise the promise ledger (in flight), the
  chapter-ending clause, `lock-constraints` on `serial.db`, the `[STATUS]` line.
- Editing pilot-2 or pilot-3 files; re-picking; redrafting any accepted scene; a model choosing
  among K worlds; a model writing the operator's craft constraints.
- Any claim that this improves prose, engagement or retention.

## Deliverables

1. Task 1's schema, rule, records, scope change and gate complaints, with tests in
   `tests/test_architect.py`, `tests/test_worlds.py`, `tests/test_integrity.py` — including the
   pilot-2 regeneration pin, the three-way exception test, and a regression test for Task 0.5 that
   fails on `main` as it stands.
2. Task 2 and Task 3's threading with byte-identical controls and no-verb tests in
   `tests/test_outline.py` and `tests/test_planner.py`, and the replay pins.
3. `plan/serial-pilot-4.md` — pre-registration **before** the run, §6 after — and
   `plan/serial-pilot-4-craft.json`.
4. Task 6's script and committed numbers.
5. A results note, new file, `research/quality-measurement/protagonist-results.md` (or under
   `plan/` if mostly design), carrying Task 0's tables, the before/after outline request and
   drafting prompt, the packet diff, P1–P5 as counts, and the cardinality measurements.
6. One stage-0 entry (§111 or later, re-checked at commit) in the house form: measured first,
   what shipped, what was refused, no bar declared, corrections in place, anti-scope — pointing
   `reader-read-3.md` and this file at it.
7. Your own commits. `uv run pytest`, `uv run ruff check .`, `uv run mypy`, `git diff --check`
   first — and no full suite while the paid run is on the box.

If Task 1 turns out to be unsafe — if the forge under the new rule collapses K worlds onto one
exception shape (spread falls well below 0.9 on the same brief), if an exception cannot be declared
without making `state.cardinality.v0` blind to the subject it excepts, or if the only way to make a
protagonist reach the page is an instruction about how to write them — **stop and write that up
instead**. A packet that quietly tells the writer how to treat the hero is a worse failure than a
world that still does not name one.
