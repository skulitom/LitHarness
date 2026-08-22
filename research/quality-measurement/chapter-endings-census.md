# Chapter endings: the rule that never arrived, the position nobody was told, and the shape nobody had counted

**Status: MEASUREMENT AND TWO REPAIRS, 2026-08-22. No bar is declared here, nothing is admitted
to the axis registry, no directive was authored, and no model was asked whether an ending is
good.** Every number below is descriptive. From `plan/handoff-chapter-endings.md`; code in
`src/litharness/application/constraint_locks.py`, `src/litharness/domain/serials.py`,
`src/litharness/application/planner.py` and `research/quality-measurement/chapter_endings.py`.
Decision log: stage-0 §108.

Nothing in this work adds a cliffhanger instruction, a hook beat function, or any default about
how a scene ends. The one ending rule that now reaches a prompt is the operator's own sentence,
written in `plan/serial-pilot-1.md` §4.2 on 2026-08-21 and unread by every scene since.

## The headline, stated first because it is not the flattering one

**The system has never once ended a chapter or a scene on a question.** Zero of 146 own-generated
units — two published chapters, plus 144 drafted scenes over 23 books; Reappraisal appears at both
grains, because its two chapters *are* its eight scenes assembled — has a final prose paragraph
ending in a question mark. It holds at a lower word floor too: at `--min-words 100`, n rises to
156 and the rate is still 0.00%. Published LitRPG runs at **6.50%** over 3,000 chapters, and
that rate is stable across every era cohort in the corpus (5.38% declared-AI 2025, 6.20%
undeclared 2025, 6.91% human pre-2023), so it is not an artefact of the year the way
`tricolon_rate` was.

Second: **both published chapters of the only assembled book end literally on a `[STATUS]`
line.** The prose ending the operator wrote to a scene plan by hand is there, and then the system
speaks after it. 2 of 2 at chapter grain; 17 of 144 at scene grain, all 17 inside the two books
that speak system voice at all.

Third, and the reason the first two are worth anything: **the only sentence about endings anybody
ever wrote into this system reached no prompt at all.** It is in the plan. It is `locked=False`.
`plans.constraints_of` selects on `locked`.

**None of that is evidence that the endings are bad.** No seated reader exists to ask, the
engagement instrument that could say whether an ending works (BCR, §94) has no seated model, and
a 6.50% genre rate is a description of a population and not a target. What is measured is that
one number is zero where a comparable population's is not, and that the direction that would have
bent it was never sent.

---

# Task 0 — what was measured before anything was built

## 0.1 The rule that never arrived

**Store:** `serial.db`, plan head `953d066fd9ee`, 23 items, 8 `scene_draft` jobs, all
`succeeded`. Read read-only; nothing was written to it.

The five constraints the Narrative Planner minted from the operator's tone note, and whether each
reached the drafting prompt of any of the eight scenes:

| plan item | `locked` | in any of the 8 prompts |
|---|:--:|:--:|
| `constraint-dramatize-on-the-page` | **False** | **0 / 8** |
| `constraint-pov-close-third-silas` | **False** | **0 / 8** |
| `constraint-prose-texture-concrete-varied` | **False** | **0 / 8** |
| `constraint-scene-endings-movement-or-cost` | **False** | **0 / 8** |
| `constraint-voice-dry-exact-funny` | **False** | **0 / 8** |
| `constraint-2e647b7010bac5ec26a6` (every gain has a price) | True | 8 / 8 |
| `constraint-45f2e2607ce0d9fa7f0e` (system voice) | True | 8 / 8 |
| `constraint-b43b7dc213e5f1fd4e29` (no real-world names) | True | 8 / 8 |
| `constraint-babf2326b10541955347` (the loop rule) | True | 8 / 8 |

The string `scenes end` occurs in **0 of 8** stored prompts. Every prompt's last line is the beat
line plus the scene-plan statement, of the form:

```
Now write Reappraisal: Scene 8 — scene 8 of 8. Dramatic function: resolution. This scene: Out of
the quarter and above the line with the ledger, …
```

**Which directive produced which item — and the field that should have said so is empty.**
`directives.produced_constraint_ids` is `[]` for **all four** interpretive directives, because
`narrative_planner` fills it from the constraints it minted **locked** and it minted none. The
lineage is only recoverable from `plan_proposals`:

