# Serial Pilot 4 — the same two chapters, on a world that says whose book it is

**Status: PRE-REGISTERED 2026-08-22; forge 1 run, nothing picked, no book drafted.** Companion to
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
| **P1** | does the forge declare a protagonist and an exception | `report()` per candidate: `protagonist_declared`, `exception_declared`, `premise_names_protagonist`; `gate_complaints`; `spread` for the set | (i) all three candidates declare a cast id and three different exceptions → the rule text works; (ii) **no candidate names a declared cast id**, or **every candidate's exception is the same rule**, → a failure of the rule text, not of the model, and it is rewritten before anything is picked; (iii) `spread` well below **0.90** on the same brief → the new rule collapsed the forge and the change is **unsafe** (`plan/handoff-protagonist.md`'s stop condition): stop and write that up instead of running the book |
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

### 5.2 Forge 2

**NOT RUN.** The corrected ask ships first.

## 6. The run record

**NOT RUN.** To be recorded in [`plan/serial-pilot-2.md`](serial-pilot-2.md) §6.2's form — ticks /
jobs / decisions / invocations / tokens / cost / scenes / words / parked / findings / gate, the
per-scene packet table, and P1–P5 as counts.
