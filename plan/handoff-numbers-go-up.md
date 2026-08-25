# Handoff: numbers go up — the protagonist's rung on a declared ladder is the number, it must rise on the page, and the forge may not invert it

You are working in `C:\DEV\LitHarness`, an autonomous fiction-production system whose goal is
superhuman popcorn-genre books (LitRPG, progression fantasy, isekai) with no human in the
production loop. Your task is one bounded piece: make the genre's one unbreakable rule — *the
numbers go up, and the power is personal to the main character* — something the system (1) forges
as a declared, countable fact of the world, (2) schedules, (3) tells the writer, (4) reads back off
the page, and (5) can count — without a single number the operator has not asked for and without
any instruction about how a scene should *feel* about a rise. Read the boundaries before you read
the tasks.

File names, line numbers and measurements below were verified on 2026-08-22 against `main` at
`8882a89`, with two worktrees in flight that touch the same files (see "Coordination"). If the repo
has drifted, the repo wins; re-anchor rather than following this document into a stale reference.
Parallel sessions run on this repository — `CLAUDE.md` carries the rules; `git status` before you
commit, commit only your own files.

## Why this exists (context you need, then stop reading context)

The operator's frame for "what readers want" is the genre's four working rules, as craft writers in
it state them: **(1) numbers go up** — the main character's own power, visibly, and they have to
have access to the system that counts it; **(2) faster is better** — never the same scene twice;
**(3) readers are smart** — do not explain, do not repeat, do not leave holes; **(4) have fun**.
Audited against this repository on 2026-08-22 (recorded in session memory; the facts are re-stated
here with their anchors so you need not trust the memory):

- **Rule 1 is not followed, and the forge is steered to invert it.** The Architect's rules
  (`application/architect.py` `_RULES`, line 350) tell the forge *"Do not use levels, hit points,
  mana, experience points, currency, or any single number that means power, unless this particular
  world genuinely needs one"* (lines 371–374) and *"Remove or invert exactly one default of the
  genre"* (line 365). On the brief `"progression fantasy"` (`pilot3/direct1/forge.json`), **all
  three** forged worlds inverted a piece of rule 1: *Senior Water* removed "portable personal power",
  *What Takes* removed "a gain can be created", *The Closing Error* removed "monotonic growth". The
  inversion rule has no guard against deleting the genre's one non-negotiable default.
- **The operator's resolution, verbatim:** *"We need numbers as well, obviously, but bronze to gold
  rank advance is the same as the number going up. Say bronze is 1 and gold is 3."* So "not
  HP/MP/Gold" (`plan/state-model-abilities.md` §0) was never "no number". **A rank ladder is the
  number**: the rung's position in the declared chain, lowest = 1. What must go up is the
  protagonist's rung, and the reader must be able to count it.
