# The Architect role: a world the writer must honour and rarely states

**Written 2026-08-21, before any code in this design was written and before any world was
generated.** Companion to [`plan/state-model-abilities.md`](state-model-abilities.md), which
designs the ontology this builds *to*, and to
[`research/progression-generalization.md`](../research/progression-generalization.md), which
overturned that ontology's first six claims. This document is the role; those two are the model.
The order matters: a world-builder that invented its own schema would be a fourth answer to a
question the research already settled.

The Architect is the fourth role after Director, Writer and Reader/Judge, and it sits **upstream
of all of them**. It says what the world *is*. It never says what the book is about (Director),
never drafts (Writer), never judges (Reader/Judge).

---

## 0. Where this came from, and what is measurably missing

**Operator direction**, standing, distilled across
[`plan/state-model-abilities.md`](state-model-abilities.md) §0, the progression-model memory
and the popcorn-register direction: readers come for unique abilities and their interactions
with the world; ranks are the fun part and a rank is something you can *see*; a world may hold
several systems with incompatible logic, or none, or a crafting-only one; there are powers above
the protagonist; power lives in objects that change hands; companions bond with trait-linked
joint abilities; breakthroughs are earned at comprehension hurdles; a system usually has a
personality and usually hides it. Underneath all of it: **the reader should feel an iceberg
under fast, plain prose.**

**What the repository actually has, measured 2026-08-21 against `serial.db`, the live serial.**

| | count | what it is |
|---|--:|---|
| canon state records | **23** | the whole world model of a nine-scene serial |
| — operator-typed seed records | 15 | `plan/serial-pilot-seed.json`, hand-written |
| — records the loop itself wrote | 8 | `status_snapshot`, `litharness.systemvoice.v0` |
| records carrying an edge (`object_ref`) | 7 | every one of them operator-typed |
| promises open / paid | **40 / 0** | the ledger has nothing to pay with |

So: the Advent, the tiers, the Tide, Marta, Vance, the assay house, the crown-and-hook mark —
every one of them appears in the prose of a book whose canon has never heard of it. Nothing in
`src/` invents a world, and nothing persists what the drafter improvises except the `[STATUS]`
line. The eight records the loop wrote are eight readings of one line form.

**And nothing in `src/` writes an edge.** `plan/state-model-abilities.md` §1 records this and it
is still true: both golden fixtures hold zero records with `object_ref` set and no code
constructs one. The live serial's seven edges came from the operator's keyboard. This is the
capability the Architect turns on, and it is why the role costs less than it looks like it
should.

---

## 1. PREREQUISITE — three defects measured before this design was written

Each was run against this repository rather than reasoned about. Each is a way a generated
world would be silently discarded, so each is fixed before the world is generated.

**1.1 The contradiction detector reads `value` and nothing else, in both directions.**
`detect_contradictions` groups on `(subject, predicate, order_key)` and counts distinct
`_value_key(record.value)`. `object_ref` is in neither the key nor the count. Measured, with the
probe in `tests/test_worlds.py::test_the_edge_cases_the_design_note_measured`:

| what the book says | how it is spelled | findings today |
|---|---|---|
| `card_of_ashes held_by → silas` and `→ marta` | edge, no value | **0** |
| the same, each edge annotated differently | edge, different values | **1, MAJOR, blocking** |
| `ash trait → keen_scent` and `→ night_sight` | edge, no value | **0** |
| `ash trait = keen_scent` and `= night_sight` | value, no edge | **1, MAJOR, blocking** |
| `silas status_snapshot {loop 1, day 1}` and `{…day 2}` at `s1` | value | 1, MAJOR, blocking |

A real impossibility is invisible; an ordinary fact is refused; and what decides which is
whether the fact was written as an edge or as a value.

***Correction, in place rather than folded away.*** `plan/state-model-abilities.md` §2's table
gives the third row as **1, MAJOR, blocking**. Run, it is **0**. The row is right only for the
fourth spelling — the trait in `value` — and the design note does not say which spelling it
measured. The generalisation the note drew from it survives and is if anything stronger: the
detector is not backwards on edges, it is *blind* to them, and the thing it actually keys on is
the annotation.

**1.2 Reified records are precise and prompt-illegible.** `state.describe` renders
`subject predicate value (object_ref)`. A five-record reified change arrives in the drafting
prompt as five machine lines. Measured on the pilot's own seed, the sheet declaration reached a
scene as `silas status_sheet fields=[{'label': 'Loop', 'name': 'loop'}…]` — which is why
`CONFIGURATION_PREDICATES` exists as a narrow patch. The general fix is a projection.

