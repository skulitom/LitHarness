# Can our world model hold a magic system the genre agrees works?

**Status: MEASUREMENT, 2026-08-22. Nothing built, nothing changed.** The operator asked for a
falsification test: *"research and map the mother of learning magic system and how its progressed.
If this system cannot be modelled by our model we need to fix something."* This is that test and
its answer.

**The answer, after adversarial review: the model CAN express it, the forge is never asked to, and
what it produces is illegible to the writer. All three of those are plumbing.**

~~The answer is **no, and the failure is structural** — a forge that conforms to our schema cannot
declare that a person can do a particular thing.~~ **Corrected the same day, and §4a is the
correction.** That sentence was the fit agent's verdict; six adversarial agents were then set to
refute its gaps and **refuted all six, 0 standing**, and an independent re-derivation confirmed
them. The vocabulary was built for exactly this and the fit agent tested the one node type of five
that has no projection sentence. The finding survives in a better and much cheaper form.

**RS1.** This is corpus-side research and it stays there. The source is the cached serial
`corpus_io.mol_chapters()` reads (108 chapters, 806,157 words, verified on this machine). Nothing
in this file may become prompt text, a schema description, a rule or an example for the generation
side; the model-fit artefact was written with neutral placeholder ids rather than by importing the
book. Nothing under `src/litharness/` references it and
`tests/test_corpus_leak_audit.py` still passes.

---

## 1. What the source actually does, measured

Four sweeps read the text by targeted search rather than from recall, and every claim below is a
count or a quote from the text. **The system carries four distinct layers, and this is the finding
the rest of the document turns on.**

| layer | what it is | evidence |
|---|---|---|
| **A. a certification ladder** | an ordinal rank a person holds, 0th to 7th | *"a certified first circle mage"*; *"spells of the first circle and above"*; 21 ordinal-circle constructions |
| **B. expertise per discipline** | the same person is at different levels in different branches | *"a certified second circle **warder**"*; **109** constructions pairing a level word (*rudimentary, basic, proficient, advanced, mastering*) with a named discipline |
| **C. a personal numeric capacity** | a named capacity carrying a magnitude | *"'Magnitude 12,' Zorian said."*; *"average mages — magnitude 8 to 12"*; *"a 15 magnitude mage"* |
| **D. an inventory of capabilities** | a countable set of named things a person can do | **77** distinct named capabilities, a verified lower bound: every candidate regexed over all 108 chapters, 77 of 77 confirmed |

**It is quantified, and it is not scored.** Digits run at **0.41 per 1,000 words**, of which the
magic-mechanical ones are **0.117** — about one magic number per chapter and a quarter, 71% of
them in the first 46 chapters, and **not one measuring the protagonist's own power after ch 46**.
The two densest magic-number chapters are the two where a friend explains the scale for the first
time. The scale is taught once and then the reader does the arithmetic unaided. `stat` and `stats`
occur **0 times in 806,157 words**; there is no status window, table or readout — the 705
bracketed spans are the book's typography for telepathic dialogue, which is the opposite thing.

**The inventory is never shown as a list.** No glossary, no appendix, no menu. The text refuses to
enumerate three separate times and makes the refusal a plot obstacle: an in-world oracle *"refused
to list all the abilities the Controller had"*, and a character says the quiet part — *"It's happy
to tell us about specific abilities if we ask, but a simple list of all options is forbidden?"* So
"no lists of abilities" as a reader complaint is not a request for a literal list. It is a request
for an inventory that **exists** and can be felt accumulating.

**Acquisition is a priced transaction with named prerequisites.** Prerequisite chains are spoken
by teachers and run to **five links**; composition is pervasive and mechanical (dimensionalism +
divination → teleportation; soul perception → simulacrum; alteration + animation + warding → a
training construct). Prices are concrete and various — unpaid labour, a monster's egg sack, a
teacher's moral objection, an iteration spent raiding. Gating is by **people with motives**, not by
institutions issuing permits.

