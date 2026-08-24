# Handoff: nine unique abilities — the inventory the vocabulary can already hold, the forge is never asked for, and the writer meets as notation

You are working in `C:\DEV\LitHarness`, an autonomous fiction-production system whose objective is
popcorn-genre fiction (LitRPG, progression fantasy, isekai) a defined audience voluntarily
continues and recommends, with no human in the production loop. Superhuman literary
quality is the long-term goal (stage-0 §126). Your task is one bounded piece: make **a countable set of distinct named things
the protagonist can do** — each with what it took to get it, what it cost, and who allowed it —
something the forge is asked for, the packet says in English, and a counter can read. Nothing here
asks you to invent an ontology; the measurement says the vocabulary already holds this and nobody
has ever been asked to fill it. Read the boundaries before you read the tasks.

File names, line numbers and measurements below were verified on 2026-08-22 against `main` at
`1e51bcd`. If the repo has drifted, the repo wins; re-anchor rather than following this document
into a stale reference. Parallel sessions run on this repository — `CLAUDE.md` carries the rules.

## Why this exists (context you need, then stop reading context)

The operator read *A Good Take* — the first book drafted on a world whose protagonist the system
chose (stage-0 §112) — and said its progression reads as *"boring accounting instead of nine
unique abilities or level 9 neural speed system"*
([`plan/reader-read-4.md`](reader-read-4.md) §1a). Then, asked for a falsification test, they named
one: map a magic system the genre agrees works and see whether our model can hold it. The result is
[`research/quality-measurement/mother-of-learning-model-fit.md`](../research/quality-measurement/mother-of-learning-model-fit.md).

Four measurements decide this task. Each was verified in running code; verify them again before you
act on them.

1. **The rungs are insignia because the schema has nowhere else to put them.** Across the 24
   distinct worlds this project has forged — 156 rungs, deduplicated by content hash over ten
   artefact files — **135 (86.5%)** are a mark other people read, and permission outnumbers
   capability 104 to 46 with 6 neither. `_RANK` (architect.py:126) is `additionalProperties: false`
   with exactly `id`, `visible_form`, `cost_to_reach`: a rung can say what it **looks like** and
   what it **costs** and has **no slot for what it lets you do**. Every capability-shaped field in
   the schema is a single string with no plural — `reach` (163's `_ENTITY`), `grants`,
   `recognises`, `joint_ability`, `edge`. That is not a prompt failure; it is the schema being
   followed correctly.
2. **The vocabulary already holds the thing, and this was established adversarially.** Six agents
   were each given one claimed gap and told to default to *refuted* unless they could show what
   breaks. **All six refuted; none standing.** The element the first pass missed is the `change`
   NODE_TYPE — one of five (`cardinality_constraint, change, constraint, criterion, view`) — whose
   eleven `CHANGE_ROLES` are `actor, participant, precondition, caused_by, performed_by,
   authorized_by, validated_by, recognized_by, effect, consumes, produces`, every one of which
   `_ROLE_PHRASE` already renders into English and `project`'s foldable set already folds.
   Re-derived independently: a capability written as a `change` node with two `precondition` edges,
   an `authorized_by`, a `consumes` and a `produces`; two cast members holding capabilities on a
   free-form `can_do` edge; and a cardinality shape reading *at most two `can_do` per subject,
   except the protagonist* —

   | | |
   |---|--:|
   | the protagonist holding three, excepted | **0 findings** |
   | another cast member holding three, not excepted | **1 blocking finding** |

   That is the operator's own hook example — *everyone has one cuff, the main character may have as
   many as they like* — expressible **and enforced**, today, with nothing changed.
   `worlds.EXCEPTS_PREDICATE`'s docstring names that example as its reason for existing.
3. **The forge is never asked, and the only route in is a smuggling route.** `_WORLD`
   (architect.py:391) has twelve array fields — systems, agencies, carriers, bonds, cast,
   creatures, places, institutions, history, mysteries, cardinality, directives — and **none holds
   abilities**. The words *ability*, *abilities*, *skill*, *magnitude* and *capab-* occur **zero
   times between them** in the 5,657-character forge prompt (k=3, scenes=8), and `change`,
   `consumes`, `produces`, `precondition` and `authorized_by` occur zero times in `WORLDS_SCHEMA`,
   `_RULES` (architect.py:458) and `_SYSTEM_MESSAGE`. A conforming forge answer *can* carry a
   change node — through `_ENTITY.relationships` with
   `{"predicate": "type", "target": "change", "note": "change"}`, a field whose own description
   says it is for *"who this subject stands in what relation to (owes, employs, married_to,
   blames, outranks)"*. It is schema-conforming and gate-clean and **no model would write it
   unprompted**. This is an *affordance* gap, not an expressiveness gap.