**1.3 There is no way to say "true, and nobody has been told".** `pov_visibility` is packet
access control and `plan/state-model-abilities.md` §0.1 row 2 forbids overloading it. So the
one thing an iceberg is made of — a fact that is true, that the writer must honour, and that no
character and no reader has yet been given — **cannot be said at all**. A secret written into
`pov_visibility` reaches no packet, which is the opposite of what it is for.

---

## 2. The rail: an Architect proposes a world; it may not lock a plan item

The Director's rails are that a brief may name what the book is about but not what good prose
is, and that a personality has to be earned. The Architect inherits both and needs a third,
because it writes into **canon** rather than into a directive inbox — and canon is what the
packet hands the writer as "established and may be relied on".

**Rail one: Architect output is a proposal, and it enters canon only through a recorded policy
decision after deterministic gates.** Mirrored on `directors.machine_author`: every record and
directive the Architect produces is stamped `architect:<architect_id>`, the id is a content
address over the brief, and the decision that admits a world carries the candidate count. It may
not lock a plan item: `PlanAuthority.INTENDED`, `locked=False`, exactly as `outline.py` records
its own reason — *"a model wrote it"*. The one locked item a forged world produces is the
premise, and the premise is locked by `cmd_new` on the operator's act of running it.

**The rail has exactly one exit and it is `forge --pick`.** `records_for` defaults to `PROPOSED`
and is called with `ACCEPTED_CANON` at that one call site, where a person has chosen among K and
the choice is its own decision row — the same authority `cmd_import` writes an operator's
snapshot under, on its own recorded grounds: *accepted on the director's authority, not extracted
from prose this system generated*. **Without that exit the role would be inert and quietly so**:
`context.assemble` filters proposals out by `is_canon` before anything else happens, so a serial
seeded from an un-admitted world would draft against a premise and nothing else, looking at every
layer exactly like the book this role exists to stop producing.

**Rail two: no model picks the world.** K candidates are generated in one structured call, gated
deterministically, and then *stopped*. If a world is chosen among K, a person chose it and the
choice is a separate recorded act with its own decision row. §61(5) then divides the confidence
level by the candidate count, and the count is on the record so the division is possible.
`plan_search`'s judge path is not reused and is not reachable from here: there is no quality
ordering over worlds, and inventing one would be the frame this project has buried three times.

***Amended 2026-08-24: a forge is three stages of calls, and the rail is unchanged.***
`plan/handoff-clarity-first.md` boundaries 4 and 5 split the premise out of the structured call
— the world is data, and the paragraph a reader is pitched is written as prose by its own call —
and put a comprehension screen between the premise and the operator: four genre readers restate
it and quote every word they were never given, and it passes at zero. **None of that orders
anything.** The screen refuses on a deterministic count, exactly as the world gates do; what
survives is presented in the order it was forged; and `--pick` remains the only selection. Each
stage records its own decision row, so §61(5)'s division still counts candidates rather than
calls. `application/comprehension.py` and stage-0 §125.

**Rail three: a palette, never a checklist.** A world may declare one system, several with
incompatible logic, crafting-only progression, or none. The generator is told this in as many
words, the validators never require a system to exist, and the counters report *coverage of what
was declared* rather than presence of what a genre expects. `research/progression-generalization.md`
§13's rejection list is the test: nothing here defaults to level, HP, MP, currency, a scalar
power score, a ladder, a diegetic System, a printed stat line, or combat.

**Rail four: RS1 / C3, enforced at the gate and not only in the prompt.** No real work, author,
brand, game or system is named, quoted or imitated in any generation prompt or output. The
prompt says so; a deterministic refusal reads the *output* for a shipped deny-list of the forms
this project has already seen a model reach for. It is a vocabulary guard and, per §97.3, a
vocabulary guard is not comprehension — which is why the prompt carries the rule as well.

---

## 3. The model, as record patterns over `StateRecord`

**No migration, no schema classes, no new record kind.** Everything below is
`(subject, predicate, value, object_ref, story_position, authority, pov_visibility)` — the shape
the contract already has and `record_json` already carries whole. This is
`plan/state-model-abilities.md` §5 item 3 and `research/progression-generalization.md` §14.1
item 2, taken literally.

**3.1 Entities are ordinary subjects.** The pilot seed already writes them:
`(silas, is_a, "junior appraiser at the Corvessa assay house…")`. The Architect adds one
machine-readable tag so counters can find them:

```
(ember_fox, is_a,        "a fox the colour of banked ash; it hunts by heat, not by scent")
(ember_fox, entity_role, "creature")
```