- **The ladder vocabulary already exists and nobody stands on it.** `_CRITERION` (architect.py:126)
  carries `comparator` and `ranks` (`_RANK`, line 119: `id`, `visible_form`, `cost_to_reach`);
  `records_for` (line 704) emits each rank's `manifests_as` and `costs` and the chain as `precedes`
  edges with the criterion in the value slot (lines 896–926); `worlds.rank_order` (line 514) and
  `worlds._ladder_for` (line 931) read the chain back; `worlds.criterion_brief` (line 908) hands
  the writer *"crit_x: ordinal — bronze then silver then gold"* through `render_prompt` (planner.py,
  `criteria=` at line 928). The research's evaluation shape is declared (`EVALUATION_SUBJECT /
  CRITERION / RESULT`, worlds.py:161–163) and **no record in any store uses it**. On `serial3.db`
  (*What Takes*) the two criteria are `set_inclusion` and `replacement_equivalence`, both with a
  `precedes` chain (`single_stem → two_wood → crowned → chimera`; `clean_return →
  equivalent_return → unreturnable`), and **zero** cast members carry any standing on either;
  `ranks_at` is emitted for *creatures* only (architect.py:990). A ladder with nobody on it is a
  costume with nobody in it.
- **The numeric apparatus exists and is off for every forged world.** `[STATUS]` line,
  `speaks_system_voice` (extraction.py:583), `system_voice_example` (line 1100),
  `progression_target` (line 540), the outline's `_milestones` (outline.py:373, refuses stasis
  and flat stretches, lines 455–463) and `milestone_records` (line 567) all key on a
  `status_snapshot` seed. `serial3.db` holds none, so the outline asks for no schedule
  (`test_a_book_that_does_not_speak_system_voice_gets_no_schedule`, tests/test_outline.py:800),
  the writer is handed no target, and nothing ever moved. The one book that had a sheet
  (`serial.db`, *Reappraisal*) kept `Loop` / `Day` — a clock, not power.
- **The page cannot give the number back, by construction.** The second extractor family is built:
  `GraphLine` (extraction.py:263), `parse_graph_line` (359), `graph_line_for` (410),
  `extract_graph_facts` (769), `promotions` (849), called from `extract_state` (line 1028) on every
  accepted scene. But the forge is told *"If this world announces nothing in print, leave
  `graph_line` out — most worlds should"* (architect.py:385–390), *What Takes* declared none, and
  **`render_prompt` has no graph-line input at all** — grep `planner.py` for `graph_line`: nothing.
  The writer is never asked to print the line the parser reads. Pilot 3's gate failed on exactly
  one check: 0 state records read off prose, 328 seeded (`pilot3/RUN.md`).
- **The protagonist is being built next door.** `plan/handoff-protagonist.md` (worktree
  `handoff-protagonist-plan-29c957`, uncommitted on 2026-08-22, claims stage-0 §112) adds a
  `protagonist` object to the forge (`id`, `exception`, `edge`, `wants`, `price`), a `protagonist`
  entity role, `exception_to` / `excepts`, and threads the id to the outline and the packet. **That
  id is the subject whose number must go up.** This handoff does not add a second one.
- **Rule 2's one cheap instrument was never run.** The summary's DELTA question (§110;
  `application/summarize.py` `DELTA_FIELDS`, line 161; `zero_delta` INFO finding, line 576) postdates
  both pilots: `scene_summaries.delta_json` is null on all 16 scenes across `serial.db` and
  `serial3.db`. Null there means *not asked*, not *nothing moved*.
- **Progression promises:** `serial3.db` 2 opened / 0 paid; `serial.db` 6 / 0 (`promises` table,
  `kind = 'progression'`).

The research behind the world model (`research/progression-generalization.md`) says *do not adopt
"monotone power as the definition of progression"* (its closing list, ~line 964). That stands, and
nothing here touches it: the ontology stays general — comparators, partial orders, revocable rank
in a world that wants it. What this handoff adds is a **genre contract the directed brief
declares**: on this brief, the protagonist's standing on one declared ordinal ladder rises within
the arc being written, and the rise is printed. A world may still fall later by directive. The
distinction is the same one `plan/state-model-abilities.md` §4 draws: direction is checked *per
comparator*, and for `ordinal` the check is "the result moved up the order".

That is the whole context. Everything below is the bounded work.

## The hard boundaries

These are not preferences. Work that breaks one of them is worse than work not done.

1. **Code carries facts, positions and schedules — never taste.** A ladder, a rung, a standing and
   a milestone are declared facts and positions, the same class as the numeric schedule that
   already exists (§52, §55: *"the book's plan has the state reaching this later on … move it
   toward that where the events warrant it"*). You may render the next rung and its visible form
   to the writer in exactly that register. No "earn it", "make the reader feel it", "triumphant",
   "pay it off" — no adjective and no verb about how to write the rise enters any prompt,
   template, beat function or system message. Pin it the way
   `test_the_chapter_cue_carries_no_verb_and_no_adjective` (tests/test_planner.py:624) does.
2. **No verdict channel.** No model is asked whether a ladder is good, which rung is right, which
   of K worlds to pick, or whether a rise "lands". The forge stops and a person chooses
   (`plan/world-architect.md` §2; `forge --pick` is `VerdictSource.HUMAN`). E6 stays byte-frozen.
3. **RS1.** No anchor, corpus or RoyalRoad prose crosses to the generation side — not as an
   example status line, not as an example ladder. `tests/test_corpus_leak_audit.py` checks.
   No real person, talk, book or game is named in any prompt text; cite this file in a code
   comment instead.
4. **Declare no bar.** Every count is descriptive and says so (§81, §85, §87, §89). "How often
   should the number move" is the operator's to set over a measured distribution (Task 6). The
   schedule validator enforces *shape* (declared rungs, non-decreasing, at least one rise) — the
   same class of check `_milestones` already makes — not a rate.
5. **Scope axiom (§95); LLM-only.** No human readers, labels or solicited judgment.
6. **Counts point to canonical homes; corrections in place; the ledger is append-only.** The next
   stage-0 number is **§113 or later** — §111 lives in the worldbuilding worktree, §112 is claimed
   (uncommitted) by the protagonist worktree; re-run the `CLAUDE.md` check at commit time. Never
   cite a test name that does not exist (`tests/test_architecture.py`).
7. **`serial.db`, `serial3.db`, `pilot3/`, and whatever pilot 4 produces are read-only.** Redraft
   no accepted scene; re-pick nothing. Your run is a **new** directory and database (Task 4).
8. **Backwards compatibility is a test, not a hope.** A world that declares no ladder and no
   standing regenerates byte-identically
   (`tests/test_architect.py::test_the_pilot_package_regenerates_the_world_it_was_run_on`,
   line 611); a book whose canon declares none renders **today's outline request and today's
   drafting prompt byte-for-byte** (`tests/test_planner.py::test_the_prompt_is_byte_identical_when_a_chapter_is_one_scene`,
   line 565; `tests/test_outline.py::test_a_book_that_does_not_speak_system_voice_gets_no_schedule`,
   line 800). `input_digest_for` covers the prompt and is the sampler seed — a leak into the control
   path silently re-decodes every new job. Both golden fixtures (`litrpg`, `mystery`) are untouched
   by construction: `test_a_world_that_declares_nothing_projects_nothing` (tests/test_worlds.py:272)
   and `test_a_book_that_declares_no_graph_line_extracts_no_edges` (line 631) stay green.
9. **One shape for one fact.** The protagonist's standing is a **flat edge** —
   `subject stands_at → rung_id` — because the page can only print a flat edge and the forge's copy
   of the same fact must be readable by the same function. Do not also write the reified
   `evaluation.*` triple for it; leave `EVALUATION_*` as it is for worlds that reify an evaluation
   with an authority (`research/progression-generalization.md` §8.3). The criterion a standing
   belongs to is *derived* from which declared chain the rung sits in; a rung id in two chains is a
   validator complaint, not a guess.
10. **The number is derived, never stored.** `rung_index` is the rung's 1-based position in
    `_ladder_for`'s chain, computed when asked. Storing an integer beside the chain is a second
    answer to "which rung is third", and the two would eventually disagree (`domain/beats.py`'s
    rule).
11. **No new ontology type.** `plan/state-model-abilities.md` §3.5: a tier ladder *is* an ordinal
    criterion domain plus a presentation per result. You add no "ladder" type, no comparator, no
    `GROUP_KEYS` member without a stage-0 note saying why.
12. **New files where you can.** Do not restructure `plan/world-architect.md` or
    `plan/state-model-abilities.md`; extend each with a dated section.

## Coordination

- **Depends on the protagonist object.** `handoff-protagonist-plan-29c957` has uncommitted edits to
  `architect.py` (+241), `outline.py`, `planner.py`, `worlds.py` (+237), `axes.py` and their tests.
  Task 1 needs `protagonist.id` as the subject of the standing. **Order of work:** Task 0 and
  Task 6 first (they touch nothing that worktree touches); Task 3's extractor change is
  subject-agnostic and can proceed; Tasks 1, 2 and 4 wait until that work is on `main` or you
  branch from its branch and rebase. Keep every schema change **additive** — one optional `standing`
  object on the protagonist, one rule, one amendment to two existing rules, gate complaints,
  counters — so the two merge. Do not add a second protagonist-shaped field.
- **The worldbuilding worktree** (`handoff-worldbuilding-plan-ae1861`, 10 commits ahead, §111)
  added `domain/world_brief.py` and an optional `world=` on `render_outline_request` and
  `narrative_planner.render_request`. If it has merged when you reach Task 2, put the ladder block
  inside that brief rather than beside it; if not, add yours as a sibling keyword and say so.
- `tools/rematerialise_forge_bundle.py` rebuilds a seed/directives/promises bundle from a committed
  world JSON; use it, not a second `--pick`, if a bundle needs re-materialising.
- Before the paid run (Task 4): no other paid arm, pilot loop or forge on the box (`claude -p`
  fails silently under box load — `CLAUDE.md`); one CLI arm at a time; read `transport_failures`
  before any count.

## Task 0 — measure before building (no provider call, all local)

Record these as output in your results note, not as prose claims. Use the `debug-book` skill for
provenance questions before opening a database by hand.

1. **The apparatus is off on the forged book.** On `serial3.db` canon: `speaks_system_voice` is
   False; `system_voice_example` and `progression_target` return `None` for every beat position;
   the stored outline request (the `book_outline` job payload) carries `starting_state: null` and
   no milestone rules.
2. **Ladders present, nobody on them.** `worlds.criteria` and `worlds._ladder_for` per criterion on
   `serial3.db` canon: list the chains. Count records with predicate in `{stands_at, ranks_at,
   evaluation.subject}` whose subject carries the `cast` role: expect 0. Repeat on
   `plan/serial-pilot-2-world.json` via `records_for`.
3. **The three inversions, verbatim**, from `pilot3/direct1/forge.json` `inversion` fields; and
   pilot 2's (`plan/serial-pilot-2-world.json`). Record which genre default each removed, in their
   words. Four worlds; how many removed a rule-1 ingredient (personal / monotone / creatable /
   countable). This is the number P1 is read beside.
4. **The graph line is never asked for.** `grep -n graph_line src/litharness/application/planner.py`
   → no hits; `render_prompt`'s signature (planner.py:300) has no such input; `extract_state`
   (extraction.py:1028) calls `extract_graph_facts` on every accepted scene regardless;
   `graph_line_for(serial3 canon)` → `None`. The chain *declare → ask → print → read* is broken at
   *ask* and absent at *declare* on the one forged book.
5. **DELTA null ×16.** `scene_summaries.delta_json` on both stores; `zero_delta` findings 0 on both
   (`findings.subtype`). Record the summaries' `created_at` against the commit that added
   `DELTA_FIELDS`, so the null is recorded as *unasked*.
6. **The genre's number on the page — is it already measured?** `domain/axes.py` has `_SYSTEM_LINE`
   (line 73), `system_digit_count` (line 191) and `strip_system` (line 94);
   `research/quality-measurement/state_coverage.py` measures cost-unit correspondence. Find whether
   any committed result gives, over the RoyalRoad cohort, the share of chapters with ≥1
   system-voice line and system lines per 1k words. If yes, cite it and skip Task 6's population
   leg; if no, Task 6 produces it.

## Task 1 — the forge declares a ladder the reader can count, and the inversion may not remove it (Architect)

All additive; every world forged so far stays valid and regenerates unchanged.

**Schema** (`architect.py`): on the protagonist object the other handoff added, one optional
`standing`: `{criterion: <declared criterion id>, rung: <declared rank id>}`. Require it **in the
forge request only** — add to the protagonist's `required` for `WORLDS_SCHEMA` and refuse in
`worlds_from` (line 530) the way a missing premise is refused — but `records_for` (line 704)
tolerates absence so the pilot-2 and pilot-3 packages regenerate byte-identically. The protagonist
handoff's `minLength: 1` lesson applies (an empty conforming premise cost $1.48).

**Rules** (`_RULES`, line 350), each in the register of the rules already there — declared shapes,
never taste — with a comment beside it citing this file:

- *New, beside the rank rule (line 357):* at least one criterion has comparator `ordinal` and
  carries `ranks` — a chain of **at least three**, lowest first, each with a `visible_form` a
  reader can see and a `cost_to_reach` payable on the page; the protagonist's `standing` names
  that criterion and a rung that is **not the top**; the number a reader counts is the rung's
  position from the bottom. Do not write any verb about outcome ("rises fastest", "wins") into
  the rule: the opening standing is a fact; who rises is the book's.
- *Amend the inversion rule (line 365):* "Remove or invert exactly one default of the genre
  **other than this one, which is not invertible here: the protagonist's standing on a declared
  ordinal ladder can rise and the reader can count it** — and say what fills the hole." Comment:
  3 of 3 forged worlds on the pilot-3 brief inverted a piece of it.
- *Amend the graph-line rule (lines 385–390):* a world that declares a ladder **declares a
  `graph_line`** — one bracket tag and at least one phrase whose predicate is `stands_at` (the
  standing predicate; a constant in `domain/worlds.py`, not a string in the prompt) — so that a
  change of standing is a line a scene prints and the parser reads. "Most worlds should leave it
  out" becomes "a world with no ladder may leave it out". The shape bounds (`LABEL_WORDS`,
  `PHRASE_WORDS`, extraction.py:236–240) already refuse a paragraph.
- *Leave the no-levels rule (lines 371–374) as it is* and add one clause at its end: the ladder's
  rungs are the numbers this world counts; HP, mana, experience and currency are still not
  assumed. This is the operator's direction, not a softening of it.

**Records** (`records_for`): `<protagonist_id> stands_at → <rung_id>` with `object_ref` set and
`value = <criterion_id>` (mirror `precedes`, lines 919–926: the criterion rides on the edge so two
ladders cannot be spliced), placed at `story_key(1, scenes=scenes)` — the opening — and
`PROPOSED` until `--pick`, exactly as the rest. Say in the docstring why it is placed rather than
unplaced: `progression_target`-class lookups compare order keys, and an unplaced standing cannot
be "before" a milestone.

**Vocabulary** (`domain/worlds.py`): `STANDS_AT_PREDICATE = "stands_at"`;
`ladder_of(records, criterion) -> tuple[str, ...]` (a public name for `_ladder_for`'s chain, or
`_ladder_for` made public — one function, not two); `rung_index(records, criterion, rung) ->
int | None` (1-based; `None` when the chain is not a chain — *empty rather than a guess*);
`standing_of(records, subject, *, at=None) -> dict[criterion, rung]` reading canon `stands_at`
edges, the latest at or before `at` per criterion; `criterion_of_rung(records, rung) -> str |
None` (`None` and a `validate` complaint when a rung sits in two chains). `validate` (line 793)
gains: a `stands_at` rung that is not a declared rank; a rung in two chains; a standing whose
criterion is not `ordinal`.

**Gate** (`gate_candidate`, line 592), non-blocking like the rest: no ordinal criterion with ≥3
ranks; protagonist `standing` names an undeclared criterion or rung, or the top rung; a ladder
declared and no `graph_line`; a `graph_line` with no `stands_at` phrase; a rank without
`visible_form` (exists, line 640).

**`report()`** (line 1198) adds counters, not verdicts: `ladders` (ordinal criteria with a chain),
`rungs_per_ladder`, `opening_rung_index`, `graph_line_declared`, `inversion_text` (verbatim, for
the run record; no classifier).

**Pins** (`tests/test_architect.py`, `tests/test_worlds.py`): the pilot-2 regeneration pin; a
world with a ladder and a standing round-trips `records_for → standing_of / rung_index`; a rung in
two chains is a complaint; a world with no ladder reports `ladders: 0` and byte-identical records.

The claim you may make is "a world can now declare a countable ladder and place its protagonist
on it, and the forge can no longer invert that by default", and only that.

## Task 2 — the schedule: the outline places the protagonist's rungs, and they must rise

`render_outline_request` (outline.py:208) gets one new keyword input and **renders nothing new
when it is empty** (byte-identical control, pinned beside `test_a_book_that_does_not_speak_system_voice_gets_no_schedule`):

- `ladder`: `{protagonist, criterion, rungs: [ids lowest first, each with visible_form],
  opening_rung}` — read from canon at the one caller (the handler's `canon` read, outline.py
  ~815–830, where the status seed is read today) via `standing_of` / `ladder_of`. If §111's
  `world=` brief has merged, this is a block inside it.

Rules added only when present, in the register of the milestone rules already there (lines
272–286): return `standing_milestones: [{ordinal, rung}]`; use only the rung ids given; **the
standing must actually move — a schedule where every milestone repeats the opening rung plans a
book in which nothing rises**; place them at scenes whose statement would plausibly change it;
every rung has a `cost_to_reach`, so the statement at a milestone scene says what is paid. **Shape
and fact; no adjective, no outcome verb.** Pin the no-verb test.

`_standing_milestones` validator, mirroring `_milestones` (line 373): ordinals exist and are
unique; a milestone only where `story_order_key` is not `None`; rungs declared; refuse stasis (all
equal the opening) and flat stretches (consecutive equal); **direction**: `rung_index` is
non-decreasing from the opening and at least one milestone is strictly higher. Refuse the whole
outline on failure, for §55's reason. Put the direction check's rationale in the docstring: this
is the directed brief's genre contract applied to the arc being written, checked per comparator as
`plan/state-model-abilities.md` §4 says ordinal is checked; a world that wants a fall writes it in
later by directive.

`standing_milestone_records` mirroring `milestone_records` (line 567): `PROPOSED` `stands_at`
edges at each milestone's position — `PROPOSED` so they reach no packet and `detect_contradictions`
ignores them, exactly the argument `milestone_records` makes — ids derived from position so a
re-run converges.

`extraction.standing_target(records, *, at) -> str | None`, the twin of `progression_target`
(line 540): the nearest PROPOSED standing at or after `at`, rendered as one line of facts —
`<protagonist> stands at <rung> (<i> of <n>): <visible_form>; the plan has them at <rung'> (<j> of
<n>) by scene <ordinal>`. Pin beside `test_a_schedule_aims_at_the_next_milestone_not_the_last`
(tests/test_planner.py:1535).

`render_prompt` (planner.py:300) gets two inputs, both `None` for every book without a ladder
(byte-identical control): `standing` (the line above) and `graph_line` (the book's declared
`GraphLine`). Render them in the system message next to the status/progression block (lines
414–438), **reusing the numeric block's wording** — *"The book's plan has the standing reaching
this later on: … Move it toward that in this scene where the events warrant it; do not jump to it,
and do not move it for no reason on the page."* — and then, once: *"When the standing changes,
print the line in this form, as the book prints it:"* followed by `graph_line.render(<protagonist>,
<stands_at phrase>, <rung>)` filled with the **current** rung (the `system_voice_example` lesson,
extraction.py:1100: a filled example, never a template with braces — a model wrote `{subject}`
verbatim once). Thread both from the production call (planner.py:905–932). Nothing says when, how
often, or how it should feel.

## Task 3 — the read-back: the number comes off the page, and it is canon when the page printed it

`extract_graph_facts` (extraction.py:769) already reads `[TAG] who <phrase> what` and writes
`PROPOSED` edges; `promotions` (line 849) promotes on later causal reuse. For the standing that
rule is wrong in a specific way: a rung change printed by the system voice is the book's own
statement, the same class as a `[STATUS]` line, whose records are `ACCEPTED_CANON` at the position
because *no model returned it — a recorded decision accepted the prose and this is a mechanical
restatement* (the module docstring, line 1). So: a graph-line edge whose predicate is `stands_at`,
whose subject is canon-known and whose object is a **declared rung** of a **declared ladder** is
written at `extract_state` as the status line is — canon at that position — and carries
`GRAPH_REGISTRY_VERSION`. A page-minted rung (`[RANK] Kell now holds platinum`, `platinum`
undeclared) stays the general case: `PROPOSED`, promoted only by reuse. Pin both; pin that the
litrpg and mystery fixtures extract exactly what they extract today.

Then the standing is a canon fact the next packet carries (`worlds.project`, line 996, renders the
edge as a sentence — check it reads well; `_SATELLITE` at line 958 does not swallow it), and
`standing_of` reads the live rung, so `standing_target` aims at the *next* milestone from where the
book actually is.

**Cardinality — count, do not gate.** "One standing per ladder at a position" is not declarable
with today's `GROUP_KEYS` (`subject`, `subject,order_key`, `object` — worlds.py:218); a subject on
two ladders legitimately holds two `stands_at` edges at one position. Do not add a group key here
(boundary 11). Count two rungs of one ladder at one position as a descriptor in Task 3's measure
and name the decision in `plan/world-architect.md` §8 (open decisions).

**The measure**, under `research/quality-measurement/` (never `src/`; read `BRIEF.md` §2 and
`CONTRIBUTING.md` "Before proposing a quality or craft metric" first): `standing.py` — per book,
no model: the protagonist's `rung_index` by story position from canon; number of rises, drops and
lateral moves; scenes between rises; word offset of the first rise; graph lines printed per 1k
words; `zero_delta` count and DELTA-non-null share from `scene_summaries`; and the same `stands_at`
counts for every other subject (P4). Descriptive; no bar; prints a table.

## Task 4 — pre-register, forge once, run once, record

**Pre-register first**, as `plan/serial-pilot-5.md` §4 in the pilot-2 table form
(`plan/serial-pilot-2.md` §4), before any paid call. Every question is structural; none asks
whether the prose is good.

| # | question | how it is answered | outcomes named in advance |
|---|---|---|---|
| **P1** | does the forge declare a ladder and place the protagonist below its top, and does the inversion leave the ladder alone | `report()` per candidate: `ladders`, `rungs_per_ladder`, `opening_rung_index`, `graph_line_declared`; `inversion_text` read beside Task 0.3's four | 0 of 3 candidates with a ladder, or every candidate inverting the ladder anyway, is a failure of the rule text; measure `spread` against pilot 2's 0.93 / pilot 3's 0.90 — a collapse onto one ladder shape is the stop condition |
| **P2** | does the schedule rise | the stored outline request carries `ladder`; `standing_milestones` validated; number of rises scheduled within the 8 scenes; opening and final scheduled `rung_index` | a refused outline is a validator finding, not a prose finding; record refusals and their reasons |
| **P3** | does the number move on the page | `standing.py`: rises read back from prose (count), scene and word offset of the first, graph lines per 1k words, DELTA non-null of 8, `zero_delta` count | 0 rises read back while ≥1 was scheduled is the defect this handoff exists for — report it, do not repair it in-run |
| **P4** | is the rise the protagonist's | `stands_at` changes by subject: protagonist vs every other subject | descriptive; "faster than anyone else" is a count beside another count, never a bar |
| **P5** | is the price on the page | for each rise read back, does the same scene's summary (`EVENTS` / `DELTA` / `paid`) name a cost — count | the existing report channel, no new question; count only |

Then: `litharness --database pilot5/forge.db forge "progression fantasy" --k 3 --shape direct --out
pilot5/direct1 --scenes 8` (same brief as pilots 3 and 4, so the only change is the rule set),
pick by the **recorded rule** — first candidate clear of every gate whose real domain was not
forged in pilots 2–4 — and write the rule into the run record beside the decision id; the operator
may re-pick later and that is a different row. Stand it up with
`tools/serial-pilot-2-setup.ps1 -Forge pilot5\direct1 -Scenes 8 -Database serial5.db -Craft <the
latest craft JSON: plan/serial-pilot-4-craft.json if landed, else pilot 2's>`, then the two phases
exactly as `plan/serial-pilot-2.md` §3 — budget phase 1 at ~2× the directive count in ticks — and
`tools/serial_pilot_check.py` with both `--spec`s. `--context-budget 16000` is a precondition.
Keep the database. Record `plan/serial-pilot-5.md` §6 in §6.2's form: ticks / jobs / decisions /
invocations / tokens / cost / scenes / words / parked / findings / gate, the per-scene packet table,
and P1–P5 as counts. Cost: ~$1.50 + ~$5.

