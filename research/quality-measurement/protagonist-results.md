# The protagonist the pipeline never decided: what was measured, what shipped, and what did not

**Status: MEASUREMENT AND BUILD, 2026-08-22.** Answers
the stage-0 §112 protagonist task; the read that nominated the
work is [`plan/reader-read-3.md`](../../plan/reader-read-3.md); the decision record is stage-0
§112. Every number below was computed in this session against `main` at `f947247`, with the
scripts named. Nothing here is a claim that any book got better.

**Reading order.** §1 is the measurement that licensed the build; §2–§5 are what shipped, each
with the before/after bytes; §6 is what was refused; §7 is what was found and not fixed.

**The pilot ran.** [`plan/serial-pilot-4.md`](../../plan/serial-pilot-4.md) §5 and §6 carry it:
three forges, one pick by the operator, eight scenes drafted on *A Good Take*, gate green, P1–P5
answered as counts, $13.73. Two defects this branch shipped were found by that run's early gate
and are fixed with regression tests — stage-0 §112.7a. The headline the run adds to everything
below: **6 of 6 forged cast members reached the page and 8 of 8 scene statements name the
protagonist as the actor**, against 1 of 5 and an invented protagonist on *What Takes*.

---

## 1. Task 0 — measured before anything was built

### 1.1 The outline was blind to canon

`render_outline_request` (`application/outline.py:208` at `f947247`) took exactly five inputs, and
none of them is a `StateRecord`:

| input | type | where the one caller got it |
|---|---|---|
| `premise` | `str` | `premise_of(base.items)` — the string typed at `new`, verbatim |
| `beats` | `Sequence[Beat]` | `beats_for(head, template_for(head))`; only ordinal, of_total and function are serialised |
| `base` | `PlanRevision` | only `base.plan_revision_id` reaches the prompt |
| `seed` | `Mapping \| None` | the first canon `status_snapshot` record's **value dict**, and nothing else about that record |
| `promises` | `Sequence[Promise]` | the promise ledger's open rows — a different table, not canon |

The module contained **0** references to `domain/worlds`, so `worlds.project` — the sentence-per-
record projection the packet uses — was never called there. The call site read the whole of canon
(`outline.py:823`) and consumed it in exactly one expression: the `next(...)` looking for a status
snapshot. **On a forged world that finds nothing**: 0 of pilot 3's 328 records carry
`status_snapshot`, so `seed or None` was `None` and the request was the bare 7-rule control.

The control is pinned by its bytes: system message 254 chars, sha256
`8a5bccca338643c39fffd07da9e74a143ead905d1a7e2eb47d0422d901ab8839`; 7 rules bare, 12 with a
non-empty seed, +4 more when a promise survives the ordinal filter.

### 1.2 The viewpoint seam was wired and never passed anything

`pov_character_id` has 10 source sites (`planner.py:500,560`; `context.py:198,306,357,439,444,652`;
`state.py:115,123`). Of the **27** `packet_for` call sites in the repository — 1 in `src/`
(`planner.py:871`), 23 in `tests/`, and 3 outside both (`tools/interiority_packet_proof.py:159`
and `:180`, `research/progression-clause/ablate.py:470`) — **zero** passed one. Every packet this
system has ever built was built for no one.

The seam is not neutral when unused. `state.visible_to` is a whitelist in which an absent POV
**fails** a restriction: `visible_to(restricted-to-silas, None)` is `False`. So any record carrying
a non-empty `pov_visibility` would have been dropped from every packet in the book and logged
`not visible to POV (none named)`. Measured: **0 of 328** records on pilot 3's forged world carry
one, so on a forged world the filter is a no-op and the observable effect of passing an id is the
facts heading alone.

### 1.3 The premise is frozen at `new`