`ENTITY_ROLES = ("cast", "creature", "place", "institution", "carrier", "agency", "system")`.
A role is a tag on an ordinary subject, not a type — an agency is "an ordinary entity playing
causal, authorizing, validating, or recognizing roles" and nothing here contradicts that.

**3.2 Rules, and the consequences that are the actual content.**

```
(provenance,   world_rule,  "every made thing carries the history of its making, and that
                             history is what fixes its price")
(provenance,   consequence, "assay houses are banks; a ledger is worth more than the vault",
                            object_ref=economy)
(provenance,   consequence, "forging a history is the capital crime, not forging the coin",
                            object_ref=law)
(provenance,   consequence, "a child's first tool is kept unrepaired so its history stays
                             legible", object_ref=daily_life)
```

`CONSEQUENCE_DOMAINS = ("economy", "law", "religion", "crime", "daily_life", "politics",
"craft", "war")`. **Uniqueness lives in consequences more than in names**, so the counter is
distinct domains per rule and the gate is ≥3.

**3.3 Criteria, ranks, and the visible form.** A rank is an evaluation result under a
criterion, never a property, and the ordinal domain is `precedes` edges. The visible form rides
on the *result*, because that is the thing a reader sees:

```
(assay_grade, type,       "criterion")
(assay_grade, comparator, "ordinal")
(assay_grade, evaluates,  object_ref=appraiser)
(third_seal,  precedes,   object_ref=second_seal)
(third_seal,  manifests_as, "a plain lead seal on the cuff; it goes green in a week and
                             everyone knows how old yours is")
```

`COMPARATORS = ("ordinal", "numeric", "threshold", "equality", "set_inclusion", "pareto",
"replacement_equivalence")` — `plan/state-model-abilities.md` §5 item 7's registry, and
deliberately not a formula language.

**3.4 Constraints and scoped cardinality.** The five-record shape is
`research/progression-generalization.md` §8.2 unchanged:

```
(one_holder, type,      "cardinality_constraint")
(one_holder, predicate, "possessed_by")
(one_holder, scope,     object_ref=carrier)          # an entity_role, or "*" for every subject
(one_holder, group_key, "subject,order_key")
(one_holder, maximum,   1)
```

**Undeclared means unchecked.** A predicate no world declares a shape for stays untyped and
non-blocking, which is what keeps free-form predicates cheap. Minimum counts are not
implemented: under open-world reading a missing value is unknown rather than false, and a
minimum is unsafe until a scope is explicitly closed.

**3.5 Claims, belief, disclosure — the iceberg.** A claim is a node; `believes` and
`disclosed_to` are relations on it. This is where secrets live, and it is **not**
`pov_visibility`:

```
(claim_token_older, claim.content, "the token's countdown was started by whoever the tide is
                                    aimed at, and it is not the city")
(claim_token_older, contradicts,   object_ref=provenance)
(silas,             believes,      object_ref=claim_token_false)   # his false belief
(reveal_ch4,        disclosed_to,  "reader", object_ref=claim_token_older,
                                   story_position=s07)             # the payoff window
```

A claim with content and no `disclosed_to` at or before the current position is **true, not yet
disclosed**. That is the packet's hidden section, and the answer is recorded at forge time so
the promise ledger finally has something to pay with: each such claim opens a `mystery` or
`plot` promise whose due key is the disclosure position.

**A reveal scene and a reveal position are two things, and conflating them leaked.** An open-ended
serial schedules most of its answers past the chapters being written, and a story `order_key` is
an opaque string whose ordering means something only inside one book's vocabulary — `beats_for`
mints `s1…s8` for eight scenes, width **one**. A fixed two-digit `s04` therefore compares *below*
`s1`, and on the first pilot run **both answers the opening existed to keep were handed to the
writer as established fact from scene one**. So the ordinal is stored as an ordinal
(`worlds.REVEAL_SCENE`), a `disclosed_to` *position* is minted only in the book's own width and
only for a scene the book actually has, and a reveal past the end gets no position at all — the
claim stays hidden throughout, which is what "the reader is not told in this book" means.

**3.6 Cast, creatures, places — and what each owes.** All of them are ordinary subjects with a
role tag; what differs is the record patterns they carry, and each is a deliverable rather than a
nicety.

