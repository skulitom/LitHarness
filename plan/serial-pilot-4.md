# Serial Pilot 4 — the same two chapters, on a world that says whose book it is

**Status: RUN, 2026-08-22.** Three forges, one pick by the operator, eight scenes drafted, gate
green, P1-P5 answered in §6.2. Total spend $13.73. Companion to
[`plan/serial-pilot-2.md`](serial-pilot-2.md) and [`plan/serial-pilot-3`'s record](reader-read-3.md);
the design record is [`plan/world-architect.md`](world-architect.md) and the decision record is
stage-0 §112. §4 was written **before any paid call**; §5 records what has been bought so far and
§6 is empty until a book is drafted.

## 0. What this pilot is for, and the one thing it may not be read as

**One difference from Serial Pilot 3, and everything else held.** Same brief
(`"progression fantasy"`), same shape (`--shape direct`), same K (3), same scene count (8), same
chapter shape, same target words, same context budget, same provider, same craft constraints
except C7's recorded edit. The difference is that the forge is now asked for a **protagonist**:
one member of the cast, the one declared rule or cardinality shape that does not hold for them,
what that lets them do, what they want, what it costs — and a premise written as that person's
situation. The outline is told the world's cast and which of them the book is about; the drafting
packet and the beat line are told the same.

**It cannot support a quality claim and no reading of it may make one.** Two chapters is not a
sample; §61's bar is a blinded position-swapped win rate against matched published prose and this
is not that. Every question in §4 is structural: does the forge declare it, does the declaration
reach the outline and the packet, who acts on the page, does the exception survive the gate, and
where does a reader meet the protagonist. Pilot 2's §0 said this about itself and it is repeated
rather than referenced, because a package that assumes its reader has read the previous package is
how a bar gets quietly relaxed.

**What this pilot is NOT.** It is not a test of whether the hook is good. No model is asked
whether a hook is good, which premise hooks more, whether a protagonist is interesting, or which
of K worlds to pick. The forge stops and a person chooses (`plan/world-architect.md` §2;
`forge --pick` is `VerdictSource.HUMAN`).

---

## 1. The world, and how it will be chosen

Recorded before the forge runs, because the choosing is the part that must stay auditable.

```powershell
uv run litharness --database pilot4\forge.db forge "progression fantasy" `
  --k 3 --shape direct --out pilot4\direct1 --scenes 8
```

**The pick rule, written down before the candidates exist.** The first candidate clear of every
gate whose literalised real domain was **not** forged in pilots 2 or 3 — that is, not water law,
not transplant immunology, not land surveying, not horticultural grafting. The rule goes into the
run record beside the decision id. The operator may re-pick later on any grounds they like; that
is a different row and it is recorded as one.

**What is measured about the forge before anything is picked**, per candidate, from `report()`:
`spread` for the set, and per candidate `protagonist_declared`, `exception_declared`,
`premise_names_protagonist`, plus `gate_complaints`. Pilot 2's spread was 0.93; pilot 3's was
**0.8959** (measured from `pilot3/direct1/forge.json`, where the handoff's "0.90" is that figure
rounded).

## 2. What changed in the machinery since pilot 3

Every item is additive; a world that declares no protagonist regenerates byte-identically and its
book renders today's outline request and today's drafting prompt byte-for-byte.

| | change | pinned by |
|---|---|---|
| Architect | optional `protagonist` object in the world schema, required of the **forge** (`worlds_from` refuses; `records_for` tolerates absence) | `test_a_world_that_names_no_protagonist_is_refused_at_the_forge`, `test_the_pilot_package_regenerates_the_world_it_was_run_on` |
| Architect | one rule in `_RULES`, cited to `reader-read-3.md` | `test_the_protagonist_rule_asks_for_a_declaration_and_never_an_outcome` |
| Architect | `protagonist` as a second `entity_role`; `edge`, `wants`, `exception_to` (edge), `price` as records | `test_the_protagonist_reaches_canon_as_records_and_not_as_a_field` |
| worlds | `CardinalityShape.except_subjects`, `in_scope` returns `False` for an excepted subject | `test_the_excepted_subject_is_the_one_the_maximum_does_not_bind` |
| integrity | the declared exception reaches the wired detector | `test_the_declared_exception_reaches_the_live_detector_and_binds_nobody_else` |
| outline | a `protagonist` input beside §111's `world` brief; one rule, added only when it is present | `test_a_book_whose_canon_declares_nobody_renders_the_bytes_it_always_did` |
| planner | `pov_character_id` threaded to the one production `packet_for`; `Point of view: {id}.` in the beat line | `test_the_prompt_is_byte_identical_when_canon_names_no_protagonist` |

## 3. Standing it up

```powershell
.\tools\serial-pilot-2-setup.ps1 -Forge pilot4\direct1 -Scenes 8 -Database serial4.db -Craft plan\serial-pilot-4-craft.json
```

Then the two phases exactly as [`plan/serial-pilot-2.md`](serial-pilot-2.md) §3 — direction first,
gated, before a paid call is spent on prose. **Budget phase 1 at roughly twice the directive count
in ticks**: pilot 3 needed 26 rather than 14, because each verbatim constraint bumps the plan epoch
and re-mints the interpretive jobs behind it.

```powershell
.\tools\run-loop.ps1 -Database serial4.db -Ticks 26 -DelaySeconds 2 `
  -TickArgs '--target-words','900','--context-budget','16000','--chapter-scenes','4','--max-cost-usd-per-day','10','--max-invocations-per-day','80'
uv run python tools/serial_pilot_check.py --database serial4.db --phase directives `
  --spec pilot4\direct1\directives.json --spec plan\serial-pilot-4-craft.json
```

Only when the early gate is green:

```powershell
.\tools\run-loop.ps1 -Database serial4.db -Ticks 48 -DelaySeconds 2 `
  -TickArgs '--target-words','900','--context-budget','16000','--chapter-scenes','4','--max-cost-usd-per-day','10','--max-invocations-per-day','80'
uv run python tools/serial_pilot_check.py --database serial4.db `
  --spec pilot4\direct1\directives.json --spec plan\serial-pilot-4-craft.json
```

`--spec` is repeatable and **both are needed**: the gate sums the counts, and one spec alone would
report the inbox short by the size of the other.

**`--context-budget 16000` is a precondition, not a preference** — pilot 2 measured a forged world
at a flat ~46% of a 16,000-token packet, and at the 6,000 default the same world dropped every
prior scene and 92 facts. Measured again on pilot 3's world at 16,000: scene 1 carries **224
established facts, 23 hidden claims, 7,493 tokens, `context_omitted = 0`**.

**`plan/serial-pilot-4-craft.json` issues six constraints and proposes two.** C9 (chapter-grain
introduction budget) and C10 (the first person named) sit in a `proposed` array **outside**
`directives`, so no script issues them: C9's number is unset and C10 is direction the operator has
not given. Moving an entry into `directives` is the operator's act and is what issues it.

**Cost.** ~$1.50 for the forge (pilot 3's three worlds cost $1.24, plus one refused forge at
$1.48 that returned an empty premise — the schema now carries `minLength: 1` on the fields added
since) and ~$5 for the two chapters (pilot 2's run B was $5.89). One CLI arm at a time; check no
other paid arm, pilot loop or forge is running first — `claude -p` fails under box load and still
returns.

---

## 4. What is pre-registered, before the loop runs

Numbered so a later reading cannot quietly become a different question. Every one is structural;
none is about whether the prose is good. **Pre-registered 2026-08-22, before any paid call.**

| # | question | how it is answered | outcomes named in advance |
|---|---|---|---|
| **P1** | does the forge declare a protagonist and an exception | `report()` per candidate: `protagonist_declared`, `exception_declared`, `premise_names_protagonist`; `gate_complaints`; `spread` for the set | (i) all three candidates declare a cast id and three different exceptions → the rule text works; (ii) **no candidate names a declared cast id**, or **every candidate's exception is the same rule**, → a failure of the rule text, not of the model, and it is rewritten before anything is picked; (iii) `spread` well below **0.90** on the same brief → the new rule collapsed the forge and the change is **unsafe** (stage-0 §112's stop condition): stop and write that up instead of running the book |
| **P2** | does the protagonist reach the outline and the packet | the stored outline request carries a `protagonist` block and a `cast` block; every scene's stored drafting prompt carries `Point of view: <id>.`; the packet's facts heading reads `Established facts known to <id>:` | anything missing is a **threading defect**, reported as one and never as a prose finding. Measured before the run on *What Takes*: the packet diff is exactly two lines and the prompt diff exactly one |
| **P3** | who acts | per scene, from the stored scene-plan statement: does it name the protagonist as an actor (count of 8)? Named persons introduced per chapter with first-appearance offsets (`named_persons.py`); forged-cast ids on the page (count of 5) | *What Takes*: **8 and 18** distinct names by counter, **9** persons by the operator's hand count in chapter 1, and **1 of 5** forged cast ids on the page. Report the new numbers beside them. **No bar** — `named-persons-results.md` records that this counter puts the complained-about chapters *below* the genre median, so a movement in either direction is a description and not a verdict |
| **P4** | does the exception survive the gate | `state.cardinality.v0` findings on the protagonist's excepted shape across the whole run (expect **0**), beside a planted positive control on a **copy** of the run's canon (expect **≥1**) | a finding on the excepted subject means Task 1's scope change did not reach the live detector. **The positive control is not optional**: zero findings with no control is indistinguishable from a detector that never ran |
| **P5** | where does the reader meet the protagonist | word offset of first appearance in chapter 1; share of the first three hundred words' name mentions; the offset at which their role is first stated. Offsets under `domain/axes`' tokeniser, stated as such | descriptive, beside *What Takes*: first appearance at **17**, **9** mentions to Lady Ossary's **7** in scene 1, role first stated at **804** (tokeniser) / **802** (plain split). No bar, and no direction is preferred: C10, which would ask for the first sentence, is **proposed and not issued** |

### 4.1 What would make this pilot unreadable, named in advance

- A `transport_failures` row on any tick. Read it before reading any verdict; `claude -p` fails
  under box load and a failing call still returns with the run completing.
- A second book in `serial4.db`. Every unscoped directive becomes ambiguous and the planner
  materialises none of them — the setup script refuses on this precondition.
- The forge picked by anything other than the recorded rule, without the departure recorded.
- **A forge refused wholesale.** `worlds_from` refuses a missing or empty `protagonist` field the
  way it refuses a missing premise — on the *first* bad world, so one bad candidate costs all
  three. That is the existing behaviour of every shape refusal in that function and it has already
  been paid for once: the 2026-08-22 forge that returned an empty premise cost $1.48 for nothing.
  A refusal is not a finding about the rule; re-run once, and only if it happens twice is the rule
  text what needs changing.

### 4.2 The operator's alternative, named and not taken here

The cheap test on *What Takes* itself: a locked `constraint` naming one of its cast as the
protagonist and their exception, then a re-run on the same world. It reaches the plan and every
packet through machinery that already exists. **It requires a person to author the hook**, which
is authoring rather than operating, so it is available and it is the operator's to take. It is not
done here and no part of this package depends on it.

---

## 5. The run

### 5.1 Forge 1 — P1 answered (ii): the rule text, not the model

`dec-f80cd6fdf39aa99335f23213`, `arch-d425316522615ff9fa369e68`, 2026-08-22.
`litharness --database pilot4/forge.db forge "progression fantasy" --k 3 --shape direct
--out pilot4/direct1 --scenes 8`. **96,533 tokens, $1.45, `claude_code` / `claude-opus-5`.**

| | [0] *Cut Once* | [1] *The Ghost Bitting* | [2] *The Bearing Year* |
|---|---|---|---|
| real domain | glassworking — annealing and residual stress | locksmithing — master-keyed pin systems | pomology — grafting and rootstock |
| geometry | threshold | graph | cycle |
| records / edges | 287 / 87 | 311 / 96 | 317 / 99 |
| rules, min consequence domains | 5 at 3 | 5 at 3 | 6 at 3 |
| manifestation coverage | 1.00 | 1.00 | 1.00 |
| answered claims | 25 | 26 | 27 |
| cardinality shapes | 2 | 3 | 3 |
| `protagonist_declared` | ✔ | ✔ | ✔ |
| `exception_declared` | ✔ | ✔ | ✔ |
| `premise_names_protagonist` | ✔ | ✔ | ✔ |
| protagonist id is a declared cast id | ✔ | ✔ | ✔ |
| gate complaints | **1** | **1** | **1** |

**within-forge spread 0.9158**, against pilot 2's 0.93 and pilot 3's 0.8959. **The stop condition
does not fire**: the new rule did not collapse the forge, and on this one measurement it sat
between the two prior forges rather than below either.

**Clear of every gate: 0 of 3, and all three failed the same way.** Each candidate put a real
declared id in `exception` and then glossed it in the same field:

| protagonist | `exception` as returned | leading token | is it declared? |
|---|---|---|---|
| `wick_haldrey` | `one_cooling_history — the shape that gives a body one cooling history and one fringe order does not hold for him. He carries two…` | `one_cooling_history` | yes, a declared cardinality shape |
| `corrin_vane` | `one_key_per_name — the shape that gives one person one key does not hold for her. She carries an issued blank and a ghost bitting…` | `one_key_per_name` | yes, a declared cardinality shape |
| `sabel_quist` | `rule_family_or_black — the rule that a cutting takes only between kin-families, and blackens and casts off otherwise, does not hold for her…` | `rule_family_or_black` | yes, a declared rule |

`worlds.normalise_id` turns each of those sentences into one long snake_case token that names
nothing, so `gate_candidate` reported *"an exception to nothing in particular is a description"*
three times out of three. **This is P1's outcome (ii) exactly as registered — a failure of the
rule text and not of the model** — and the registered response is to rewrite the ask before
anything is picked.

**Why the ask was wrong.** It read *"the ONE rule or cardinality shape of this world — by its id —
that does not hold for them or holds differently"*. That is a sentence describing **which** thing
to select, and the model wrote the description into the field along with the id. Nothing told it
that `exception` holds an id and not an account of one. The fix separates the two: the selection
criterion stays in the rule, the field gets `pattern: ^[a-z0-9_]+$` and a description that says
*AN ID AND NOTHING ELSE*, with the failing form spelled out as the counter-example.

**Nothing was picked and nothing was renamed.** The forge stands on the record as it ran;
`pilot4/direct1/forge.json` is its artefact, and this table is the pre-fix number kept beside the
post-fix one, which is the discipline §107.9.1 records for a counter and applies here to a prompt.

### 5.2 Forge 2 — the protagonist half passes 3 of 3, and something else stubs out

`arch-d425316522615ff9fa369e68`, 2026-08-22, same command with `--out pilot4/direct2`, run against
the corrected ask at `ac2ccde`. **93,783 tokens, $1.38.**

**The correction worked, and this is the measurement of it.** Every candidate put a bare declared
id in `exception`, with no gloss and no dash, and no candidate drew the complaint all three drew
in forge 1:

| protagonist | `exception` | what it names |
|---|---|---|
| `vess_almadry` | `rule_every_gain_is_debited` | a declared rule |
| `oree_valland` | `rule_one_ancestor_per_word` | a declared rule |
| `nias_orrel` | `card_one_bond_per_person` | a declared **cardinality shape** — the case that exercises the `excepts` derivation |

**within-forge spread 0.9182**, the highest of the three forges taken under this brief (pilot 3:
0.8959; forge 1: 0.9158). Real domains: municipal water engineering, historical linguistics,
quantitative genetics — none of them forged in pilots 2 or 3.

**And still 0 of 3 clear of every gate, for an unrelated reason.** Each world emitted, inside one
system's `rules` array, a **consequence object where a rule belongs**, filled with the literal
word `placeholder`:

```json
"rules": [
  { "id": "rule_bright_dies_by_the_hour", "rule": "…", "manifests_as": "…" },
  { "domain": "placeholder", "consequence": "placeholder" }
]
```

`_RULE` declares `additionalProperties: false` and requires all four fields, so that entry
violates the schema; `providers/base.parse_schema_payload` is shallow by design and never descends
into `worlds[].systems[].rules[]`, so it survived parsing. The damage is contained and the gate is
what contained it: `records_for` skips a rule with no id, so nothing entered the records, and the
gate reported the rule that lost its consequences *and* the orphan entry — two complaints, one
defect. Each world still declared four to six complete rules at four consequences apiece across
four distinct domains, manifestation coverage 1.00, and 26 to 30 answered claims.

Nothing was picked: the recorded rule is *the first candidate clear of **every** gate*, and none
is. Changing that rule now, with the candidates in view, is what the pre-registration exists to
prevent.

**Two things this forge is evidence about, and one it is not.** It is evidence that the corrected
ask produces bare ids (3 of 3, against 0 of 3 before) and that the new rule does not collapse the
forge (0.9182). It is **not** evidence about how often a world stubs a rule out: two forges is two
draws, the defect appeared in one of them, and the honest reading is that this is the first time
this project has seen it.

**Noted, not fixed.** The gate prints `rule ?` for an entry with no id, which is accurate and
undiagnosable — the reader cannot tell from it that a consequence was emitted one level too high.
A message that named the shape would have made this five minutes rather than twenty. Out of scope
here; it is the gate working, not the gate failing.

**A hypothesis, recorded before the next forge so it cannot be fitted afterwards.** The corrected
ask made the schema *longer* — five field descriptions and a pattern, ~600 characters of new
instruction text, which `providers/cli.py` serialises into the prompt. Forge 1 ran under the short
schema and stubbed nothing; forge 2 ran under the long one and stubbed one rule in every world.
That is one draw against one draw and it is **not** evidence; it is written down now so that a
third forge is a test of it rather than a rationalisation after the fact. If forge 3 stubs under
the same schema, shortening the descriptions is the first thing to try; if it does not, the
hypothesis is dead and forge 2 was variance.

### 5.3 Forge 3 — 3 of 3 clear, and the hypothesis §5.2 registered is dead

`dec-25c58304a408437ec81d74a3`, 2026-08-22, `--out pilot4/direct3`, same corrected ask.
**$1.75.** **3 of 3 clear of every gate**, within-forge spread **0.9169**.

| | (`--pick 1`) *The Ninth Order* | (`--pick 2`) *Calling the River* | (`--pick 3`) *A Good Take* |
|---|---|---|---|
| real domain | land surveying and geodesy | water law and hydrology, arid basin | immunology — graded inoculation |
| geometry | graph | chain | cycle |
| records / edges | 296 / 91 | 305 / 91 | 293 / 88 |
| rules at min domains | 5 at 3 | 5 at 3 | 5 at 3 |
| manifestation | 1.00 | 1.00 | 1.00 |
| answered claims | 25 | 29 | 26 |
| protagonist | `sabel_ruck` | `cass_odom` | `nella_scur` |
| `exception` names | `rule_every_loop_must_be_adjusted` (a declared **rule**) | `card_one_holder_per_date` (a declared **shape**) | `card_one_ladder_per_person` (a declared **shape**) |
| gate complaints | **0** | **0** | **0** |

**The §5.2 hypothesis is refuted, and it was written down before this draw.** Forge 3 ran under
the identical long schema and stubbed nothing in any of three worlds. So the `placeholder` rule
entries in forge 2 were variance, not pressure from the added descriptions, and the descriptions
stay. One draw does not make the rate small — it makes the mechanism *not* the schema.

**Two of three exceptions name a cardinality shape**, which is the case that exercises the
`excepts` derivation `records_for` performs: declaring the protagonist the exception to a shape is
what puts them out of `in_scope` and keeps the maximum binding on everybody else.

### 5.4 The pick is blocked on a reading of the pick rule, not on a gate

**The recorded rule:** *the first candidate clear of every gate whose real domain was not forged in
pilots 2 or 3 — that is, not water law, not transplant immunology, not land surveying, not
horticultural grafting.* Checked against what is on disk rather than from memory:

| forged before | where |
|---|---|
| Western water law and hydrology | pilot 2, picked (*First In Time*) |
| prior-appropriation water law and irrigation hydrology | pilot 3 candidate 1 (*Senior Water*) |
| horticultural grafting and rootstock science | pilot 3, picked (*What Takes*) |
| land surveying and geodesy | pilot 3 candidate 3 (*The Closing Error*) |

So *The Ninth Order* (land surveying and geodesy — the same words as *The Closing Error*) and
*Calling the River* (water law in an arid basin — pilot 2's domain) are both excluded outright.
**The rule turns on one word for the third.** It excluded *transplant* immunology; *A Good Take*
literalises **graded inoculation** — dose-response, the interval between too little and too much,
waning tolerance, asymptomatic carriage. Graft rejection and dose-response tolerance are different
mechanisms inside one field. Under the rule read literally, *A Good Take* qualifies and is the
pick; under the rule read as *a field this project has not already forged in*, nothing qualifies.

**That was not resolved here, and it was not resolved by this session.** `forge --pick` is
`VerdictSource.HUMAN` and [`plan/world-architect.md`](world-architect.md) §2 says the forge stops
and a person chooses; a rule reinterpreted with the candidates already in view is the thing the
pre-registration exists to prevent. The three worlds were put to the operator with the ambiguity
named, and **the operator picked *A Good Take*** — `dec-7f3ea41cdb149f2bb0b4bb80`,
`--pick 3`, 2026-08-22. That resolves *transplant immunology* to the literal reading: graft
rejection and dose-response tolerance are different mechanisms and only the first was forged
before. The rule stands as written; a person applied it where it needed a person.

### 5.5 The world as canon, and the two defects the first book found

`A Good Take`, immunology and graded inoculation, cycle geometry. **293 records, validator
clean**, six cast, five forged directives, six seeded promises. The hook is the operator's own
template, forged rather than authored:

| | |
|---|---|
| protagonist | `nella_scur`, roles `('cast', 'protagonist')` |
| exception | `card_one_ladder_per_person`, a declared **cardinality shape** |
| the shape, as canon holds it | `at most 1 graded_on_ladder per subject, scope=cast, except=('nella_scur',)` |
| edge | a shoulder that reads as three ladders at once; every matcher who puts a glass on it sets the glass face-down before asking anything |
| price | no schedule — she learns she is due by bleeding onto her hand in a doorway, and has to decide in that scene whether to spend a dose she may not need and cannot replace |

The `excepts` derivation fired end to end: the world declared her the exception to a shape, and
`records_for` wrote the edge from the shape's end, so the maximum binds on the other five cast
members and not on her.

**Setup and phase 1.** `serial-pilot-2-setup.ps1 -Forge pilot4/direct3 -Scenes 8 -Database
serial4.db -Craft plan/serial-pilot-4-craft.json` — 11 directives accepted (5 forged + 6 craft),
no prose, no provider call. Then 26 ticks of direction. **8 calls, 470,972 tokens, $3.15**;
20 jobs succeeded, `context_omitted = 0`, the outline covered 8 of 8 scenes, 24 plan items with
15 locked.

**And the early gate refused the book, on two findings that are the same defect and both of them
this branch's.** A protagonist is a *second* `entity_role` on a cast member, and
`state.contradiction.v1` reads a subject holding two values for one predicate at one position as
MAJOR and blocking:

```
nella_scur entity_role holds 2 different values at (unplaced): "cast", "protagonist"
nella_scur wants holds 2 different values: "Fourth-grade material before Orin's
    throat-mark lapses in nine days.", "Fourth-grade material, in nine days, by any route."
```

One scene parked, one poisoned, two of eight blocked — **before a word of prose was judged**.

**The first is older than this branch and this branch is what tripped it.**
`worlds.entity_roles` returns roles *plural* and says why in its own docstring — the System is an
`agency` and a `system`, a guild is an `institution` and, when it acts, `cast`. No world had ever
happened to give one subject two roles, so nothing exercised it. `integrity.MULTI_VALUED` now
names `entity_role` as a set rather than a slot, and it is deliberately a named set of one: a
heuristic that guessed which disagreements are allowed would be the frozen arity table
`detect_cardinality_violations` refuses.

**The second is a genuine single slot and the fix is the other way.** `_ENTITY` carries `wants`
for everybody and `_PROTAGONIST` restates it, so a world can say it twice — and this one said it
twice in two wordings. Canon now takes the cast entry's and drops the protagonist's copy, and
`gate_candidate` complains when both are declared and differ, so the divergence is seen at forge
time rather than at scene four.

**What let this reach a paid run.** No test ran a detector over a world that declares a
protagonist. The suite had `run_detectors` over a planted cardinality violation and
`protagonist_brief` over a peopled world, and never the two together. Two tests now do, and both
fail on the code that shipped this morning:
`tests/test_integrity.py::test_a_subject_that_is_two_things_at_once_is_not_contradicting_itself`
and `tests/test_architect.py::test_a_declared_protagonist_does_not_poison_its_own_book`, the
second of which runs the whole wired ladder over `records_for`'s output and asserts silence.

### 5.6 A second defect, and this one is the operator's

`forge --pick` mints each reveal's disclosure position at `args.scenes`, which **defaults to
`DEFAULT_SCENES = 6`**, and the pick on 2026-08-22 was run without `--scenes 8`. The setup script
then created the book at 8. So `serial4.db` was seeded from a six-scene bundle into an eight-scene
book, and `story_key` mints no position for a scene the book does not have:

| | pick at `--scenes 6` (what ran) | pick at `--scenes 8` (correct) |
|---|---|---|
| seed records | 291 | **292** |
| reveals given an in-book position | `myst_why_reeves_takes_fail` → `s4` | `myst_why_reeves_takes_fail` → `s4`, `myst_where_the_fourth_grade_went` → **`s8`** |

**The reveal the eight scenes exist to settle would never have landed.** Its ordinal was stored,
its position was not, and `undisclosed_claims` keeps a claim with no position hidden throughout —
which is the 40-opened-0-paid defect reproduced by the machinery built to fix it, and exactly what
`architect.story_key`'s docstring warns about in as many words.

Nothing in the tooling could have caught it: `forge.json` does not record the scene count it was
forged for, so `--pick` cannot default to it and an operator has to carry the number by hand
between two commands. The `--scenes` flag is on both; only one of them was given it. **Recorded as
a defect of the pick path, not fixed here** — stage-0 §112 does not reach the
forge CLI, and a change to what `--pick` defaults to is its own piece of work with its own test.

**Fixed on 2026-08-23 as stage-0 §115.** The forge now records the width it forged at, `--pick`
reads it when `--scenes` is absent, and a `--scenes` that disagrees with the record is refused
naming both numbers. The four runs in §115.1 re-ran this pick against this bundle read-only and
reproduce the two record counts above exactly; a `forge.json` written before the width was
recorded — which is every one on this machine, including `pilot4/direct3/` — still picks exactly
as it did, so the table above stays reproducible.

**Consequence for this pilot: `serial4.db` is unusable and cannot be patched.** The `wants`
duplicate is one record; the missing disclosure position is a different world. The bundle has been
re-picked correctly (`dec-7f3ea41cdb149f2bb0b4bb80`, 292 records, two positions minted, wired
ladder silent), and a book drafted on it has to start from a fresh database.

**A finding the pick question exposed, worth more than the pick.** Of nine candidates forged from
`"progression fantasy"` across pilots 3 and 4, **water law appears three times, land surveying
twice, and the graft/immunology family twice.** The brief is the same string every time and the
forge keeps landing in the same few real domains. Stage-0 §112 names cross-forge
collapse as out of scope here and it is left alone — but the collapse gate is *within*-forge only,
so nothing in the machinery would ever have said this out loud, and it is said here so that the
next person to read a `spread` of 0.92 knows what that number does not cover.

## 6. The run record

### 6.1 The run, in §6.2's form

*A Good Take*, `serial4.db`, rebuilt on the correctly re-picked bundle after §5.5 and §5.6.
Two phases, 26 + 48 ticks.

| | |
|---|--:|
| ticks | 74 |
| jobs | **45, all succeeded** — 0 parked, 0 poisoned, 0 failed |
| decisions | 22 — 21 accept, 1 retry |
| invocations | 13 |
| tokens | 822,505 |
| cost | **$6.00** |
| scenes | 8 of 8 drafted |
| words | 7,865 |
| parked | **0** |
| exceptions raised | **0** |
| findings | 11, all `promise.overdue.v0` at **minor** — annotating, never blocking |
| promise ledger | 49 rows, 40 open, **9 paid** |
| gate | **green**, both specs, full run |

**The per-scene packet**, at `--context-budget 16000`:

| scene | facts | hidden | threads | prior prose | summaries | tokens | omitted | `Point of view:` |
|---|--:|--:|--:|--:|--:|--:|--:|:--:|
| 1 | 204 | 19 | 6 | — | — | 7,363 | 0 | ✔ |
| 2 | 204 | 19 | 11 | — | — | 8,702 | 0 | ✔ |
| 3 | 204 | 19 | 14 | — | — | 10,048 | 0 | ✔ |
| 4 | 205 | **18** | 18 | — | — | 11,581 | 0 | ✔ |
| 5 | 205 | 18 | 22 | — | — | 12,992 | 0 | ✔ |
| 6 | 205 | 18 | 27 | — | — | 12,632 | 0 | ✔ |
| 7 | 205 | 18 | 35 | — | — | 12,990 | 0 | ✔ |
| 8 | 206 | **17** | 36 | 3 | 4 | 13,240 | 0 | ✔ |

`context_omitted = 0` for the whole book. **The hidden section drops at exactly the two scenes
the world scheduled** — 19 → 18 at scene 4 and 18 → 17 at scene 8 — which is the iceberg working,
and the scene-8 drop is the one the six-scene bundle of §5.6 would have lost entirely.

### 6.2 P1–P5, answered as counts

| # | registered question | answer |
|---|---|---|
| **P1** | does the forge declare a protagonist and an exception | **3 of 3**, on the second ask. Under the original rule text 0 of 3 (all three glossed the id — §5.1); under the corrected ask 3 of 3 bare declared ids, 2 of them cardinality shapes. Spread 0.9158 / 0.9169 against pilot 3's 0.8959 — **the stop condition never fired** |
| **P2** | does the protagonist reach the outline and the packet | **8 of 8** drafting prompts carry `Point of view: nella_scur.`; every packet's facts block is headed `Established facts known to nella_scur:`. The seam had 27 call sites and had never been passed anything |
| **P3** | who acts | **8 of 8** scene statements name her as the actor. **6 of 6 forged cast members reach the page** — `nella_scur` 41 whole-word hits, `dog_pell` 34, `cadge_reeve` 23, `orin_scur` 13, `hesta_polt` 9, `sef_ombry` 8. Named-thing introductions: **11 and 10** per chapter (3,972 and 3,911 words) |
| **P4** | does the exception survive the gate | **0** findings across the run's canon, as registered. Positive control on a copy: planted on the excepted subject → **0**; the same violation on `cadge_reeve`, same kind, not excepted → **1**, `card_one_ladder_per_person admits at most 1 graded_on_ladder per subject; cadge_reeve has 2` |
| **P5** | where does the reader meet her | **word 0.** *"Nella had the case on her hip and eighty people between her and the lane she wanted."* 16 mentions in chapter 1; in the first 300 words she is named 2 times, level with Reeve (2) and Orin (2) |

**The comparison P3 and P5 were registered against**, and it is a description and not a verdict:

| | *What Takes* (pilot 3) | *A Good Take* (pilot 4) |
|---|---|---|
| forged cast reaching the page | **1 of 5** | **6 of 6** |
| scene statements naming the protagonist | the protagonist was invented by the outline and occurs 0 times in the forged world | **8 of 8** |
| protagonist's first appearance | word 17, behind another person's name | **word 0** |
| where their role is first stated | word 804, inside reported speech | the first sentence puts her at work with the case on her hip |
| names introduced per chapter | 8 and 18 | 11 and 10 |

**What this table may not be read as.** It is one book against one book, and the two differ in
more than the protagonist: different world, different domain, different forge, and a corrected
`--pick`. It says the declaration reached the page, which is P2 and P3's structural question. It
says nothing about whether *A Good Take* is a better book, and no instrument here could.

**C10 was not issued.** The constraint that would have asked for exactly what P5 measured — *the
first sentence of the book belongs to the protagonist* — sits unissued in
`plan/serial-pilot-4-craft.json`'s `proposed` array. The book opened on her anyway, from the
declaration alone. One book is not evidence that direction is unnecessary; it is evidence that
this one did not need it.

### 6.3 Total spend

| | |
|---|--:|
| forge 1 (refused ask) | $1.45 |
| forge 2 (stubbed rules) | $1.38 |
| forge 3 (3 of 3 clear) | $1.75 |
| phase 1, poisoned run | $3.15 |
| phases 1 + 2, the book | $6.00 |
| **total** | **$13.73** |

Against the ~$6.50 estimated. $2.83 of the overrun is two forges spent on a rule text this session
wrote wrong and a model stub; $3.15 is a book poisoned by two defects this session shipped and one
`--scenes` flag it forgot. All three are recorded above with what they cost.