4. **What the forge does emit, nothing reads.** `can_reach`, `grants`, `recognises` and
   `prices_the_present` have exactly two mentions each in the whole of `src/` — the schema line and
   the emit line in `architect.py`. No constant, no validator clause, no projection sentence, no
   reader. `_record_sentence` (worlds.py) has a sentence for ten predicates —
   `world_rule, consequence, manifests_as, exception_to, edge, price, entity_role, precedes,
   stands_at, claim.content` — and **none for `can_do`, `permits` or `member`**. So a person's
   abilities reach the writer as `state.describe`'s flat fallback, `sera can_do (cap_walk_between)`,
   and land in the world brief's `other` bucket, because `world_brief._ROLE_GROUP` has no entry for
   them. `worlds.py`'s own docstring calls the projection *"the gate on the model being usable at
   all"*.

**What the source that motivated this actually does**, so the target is not guessed: **77** distinct
named capabilities (a counted lower bound), acquisition by explicit prerequisite chains up to five
links spoken by teachers, composition throughout (A + B → C), prices in varied currencies, gating
by people with motives rather than institutions issuing permits — and **no enumerated list
anywhere**, the text refusing to enumerate three times. So the ask is not a list on the page. It is
an inventory that **exists**, is **countable**, and can be felt accumulating.

That is the whole context. Everything below is the bounded work.

## The hard boundaries

These are not preferences. Work that breaks one of them is worse than work not done.

1. **Code carries facts and positions, never taste.** A capability is a declared fact of the world —
   what it is, what it needs, what it costs, who allows it — exactly the class of "scene 3 of 8",
   the chapter cue and `Point of view:` (§108.4, §112). **No instruction about how to write a
   capability may enter any prompt, template, beat function or system message**: not "show the
   ability being used", not "make the reader feel the gain", not "open on a new power". Direction
   about that is the operator's. Three tests already check the three strings this project has added
   for the vocabulary such an instruction would need; add a fourth for yours.
2. **No verdict channel.** Do not ask any model whether an ability is interesting, which of K
   worlds has the better inventory, or whether a capability is worth having. The forge stops and a
   person chooses (`plan/world-architect.md` §2). E6 stays byte-frozen.
3. **Declare no bar.** *"Nine"* is the operator's word for *an inventory*, not a threshold. Do not
   put a floor on the count of capabilities, do not gate on one, and do not let `report()` imply
   one. If the operator ever wants a number it comes from a measured distribution and is theirs to
   set (§81, §85, §87, §89 each named a quantity that could not do what it said).
4. **RS1.** The source that motivated this is a real published work read on the corpus side. **No
   part of it may cross to the generation side** — not a name, not a coined term, not a mechanic as
   an example, not paraphrased. `tests/test_corpus_leak_audit.py` checks; run it.
5. **Backwards compatibility is a test, not a hope.** A world declaring no capabilities must
   regenerate byte-identically (`test_the_pilot_package_regenerates_the_world_it_was_run_on`) and
   a book whose canon declares none must render **today's outline request and today's drafting
   prompt byte-for-byte** — the control the chapter cue and the viewpoint fragment both pinned.
   `input_digest_for` covers the prompt and is the sampler seed.
6. **Do not re-litigate the ladder.** Stage-0 §113 built it — `STANDS_AT_PREDICATE`, `ladder_of`,
   `rung_index`, `standing_of`, `_PROTAGONIST.standing`, the `Ladder` in `world_brief` — and it is
   merged. A rung and a capability are different objects: a rung is a position in a recognised
   order, a capability is a thing a person does. **Do not collapse them, do not add a second
   standing, and do not change what §113 shipped.** Where they meet is one edge: a rung may
   `permits` a capability.
7. **Counts point to canonical homes; corrections in place; the ledger is append-only.** The next
   stage-0 number is **§114 or later** — §113 is on `main` as this is written. Re-run the check in
   `CLAUDE.md` at commit time. Never cite a test name that does not exist.
8. **New files where you can.** Do not restructure `plan/world-architect.md` or
   `plan/state-model-abilities.md`; extend them with dated sections.

## Coordination

- `plan/handoff-numbers-go-up.md` **has landed** (stage-0 §113) and its worktree is clean. You are
  building beside it, not under it. Read §113 before you touch `architect.py`: it added one rule
  and amended three, and it owns every line about standing.
- `plan/handoff-protagonist.md` landed as §112 and owns `_PROTAGONIST`, `exception_to`, `excepts`
  and the viewpoint fragment. The protagonist's id is the subject whose inventory this is. Do not
  add a second protagonist and do not change `edge` — `edge` is *the one exception*, singular by
  design; an inventory is a different field.