| directive | kind | status | `author` | `produced_constraint_ids` | items its proposal created |
|---|---|---|---|---|---|
| `dir-6f1e17c9…` | constraint | applied | `None` | 1 id | the loop rule |
| `dir-7bcda8fc…` | constraint | applied | `None` | 1 id | system voice |
| `dir-7abfd6f3…` | constraint | applied | `None` | 1 id | no real-world names |
| `dir-82b2d46d…` | constraint | applied | `None` | 1 id | every gain has a price |
| `dir-7961d4ee…` | **tone_note** | applied | `None` | **`[]`** | **the five unlocked constraints** |
| `dir-95037fe5…` | arc_note | applied | `None` | `[]` | book plan, 2 chapter plans, 8 scene plans, 1 promise |
| `dir-a5557eaa…` | chapter_note | applied | `None` | `[]` | rewrote chapter 1's scene plans |
| `dir-0f2ff383…` | chapter_note | applied | `None` | `[]` | rewrote chapter 2's scene plans, 1 promise |

**`author` is `None` on every row**, which is "unrecorded" and never "machine"
(`directors.is_machine_author`) — every one of these predates the column. That is what makes the
repair in Task 1 admissible at all, and it is also the weakest link in it; §108.2 says so.

**A correction to `plan/serial-pilot-1.md` §4.5, made in place.** That section says the five
prose defects the operator named after the first read were not disobedience, "the tone note
reached the plan, became locked constraints and sat in every packet." The first clause is true
and the second and third are not. The finding gets *stronger*: the tone note could not have been
disobeyed, because no scene was ever shown it.

## 0.2 What a reader sees last

Every own-generated book reachable on this machine. `bz3.db` holds 29 tables and 24 rows, all in
`schema_migrations` — no books, no prose; it is an empty schema and is reported as one rather
than as a book with no endings. The database copies of the exported books are byte-identical
mirrors of the `.md` exports and are **not** counted twice.