| | owes |
|---|---|
| **cast** | a `wants`; a `can_reach` — a *capability position*, stated as what is reachable rather than as a number; `relationships` as **edges** to other declared subjects (owes, employs, blames, outranks) with the one thing a scene could use; at least one **false belief**, as a claim marked `claim.false` and held by a `believes` edge; a **secret**, as a claim with no reveal; a `voice_tag` so two people do not speak alike |
| **creature** | a **mechanism** (how it works), an **ecology** (what it needs and what kills it), a **rank** if the world ranks it, a **human use** — trade, law or religion — one **behaviour that creates scenes**, a **bond potential**, and a `manifests_as`. A creature missing any of the first four is refused by the gate, which is what stops a renamed stock monster |
| **place / institution / history** | `is_a`, and for history a `prices_the_present`: the provenance layer whose only job is to make the past cost something now |
| **agency** | nothing special. `plan/state-model-abilities.md` §3.5's reduction: an ordinary entity playing causal, authorising, validating or recognising roles. A god, a State, a spirit and the System are cast members with an `agency` tag, which is what makes "immaterial things are characters" cost nothing |

**3.7 What the vocabulary reduces to.** Nothing above is a new primitive.
`plan/state-model-abilities.md` §3.5's reduction table stands unedited: a system is a named
bundle, an ability a named affordance, a tier ladder an ordinal criterion domain, a rank an
evaluation result, a cost an adverse effect, a carrier an entity whose possession changes
preconditions, a bond a composite subject, an agency a role, a hidden personality a claim not
yet disclosed. The Architect writes vocabulary; the store holds four patterns.

**3.8 The protagonist, added 2026-08-22.** A world may name one member of its cast as the
`protagonist`, and the record patterns are the ones already here rather than new ones: a second
`entity_role` on that cast member (roles are plural, so nothing has to choose between "cast" and
"protagonist"), `edge` and `price` as assertions in the `manifests_as` register, `wants` as the
cast pattern already carries it, and `exception_to` as an **edge** to the declared rule or
cardinality shape that does not hold for them. The exception is the shape of a hook as the
operator defines one — *an exception to the world's rule, belonging to one person*
([`plan/reader-read-3.md`](reader-read-3.md) note 1) — and the inversion rule of §4 cannot express
it, because an inversion changes a default for everyone.

**The exception reaches the gate rather than decorating the schema.** `CardinalityShape` carries
`except_subjects`, populated from an `excepts` edge on the shape, and `worlds.in_scope` returns
`False` for an excepted subject before it consults roles. Scope stays an `entity_role` and §3's
argument for that is untouched: a shape is a rule about a *kind* of thing. An exception is the
other object — a declared fact about one subject — so it is declared as one and read beside the
shape. Two declaration sites, one predicate, one reader: a shape may list its own `except`, and
`records_for` also emits `<shape> excepts <protagonist>` when a protagonist's `exception` names a
declared shape, because "X is the exception to S" and "S does not govern X" are one fact from two
ends of one edge and only the second is what the detector reads.

**3.9 Where the protagonist stands, added 2026-08-22 (§113).** §3.3's ordinal domain existed from
the first day of this design and **nobody ever stood on it**: measured across the four worlds
forged before today, two declared an ordinal chain of at least three ranks and *not one cast
member of any of the four* carried a standing on any chain. So one predicate closes it, and it is
`precedes`' own shape from the other side:

```
(silas, stands_at, object_ref=second_seal, value="assay_grade", order_key="s1")
```

**Flat, and the flatness is the argument.** The page can only print a flat edge — a scene writes
`[ASSAY] Silas now stands at second seal` and `parse_graph_line` reads it back — so the forge's
copy of the same fact has to be readable by the same function. The reified `EVALUATION_*` triple
of §3.3 stays exactly where it is, for the world that reifies an evaluation with an authority that
performed it (`research/progression-generalization.md` §8.3); a standing is not that case, and
writing both would be two answers to "which rung is this person on".

**The criterion rides in the value slot for `precedes`' reason**: a world may run two ladders at
once and an unscoped standing would splice them. The criterion a standing belongs to is otherwise
*derived* — `criterion_of_rung` finds which declared chain holds the rung and abstains when two
do, which is a `validate` complaint rather than a guess.

**The number is the rung's 1-based place in the chain and it is never stored.** The operator's
direction is that a rank ladder *is* the genre's number ("bronze to gold rank advance is the same
as the number going up; say bronze is 1 and gold is 3"), so `rung_index` computes it from
`ladder_of`'s chain when asked. A stored integer beside the chain would be a second answer to
"which rung is third". The chain is read **lowest first**, which is why the rule text says so —
see §8 item 7 for the measurement that forced the clause.

**Placed at the opening rather than left unplaced.** A standing is a fact that *changes*, so
`standing_of` has to be able to answer "which standing is in force at this scene" and
`standing_target` "which scheduled one is still ahead" — both comparisons of order keys. An
unplaced record asserts no position and `records_before` keeps it in every window, so an unplaced
standing could never be *before* a milestone. Standing world rules are unplaced for exactly the
opposite reason: they never change.