- Check `git status` and the worktree list before you commit, and commit only your own files.

## Task 0 — measure before building (no provider call, all local)

Record these as output in your results note, not as prose claims. Every one is a re-derivation of a
number this document asserts; if one disagrees, the repo wins and you say so.

1. Re-run the rung census: over every `forge.json` you can find plus
   `plan/serial-pilot-2-world.json`, dedupe worlds by content hash and report total rungs, and the
   insignia / permission split with your classification rule stated first.
2. Confirm `_RANK`'s three properties and `additionalProperties: false`; confirm every
   capability-shaped field is a single string; confirm `_WORLD`'s array fields hold no abilities.
3. Confirm the zero-mention counts: *ability*, *skill*, *magnitude*, *capab-* in the rendered forge
   prompt, and `change` / `consumes` / `produces` / `precondition` / `authorized_by` in
   `WORLDS_SCHEMA` + `_RULES` + `_SYSTEM_MESSAGE`.
4. Confirm `can_reach`, `grants`, `recognises`, `prices_the_present` have no reader in `src/`, and
   count how many records of each the forged worlds actually emit.
5. **Reproduce the enforcement demonstration** in boundary-2's table from scratch, with your own
   script: a `change`-node capability, `can_do` edges, a cardinality shape with the protagonist in
   `except`. It must give 0 findings on the excepted subject and ≥1 on another cast member. This is
   your baseline; everything below is making it *reachable* rather than making it *possible*.
6. Render a packet for a world carrying one such capability and record, verbatim, what the writer
   sees — the `change` node's folded sentence and the `can_do` line. That is the before.

## Task 1 — the forge is asked for the inventory

**Schema** (`architect.py`, near `_WORLD` at line 391): one optional array, `capabilities`, each
entry an object carrying — at minimum — `id`, what it lets a person do (in the `manifests_as`
register: how it shows on the page, never an explanation), `needs` (ids of capabilities or rungs
that must come first, possibly several), `costs`, and `allowed_by` (a declared subject who permits
or teaches it, or absent when nobody does). Give every text field `minLength: 1` and every id field
the `^[a-z0-9_]+$` pattern and a description saying **AN ID AND NOTHING ELSE** — §112.5 records what
it cost to learn that a field described as "the id of the rule that does not hold for them" gets an
id *and a clause explaining it*, three worlds out of three.

**Optional, and that word is load-bearing.** A world with no capabilities is a world with no
capabilities: `records_for` emits nothing, the gate says nothing, and the packet is byte-identical.
Do not add it to `_WORLD["required"]`. Most worlds this project has forged are not about a person
acquiring things, and a required inventory would make every one of them lie.

**Records** (`records_for`, architect.py:1149): each capability becomes a `change` node — the
vocabulary's own object for *one occurrence with many roles* — typed with `TYPE_PREDICATE` to
`worlds.CHANGE`, its `needs` as `precondition` edges, its `costs` as `consumes`, what it produces
as `produces`, and `allowed_by` as `authorized_by`. Who holds it is a `can_do` edge from the
person. **Nothing new is invented**: every one of those is already a `CHANGE_ROLE` with a phrase in
`_ROLE_PHRASE`. Add `can_do` as a named constant in `domain/worlds.py` with a docstring — the four
inline-literal predicates in Task 0.4 are the precedent for what happens when you do not.

**One entity role.** `ENTITY_ROLES` (worlds.py) is `cast, creature, place, institution, carrier,
agency, system, protagonist` and has no member meaning *a thing a person can do*. A capability
smuggled in as an entity today acquires a role that is a lie and is filed under `institutions` in
the world brief. Add one, and pin that a world declaring none is unaffected.

**Gate complaints**, non-blocking like the rest, and deterministic: a `needs` naming nothing the
world declared; a `can_do` naming a capability the world never declared; an `allowed_by` naming
nobody. **No complaint about how many** — see boundary 3.

**`report()`** (architect.py:1808) gains counters, not verdicts: how many capabilities are declared,
how many the protagonist holds, how deep the longest `needs` chain runs. Counters only; nothing
orders one world above another.

## Task 2 — the writer meets it in English

This is the smaller half and the one that decides whether any of it is worth doing. Measured fix:
**two branches and one dict entry.**

- `_record_sentence` in `domain/worlds.py` has a sentence for ten predicates and none for `can_do`,
  `permits` or `member`. Add them, in the register the existing ten use — *what is so*, never an
  instruction. `<person> can do <capability>` is a fact; *"show her using it"* is not.