| source | grain | units | end literally on a system line |
|---|---|--:|--:|
| `book-library/*/chapters/*.txt` | chapter | 2 | **2 (100%)** |
| `serial.db` (Reappraisal) | scene | 8 | 7 (87.5%) |
| `corpora/toll.db` (The Toll Road) | scene | 10 | 10 (100%) |
| `corpora/fitness/*.db` (21 books) | scene | 126 | 0 (0%) |
| `bz3.db` | — | 0 | — (empty schema) |
| `exports/book-snapshots.db` (2 books) | scene | 0 *(both books' scenes are under the 200-word floor)* | — |
| **pooled across both grains** | mixed | **146** | **19 (13.0%)** |

Reappraisal is counted at both grains and the pooled row says so rather than calling itself
deduplicated: its two chapters are its eight scenes assembled, so the 146 is 138 distinct texts
plus one book counted twice.

Both published chapters, in full:

| chapter | last prose paragraph (words) | literal last line |
|---|--:|---|
| Chapter 1 | *"…and outside, in fifty minutes, every siren in the city."* (29) | `[STATUS] Silas — Loop 2 \| Day 1` |
| Chapter 2 | *"His arithmetic was not the problem. The arithmetic had never once been the problem."* (14) | `[STATUS] Silas — Loop 2 \| Day 2` |

**Counted, not moved.** Whether the `[STATUS]` line belongs at the end of a published chapter is
an operator decision and nothing here touches it. The instruction that puts it there —
"End the scene with a status line" in `render_prompt` — is unchanged.

## 0.3 The architecture fact

Both halves held at the time of the work, and one no longer does because this pass changed it:

- **`domain/serials.py` had zero importers in `src/`.** `grep -rn serials src/` returned eight
  hits, every one of them the English word "serials" inside a comment. Its only callers were
  `tests/test_serials.py`. As of this pass `application/planner.py` imports
  `chapter_positions`, `Position` and `SerialShape`, which is the module's **first production
  caller**; every pre-existing test name in `tests/test_serials.py` is still there and still
  passing.
- **The only chapter-size declaration is `--chapter-scenes`**, a top-level flag defaulting to
  `library.DEFAULT_SCENES_PER_CHAPTER` = 1, read at exactly one place (`_publish_library`, publish
  time). It is now read at a second: the tick's work selector. Nothing else in the system knows
  what a chapter is.

---

# Task 1 — the rule reaches scenes, and the proof is structural

**Route B was taken: a deterministic, free, replayable plan proposal.** Route A — re-issuing the
tone note verbatim as `--kind constraint` — was rejected on two counts. It spends a paid call, and
`narrative_planner.render_request` shows the model `current_plan_items`, so it may equally
`UPDATE` the five existing items or `CREATE` five near-duplicates beside them; the plan would then
carry two readings of one instruction and nothing could say which governs. Route B cannot produce
a duplicate because it creates nothing.

## 1.1 What the lane does, and the three things it refuses

`litharness lock-constraints [--dry-run]`, over
`application/constraint_locks.py`.

- **It changes `locked` and never a word of text.** The item is carried forward whole through
  `dataclasses.replace`; a lane that could edit `text` would be a paraphrase wearing a repair's
  name.
- **It refuses a machine-authored directive's constraint** (`directors.is_machine_author`). The
  lock is a person's standing: a locked constraint lands in the packet at priority 2 and is
  effectively never dropped.
- **It refuses a constraint whose producing directive cannot be recovered.** Unattributable is not
  human.
- **It refuses everything that is not a `CONSTRAINT`.** `narrative_planner`'s symmetric rule
  forces the lock only on that kind, so widening it here would not restore what the fixed minting
  rule produces — it would be a wider rule invented by the repair. The two promises and the eight
  scene plans on the pilot's head stay unlocked, which is also what `plan_search` needs.
- **It is idempotent.** A second run finds no candidates and constructs no proposal at all
  (`PlanProposal` refuses an empty edit set, so "propose nothing" has to be a decision taken
  before the constructor).

**It carries no `DirectiveReading`, and that is load-bearing rather than an omission.**
`commit_plan_application` acts on a reading by calling `Directive.interpret`, which is
`RECEIVED -> INTERPRETED`; the directives this traces are already `APPLIED` and
`TRANSITIONS[APPLIED]` is `{SUPERSEDED}`. A reading would not record provenance — it would raise
`IllegalTransition` and make the lane unrunnable. The lineage goes into the proposal's rationale
and the decision's `policy_config_digest` instead.

**"The last edit wins" is the revision chain, not the clock.** `plan_proposals` returns rows
ordered by `(created_at, proposal_id)`, so proposals accepted inside one ISO second sort on a
content hash. Walking `base_plan_revision_id -> resulting_plan_revision_id` gives the true order
with no timestamp in it. This was found by a test failing, not by reading the code
(`test_a_rollback_clears_the_lineage_because_it_reads_no_directive`).

## 1.2 The packet, before and after

Run against a **copy** of `serial.db`, no provider call, through `planner.packet_for` /
`context.assemble` and `render_prompt`. Plan head `953d066fd9ee` → `d5820540fa41`; locked items
5 → 10; unlocked constraints 5 → 0; plan epoch 8 → 9.

**`scene-8` CONSTRAINTS, before — 4 items:**

```
- Every gain — a Skill, an item, an acquaintance, a fact learned by Appraisal — carries a price…
- System voice: when Loop or Day changes on the page, the System prints one line of the exact…
- Never name, quote, or imitate any real-world person, brand, or published fictional work…
- Loop rule: when Silas dies, time returns to the morning of the Advent…
```

**`scene-8` CONSTRAINTS, after — 9 items**, the same four followed by:

```
- Dramatize rather than summarize: if something matters to the story, it happens on the page…
- Close third person, past tense, anchored to Silas for the whole book…
- Concrete specifics over abstraction: name the object, the sum, the street, the gesture…
- Scenes end on movement or on a cost paid — someone leaves, acts, loses something, or commits
  to a price. They never end on a tidy emotional summary, a moral drawn…
- Voice: dry, exact, quietly funny. Silas's habit of pricing what he sees…
```

**The claim is "the rule is now in the packet", and only that.** The eight accepted scenes are not
redrafted; revisions are immutable and repair is a separate program.

**And it is not free at the far end of the book**, which is the honest half:

| scene | packet tokens | omitted items | SUMMARIES section | prompt chars |
|---|---|--:|---|--:|
| `scene-1` | 1,887 → 2,145 | 0 → 0 | — | 8,758 → 9,997 |
| `scene-8` | 4,458 → **4,448** | **1 → 2** | **5 → 4** | 20,335 → 20,354 |

At scene 8 the packet is already at its budget, so the five constraints arrive **at the cost of
one scene summary**. The token count goes *down* because a dropped summary is larger than the
text that displaced it. That is the packer working as designed (constraints are priority 2,
summaries are lower) and it is a real trade this repair makes rather than a free win.

**Nothing else moved.** All 38 stored jobs, compared on `(job_id, input_digest)`, are identical
before and after the repair — the eight accepted scenes keep the prompts they were drafted from,
and `plan_progress` reports 8 of 8 drafted, so the epoch advance re-mints nothing and cancels
nothing.

## 1.3 Was it safe? The stop condition, checked rather than assumed

The handoff's stop condition was: *if locking an interpreted constraint after the fact would lock
a text the operator never saw, or if a packet would silently change for a book in flight, stop and
write that up instead.* Four checks:

1. **Is the text the operator's?** No — the five sentences are the planner's reading of the
   operator's tone note. **But that is exactly what `acf0e05` now mints**: a constraint from a
   human-authored directive locks by construction, with the model's words and no second look. The
   repair reproduces on stored data what today's code produces on new data, and does not invent a
   new authority.
2. **Can the operator see it before it binds?** Yes. `--dry-run` reports every candidate and every
   refusal and writes nothing, `litharness plans` prints the lineage, and `revert-plan` can undo
   it — a rollback is the one proposal permitted to move a locked item.
3. **Is a book in flight?** No. All 8 `scene_draft` jobs are `succeeded`, `plan_progress` is 8 of
   8, and the queue holds no scene work for this branch.
4. **Does anything already written change?** No, per the 38-job comparison above.

**The one weakness, stated rather than buried:** `author` is `None` on all eight directives,
which the code reads as "unrecorded, and unrecorded is not machine". On this store that is
certainly right — no Director existed when they were written. On a future store it is a
permission that a row predating the column inherits by default. The narrower rule ("lock only
where `author` is a recorded person") would refuse every one of the five and repair nothing, so
the wider rule is the one that ships, with the trade named here and in §108.2.

**Pilot 2 is untouched, and carries no ending clause at all.** `plan/serial-pilot-2-directives.json`
holds six directives — two constraints, two tone notes, one arc note, one chapter note — and not
one of them contains the words *end*, *ending*, *hook*, *cliffhanger*, *final line* or *last
line*. Whether an ending rule should be added there is the operator's decision; the safe form is
a verbatim-lane `constraint`, which locks by construction and passes through no model.

---

# Task 2 — the writer is told where the scene sits

The drafting path had no notion of a chapter, so a writer on scene 4 of 8 could not know that
scene 4 was the last thing a reader would receive in one sitting. It now can.

**Position only.** The fragment is `Chapter {c}, scene {k} of {n}.` — no verb, no adjective,
nothing about what to do there. `test_the_chapter_cue_carries_no_verb_and_no_adjective` slices
the cue out of a rendered prompt and asserts it against the vocabulary a hook instruction would
have to use.

**Where it goes and why.** In the beat line, after `scene {ordinal} of {of_total}.` and before
`Dramatic function:`. Not after the scene-plan statement: `plans.scene_plan_line` is rendered
last, always, and `plan_search`'s controlled comparison depends on the K candidate prompts
differing in that final fragment and nowhere else.

**The pinned forms** (`serial.db`, 8 scenes, `--chapter-scenes 4`):

```
scene 1 of 8. Chapter 1, scene 1 of 4. Dramatic function: setup.
scene 4 of 8. Chapter 1, scene 4 of 4. Dramatic function: rising.
scene 5 of 8. Chapter 2, scene 1 of 4. Dramatic function: turn.
scene 8 of 8. Chapter 2, scene 4 of 4. Dramatic function: resolution.
```

**The byte-identical control**, which is the important half. At `--chapter-scenes 1` — the default,
which "asserts nothing" — `serials.chapter_positions` returns an empty mapping and the rendered
prompt is byte-for-byte what it was before this parameter existed. Verified for all eight scenes
of `serial.db` and for the six-scene mystery fixture
(`test_the_prompt_is_byte_identical_when_a_chapter_is_one_scene`,
`test_the_default_selector_queues_the_prompt_it_always_queued`). This matters beyond tidiness:
`input_digest_for` covers the prompt and that digest is the sampler seed, so a cue leaking into
the default path would silently change the decoding of every newly minted job in the system.

**Truthful about a partial chapter.** `scenes_in_chapter` is the chapter's real complement, not
the shape's, so scene 9 of a nine-scene serial at four per chapter reads `Chapter 3, scene 1 of
1`. Reporting `of 4` would be the tool telling a writer about three scenes nobody has decided to
write.

**Arithmetic borrowed, not rewritten.** `chapter_positions` groups with `serials.chapters_of`
rather than a `divmod` beside it, and both it and `beats.beats_for` read `scene_nodes`, so a
beat's ordinal and its position are cut from one list in one order.
`test_a_scenes_position_agrees_with_the_chapters_it_is_grouped_into` checks the two against each
other at every serial length from 0 to 29.

**Replay.** Job identity excludes the prompt by design (`beat_job_id` keys on book, branch, scene,
template and plan epoch), so a book planned before this parameter existed converges rather than
re-minting: `test_a_tick_over_a_book_planned_before_the_cue_remints_nothing` plans a book at the
default, re-ticks it at four scenes a chapter, and asserts every stored `(input_digest, prompt)`
is unchanged.

**The next step, named and not built.** The shape is passed per run, not stored per book: a
`serial.db` ticked without `--chapter-scenes 4` drafts with no cue. Persisting a shape per book
needs a migration, a plan item or a column, and it is the operator's call which — so it is named
here and left.

---

# Task 3 — the locator and the census

`research/quality-measurement/chapter_endings.py`. **Deterministic, model-free, no anchor set, no
shape classification.** stage-0 §104.4's chapter-hook-shape property stays gated on the anchor
set; what is committed here is the locator and four counters that read characters.

- `final_paragraph(text)` — the last prose paragraph, with system-voice lines excluded via
  `domain/axes.strip_system` rather than a second regex. System lines are dropped *within* a
  block, so a paragraph carrying a status line in its middle stays one paragraph.
- `final_words`, `is_dialogue` (opens or closes on a quotation mark), `ends_on_question` (looks
  past closing punctuation), `is_system_line` on the literal last line.
- The **penultimate paragraph** is measured by the same rule as a control in the same pass. On
  RoyalRoad the last block of a chapter is often an author's note and nothing deterministic
  separates the two, so the gap between the two rows bounds that contamination.

```bash
uv run python research/quality-measurement/chapter_endings.py --substrate local
```

```bash
C:/DEV/MirrorBench/.venv/Scripts/python.exe research/quality-measurement/chapter_endings.py --substrate royalroad
```

```bash
uv run python research/quality-measurement/chapter_endings.py --substrate report
```

## 3.1 The numbers

**Every row ran.** The RoyalRoad shards (3 and 30, snapshot `0e4df3f2…`) are present on this
machine and `C:/DEV/MirrorBench/.venv` has pyarrow, so nothing is NOT RUN.

| | published chapters | own drafted scenes | RoyalRoad LitRPG |
|---|--:|--:|--:|
| source | `book-library/*/chapters/*.txt` | `corpus_io.generated_scenes`, 23 dbs | `corpus_io.royalroad_chapters` |
| works | 1 | 23 books / 22 title keys | 102 stories at ≥5 chapters |
| n | 2 | 144 | 3,000 |
| final paragraph, median words | 21.5 | 18 | 17 |
| final paragraph, mean words | 21.5 | 21.3 | 75.4 |
| **% ending on a question** | **0.00** | **0.00** | **6.50** |
| % final paragraph is dialogue | 0.0 | 37.5 | 33.7 |
| % last line is a system line | **100.0** | 11.8 | 0.17 |
| penultimate: % question *(control)* | 0.00 | 1.39 | 7.37 |
| penultimate: % dialogue *(control)* | 0.0 | 42.4 | 33.1 |

**The era control, which is the one BRIEF.md §2 exists to demand.** `tricolon_rate` looked like an
AI-tell at 0.629 until its undeclared-2025 control separated at 0.606 — it detected the year.
This descriptor does not:

| RoyalRoad cohort | n | % ending on a question | median final words | % dialogue |
|---|--:|--:|--:|--:|
| `human_pre_llm` (pre-2023) | 1,491 | 6.91 | 17 | 35.8 |
| `undeclared_2025` | 1,323 | 6.20 | 17 | 33.1 |
| `declared_ai_2025` | 186 | 5.38 | 19.5 | 22.0 |

A spread of 1.53 points across three eras, against a 6.50-point gap to this system's zero.

**Within story, because every confound this directory has killed was a between-story one.**
Grouped by `corpus_io.by_story` at five chapters minimum: **102 stories**, mean of story means
**6.43%**, and **58 of 102 stories have at least one chapter that ends on a question**. The
population rate is not carried by a handful of outlier books.

**The penultimate control does its job.** RoyalRoad's penultimate paragraphs end on a question
**more** often than its final ones (7.37% against 6.50%), which is the opposite of what
author-note contamination would produce — a note asking "what did you think?" would push the
*final* rate up. So the 6.50% is not an artefact of notes.

## 3.2 What this census cannot see, named

- **`strip_system` reads bracketed all-caps tags and bold spans, and nothing else.** The 21-book
  fitness corpus contains **zero** bracketed tags — its system voice is rendered as *unbracketed*
  ALL-CAPS readouts, invisible to the locator. A one-off probe (final paragraph ≥60% uppercase
  letters and ≥4 words) finds **1 of 144** own-generated units where the "final prose paragraph"
  is a system readout, so `% last line is a system line` under-counts by at most about 0.7 points
  on this corpus. The probe is stated here and deliberately **not** committed as a counter: a
  threshold on capitalisation is half a classifier.
- **`is_dialogue` counts a typographic fact, not speech.** Narration closing on a quoted phrase
  scores true; unquoted dialogue scores false. It is reported because it is checkable, not because
  it is the question.
- **n = 2 at chapter grain.** The only assembled book in this repository is Reappraisal. Every
  other own-generated row is a *scene* ending, and a scene ending is not the unit a reader
  experiences as a chapter ending. The 144 are colour, not the measurement.
- **Nothing here says whether an ending works.** BCR (§94) has no seated model and E6 is the only
  licensed verbal frame. "Zero questions against a genre 6.50%" is a difference in one countable
  feature between two populations, and it is not a defect until something that can measure reader
  effect says so.
- **The draw was wrong the first time and the correction is in the code.**
  `royalroad_chapters` streams shard 3 then shard 30 under one global `limit`, so the first run at
  `limit=3000` returned **no pre-2023 chapters at all** — two 2025 cohorts and silently no
  control era, which looks identical to a corpus that holds no old chapters. `run_royalroad` now
  draws half the budget per shard. The numbers above are from the corrected draw.

## 3.3 A bar is not declared, and here is what one would have to survive

Left as a proposal, undeclared, per the handoff's rule 4 and the seven prior declarations that
named a quantity which could not do what it said (stage-0 §81, §85, §87, §89). Anything of the
form *"chapter endings should ask a question at rate r"* must first answer:

1. **Range at the real n.** At chapter grain this system has produced **two** units. A rate on
   n = 2 takes the values 0, 50 or 100; no bar between them is expressible, and no bar at all is
   measurable until the shelf is roughly 30 chapters.
2. **Direction.** Nothing measured here says a question is better. The genre does it 6.5% of the
   time, which is also 93.5% of the time it does not.
3. **An independent unit.** The counter would be read off the same chapters the writer is being
   directed to change, which is the Goodhart the §94 per-kind tripwire was built against — and
   "end on a question" is the cheapest instruction in the world to obey vacuously.
4. **A non-empty subgroup.** Any subgroup analysis of two chapters is empty by construction.

Until all four are answerable, this is a description of two populations and nothing else.