## Task 5 — the operator's directive text, drafted and not issued

One entry for the operator's craft JSON (`plan/serial-pilot-5-craft.json`, carrying the pilot-4
file forward verbatim if it exists, else pilot 2's), `"source": "plan/handoff-numbers-go-up.md"`,
**proposed, not issued**: *the visible form of a rung appears on the page in the scene the rung is
reached, and the price is paid in the same scene or earlier.* It is a craft rule like C5 and the
operator's to issue. Do not put any form of it into code.

## Task 6 — the counter: the genre's numbers on the page, no bar

Under `research/quality-measurement/` (read `BRIEF.md` §2 first): `system_lines.py` — a
deterministic counter reusing `domain/axes._SYSTEM_LINE`, `strip_system` and
`system_digit_count` rather than a second regex: per chapter, system-voice lines, lines per 1k
words, digits on them, and whether any two consecutive system lines in a chapter differ in a digit
(the cheapest "did a number move" a regex can see; say what it cannot see). Run over own books
(`corpus_io.generated_scenes`, `by_story`; `book-library/*/chapters/*.txt`) and over the cached
RoyalRoad cohort (`corpus_io.royalroad_chapters` — parquet, so the **MirrorBench** interpreter,
`C:/DEV/MirrorBench/.venv`; if the shards are not on this machine, record NOT RUN with the
reason, in the table, never omitted). Commit numbers beside `opening-counters-results.md`; label
them **descriptive**; state which source ran. This is the distribution any future "the number
should move at least every N words" would sit on; the operator sets N, you do not.