`cli.py:3464-3470` is the **only** `PlanKind.PREMISE` construction in `src/`: `logical_id
"plan-premise"`, `text=args.premise`, `locked=True`. The narrative planner's rules say *"Never
update or delete a locked item"* and *"The result must contain exactly one premise"*, and both are
enforced by raises rather than asked for — verified by running `apply_plan_proposal`, not by
reading it: an UPDATE or DELETE against `plan-premise` raises `PlanProposalError`
(`plan_refinement.py:270-271`, `:278-279`), and a second premise-kind item raises at `:243-245`.
The only bypass is a rollback proposal, reachable from `revert-plan` alone, which restores an
earlier revision and cannot author new text. `DirectiveKind.PREMISE` is **interpretive**, with the
lowest default precedence (10). **A `premise` directive cannot rewrite the premise.** The hook has
to be right at the forge, or arrive as a locked `constraint`.

### 1.4 The read's numbers, re-derived from the store

Substrate: `serial3.db` head revision `d47a488e…` and `book-library/what-takes/chapters/`. Scene 1
is a verbatim prefix of Chapter 1, so both substrates agree.

**Scene openings** (`domain/axes.opening_proper_nouns`, 300-word window):

| | s1 | s2 | s3 | s4 | s5 | s6 | s7 | s8 |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| raw | 2 | 4 | 1 | 2 | 3 | 2 | 3 | 4 |
| contraction artefacts | 0 | 1 | 0 | 0 | 0 | 1 | 1 | 2 |
| real names | **2** | **3** | **1** | **2** | **3** | **1** | **2** | **2** |

The real-name row is exactly `reader-read-3.md`'s **2, 3, 1, 2, 3, 1, 2, 2**. **Correction in
place:** that document says the counter flags four `I'll`/`I'd`/`I've` false positives; there are
**five**, across four scenes — scene 8 carries two. The real-name row is unaffected. C6 was
honoured in every scene.

**Chapters** (`named_persons.py`, whole-chapter window, tokeniser offsets):

| chapter | words | raw | net of contractions | per 1k |
|---|--:|--:|--:|--:|
| Chapter 1 | 3,805 | 9 | **8** | 2.10 |
| Chapter 2 | 3,917 | 21 | **18** | 4.60 |

Chapter 1's introductions: `Lady Ossary` 0, `Kell` 17, *(I'll 236)*, `Assize` 804, `Ivor Ossary`
1234, `Sull` 2936, `Del` 3123, `Hask Orley` 3201, `Vane` 3565.

**Correction in place, and it resolves an apparent contradiction.** `reader-read-3.md` gives word
804 for where the protagonist's trade is first stated, and an independent re-derivation found 802.
Both are right about different indexes of the same sentence: a plain `str.split` puts `clerk` at
**802** and `Assize` at **805**; `domain/axes`' tokeniser puts `Assize` at **804**. The document's
number is the tokeniser's. Every offset in this file is a tokeniser offset and says so;
`test_an_offset_indexes_the_tokeniser_and_not_a_naive_split` pins the distinction.