---

## 4. How to prompt for *unique* — the part that is prompting

One structured call, K candidates, refused deterministically on collapse. The prior this is
written against is the repository's own: **personas are inert and instructed distinctness is not
distinctness** (§89.1's byte-identical answer vector across four personas; §77's
persona-to-passage ratios of 0.0028, 0.0071, 0.0342). So each candidate is forced to differ on
axes that are *checkable after the fact*, not merely asked to be different:

1. **A literalised real domain**, named per candidate and required to differ across K. The
   system's logic and costs come from the domain's real constraints — assay, coopering, salvage
   law, beekeeping, epidemiology, bookkeeping — so the book runs on real ideas. Reappraisal's
   appraisal graph is the in-house proof that this survives contact with prose.
2. **A geometry**, from `chain | graph | cycle | threshold | estimate | set`, required to differ
   across K, and a one-line statement of what "progression" even means in this world.
3. **A collision**: two systems whose logics are incompatible, plus the interface between them —
   exchange rate, who can cheat whom, legal status. The interface is the content.
4. **An inversion**: one genre default removed or reversed, and what fills the hole.
5. **A consequence cascade**: every rule names ≥3 second-order consequences across distinct
   domains, each a plot engine.
6. **Visibility and price**: every rank has a form you can see; every gain has a cost payable on
   the page.
7. **The hidden layer**: the View lies or withholds; one mystery per arc with its answer
   recorded and a payoff window; a System's flat register *is* its concealment rather than an
   absence of personality (`plan/state-model-abilities.md` §6 item 5, taken).

**Two prompt shapes are built and the one that measures better is kept.** Shape A asks for the
world directly. Shape B asks for the *domain and its real constraints* first and derives the
system from them inside the same call. The repository's prior says instructed distinctness is
weak, so the comparison is between a shape that instructs and a shape that constrains the
material. Which won is reported with its numbers; if neither separates, that is the finding.

---

## 5. Change surface

Ordered, and each step runnable and measured before the next. `plan/state-model-abilities.md`
§5's item numbers are given so the two documents can be read against each other.

| # | change | where | design item |
|---|---|---|---|
| 1 | record patterns, validators, counters, projection | `domain/worlds.py` (new) | §5.3 |
| 2 | `forge`: brief → K candidates → gates → recorded decision → seed bundle | `application/architect.py` (new), `cli.py` | — |
| 3 | projection layer: reified records rendered as sentences before the packet | `domain/context.py` | §5.2 |
| 4 | packet section `hidden`: true, not yet disclosed — honour, never state, packed **above** the ordinary facts and rendered below them, with its own coordinate (`disclosure_at`) separate from the record-slicing cutoff | `domain/context.py`, `application/planner.py` | §5.5 |
| 5 | the criterion the scene is writing against, in the drafting system message | `application/planner.py` | §5.11 |
| 6 | scoped cardinality; `object_ref` enters the contradiction key | `domain/integrity.py` | §5.1 |
| 7 | second extractor family: a declared graph-line form, with promotion | `domain/extraction.py` | §5.9, §6.1 |
| 8 | a `mystery`/`plot` promise per recorded reveal, opened from the seed | `application/architect.py` | §5.10 |
| 9 | retrieval when the serial outgrows the packet | — | design note only, §101.2 |
| 10 | *(2026-08-22)* a declared protagonist, and a cardinality exception belonging to one subject | `application/architect.py`, `domain/worlds.py`, `domain/integrity.py` | §112 |
| 11 | *(2026-08-22)* the cast and the protagonist reach the outline; the viewpoint reaches the packet and the beat line | `application/outline.py`, `application/planner.py` | §112 |
| 12 | *(2026-08-22)* a declared ordinal chain, a standing on it, and the printed form a change of standing is announced in | `application/architect.py`, `domain/worlds.py` | §113 |
| 13 | *(2026-08-22)* the rung schedule: the ladder reaches the outline, `standing_milestones` is validated for direction, and the next rung and its line reach the drafting prompt | `domain/world_brief.py`, `application/outline.py`, `application/planner.py`, `domain/extraction.py` | §113 |
| 14 | *(2026-08-22)* a printed rung on a declared chain is read back as canon at that position | `domain/extraction.py` | §113 |

**Step 7's line form, because it is the one that could go wrong quietly.** The world declares
its own graph line the way it already declares its sheet, and a world that declares none
extracts no graph facts — absence is free and both golden fixtures are untouched by
construction. The declaration is a phrase → predicate map, so the printed line is the book's own
words and the parse is exact:

```json
{"label": "SYSTEM", "edges": [{"phrase": "is bonded to",   "predicate": "bonded_with"},
                              {"phrase": "now holds",      "predicate": "possessed_by"},
                              {"phrase": "is recognised as","predicate": "recognized_by"}]}
```

`[SYSTEM] Silas is bonded to Ember Fox` parses to `(silas, bonded_with, → ember_fox)`. This is
`research/progression-generalization.md` §14.3's rule honoured rather than dodged — a rigid
*hidden* extraction format is useful and a rigid in-story status line is not the general
abstraction — by making the in-story form a per-world declaration instead of a constant.

**Promotion, per §6 item 1.** A minted edge enters `PROPOSED`. Repetition never promotes. An
edge is promoted to `ACCEPTED_CANON` when a **later** scene names one of its endpoints under a
*different* predicate — the book used the thing again to do something. That is "later causal
reuse" in the narrowest form a deterministic reader can check, and it is stated as narrow rather
than sold as more.

### 5.1 Retrieval — the design note, and the number that makes it a real question

Step 9 is a note rather than code, and it is written now rather than deferred because steps 1–8
produced the measurement that decides when it stops being optional.

**Measured, on live forges.** A 329-record world assembles into a scene-one packet at **6,731
tokens of a 16,000-token budget** with zero omissions, and **13,031** at scene eight with all
seven prior 900-word scenes present. So a forged world costs roughly **46% of what a 16,000-token
packet can hold**, flat, from the first scene onward, and it does not grow with the book. Prose
does.

Three consequences follow and none of them needs a retriever yet:

1. **The 6,000-token default cannot carry a forged world.** The same world at 6,000 keeps 139 of
   231 facts and drops **all seven prior scenes**, 99 omissions in total. What survives is every
   one of the 18 hidden claims, because the iceberg packs above the ordinary facts — an ordering
   this measurement decided. `--context-budget 16000` is not a tuning knob for a forged serial;
   it is a precondition, and the pilot package says so.
2. **The binding point is neither the world nor the prose — it is the promise ledger.** Measured
   across Serial Pilot 2's eight live packets: the world holds flat at 229–231 facts while the
   **threads section grows from 6 to 41**, one row per promise the summariser opens. The prompt
   runs 9,052 → 14,443 tokens, prose stops fitting at **three prior scenes** from scene four
   onward, and the summaries slot absorbs the rest — `context_omitted` is **0 for the whole
   book**, on both runs. So a synthetic estimate of "the world plus seven scenes" was wrong in
   the right direction: at this growth the 16,000 budget runs out somewhere around scene ten or
   eleven, and what fills it is a ledger nobody prunes.
3. **What a retriever would have to be, when one is needed — and it is not the first thing to
   build.** The measurement above says the world is *stable* and the threads are what grow, so
   the cheapest real gain is a **ledger policy** (what an open promise is still worth carrying
   at scene forty) rather than relevance scoring over the world. When a world subset does become
   necessary, the honest first form is per-scene selection driven by the scene's own plan
   statement — a query with a known answer shape rather than an open ranking problem — and the
   projection already renders per record, so a subset costs nothing structurally.

**Why it is not built.** A retriever that selects world facts is a component that decides what
the writer is allowed to know, and this project has no measurement of whether its selection is
right. `domain/context.py`'s existing baseline is honest about the same gap and pays for it by
recording every omission; a world subset would make omissions *routine* rather than exceptional,
which is a different contract and needs a gold suite with binding-budget cases before it can be
graded. §101.2's point stands: the question is when the serial outgrows the packet, and the
answer measured here is **around scene ten at four scenes a chapter — and the thing that fills
it is the promise ledger rather than the world**, which is the first number this project has had
for it and not the number that was expected.

### 5.2 The two planner calls — added 2026-08-22

Until 2026-08-22 the Architect's world reached the
*writer* — a flat 229–231 established facts per drafting prompt on pilot 2, `context_omitted = 0`
— and reached neither call that writes the scene plan the writer executes. Measured on pilot 3:
`render_outline_request` received the premise, the beat sheet, the status seed and the open
promises, and **not one `StateRecord`**, so it invented a protagonist who occurs nowhere in the
forged world and every other named person in the book, while four of the five forged cast members
never reached the page. The change surface is two optional keyword inputs on that call —
`world` (the declared world including its people, phrased by `worlds.project` first and
`state.describe` as the fallback, which is `context._state_item`'s own two steps; stage-0 §111's
`domain/world_brief.py`) and `protagonist`, which is the one thing a brief grouped by kind cannot
say — plus `pov_character_id` finally passed at the one production `packet_for` call site, where
the seam had existed unused since it was written. A book whose canon declares neither renders the
bytes it rendered before, which is asserted rather than argued.