---

## 2. The test: an actual world, against the actual schema

A MoL-shaped world was written against `architect._WORLD` and run through the real code. **It
passed everything**: 0 schema errors, `worlds_from` accepted it, `gate_candidate` returned 0
complaints, `worlds.validate` returned 0 complaints, `records_for` produced 317 records (99 edges).

**And the clean pass is the finding, because of how it was obtained:**

> *"I had to fabricate to satisfy it: I promoted a private drill sequence to a rank ladder and
> invented a `visible_form` for each of its five rungs, because the gate refuses a rung nobody can
> see."*

The verdict, in one sentence — ~~and it is wrong; see §4a~~:

> ~~"There is no record that says a person can do a particular thing, and no record that says how
> they came to be able to do it."~~

The half of that verdict which **survives refutation**, and it is the half that matters:

> *"Every rung of every ladder the forge has produced being a permission rather than a capability
> is **not a drafting failure or a prompt failure — it is the schema being followed correctly**."*

The rungs are insignia because `_RANK` has no slot for what a rung lets you do. That stands. What
does not stand is that the *world* has nowhere to say it — it has somewhere, one level down, and
nothing points a forge at it.

---

## 3. The four layers against our model

Each row re-verified directly against the code rather than taken from an agent.

| layer | our model | measured |
|---|---|---|
| **A. certification ladder** | **yes** | `_CRITERION` + `_RANK` + `precedes` chain + `stands_at`. The rising half is being built next door — [`plan/handoff-numbers-go-up.md`](../../plan/handoff-numbers-go-up.md) |
| **B. expertise per discipline** | **ontology yes, schema no** | `worlds.standing_of` already returns **a dict keyed by criterion** — its own docstring: *"A dict per criterion rather than one rung, because a subject may be on two ladders."* But `_PROTAGONIST.standing` is a **single object**, and `_SYSTEM.criterion` is a single object and not an array — so a forge can declare one ladder per system and one standing per person |
| **C. personal numeric capacity** | **no** | The **only two integer fields in the entire schema** are `mysteries[].disclosed_at_scene` (a scene ordinal) and `cardinality[].maximum` (an edge count). Nothing anywhere attaches a magnitude to a person or to a named capacity. `numeric` and `threshold` are members of `COMPARATORS` that no code computes with |
| **D. inventory of capabilities** | **no** | `_WORLD` has twelve array fields — systems, agencies, carriers, bonds, cast, creatures, places, institutions, history, mysteries, cardinality, directives — and **none holds abilities**. Every capability-shaped field is a single string with no plural: `reach`, `grants`, `recognises`, `joint_ability`, `edge` |

**`_RANK` is where layer D dies.** It is `additionalProperties: false` with exactly three
properties — `id`, `visible_form`, `cost_to_reach`. A rung can say what it **looks like** and what
it **costs**, and has **no slot for what it lets you do**. That is why 86.5% of the 156 rungs this
project has forged are insignia: the schema has nowhere else to put them.

**The forge is not even asked.** The words *ability*, *abilities*, *skill*, *magnitude* and
*capab-* occur **zero times between them** in the 5,657-character forge prompt (k=3, scenes=8,
measured directly).

**And what it does emit, nothing reads.** `can_reach`, `grants`, `recognises` and
`prices_the_present` have exactly two mentions each in the whole of `src/` — the schema line and
the emit line in `architect.py`. There is no constant, no validator clause, no projection sentence
and no reader. They reach the packet as flat `state.describe` notation.

---

## 4. The gaps, sorted by what they cost to close

**(1) The ontology already works and the forge never asks — plumbing.**
- **Acquisition.** A `type: change` node expressing *how a capability was gained* validates clean
  today and projects to a readable sentence carrying `needs` / `performed by` / `authorised by` /
  `costs` / `produces`. `worlds_mod.CHANGE` appears **0 times** in `architect.py` and `_WORLD` has
  no `changes` array. This is the largest single gap and it needs no new ontology.