**Kell.** First appearance at word **17** (0-indexed, plain split — *"Lady Ossary held her arm out
across the table, and the old cloth would not come away."* is words 0–16). In scene 1 he is named
**9** times to Lady Ossary's **7**, and all seven of hers are the full "Lady Ossary" — bare
`Ossary` is 0, so the surname count cannot be inflated by the brother. **`Kell` occurs 0 times in
`pilot3/direct1/forge.json`**, and 0 times in `seed.json`, `directives.json`, `promises.json` and
all 328 of `serial3.db`'s state records. The scene-1 statement the writer executed reads: *"Kell, a
grafting-clerk of the Assize, watches…"* — the outline invented the person, his trade and his
errand.

### 1.5 The forged cast on the page

| forged cast id | is_a | whole-word hits in the two chapters |
|---|---|--:|
| `hesper_ivane` | bark-matcher | **0** (near-collision only: the prose has an `Ilsa Vane`) |
| `nib_calder` | orphan-trade runner | **0** |
| `ossen_wray` | wasper | **0** (the prose's dominant surname is `Ossary`) |
| `teoma_shale` | crowned hand | **0** |
| `clerk_amble` | Assize clerk | **6** on `amble` |

**Correction in place.** `reader-read-3.md` says *"None of the forged cast reaches the page"* and
that *"Amble" appears only as a place-name and a surname the outline reused*. Measured, the
intersection is **1 of 5**, not 0: `Amble` is used three times as a vocative to a clerk and three
times inside a read-out record naming a `Rester Amble` the prose calls a grandfather. Whether that
clerk *is* `clerk_amble` is a judgment with no instrument here; the name-level intersection is 1.
The direction of the finding is unchanged — four of five forged people never reached the page, and
the seventeen named persons the read counted were written by a call that had never seen the cast.

### 1.6 The cardinality exception was undeclarable, and the detector proves it

Pilot 3's picked world (`forge.json` candidate index 1, *What Takes*; decision
`dec-322a61ad75c577a9c711569f`, `verdict_source` HUMAN, *"the operator chose world 2 of 3"*)
declares four shapes:

| shape | predicate | scope | group_key | max |
|---|---|---|---|--:|
| `c_one_borer_jar` | `tests_with` | institution | subject | 1 |
| `c_one_donor_per_union` | `stands_donor_to` | cast | subject,order_key | 1 |
| `c_one_owner_per_trait` | `records_owner_of` | institution | object | 1 |
| `c_unions_per_stock` | `carries_union` | cast | subject | 4 |

**Positive control, measured.** Baseline over the unmodified 328 records: **0** findings. Two
planted `clerk_amble stands_donor_to …` edges (two, because the world holds zero `stands_donor_to`
edges and the maximum is 1): **1** finding —
`c_one_donor_per_union admits at most 1 stands_donor_to per subject,order_key; clerk_amble at  has 2`.
So the detector fires.

**And there was no way to except one person.** `in_scope`'s docstring: *"Scope is an `entity_role`,
or `*`. Not a subject id: a shape that named one carrier would be a fact about that carrier, and
the thing being declared is a rule about a *kind* of thing."* Traced end to end with a subject id
put where a role belongs: the schema enum excludes it, **but the enum is prompt text** — the CLI
transport serialises the schema into the prompt and `providers/base.parse_schema_payload` is
shallow by design and never descends into `worlds[].cardinality[].scope`. So a subject-id scope
survives parsing, `records_for` emits it unchecked, `cardinality_shapes` builds a well-formed shape
from it, and `in_scope` then matches it against `roles.get(subject)` — where a subject id can never
appear. **Silently ignored, at `worlds.py:736`.** The shape governs nobody and looks exactly like a
shape that governs everybody.

---

## 2. Task 1 — the protagonist as a declared fact of the world

**Schema.** An optional `protagonist` object — `id`, `exception` (a declared rule or cardinality
shape, by id), `edge`, `wants`, `price` — required in `_WORLD["required"]` and refused in
`worlds_from` the way a missing premise is refused, **field by field on emptiness rather than on
absence**: the 2026-08-22 forge returned a world whose `premise` was the empty string under a
schema that asked for a string, conformed, and then failed the shape check. The five new fields
carry `minLength: 1`; the older fields keep `_TEXT`, because tightening them would change the
schema every existing world was forged under.

**One rule** in `_RULES`, beside the inversion rule it complements (that one inverts a default for
everyone; this one declares an exception for one), cited to `reader-read-3.md` in the comment.
`test_the_protagonist_rule_asks_for_a_declaration_and_never_an_outcome` checks the rule text for
*win, winning, hero, likeable, sympathetic, root for, faster, fastest, strongest, best, succeed,
success, triumph, interesting, compelling*. The word *reader* is deliberately not on that list and
the test says why: the rules beside it already use it for what shows on the page.

**Records.** `protagonist` added to `worlds.ENTITY_ROLES` as a **second** role on a cast member
(`entity_roles` returns roles plural, so nothing has to choose between "cast" and "protagonist");
`edge`, `wants`, `price` as assertions and `exception_to` as an **edge**. A `wants` declared twice —
once on the cast entry, once on the protagonist — produces one record, because `records_for` keys a
record on its content.

**The exception reaches the gate.** `CardinalityShape.except_subjects`, populated from an `excepts`
edge, and `in_scope` returns `False` for an excepted subject before it looks at roles. Two
declaration sites, one predicate, one reader: a shape may list `"except": [ids]` itself, **and**
`records_for` emits `<shape> excepts <protagonist>` when the protagonist's `exception` names a
declared shape. That derivation is the one in the module and it is a definition rather than an
inference — "X is the exception to shape S" and "S does not govern X" are one fact from two ends of
one edge, and only the second is what the detector reads. Without it a world could declare an
exception the gate still refuses, which is decoration.

Three assertions, pinned together, and the third is the one that matters:

| | |
|---|---|
| a shape that excepts nobody | fires on the planted violation, exactly as before |
| the same violation on the excepted subject | **0** findings |
| the same violation on a **different** subject of the same kind | still fires |

A change that made the detector blind to the *shape* would pass the middle assertion and fail the
last one.

**Gate complaints**, non-blocking like the rest, and silent for a world that declares no
protagonist: the id is not a declared cast id; the exception names neither a declared rule nor a
declared shape; the premise never names the protagonist (word-boundary match on the snake_case
parts of the id, so a two- or three-letter part cannot be satisfied by the middle of an unrelated
word — the failure class `worlds.key_nouns` records from its own first live run).

**`report()`** gains `protagonist_declared`, `exception_declared`, `premise_names_protagonist`.
Counters, not verdicts; nothing orders one world above another.

**Backwards compatibility, as a test rather than a hope.** `plan/serial-pilot-2-world.json`
regenerates to the same **329** records at `scenes=8`, gates clean, validates clean, declares no
protagonist, emits **no** record of the new vocabulary, and every shape carries an empty
`except_subjects`. (329 is an artefact of the forced `scenes=8`; `DEFAULT_SCENES` yields 328 — the
difference is the in-book disclosure positions.)

---

## 3. Task 2 — the outline is told the world's people

**Read the collapse first.** This section measures a `cast` input this call briefly took. Stage-0
§111 — the worldbuilding branch — reached `origin/main` before this work did, and its `world` brief
already renders every declared person from the same projection. So at the merge the `cast`
parameter, its rule, and `worlds.cast_brief` / `worlds.CastMember` were **deleted**, and what
ships is `world` (people included) + `protagonist`. §112.7 named that debt and this is it paid.
The numbers below are what the separate rendering measured; they are kept because they are the
before/after for *the world's people reaching the outline at all*, which is the finding, and they
are no longer a description of the shipped call's byte count.

`render_outline_request` renders nothing new when its inputs are empty. Absent rather than null:
`json.dumps` writes `null` for a key whose value is `None`, so a key that is always present is a
payload that always changed — and `input_digest_for` covers the prompt and is the sampler seed.

Measured on *What Takes*' own canon, before and after (this branch's `cast` rendering, since
superseded):