Two branches met at this call within a day of each other and one input was collapsed rather than
kept: a separate `cast` rendering was deleted when §111 landed first, because a request carrying
the same people twice spends its budget saying one thing (stage-0 §112.7).

---

## 6. What is measured, and what it is not allowed to say

Pre-registered as [stage-0 §107](stage-0-decisions.md) before the pilot runs. Distributions
before bars — no bar is declared here that has not had its range, direction, unit and
non-emptiness checked on the substrate actually in hand (the rule seven prior declarations
broke).

| # | quantity | range | direction | unit |
|---|---|---|---|---|
| M1a | within-forge **spread**: mean pairwise distance among the K worlds of one call | [0, 1] | reported, no bar | normalised compression distance |
| M1b | between-**shape** distinctness, `directors.distinctness` over the two prompt shapes | reading | between > within | the same distance |
| M2 | genre-lexicon overlap: share of a world's key nouns present in the RoyalRoad blurb/tag lexicon | [0, 1] | **reported, no bar** | share of key nouns |
| M3 | consequence domains per declared rule | [0, 8] | ≥ 3 to pass the gate | distinct domains |
| M4 | manifestation coverage over declared features | [0, 1] | 1.0 to pass the gate | share of features |
| M5 | integrity findings per accepted scene | [0, ∞) | reported | findings |
| M6 | disclosure-schedule adherence | [0, 1] | reported | reveals landing inside their window |

**M1 is two readings and only one of them is a distinctness.** `directors.distinctness` asks
whether the gap between two *sources* clears each one's own noise floor. K worlds from one call
share a source, so there is no floor to clear and the number can only say how far apart this
call's answers landed — that is M1a, and it is reported without a bar. The comparison that is a
distinctness reading is between the two prompt shapes, with the shape playing the role the
director plays in §89's control; at K=3 per shape that is exactly `DISTINCTNESS_FLOOR` draws a
side. `DISTINCT_NO_FLOOR` is a real outcome here and must not be reported as `DISTINCT`: the
pinned provider is greedy, and a control that cannot fail is not a control.

**M2 has no bar and the reason is the rule.** A ceiling on overlap would be a bar on a
distribution nobody has measured; `opening_proper_nouns` is the cautionary case in this
repository — a counter nominated for a named defect that turned out to place the complained-about
chapter at the **68.5th percentile** of published LitRPG openings, and therefore not to
discriminate the defect at all. So the K candidates' overlap distribution is reported first. The
lexicon is built from the `description` and `tags` columns of the cached RoyalRoad shards — a
column **no code in this repository has ever read** — and lives strictly on the measurement side
of RS1.

**M5 and M6 are fidelity, not quality.** Nothing here claims a forged world produces a better
book. Reader effect reaches this programme only through the §97 readership sim and the
operator's `NOTES.md` defect harvest; anything else is a hypothesis and is labelled one.

---

## 7. What the Architect may do, in one table

| | |
|---|---|
| **May** | say what the world is: rules, systems, criteria, cast, creatures, places, institutions, history |
| | record the answer to a mystery, and the position where it is disclosed |
| | propose directives of the interpretive kinds, and constraints that are *world facts* rather than prose doctrine |
| | derive a premise from the world it built |
| | *(2026-08-22)* name one member of its cast as the protagonist, the rule or shape that does not hold for them, what that lets them do, what they want and what it costs |
| | *(2026-08-22)* declare that a cardinality shape does not govern a named subject |
| | *(2026-08-22, §113)* declare where its protagonist **stands** on one declared ordinal chain, and the printed form a change of standing is announced in |
| **May not** | say what the book is about beat by beat — that is the Director |
| | write prose, or name a scene's events — that is the Writer |
| | judge anything, rank anything, or select among its own candidates |
| | lock a plan item, or write `ACCEPTED_CANON` without a recorded decision |
| | name, quote or imitate a real work, author, brand, game or system |
| | require a world to have a system, a ladder, a sheet, a number, or combat |
| | *(2026-08-22)* say how a protagonist should be **handled** — opened on, liked, shown winning, or progressing faster than anyone. An exception declared is a fact about the world; who wins is the book's, and the direction is the operator's |
| | *(2026-08-22, §113)* say how a **rise** should read — earned, felt, celebrated, paid off. A rung and its price are declared facts; how a scene handles reaching one is the writer's and the operator's |

**And nothing here can block.** The Architect runs before a book exists; it has no gate, no
veto, no `GateOutcome` of its own beyond the shape gate that refuses its own malformed output.
Enforced by the absence of the capability and pinned by a test, exactly as the Director's is.