- **Layer B, the expertise matrix.** `standing_of` is already per-criterion. Making
  `_PROTAGONIST.standing` a list and `_SYSTEM.criterion` an array would let a world say *second
  circle warder, rudimentary diviner* — which is what the source does 109 times.
- Eleven `CHANGE_ROLES`, the `evaluation.*` triple and `recognized_by` — *"what separates rank
  from capability"* — are all in the vocabulary with **zero write sites anywhere in `src/`**.

~~**(2) The ontology genuinely cannot say it — design work.** A capability subject and a `can_do`
relation … the reduction was never implemented.~~ **Refuted — see §4a.** The reduction *is*
implemented; it is spelled `change` + `CHANGE_ROLES` + free-form edges, and it works today.

~~**(3) Worse than absent — actively refused.** `_ladder_complaints` refuses a world that relies on
set-inclusion progression.~~ **Refuted.** `GEOMETRIES` carries `"set"` as a first-class declared
geometry and `detect_cardinality_violations` is a set-cardinality counter — *"the only thing in
the repository that counts a set, and it exists for exactly this predicate shape."* A world may
carry both a ladder and a set; the ladder floor requires the former and does not forbid the latter.

**Layer C, a magnitude, is the one gap that survives in bucket (2).** Nothing in the vocabulary
attaches a number to a named capacity, and the only two integers in the schema are a scene ordinal
and an edge count.

---

## 4a. The correction: six refutations, and what they found

Six agents were given one claimed gap each and told to default to *refuted* unless they could show
what breaks. **All six refuted. 0 standing.** Each read `worlds.py` and `architect.py` in full and
then expressed the mechanic in running code.

**What the fit agent missed:** the `change` NODE_TYPE. It is one of five declared node types;
`CHANGE_ROLES` carries eleven members — `precondition`, `effect`, `consumes`, `produces`, `actor`,
`performed_by`, `authorized_by`, `validated_by`, `recognized_by`, `participant`, `caused_by` —
`_ROLE_PHRASE` ships an English phrase for every one, and `project`'s foldable set includes it.
`permits` is documented as *"what they make reachable"*, and *reachable* is the ontology's own word
for an ability.

**The strongest demonstration**, from the agent that took the capability-subject claim: a world
declaring **six named capabilities** — each with who can do it, what it does, what it costs, which
rung makes it reachable, a world limit of three-to-a-hand and the protagonist as the declared
exception — passes `gate_candidate` and `worlds.validate` with **zero complaints, through the
existing schema and vocabulary unchanged**, and the limit is then enforced by a **blocking**
detector.

**Re-derived independently rather than taken on trust.** A capability written as a `change` node
with two `precondition` edges, an `authorized_by`, a `consumes` and a `produces`; two cast members
holding capabilities via a free-form `can_do` edge; and a cardinality shape reading *at most two
`can_do` per subject, except the protagonist*:

| | |
|---|--:|
| the protagonist holding three, excepted | **0 findings** |
| another cast member holding three, not excepted | **1 blocking finding** — *"card_two_arts admits at most 2 can_do per subject; bram has 3"* |

That is the operator's own cuff example — *everyone has one, the main character may have as many as
they like* — expressible **and enforced**, today, with nothing changed. `EXCEPTS_PREDICATE`'s own
docstring names that example as its reason for existing.

**And the projection already writes the acquisition sentence:**

```
cap_walk_between happened — needs cap_see_the_seam; needs cap_hold_a_shape;
    authorised by teacher_ilsa; costs a_month_of_unpaid_work; produces reach_the_far_room
```

### What actually fails, then

Three things, and all three are downstream of expressiveness.

