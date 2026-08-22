# Numbers go up: what was measured before the build, what shipped, and what is still not known

**Status: MEASUREMENT, 2026-08-22. No bar is declared here**, nothing is admitted to the axis
registry, no counter in this note gates anything, and no direction is declared for any quantity.
Built from [`plan/handoff-numbers-go-up.md`](../../plan/handoff-numbers-go-up.md); the decision
record is stage-0 §113; the pre-registration for the paid run is
[`plan/serial-pilot-5.md`](../../plan/serial-pilot-5.md) §4 and **it has not run**.

The claim available from everything below is exactly this and nothing wider: *the forge declares a
countable ladder and cannot invert it away by default; the outline schedules a rise and refuses a
schedule that does not rise; the writer is handed the next rung and the line the book prints; a
printed rung on a declared chain comes back as canon; and the counts are P1–P5.* No claim is made
that any of it improves prose, engagement or retention.

---

## 1. Task 0 — what was true before anything was built

All local, no provider call. Measured 2026-08-22 against `serial.db` (*Reappraisal*, pilot 2),
`serial3.db` (*What Takes*, pilot 3), `pilot3/direct1/forge.json` and
`plan/serial-pilot-2-world.json`. **Two of the handoff's own premises did not survive the
measurement and are corrected in §1.5.**

### 1.1 The numeric apparatus is off on the forged book

| | `serial.db` (*Reappraisal*) | `serial3.db` (*What Takes*) |
|---|---|---|
| canon records | 23 | 328 |
| `speaks_system_voice(canon)` | True | **False** |
| `system_voice_example(canon)` | `[STATUS] silas — Loop 1 \| Day 1` | **None** |
| order keys in the store | `s1`…`s8` | `s5` only |
| positions where `progression_target` is non-None | **0 of 8** | **0 of 1** |
| `graph_line_for(canon)` | None | **ASSIZE, 5 edges** |

*Reappraisal* speaks system voice and its sheet is `Loop \| Day` — a clock, not power — and no
milestone was ever scheduled, so `progression_target` answers `None` at every position in both
books. *What Takes* holds no `status_snapshot` at all, so
`test_a_book_that_does_not_speak_system_voice_gets_no_schedule` applies: the outline asked for no
schedule, the writer was handed no target, and nothing ever moved.

### 1.2 Ladders present, nobody on them

`worlds.criteria` and the `precedes` chain per criterion, over `records_for` at
`ACCEPTED_CANON`:

| world | criteria and comparators | chains | ordinal chains of ≥3 | cast | cast/protagonist standings |
|---|---|---|--:|--:|--:|
| *First In Time* (pilot 2, picked) | `cr_priority` **ordinal**, `cr_depth` numeric | `k_no_date → k_junior_date → k_working_date → k_senior_date → k_first_water` (5); `k_shallow_bore → k_deep_bore → k_salt_bore` (3) | **1** | 6 | **0** |
| *Senior Water* (pilot 3, #0) | `crit_priority` **ordinal**, `crit_lift` threshold | `first_water → morning_right → tail_right → wash_right` (4); 2 | **1** | 5 | **0** |
| *What Takes* (pilot 3, #1, picked) | `crit_kinship` set_inclusion, `crit_return` replacement_equivalence | `single_stem → two_wood → crowned → chimera` (4); `clean_return → equivalent_return → unreturnable` (3) | **0** | 5 | **0** |
| *The Closing Error* (pilot 3, #2) | `crit_misclosure` numeric, `crit_witness` set_inclusion | 4; 3 | **0** | 5 | **0** |

**Two of four worlds declare an ordinal chain long enough to count on. Not one cast member of any
of the four stands anywhere on any chain.** `ranks_at` is emitted for *creatures* only — 2, 3, 2
and 3 records respectively, all of them bestiary abundance notes. A ladder with nobody on it is a
costume with nobody in it.

**And the one ordinal chain that pilot 3 produced runs the wrong way.** *Senior Water* lists
`first_water` first — the most senior right — so its `precedes` chain reads
`first_water → morning_right → tail_right → wash_right` and a reader counting *up* it counts a
person getting weaker. Nothing in the rule text said which end came first. Pilot 2's *First In
Time* happened to list lowest-first. That is the measurement behind the new rule's
"listed LOWEST FIRST" clause.

### 1.3 The three inversions, verbatim, and what each removed

Brief `"progression fantasy"`, `spread` 0.8959, all three usable:

| world | the genre default it removed, in its own words | a rule-1 ingredient? |
|---|---|---|
| *Senior Water* | "portable personal power. Nothing here can be carried on the body: a right is fastened to the ground it was first used on, and a person who leaves has nothing." | **yes — personal** |
| *What Takes* | "that a gain can be created. Nothing is made here; every trait carried is a trait somewhere lost, in a named body, on a recorded day." | **yes — creatable** |
| *The Closing Error* | "monotonic growth. Rank here is retroactively revocable: one published misclosure demotes the surveyor and re-opens every deed they ever signed, back to the beginning." | **yes — monotone** |
| *First In Time* (pilot 2, different brief) | "effort. No amount of work, courage, training or cleverness moves anyone up the chain." | no — it removes the *cause* of a rise and keeps the ladder, explicitly: "everyone below it steps up one place" |

**3 of 3 on the directed brief; 3 of 4 overall.** The inversion rule had no floor and deleted the
genre's one non-negotiable default three times out of three. That is the number the new rule's
amendment is read beside, and it is the number P1 will be read beside.

### 1.4 The graph line was declared and never asked for

`grep -c graph_line src/litharness/application/planner.py` → **0**. `render_prompt`'s signature
carried no such input, and `extract_graph_facts` ran on every accepted scene regardless. So the
chain *declare → ask → print → read* was broken at **ask**:

| world | declares a `graph_line` | parses under `parse_graph_line` | carries a `stands_at` phrase |
|---|---|---|---|
| *First In Time* | yes | **no** — label `one dry season in the Kettle Basin` is 7 words against `LABEL_WORDS` 3 | no |
| *Senior Water* | yes (`CALL`, 5 edges) | yes | no |
| *What Takes* | yes (`ASSIZE`, 5 edges) | yes | no |
| *The Closing Error* | yes (`REGISTER`, 5 edges) | yes | no |

All four declared one; none of the twenty declared phrases meant "stands at". *What Takes*
declared `ASSIZE` and **printed zero lines across 7,704 words in 8 scenes** (`standing.py`).

### 1.5 Two corrections to the handoff's own premises

Recorded in place rather than quietly fixed, because the handoff is the document a later reader
will find first.

1. **"DELTA null ×16" is wrong.** `scene_summaries.delta_json` is **non-null on all 8 scenes of
   both books**, and `zero_delta` findings are 0 on both — meaning every scene reported a value
   shift, not that nothing was asked. `DELTA_FIELDS` landed in `7cbd762` on **2026-08-17**, before
   pilot 2 (summaries stamped 2026-08-21T17:12–17:52) and pilot 3 (2026-08-22T14:45–15:00). The
   handoff's "null there means *not asked*" reasoning was sound; its premise was stale.
2. **"*What Takes* declared no graph line" is wrong.** It declared `ASSIZE` with five phrases, and
   so did the other two pilot-3 candidates. The break was at *ask*, not at *declare* — which makes
   the defect narrower and the fix smaller than the handoff supposed. (`graph_line_for` returns
   `None` on a candidate's `records_for` output only because those records are `PROPOSED`; under
   `ACCEPTED_CANON` all three parse.)

### 1.6 Progression promises, for the record

`promises` table, `kind = 'progression'`: `serial3.db` 2 opened / 0 paid; `serial.db` 6 / 0.
Across all kinds: 52 / 0 and 40 / 0.

### 1.7 Is the genre's number on the page already measured? (Task 0.6)

**No, and Task 6 therefore ran.** `chapter-endings-census.md` reports *"% last line is a system
line"* (100.0 / 11.8 / 0.17 across the three substrates), which is a different question: it asks
where a system line sits, not how often one occurs. Neither *the share of chapters with ≥1
system-voice line* nor *system lines per 1k words* existed anywhere committed. §4 below is the
first.

---

## 2. What shipped

### 2.1 The forge (Task 1)

`domain/worlds.py`: `STANDS_AT_PREDICATE`, one **flat** edge `subject stands_at → rung` with the
criterion in the value slot exactly as `precedes` carries it, because the page can only print a
flat edge and both copies of the fact must read through the same function. `ladder_of` (the old
private `_ladder_for`, made public under the name its callers wanted — one function, not two),
`rung_index` (1-based, `None` when the chain is not a chain), `criterion_of_rung` (`None` when two
chains claim a rung), `standing_of` (canon, latest at or before a position, per criterion).
`validate` complains at an undeclared rung, a rung in two chains, and a standing on a
non-`ordinal` comparator. `project` renders a standing as `silas stands at second_seal (2 of 3)`.

**The number is derived and never stored.** A stored integer beside the chain is a second answer
to "which rung is third".

`application/architect.py`: one optional `standing` on the protagonist, **required of the forge**
(`worlds_from` refuses, as a missing premise is refused) and **tolerated as absent by
`records_for`**, so pilot 2's package regenerates byte-for-byte. Four rule changes — one new
(the ordinal chain of ≥3, lowest first, standing below the top), one amendment fencing the
inversion off that default, one requiring a `stands_at` phrase in the `graph_line` of a world with
a ladder, one clause telling the no-levels rule that the rungs are this world's numbers. Five
membership complaints in `gate_candidate`, silent for a world that declares no standing. Five
counters in `report()`: `ladders`, `rungs_per_ladder`, `opening_rung_index`,
`graph_line_declared`, `inversion_text` verbatim — no classifier.

### 2.2 The schedule and the writer (Task 2)

The ladder rides **inside** §111's world brief rather than beside it, since that work had merged:
`world_brief.Ladder` carries the chain lowest first with each rung's visible form and price, plus
the opening rung. `ladder_for` returns `None` for a book with no protagonist, no standing, a
partial order rather than a chain, or a protagonist on two ladders — the last is
`criterion_of_rung`'s abstention rather than a pick.

**The before/after outline request, on a world that declares a ladder.** One key added to
`world`, seven rules added, and every other field byte-identical:

```json
"ladder": {
  "criterion": "assay_grade",
  "opening_rung": "third_seal",
  "protagonist": "silas",
  "rungs": [
    {"id": "third_seal",  "visible_form": "a lead seal that greens in a week",  "cost_to_reach": "a year of unpaid readings"},
    {"id": "second_seal", "visible_form": "a brass seal worn at the throat",    "cost_to_reach": "a ruined reputation elsewhere"},
    {"id": "first_seal",  "visible_form": "a silver seal nobody hands back",    "cost_to_reach": "the name of whoever held it"}
  ]
}
```

> - Also return standing_milestones: the rung ladder.protagonist stands at by the end of certain scenes, as {ordinal, rung}.
> - Use only the rung ids given in ladder.rungs. Do not invent rungs and do not rename them.
> - The standing must actually move. A schedule where every milestone repeats the opening rung plans a book in which nothing rises.
> - The standing never moves down: each milestone's rung is at or above the one before it, starting from the opening rung, and at least one milestone is above the opening rung.
> - No two milestones in a row name the same rung.
> - Place them at scenes whose statement, as you wrote it, would plausibly change what silas counts as.
> - Every rung carries a cost_to_reach. The statement at a milestone scene says what is paid.

`_standing_milestones` mirrors `_milestones` and adds the one check it does not make: **direction**
— non-decreasing from the opening and at least one strictly above it. This is the *directed
brief's* genre contract applied to the arc being written, checked per comparator as
`plan/state-model-abilities.md` §4 says an `ordinal` is checked. Nothing in the ontology moved:
`research/progression-generalization.md`'s refusal of "monotone power as the definition of
progression" stands, comparators and partial orders are untouched, and a world that wants a fall
writes it in later by directive.

**The before/after drafting prompt.** Everything before this block is byte-identical:

```
The book's plan has the standing reaching this later on:
silas stands at third_seal (1 of 3): a lead seal that greens in a week; the book's plan has them at second_seal (2 of 3): a brass seal worn at the throat
Move it toward that in this scene where the events warrant it; do not jump to it, and do not move it for no reason on the page.
When the standing changes, print the line in this form, as the book prints it:
[ASSAY] silas now stands at third_seal
```

The wording is the numeric block's own, deliberately: a standing and a status snapshot are the
same class of fact and saying the second one's sentence in a second register would be this module
deciding one of them matters more. **No verb about rising and no adjective**, pinned by
`test_the_standing_block_carries_no_verb_and_no_adjective` against nineteen words such an
instruction would have to use. The example is *filled* rather than a template, because a model
once wrote `{subject}` out verbatim.

### 2.3 The read-back (Task 3)

`extract_graph_facts` writes **one** shape as `ACCEPTED_CANON` at the position: a `stands_at` edge
whose subject canon already uses and whose object is a declared rung of a declared chain, with the
criterion derived from which chain holds it. Nothing is minted, no model returned it, a recorded
policy decision accepted the prose, and this is a mechanical restatement — the module docstring's
own argument for the `[STATUS]` line. A page-minted rung stays `PROPOSED` and is promoted only by
later causal reuse.

**One defect the wiring exposed.** The `seen` dedupe counted the outline's own `PROPOSED` rung
schedule, so the one scene that printed a scheduled rise would have read nothing. The plan and the
page are different claims; only the page makes the rise true.

**Cardinality: counted, not gated.** "One standing per ladder at a position" is not declarable
with today's `GROUP_KEYS` (`subject`, `subject,order_key`, `object`), and a subject legitimately
on two ladders holds two `stands_at` edges at one position. No group key was added
(handoff boundary 11); the decision is named in `plan/world-architect.md` §8.

---

## 3. `standing.py` on the two existing books — the P3 baseline

`uv run python research/quality-measurement/standing.py --database <db>`, no model in the path:

| book | rungs | scenes | words | rises | drops | lateral | scheduled rises | graph lines / 1k | DELTA non-null | priced rises |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| `serial.db` (*Reappraisal*) | 0 | 8 | 8,385 | 0 | 0 | 0 | 0 | 0.0 | 8 of 8 | 0 |
| `serial3.db` (*What Takes*) | 0 | 8 | 7,704 | 0 | 0 | 0 | 0 | 0.0 | 8 of 8 | 0 |

`other_subjects` is empty on both — P4's prior is zero for everyone, not just for a protagonist
neither book declares.

**What this table cannot see, and it is the same blind spot the counter will have on pilot 5.** A
rise the prose narrated without printing the declared line is invisible to every column. The chain
is *declare → ask → print → read* and this reads the last link.

---

## 4. Task 6 — the genre's system voice on the page, three substrates, no bar

`research/quality-measurement/system_lines.py`, reusing `domain/axes._SYSTEM_LINE`,
`strip_system` and `system_digit_count` rather than a second regex. **Every row ran; nothing is
NOT RUN.** The RoyalRoad leg read shards 3 and 30 under `C:/DEV/MirrorBench/.venv`.

| | n | median words | % with ≥1 system line | lines / 1k (median) | lines / 1k (mean) | digits on them (mean) | units with ≥2 system lines | % of those whose digits differ |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| published chapters (`book-library/*/chapters/*.txt`) | 4 | 4,034 | **50.0** | 0.4855 | 0.5395 | 4.5 | 2 | 100.0 |
| own drafted scenes (24 databases) | 152 | 640 | **11.84** | 0.0 | 0.1249 | 0.441 | 1 | 0.0 |
| RoyalRoad LitRPG (shards 3 + 30) | 14,156 | 2,088 | **2.32** | 0.0 | 0.3181 | 0.064 | 144 | 43.75 |

Per published chapter, which is where the 50% comes from:

| chapter | words | system lines | lines / 1k | digits on them | digits differ |
|---|--:|--:|--:|--:|---|
| `reappraisal/Chapter1` | 4,151 | 4 | 0.971 | 8 | yes |
| `reappraisal/Chapter2` | 4,252 | 5 | 1.187 | 10 | yes |
| `what-takes/Chapter1` | 3,805 | **0** | 0.0 | 0 | — |
| `what-takes/Chapter2` | 3,917 | **0** | 0.0 | 0 | — |

**The forged world's two chapters carry zero system lines across 7,722 words.** Of the 152 own
drafted scenes, the 18 that carry one come from two books only (`toll.db` 10, `serial.db` 8).

**Within story**, at five chapters minimum: **394 stories**, mean of story means **2.59%** of
chapters with a system line, and **65 of 394** have at least one such chapter. Reported because
every confound this directory has killed was a between-story one.

**The era split, printed unasked** because `tricolon_rate` died to exactly this control:

| RoyalRoad cohort | n | % with ≥1 system line | lines / 1k (median) |
|---|--:|--:|--:|
| `declared_ai_2025` | 941 | 8.29 | 0.0 |
| `undeclared_2025` | 6,498 | 2.66 | 0.0 |
| `human_pre_llm` | 6,717 | 1.16 | 0.0 |

**Nothing is concluded from that split here**, and the seven-fold gap between `declared_ai_2025`
and `human_pre_llm` is exactly the shape `tricolon_rate` had before its control landed. Anyone
tempted to read it as an AI tell owes the control BRIEF.md §2 demands first.

### 4.1 What the counter cannot see, named rather than footnoted

- **`_SYSTEM_LINE` reads a bracketed all-caps tag and nothing else.** The 21-book fitness corpus
  renders its system voice as *unbracketed* ALL-CAPS readouts and contains zero bracketed tags
  (`chapter-endings-census.md` §3.2), so it contributes zero to every share here. **Every
  percentage in §4 is a floor, not an estimate.**
- **`digits differ` is the cheapest "did a number move" a regex can see.** It compares consecutive
  system lines within one unit. It cannot tell a rise from a fall, cannot tell a level from a page
  number, cannot see a change carried across a chapter boundary, and reads two lines about
  different subjects as one comparison. Its denominator is units with ≥2 system lines, because a
  unit with fewer has no comparison to make and counting it as "did not move" would report an
  omission of ours as a fact about the prose.
- **No bar.** This distribution is what a future "the number should move at least every N words"
  would sit on. The operator sets N. Stage-0 §81, §85, §87 and §89 each record a bar declared over
  a quantity that could not do what it said.

---

## 5. P1 answered; P2–P5 pre-registered and not yet answered

**The forge ran on 2026-08-22** (`dec-25c58304a408437ec81d74a3`, $1.4955, 98,521 tokens, one
invocation, no fallback). §3 did **not** run and nothing was picked, so P2–P5 are still open.
[`plan/serial-pilot-5.md`](../../plan/serial-pilot-5.md) §5 is the full record; the short form:

**P1 is answered, in the direction the rules were written for.** 3 of 3 candidates clear every
gate and every validator. Each declares **exactly one ordinal ladder of five rungs, listed lowest
first**, with the protagonist standing on rung **3 of 5** — below the top in all three. Each rung
of all fifteen carries a `visible_form` and a `cost_to_reach`. All three declare a `graph_line`
carrying a `stands_at` phrase. **Within-forge spread 0.9163** against pilot 2's 0.9302, pilot 3's
0.8959 and pilot 4's 0.9158: the stop condition does not fire — the new rule set did not collapse
the forge.

**And 3 of 3 inversions leave the ladder alone**, against 3 of 3 removing a rule-1 ingredient on
the same brief before it. Each removes something adjacent instead — "the private grind", "the solo
climb", "choosing when to advance" — and each explicitly keeps the rung, the rise and the count.

**Two convergences are recorded rather than smoothed over**, in `serial-pilot-5.md` §5.2: all
three chose five rungs and the exact middle one, against a rule that named a floor of three and
"not the top"; and all three rendered the `stands_at` edge as the English `"now stands at"`,
because naming the predicate by its constant is what fixes the phrase. Their other four graph-line
phrases are entirely their own.

**The pick was not made.** The recorded rule turns on whether *assaying and hallmarking* counts as
already-used — never *forged*, but the subject of the only assembled book in this repository. That
is `VerdictSource.HUMAN`'s to resolve and pilot 4 §5.4 is the precedent for putting it to the
operator rather than reading it away with the candidates in view.

The priors each question is read against:

| # | question | prior, from §1 and §3 |
|---|---|---|
| P1 | does the forge declare a ladder, place the protagonist below its top, and leave the ladder out of the inversion | prior: 2 of 4 worlds had an ordinal chain of ≥3; **0 of 4** placed anybody on one; **3 of 3** on this brief inverted a rule-1 ingredient. **Answered 2026-08-22: 3 of 3, 5 rungs each, protagonist at 3 of 5, 3 of 3 inversions leave the ladder alone, spread 0.9163** |
| P2 | does the schedule rise | no outline in this project has ever been asked. `progression_target` was non-None at **0 of 9** positions across both books |
| P3 | does the number move on the page | **0 rises, 0.0 graph lines per 1k** on both books; *What Takes* declared a line and printed none of it across 7,704 words |
| P4 | is the rise the protagonist's | 0 standings for every subject on both books |
| P5 | is the price on the page | 0 priced rises, because there are no rises |

---

## 6. What is still not known

- **~~Whether the forge declares a countable ladder at all.~~** Answered: 3 of 3, see §5.
- **Whether a model, asked for a rising rung schedule, returns one that validates.** The
  validator refuses stasis, flat stretches and any fall; nothing has ever been asked the question.
  A first-attempt refusal is information about the rule text, not about the model.
- **Whether the writer prints the line.** Every link before it is now closed and this is the one
  that has never been exercised. P3 is exactly this question.
- **Whether the rung's visible form reaches the prose at all.** Nothing asks for it and nothing
  counts it: `standing.py` counts standings and printed lines, `system_lines.py` counts bracketed
  tags. That gap is drafted as **C11** in
  [`plan/serial-pilot-5-craft.json`](../../plan/serial-pilot-5-craft.json) `proposed`, and it is a
  craft rule the operator issues — no form of it is in code, and none may be.
- **Whether any of this changes a reader.** Nothing here touches that question. There is no
  instrument for it in this project and this note adds none.
