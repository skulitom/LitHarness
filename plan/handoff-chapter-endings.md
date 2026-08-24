# Handoff: chapter endings — the rule that never arrived, the position the writer is never told, and the shape nobody has measured

You are working in `C:\DEV\LitHarness`, an autonomous fiction-production system whose objective is
popcorn-genre fiction (LitRPG, progression fantasy, isekai) a defined audience voluntarily
continues and recommends, with no human in the production loop. Superhuman literary
quality is the long-term goal (stage-0 §126). Your task is one bounded piece: make **how a scene ends — and in particular how a
chapter ends** — something the system can (1) carry from an operator's direction to the scene being
drafted, (2) tell the writer the *position* of, and (3) locate and count. Nothing here asks you to
make the system write cliffhangers. Read the boundaries before you read the tasks.

File names, line numbers and measurements below were verified on 2026-08-22 against `main` at
`23d08fa`. If the repo has drifted, the repo wins; re-anchor rather than following this document
into a stale reference. Parallel sessions run on this repository — `git status` before you commit,
commit only your own files, and see "Coordination" below for one session that is touching the same
files you will.

## Why this exists (context you need, then stop reading context)

The operator asked whether the system incorporates any cliffhanger technique. The measured answer is
**no**, in three layers:

- **Nothing in code knows what a chapter ending is.** The drafting prompt ends with
  `Now write {title} — scene {ordinal} of {of_total}. Dramatic function: {function}. This scene:
  {plan}` (`src/litharness/application/planner.py`, `render_prompt`, the f-string near line 432).
  The beat functions are `setup / inciting / rising / turn / crisis / resolution`
  (`src/litharness/domain/beats.py:67`). Chapter grouping exists only at publish time, as the
  operator flag `--chapter-scenes` (default **1**, which the help text says "asserts nothing";
  `src/litharness/application/library.py:92`, `cli.py` near line 3980). `domain/serials.py` holds
  the chapter/arc arithmetic (`SerialShape`, `chapters_of`, `next_chapter`, `window_for`) and **has
  zero callers in `src/`** — tests only. stage-0 §62 recorded the publication pillar's cut with the
  words "no hook placement (the only 'hook' in src/ is the word 'webhook')".
- **The only ending direction anywhere is Serial Pilot 1's operator directives**
  (`plan/serial-pilot-1.md` §4.2–4.4): the tone note *"scenes end on movement or cost, never on a
  tidy emotional summary … avoid moralizing final lines"*, the arc note *"Scene 8 resolves the
  chapter, not the serial: it must end on a hook"*, and chapter notes *"End the chapter there" /
  "End on that line."* The narrative planner turned the tone-note clause into a plan constraint —
  **and that constraint is `locked=False` in `serial.db`'s current plan head** (`953d066fd9ee`, 23
  items; five tone-note constraints unlocked, four verbatim-lane constraints locked).
  `plans.constraints_of` selects on `locked`, so it reached no packet. Commit `acf0e05` fixed the
  *mechanism* (human-directed constraints now lock by construction,
  `narrative_planner.py:329-348`) but the pilot ran before it and the stored plan still carries the
  unlocked items. Measured on the eight stored `scene_draft` job payloads: none contains the words
  "scenes end"; every prompt's last line is the beat line plus the scene plan.