**(i) The forge is never asked, and the one route in is a smuggling route.** `_WORLD` has no
`changes` array, and `change`, `consumes`, `produces`, `precondition` and `authorized_by` occur
**zero times** in `WORLDS_SCHEMA`, `_RULES` and `_SYSTEM_MESSAGE` between them. The only
conforming route is `_ENTITY.relationships` carrying
`{"predicate": "type", "target": "change", "note": "change"}` — through a field whose own
description says it is for *"who this subject stands in what relation to (owes, employs,
married_to, blames, outranks)"*. It is schema-conforming and gate-clean, and **no model would write
it unprompted**. That is an *affordance* gap, not an expressiveness gap — and it is exactly
consistent with every rung forged so far being an insignia.

**(ii) The writer meets it as notation.** `project()` has **no sentence** for `can_do`, `permits`
or `member`, so a person's abilities arrive through `state.describe`'s flat fallback —
`sera can_do (cap_walk_between)` — and land in the world brief's `other` bucket. That is the layer
`worlds.py` itself calls *"the gate on the model being usable at all"*. One agent's measurement of
the fix: **two branches in `_node_sentence` / `_record_sentence` and one entry in
`world_brief._ROLE_GROUP`.**

**(iii) Three legibility warts, each one line.** `_node_sentence`'s change branch hard-codes
`"{subject} happened — "`, which is the wrong aspect for a thing a person *can do*; that branch
never applies `replace("_", " ")`, so snake_case ids reach the writer; and `ENTITY_ROLES` has no
member meaning *event*, *rank* or *capability*, so a change node smuggled in as an entity is filed
under `institutions` in the brief.

---

## 5. Corrections in place

Three, all to claims this session made earlier today, and two of them were caught by the operator:

1. ~~"MoL has no rank ladder for its protagonist at all, and most of the target genre does; a fair
   critic can say I chose a book whose progression is the genre's exception."~~ **Wrong, and the
   operator corrected it**: *"mol does have a ladder, people have abilities at different levels of
   expertise with numbers attached."* Measured and confirmed — layers A, B and C above. The source
   is not the genre's exception; it carries **more** progression structure than our model can hold,
   not less. The exoticism defence for our model does not survive.
2. ~~"Every gain is permission."~~ **Overstated.** Across 24 distinct worlds and 156 rungs:
   permission 104, capability 46, neither 6. What is true is that the capability rungs are
   *quarantined* — **10 of 24 worlds have none at all**, *A Good Take* among them.
3. ~~"Crunchy without being numeric."~~ **Refuted by the measurement.** The source carries absolute
   magnitudes, a derived unit, two ordinal ladders, percentages and probabilities. *"Anyone
   claiming this genre works without numbers is wrong. The model does not need to be numberless."*
   What it does **not** do is keep score.

---

## 6. What is owned, and what is not

The **ladder** half — the protagonist's rung on one declared ordinal chain, rising within the arc
and printed on the page — is [`plan/handoff-numbers-go-up.md`](../../plan/handoff-numbers-go-up.md),
in flight in its own worktree, carrying the operator's resolution verbatim: *"bronze to gold rank
advance is the same as the number going up. Say bronze is 1 and gold is 3."* Nothing here
duplicates it and nothing here should be built into `architect.py` without coordinating with it.

The **inventory** half — layers B, C and D, and acquisition — is a different axis and **nobody owns
it**. It is the piece "nine unique abilities" asks for. This measurement says the model **can** hold
it and is never asked to, which makes it a smaller piece of work than it looked: an array on
`_WORLD`, a rule naming it, two projection branches, and one entity role. Layer C — a magnitude on
a named capacity — is the only part that needs new vocabulary.

## 7. Anti-scope

Nothing was built, no schema was edited, no rule was written, no directive issued, no bar declared,
no counter registered. No model was asked to judge anything. The source was read read-only; the
model-fit world is a scratch artefact and is not committed. Nothing here claims that a world with
an ability inventory would make a better book — it claims only that our model cannot currently
express one, which is a fact about the model.