---

## 8. Open decisions

1. **Does the book get to be wrong about a real domain?** Literalising assay or epidemiology
   means a deep reading can be *false*, and nothing here checks that. Carried over unchanged
   from `plan/state-model-abilities.md` §6 item 3; it remains the first quality question in this
   project with an answer outside the text.
2. **Who declares cardinality shapes for a second book in the same store?** "Undeclared means
   unchecked" is the safe default and leaves every invented predicate unchecked forever. Whether
   a shape can be minted from the page is not decided.
3. **How is a depth rung written down?** Short enough to sit in every later packet, specific
   enough to be checkably non-entailed by the rung beneath it. Unsolved; the Architect writes
   the hurdle and its answer, and the non-entailment check stays advisory.
4. **One Architect or several?** N architects divide §61's α by N exactly as N directors do, and
   nothing has measured that two briefs produce two worlds rather than one world in hats. The
   distinctness control is built for K candidates from one brief; the between-architect
   comparison is not run.
5. **Does a forged world survive its own serial?** The world is generated once, before scene
   one. Whether the growth path (step 7) or the operator is the right author of a mid-serial
   amendment is not decided, and no amendment surface is built.
6. *(2026-08-22, §113)* **Should "one standing per ladder at a position" be declarable?** It is
   not, with today's `GROUP_KEYS` (`subject`, `subject,order_key`, `object`) — and a subject
   legitimately on two ladders holds two `stands_at` edges at one position, so the shape is not
   simply a missing key. No group key was added: `plan/handoff-numbers-go-up.md` boundary 11
   refuses a `GROUP_KEYS` member without a decision saying why, and there is no measured case yet.
   Two rungs of *one* ladder at one position is counted as a descriptor by
   `research/quality-measurement/standing.py` rather than gated, so the decision waits on a
   number rather than on an argument.
7. *(2026-08-22, §113)* **Which way does a chain run when the world does not say?** The rule now
   says *lowest first*, because it had to: the one ordinal chain pilot 3 produced ran
   highest-first (`first_water → morning_right → tail_right → wash_right`) and a reader counting
   up it counts a person getting weaker. What is undecided is whether a *declared* direction
   should exist — a `direction` field on the criterion, or an ordering the validator can check —
   rather than a chain whose meaning depends on the rule text that produced it. Nothing is built;
   `rung_index` counts from the bottom of `precedes` and says so.

---

## 9. Anti-scope

No new judges and no new quality metric. No human raters, panels, or solicited judgment of any
kind — §95's scope axiom is unchanged. No selection among worlds by any model, score, ranking or
preference signal; no stat-sheet default and no hardcoded genre vocabulary; no schema class
where a record pattern will do; no new `StateRecordKind`, no migration, no contracts bump. No
claim about book quality from a counter. The Director, Writer and Reader/Judge roles are
untouched. Retrieval (step 9) is a design note and is not started. The golden fixtures are
untouched by construction, not by a compatibility branch: a world that declares nothing gets
exactly what it got before this existed.

**Added 2026-08-22 with the protagonist.** No model is asked whether a hook is good, which premise
hooks more, whether a protagonist is interesting, or which of K worlds to pick — the forge still
stops and a person chooses. No instruction about how to *handle* a protagonist enters any prompt,
template, beat function or system message; three tests check the three added strings for the
vocabulary such an instruction would need. No hook beat function and no change to `SIX_BEAT`. No
bar over any count the change produces, including the chapter-grain introduction distribution,
whose number is left unset for the operator. A world that declares no protagonist regenerates
byte-identically and its book renders the same outline request and the same drafting prompt it
always did — [stage-0 §112](stage-0-decisions.md).

**Added 2026-08-22 with the ladder.** No model is asked whether a ladder is good, which rung is
right, or whether a rise lands. **No adjective and no verb about how a rise should read** enters
any prompt, template, beat function or system message: the standing block reuses the numeric
block's own sentence, and two tests check the added strings against the vocabulary such an
instruction would need. No "level-up" beat function and no change to `SIX_BEAT`. No HP / MP / Gold
/ XP sheet for a forged world and no change to `DEFAULT_SHEET`. **No bar** on how often a standing
should move — the distribution is in
[`research/quality-measurement/numbers-go-up-results.md`](../research/quality-measurement/numbers-go-up-results.md)
§3 and §4 and the number is the operator's. The general ontology is untouched: comparators,
partial orders and revocable rank are exactly as §3.3 left them, and what the directed brief adds
is a genre contract over the arc being written, not a definition of progression — [stage-0
§113](stage-0-decisions.md).