- **The hooks that do exist came through the scene-plan line, by hand.** Scene 8's plan ends
  *"Ends on that reading and on the flat, unexplained fact of it: the difference is not in him"* and
  the chapter ends *"His arithmetic was not the problem. The arithmetic had never once been the
  problem."*; chapter 1 ends *"…and outside, in fifty minutes, every siren in the city."*
  (`book-library/reappraisal/chapters/Chapter{1,2}.txt`). In both, the **literal** last line is the
  `[STATUS]` line the system-voice instruction requires (`render_prompt`, "End the scene with a
  status line"). On the measurement side, stage-0 §104.4 registered **chapter-hook shapes** ("what a
  chapter's last paragraph does, as a small closed set of located contrasts … locator: the final
  paragraph; counter: the shape distribution") as a mining-side property under §97.4, gated on an
  anchor set that is three verified summits of eleven. **Nothing is mined.** The engagement
  instrument that could say whether an ending *works* (BCR, §94) has no seated model. The one
  built, hook-related thing is defensive: the promise ledger's per-kind tripwire exists to catch
  "gaming continuation by opening cheap mystery hooks while paying only tone debts"
  (`src/litharness/domain/promises.py:201`).

That is the whole context. Everything below is the bounded work.

## The hard boundaries

These are not preferences. Work that breaks one of them is worse than work not done.

1. **No cliffhanger recipe enters the code.** The system may tell the writer *where* a scene sits
   (position is information, the same class as "scene 3 of 8"). It may not tell the writer *how* to
   end a chapter unless a human directive says so, and no default instruction — "end on a hook",
   "end on a question", "raise the stakes in the last paragraph" — may be added to any prompt,
   template, or beat function. That would be the system's taste, which the regime forbids (stage-0
   §95 scope axiom, §97.1), and it is exactly the Goodhart the §94 tripwire was built against.
2. **No verdict channel.** Do not ask any model whether an ending is good, a hook, a cliffhanger, or
   which of two endings it prefers. The only licensed verbal frame is E6, byte-frozen
   (`src/litharness/domain/discrimination.py`); a new question is a new protocol with no validity
   evidence. The "keep reading" verdict is dead at 195/196. If you find yourself writing a prompt
   that contains the word "ending" and a question mark, stop.
3. **RS1.** No anchor, contrast-corpus or RoyalRoad prose crosses to the generation side — not as an
   example ending, not paraphrased. Measurement-side files may read corpora; nothing under
   `src/litharness/` may reference a corpus digest. `tests/test_corpus_leak_audit.py` checks this.
4. **Declare no bar.** Seven pre-registrations in this ledger named a quantity that could not do what
   it said (stage-0 §81, §85, §87, §89). You are not being asked to pre-register anything; every
   number you produce is descriptive and says so. If you believe a bar is needed, write the four
   attainability checks (range at the real n, direction, independent unit, non-empty subgroup) into
   your note as a *proposal* and leave it undeclared.
5. **Admit no axis, author no directive, touch no instrument.** The axis registry
   (`domain/axes.py`), the persona panel, the BCR pre-registration and `BRIEF.md`'s count are out of
   scope. Re-issuing an *existing* operator directive verbatim, if Task 1 needs it, is the one
   exception and it is the operator's text, not yours.
6. **Counts point to canonical homes; corrections are made in place; the ledger is append-only.**
   The next stage-0 number is **not §107**: §106 is the last entry on `main`, and a sibling worktree
   holds an uncommitted §107. Claim **§108 or later**, and re-check `^#{2,3} NN` across `main` and
   every `.claude/worktrees/*/plan/stage-0-decisions.md` at commit time. Never cite a test name in
   the ledger that does not exist (`tests/test_architecture.py` enforces it).
7. **LLM-only regime.** No human readers, labels, or feedback enter anything here. The operator's
   own reads are defect harvests, not data.
8. **New files where you can.** Do not restructure shared planning documents.

## Coordination (read before you touch `planner.py`)

Worktree `.claude/worktrees/litharness-architect-stage-5ee368` has **uncommitted** edits to
`src/litharness/application/planner.py` (a `criteria` parameter on `render_prompt`, world
criteria in the system message), `domain/context.py`, `cli.py`, `domain/extraction.py`,
`domain/integrity.py`, `tools/serial_pilot_check.py`, plus `plan/serial-pilot-2.md`,
`plan/serial-pilot-2-craft.json` and a `pilot2/` directory. Keep your `planner.py` change small and
additive (one parameter, one fragment in the prompt line) so it merges beside theirs; do not edit
any Pilot 2 file. Note for your results: **Pilot 2's directive set carries no ending clause at
all** — if the operator wants the ending rule live there, it is their decision, and the safe form is
a verbatim-lane `constraint` (locks by construction, no model interpretation). Say so; do not do it.

## Task 0 — measure before building (no provider call, all local)

Record these as output in your note, not as prose claims:

1. **The rule that never arrived.** From `serial.db`, for each of the eight `scene_draft` jobs
   (`jobs.payload` JSON: `logical_id`, `prompt`, `system`): whether the prompt contains each of the
   five tone-note constraints' texts, and the last line of the prompt. From the plan head
   (`plan_heads` → `plan_revisions.items_json`): every constraint with its `locked` flag and, via
   `directives.produced_constraint_ids` (or the `plan_proposals` lineage if that field is empty —
   check, don't assume), which directive produced it.
2. **What a reader sees last.** For every own-generated book you can reach (`serial.db`, `bz3.db`,
   `exports/*.md`, `exports/fitness/*.md`, `book-library/*/chapters/*.txt`): per chapter, the
   literal last line, and the last *prose* paragraph with `[STATUS]`-style system lines excluded.
   Count how many chapters end literally on a status line. Report the count; change nothing.
3. **The architecture fact.** Confirm `domain/serials.py` has no callers in `src/`, and that the
   only chapter-size declaration is `--chapter-scenes` at tick/library time. If either has changed,
   your Task 2 design changes with it.

`debug-book` (a project skill) answers provenance questions from stored rows; use it before opening
the database by hand.

## Task 1 — make the ending rule reach scenes, and prove it structurally

The five tone-note constraints (dramatize / close third / concrete-specifics-no-tricolon / **scenes
end on movement or cost** / voice) are human-directed and unlocked in the stored plan. Two routes;
measure, then pick, and say which and why:

- **Route B (preferred: deterministic, free, replayable).** A deterministic plan proposal that
  `UPDATE`s each constraint produced by a **human-authored** directive from `locked=False` to
  `locked=True`, preserving `logical_id`, through the same `accept_plan_proposal` path and with a
  recorded `PolicyDecision`, exactly as `directive_planner.py`'s verbatim lane mints its items. It
  must refuse machine-authored items (`directors.is_machine_author`) — the lock is the human
  director's authority and nothing else's. Surface it as an operator verb or a one-shot lane; either
  is fine, but it must be idempotent (a second run proposes nothing).
- **Route A (fallback).** Re-issue the tone note verbatim:
  `uv run litharness --database serial.db directive "<§4.2 text>" --kind tone_note`, then the
  phase-1 tick loop from `plan/serial-pilot-1.md` §3 and `tools/serial_pilot_check.py --phase
  directives`. Under `acf0e05` the minted constraints lock. **Before choosing this, read
  `narrative_planner.render_request`**: the model sees `current_plan_items` and may either `UPDATE`
  the five existing items or `CREATE` five duplicates beside them. Duplicates are a defect to
  report, not to leave. This route spends a paid call.

**Proof, either route:** render the packet for `scene-8` (and one other scene) from the store with
no provider call — `planner.packet_for` / `context.assemble`, the way `plan/handoff-interiority.md`
Task 1 does — and show the `CONSTRAINTS` section **before and after**. The eight accepted scenes
are not redrafted; revisions are immutable and the repair loop is a separate program. The claim you
may make is "the rule is now in the packet", and only that.

## Task 2 — tell the writer where the scene sits in its chapter

Today the writer is told "scene 4 of 8" and nothing about chapters, because the draft path has no
notion of one. Give it the position, under these rules:

- **The shape is operator-supplied, never inferred** (`SerialShape`'s own docstring). The minimal
  first step is to thread `args.chapter_scenes` from `tick` into `make_plan_selector` →
  `render_prompt` (a new optional parameter) and render nothing when it is `1`. Persisting a shape
  per book is a bigger change (a migration, a plan item or a column) — name it as the next step,
  do not build it here.
- **Position only, no intent.** The fragment is of the form `Chapter {c}, scene {k} of {n}.` and
  nothing else — no "closing", no "final", no verb, no adjective. It goes in the **beat line**,
  after `scene {ordinal} of {of_total}.` and before `Dramatic function:`. It must **not** go after the
  scene-plan line: `plans.scene_plan_line` is "rendered LAST, always", and `plan_search`'s
  controlled comparison depends on the K candidates differing only in that final fragment.
- **Byte-identical control.** With `--chapter-scenes 1` the prompt must be byte-for-byte what it is
  today. Pin it with a test, and pin `Chapter 1, scene 4 of 4` / `Chapter 2, scene 1 of 4` at four
  scenes per chapter. Use `serials.chapters_of` for the arithmetic if you can do it without a
  layering violation (`application` may import `domain`; this would be the module's first production
  caller — keep every test name in `tests/test_serials.py` alive), otherwise a `divmod` with a test
  that agrees with `chapters_of`.
- **Replay.** Job identity is content-derived. Verify that existing stored jobs are untouched and
  that a tick over a book drafted before your change converges rather than re-minting.

The deliverable is structural: the stored prompt of the next run carries the cue. You may not claim
it changes endings; no seated reader exists to ask.

## Task 3 — the locator and the census, nothing mined, no bar

§104.4's property is gated on the anchor set, which is an operator decision. What is admissible now
is the **locator and deterministic descriptors**, committed first, which is what the property ledger
asks for anyway. Under `research/quality-measurement/` (never `src/`; see `CONTRIBUTING.md` "Before
proposing a quality or craft metric" and read `BRIEF.md` §2 before you write a line):

- `final_paragraph(chapter_text)`: the last prose paragraph with system-voice lines excluded, reusing
  `domain/axes.strip_system` rather than a second regex.
- Descriptors that need no model: final-paragraph word count; whether it is dialogue; whether it ends
  in a question mark; whether the chapter's literal last line is a system line. Run them over
  own-generated books (`corpus_io.generated_scenes`, `by_story`) and over the cached RoyalRoad
  cohort (`corpus_io.royalroad_chapters` — parquet, so the **MirrorBench** interpreter, not `uv run`;
  see the house rule in your memory if you have it, otherwise `CONTRIBUTING.md`). Commit numbers,
  never prose. Label them **descriptive**; state which source ran.
- **Do not classify shapes.** "A question opened / a reversal / an arrival / a threat named / a price
  paid" is a located-contrast judgment that belongs to E6 mining when the anchor set lands; a regex
  for it is the shallow-because-easy metric §1a.1 refuses, and a model asked for it is boundary 2.

If the RoyalRoad shards are not on this machine, run the own-book half and record the other as NOT
RUN with the reason, in the table, never omitted.

## Out of scope, named so you do not drift into it

- A default hook instruction, a "cliffhanger" beat function, or any change to what `SIX_BEAT` means.
- Moving or dropping the `[STATUS]` line from chapter ends. Count it; it is an operator decision.
- Any judge, reader, persona, or BCR change; any axis admission; any pre-registration.
- Editing Serial Pilot 2's package, or re-drafting any accepted scene.
- Any claim that this improves prose, engagement, or retention.

## Deliverables

1. A results note, new file, `research/quality-measurement/chapter-endings-census.md` (or under
   `plan/` if it is mostly design), carrying Task 0's tables, Task 1's before/after packet sections,
   Task 2's pinned prompt forms, and Task 3's numbers with sources named.
2. Task 1's repair with tests beside `tests/test_plan_refinement.py` / `tests/test_narrative_planner.py`,
   and the "rule never arrived" reproduction turned into a regression test that fails on `main` as it
   stands today.
3. Task 2's cue with tests in `tests/test_planner.py`, including the byte-identical control.
4. Task 3's script and committed numbers.
5. One stage-0 entry (§108 or later, re-checked at commit), in the house form: measured first,
   what shipped, what was refused, no bar declared, corrections in place.
6. Your own commits. Run `uv run pytest`, `uv run ruff check .`, `uv run mypy`, `git diff --check`
   first — and check that no paid CLI arm is running on this box before you start the full suite
   (`claude -p` fails silently under box load; see `CONTRIBUTING.md` and the house rules).

If Task 1 turns out to be unsafe — if locking an interpreted constraint after the fact would lock a
text the operator never saw, or Route A mints duplicates you cannot cleanly retire — **stop and write
that up instead**. A packet that silently changes for a book in flight is a worse failure than an
ending rule that stays unlocked one more week.