| | before | after |
|---|--:|--:|
| top-level keys | `base_plan_revision_id, open_promises, premise, rules, scenes, starting_state` | + `cast` |
| rules | 7 | 8 |
| prompt characters | 1,785 | **4,856** |
| system message | unchanged | unchanged |

The rule that ships, verbatim: *"The protagonist is `{id}`. This is `{id}`'s book, so each
statement says what `{id}` does in that scene, or what is done to `{id}`."* Position and fact;
`test_the_protagonist_rules_name_a_person_and_never_an_outcome` checks it for the same vocabulary
the Architect rule is checked for, plus *open on* and *first*. The cast rule this branch also wrote
— *"Every named person in this book is one of the people listed in cast…"* — went with the `cast`
parameter at the merge, because §111's `WORLD_RULES` already instruct the planner against the
brief it is handed.

The people reach the request **as the packet phrases them** — `worlds.project` first,
`state.describe` as the fallback, which is `context._state_item`'s own two steps (§107.3). That was
true of this branch's rendering and it is true of §111's, which is why the collapse costs nothing:
the two were the same two calls in the same order.

`outline_job_id` is epoch-keyed and excludes the prompt, so a tick over an already-outlined book
mints no second job; pinned.

---

## 4. Task 3 — the writer is told whose scene it is

The protagonist's id is read once per book (beside the chapter positions, which are the same class
of thing) and threaded into the one production `packet_for` call and into `render_prompt`.

**The packet diff, measured on `serial3.db` scene 1 at `--context-budget 16000` (on a copy; the
original is read-only):**