- `_node_sentence`'s change branch hard-codes `f"{subject} happened — {body}"` (worlds.py:1389).
  Past tense is right for a scheduled acquisition and wrong for a standing capability. Fix it
  without breaking the acquisition reading, and note that this branch — unlike the criterion and
  cardinality branches — never applies `replace("_", " ")`, so snake_case ids currently reach the
  writer.
- `world_brief._ROLE_GROUP` has no entry for the new role, so capabilities land in `other`. Add one,
  and put it where a planner needs it: a statement that puts a capability to work is a statement
  about what somebody can do.

Pin the before and after with the packet render from Task 0.6, and pin that a book declaring no
capabilities renders byte-identically.

## Task 3 — the magnitude, which is the one real gap, and a decision rather than a build

The operator's phrase was *"nine unique abilities **or level 9 neural speed system**"*, and the two
halves are different objects. Task 1 is the first. The second is **a number attached to a named
capacity** — and the only two integer fields in the entire forge schema are
`mysteries[].disclosed_at_scene` (a scene ordinal) and `cardinality[].maximum` (an edge count).
Nothing anywhere attaches a magnitude to a person or a capability, and `numeric` and `threshold`
are members of `COMPARATORS` that **no code computes with**: every reader does string membership,
string printing, or the ordinal-only gate.

**Do not build this on your own authority.** It collides with a standing rule — *"Do not use
levels, hit points, mana, experience points, currency, or any single number that means power"* —
and with §113's resolution that *a rank ladder is the number*. Instead: state in your results note
what a magnitude would be, what it would cost to add, exactly which rule it contradicts, and what
would have to be true for it to be worth adding. **The operator decides.** If they say yes, it is
its own handoff.

## Task 4 — the counter, no bar

Under `research/quality-measurement/` (never `src/`; read `BRIEF.md` §2 and `CONTRIBUTING.md`
"Before proposing a quality or craft metric" first): a deterministic counter over a book's own
canon and prose reporting, per book — capabilities declared, capabilities the protagonist holds,
capabilities named on the page, and the scene at which each is first named. Reuse `corpus_io` and
the `named_persons.py` / `opening_counters.py` shape. **Descriptive, labelled as such, no bar, no
pole, and not registered in `axes.COUNTERS`.** Run it over the books that exist and commit the
numbers; a book with no capabilities reports zero and that is a fact about the book, not a defect.

## Out of scope, named so you do not drift into it

- Anything about the ladder, standing, `rung_index` or the rise on the page. §113 owns it.
- Any instruction to any model about how to write, open, pace or feel about an ability; any "show
  the power" beat function; any change to `SIX_BEAT` or the arc template.
- A magnitude (Task 3 is a memo, not a build). A status sheet, a `[STATUS]` line, or a graph line —
  the second extractor family is somebody else's and the forge's own rule about it is unchanged.
- Any judge, reader, persona, BCR, axis admission or pool change. No model ranks anything.
- Editing pilot 2, 3 or 4's artefacts; re-picking; redrafting any accepted scene. Those databases
  are read-only; copy before you mutate.
- Any claim that a world with an inventory makes a better book. The measurement says the model
  cannot currently *express* one; that is a fact about the model and nothing more.

## Deliverables

1. Task 1's schema, records, role, constant and gate complaints, with tests in
   `tests/test_architect.py` and `tests/test_worlds.py` — including the byte-identical
   regeneration pin, and a test that the enforcement demonstration of Task 0.5 works **through the
   forge** rather than through hand-built records.
2. Task 2's projection, with the before/after packet render pinned and a byte-identical control.
3. A test that the added prompt strings carry no instruction about how to write a capability, in
   the shape of `test_the_protagonist_rule_asks_for_a_declaration_and_never_an_outcome`.
4. Task 3 as a section of the results note. No code.
5. Task 4's counter and its committed numbers.
6. A results note, new file, `research/quality-measurement/ability-inventory-results.md`, carrying
   Task 0's tables, the before/after, and what was refused.
7. One stage-0 entry (§114 or later, re-checked at commit) in the house form: measured first, what
   shipped, what was refused, no bar declared, corrections in place, anti-scope — pointing
   `reader-read-4.md` and the model-fit note at it.
8. Your own commits. `uv run pytest`, `uv run ruff check .`, `uv run mypy`, `git diff --check`
   first.

If Task 1 turns out to be unsafe — if asking for an inventory collapses the forge's distinctness on
the same brief (`spread` well below the 0.9158 / 0.9169 / 0.8959 this brief has produced), or if the
only way to get a capability onto the page is an instruction about how to write one — **stop and
write that up instead**. A packet that quietly tells the writer to show off a power is a worse
failure than a world that still cannot name one.