## Out of scope, named so you do not drift into it

- Any instruction about how to write, feel, pace or celebrate a rise; any "level-up" beat
  function; any change to `SIX_BEAT` or the arc template; any default about chapter endings.
- HP / MP / Gold / XP sheets for forged worlds; the `DEFAULT_SHEET`; a world with two ladders being
  forced to one (it declares one standing for the protagonist; the other ladder may exist).
- Any judge, reader, persona, BCR, axis admission, pool change, or pre-registration beyond P1–P5.
- Rule 2 beyond the DELTA / `zero_delta` counts already built; rule 3's *outline invents answers
  to forged mysteries* (`pilot3/RUN.md` notes; a separate handoff); rule 4 (levity, fun).
- The protagonist handoff's own tasks; a second protagonist field; editing pilot-2/3/4 files;
  re-picking; redrafting any accepted scene; a model choosing among K worlds.
- Any claim that this improves prose, engagement or retention. The claim available is: *the forge
  declares a countable ladder and cannot invert it by default; the outline schedules a rise; the
  writer is handed the next rung and the line to print; the page gives the number back; the counts
  are P1–P5.*

## Deliverables

1. Task 1's schema, rules, records, vocabulary, validator and gate complaints, with tests in
   `tests/test_architect.py` and `tests/test_worlds.py` — including the regeneration pin and the
   no-ladder byte-identical pin.