| | without | with `clerk_amble` |
|---|--:|--:|
| items | 305 | 305 |
| established facts | 224 | 224 |
| hidden claims | 23 | 23 |
| tokens | 7,493 | 7,493 |
| omitted | 0 | 0 |
| render bytes | 38,946 | 38,967 |

**Two lines change and nothing else:**

```
-Established facts:
+Established facts known to clerk_amble:
```

That is the whole observable effect on a forged world, and it is what §1.2 predicted: `visible_to`
admits records restricted to that id, and a forged world has none. The prompt diff is one line —
`Point of view: clerk_amble.` between the chapter cue and `Dramatic function:`, never after
`plans.scene_plan_line`, which stays last so `plan_search`'s K candidates keep differing in exactly
one place.

---

## 5. Task 6 — the counter, and the null under it

Full report: [`named-persons-results.md`](named-persons-results.md). The headline, because it is a
result and not a footnote: **the counter does not reproduce the complaint.** The two chapters the
operator named as having too many names introduce 8 and 18 distinct names, at the **11.8th** and
**37.6th** percentiles of 2,000 cached LitRPG chapters (cohort median 24), and 2.10 and 4.60 per
thousand words against a cohort median of 10.90. *Reappraisal*, which this read did not complain
about, sits at the 63.5th and 61.6th. A chapter budget set from this distribution would license
*more* names than the complained-about book has.

This is the second time a counter nominated by a human read has failed to order the case that
nominated it. `plan/serial-pilot-4-craft.json` therefore carries C9 with its number unset and
**outside** the array any script reads.

---

## 6. What was refused

- **No verdict channel.** No model was asked whether a hook is good, which premise hooks more,
  whether a protagonist is interesting, or which of K worlds to pick. `domain/discrimination.py`
  is untouched.
- **No bar.** Every count here is descriptive and says so. The one number the operator might want
  — a chapter-grain introduction budget — is unset, with its distribution and its null beside it.
- **No instruction about how to write a protagonist.** Not in `_RULES`, not in the outline rules,
  not in the beat line, not in the packet. Three tests check the three strings for the vocabulary
  such an instruction would need. C10, which *is* such direction, is written into a `proposed`
  array and not issued.
- **No verdict on the book.** Task 4 ran and §6.2 reports P1–P5 as counts. It is one book against
  one book and the two differ in more than the protagonist; nothing here says *A Good Take* is
  better than *What Takes*, and no instrument in this project could. The pre-registration was
  written before the first paid call and is unedited.
- **Nothing read-only was written.** `serial3.db`, `pilot3/`, `serial.db` and the pilot-2 files are
  untouched; every measurement that needed a mutable database ran on a copy in a scratch directory.

## 7. Found, not fixed — each one a separate piece of work

1. **`c_one_owner_per_trait` can never fire, and neither can any shape with `group_key: "object"`.**
   `group_of(record, "object")` returns the `object_ref`, and `detect_cardinality_violations` then
   counts *distinct object_refs inside that bucket* — which is identically 1. So an object-keyed
   maximum is vacuous however it is declared, and one of pilot 3's four shapes is dead. Verified
   structurally and empirically (2, 3 and more edges into one object all produce 0 findings).
   Fixing it changes detector semantics for every world already forged and could newly refuse
   scenes in books already accepted, so it is reported here and not touched.
2. **A relationship reaches the outline and the packet in `state.describe`'s flat form**, so the
   cast brief carries lines like `clerk_amble employed_by and is the only person who can find
   anything in it (the_assize)`. It reads badly, and it reads *identically* badly in the drafting
   packet — which is why it was not improved here: a better sentence for a relationship edge
   belongs in `worlds.project`, and that would change the packet of every book with a forged world.
3. **The outline invents answers to forged mysteries.** Named in the handoff as a separate piece of
   work and left alone.
4. ~~**The retired worldbuilding branch also adds a keyword to `render_outline_request`**
   … whoever merges second should collapse the two cast renderings into one.~~ **Done at the
   merge, not deferred.** §111 reached `origin/main` first; this branch merged second and deleted
   its own `cast` parameter, `CAST_RULES`, `worlds.cast_brief` and `worlds.CastMember`. What ships
   is `world` + `protagonist`. See §3 above and stage-0 §112.7.