2. Task 2's outline input, validator, records and `standing_target`, and the two `render_prompt`
   inputs, with byte-identical controls and no-verb tests in `tests/test_outline.py`,
   `tests/test_planner.py`, `tests/test_extraction.py`.
3. Task 3's extractor change with fixture pins, and `research/quality-measurement/standing.py`.
4. `plan/serial-pilot-5.md` — pre-registration **before** the run, §6 after — and
   `plan/serial-pilot-5-craft.json`.
5. Task 6's script and committed numbers.
6. A results note, new file, `research/quality-measurement/numbers-go-up-results.md`, carrying
   Task 0's tables, the before/after outline request and drafting prompt, P1–P5 as counts, and the
   Task 6 table.
7. One stage-0 entry (§113 or later, re-checked at commit) in the house form: measured first, what
   shipped, what was refused, no bar declared, corrections in place, anti-scope — pointing this
   file and the session memory's audit at it; dated additions to `plan/world-architect.md` (§3, §5,
   §7, §8, §9) and `plan/state-model-abilities.md` (§4, §5).
8. Your own commits. `uv run pytest`, `uv run ruff check .`, `uv run mypy`, `git diff --check`
   first — and no full suite while the paid run is on the box.

If this turns out to be unsafe — if the forge under the new rules collapses K worlds onto one
ladder shape (spread well below 0.9 on the same brief), if the standing cannot be read back
without a model, or if the only way to make the number move on the page is an instruction about how
to write the scene — **stop and write that up instead.** A packet that quietly tells the writer
how a rise should feel is a worse failure than a world whose number still does not move.
