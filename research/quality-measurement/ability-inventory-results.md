# The ability inventory: what the schema could not say, what it says now, and what was refused

Results for [`plan/handoff-ability-inventory.md`](../../plan/handoff-ability-inventory.md), which
was written after the operator read *A Good Take* and said its progression is *"boring accounting
instead of nine unique abilities or level 9 neural speed system"*
([`plan/reader-read-4.md`](../../plan/reader-read-4.md) §1a). Registered as stage-0 §114.

Every figure below was re-derived in running code on 2026-08-23 against this branch. Where a
figure disagrees with the handoff's own, both are printed and the derivations are named. Nothing
here declares a bar, admits an axis, or asks a model to rank anything.

---

## 1. What was measured before anything was built

### 1.1 The rungs were insignia because the schema had nowhere else to put them

`architect._RANK` is `additionalProperties: false` with exactly three properties, all strings:

| property | says |
|---|---|
| `id` | what it is called |
| `visible_form` | what it **looks like** to other people |
| `cost_to_reach` | what it **costs** |

There is no slot for what a rung lets you *do*. That is not a prompt failure — it is the schema
being followed correctly, and it is the whole of the diagnosis. The handoff measured the
consequence and its figure is quoted rather than re-run: **135 of 156 criterion rungs (86.5%)
across the forged corpus are a mark other people read, and permission outnumbers capability 104 to
46 with 6 neither** (verified 2026-08-22 against `main` at `1e51bcd`). Classifying a rung as
insignia or capability is a reading, and re-running somebody else's reading would produce a second
number with no more authority than the first.

What *is* re-derived here is the denominator, because it is arithmetic: over the same corpus,
**42 criteria carrying 119 rungs** by `worlds.rank_order`. The handoff's 156 comes from a
content-hash deduplication over its own file set; this one is the canonical reader's count over
today's. **Neither is corrected by the other** — they count over different denominators, and the
86.5% share does not depend on which.

### 1.2 The corpus: 24 worlds, and the three predicates none of them has ever emitted

Every world this project has forged, deduplicated by content hash over the raw payload: **24
distinct worlds, from 9 contributing artefact files of 23 scanned** (`pilot3/`, `pilot4/direct1–3`,
`plan/serial-pilot-2-world.json`, and four bundles in sibling worktrees). All 24 rebuild through
`records_for` without error. Predicate census, at `ACCEPTED_CANON`, scenes=8:

| predicate | records | reader in `src/` |
|---|--:|---|
| `manifests_as` | 839 | yes — projected |
| `entity_role` | 562 | yes — `entities_with_role` |
| `is_a` | 550 | **no projection sentence**; reaches the writer via `state.describe` |
| `prices_the_present` | 245 | no |
| `grants` | 271 | no |
| `can_reach` | 207 | no |
| `costs` | 156 | **no projection sentence**; `state.describe` |
| `recognises` | 127 | no |
| `member` | 75 | no |
| `permits` | 35 | no |
| **`can_do`** | **0** | — |
| **`requires`** | **0** | — |
| **`taught_by`** | **0** | — |

`grants + recognises + can_reach + prices_the_present` = **850 records with no reader anywhere in
`src/`**, which is the handoff's figure exactly.

The last three rows are the load-bearing ones. **`can_do`, `requires` and `taught_by` are the only
predicates in this vocabulary that no world has ever emitted**, which is what makes it safe to give
them projection sentences: no packet that has ever been built changes.

### 1.3 The forge was never asked

Word counts in the forge prompt, before and after, at k=3 scenes=8, with word boundaries:

| | prompt chars | `ability` | `abilities` | `skill*` | `magnitude*` | `capab*` |
|---|--:|--:|--:|--:|--:|--:|
| before (`HEAD~1`) | 5,657 | 0 | 0 | 0 | 0 | 0 |
| after | 6,284 | 0 | 0 | 0 | 0 | 3 |

Schema JSON grew 13,063 → 15,315 characters, with `capab*` going 0 → 9. Measuring the *before*
figure against today's `worlds` module shows one spurious schema hit, because the `scope` enum is
derived from `ENTITY_ROLES` and `capability` is now a member; the pre-change figure above is the
handoff's, measured before that was true.

**The words `ability`, `abilities`, `skill` and `magnitude` are still zero after the change, and
that is deliberate.** The schema says `capabilities`, and §1.5 says why nothing says `magnitude`.

### 1.4 Only two integer fields in the whole forge schema, and there still are

`$.worlds.items.mysteries.items.disclosed_at_scene` (a scene ordinal) and
`$.worlds.items.cardinality.items.maximum` (an edge count). Re-counted after the change: **still
exactly two.** The inventory added no number anywhere, which is Task 3's boundary honoured in code
rather than only in prose.

### 1.5 The enforcement baseline, before a line was written

The operator's own definition of a hook — *everyone in the world has one cuff, the main character
broke the system and can now have as many as they like* — was expressible and **blocking** before
this handoff started, using `EXCEPTS_PREDICATE` and a `cardinality_constraint`:

| | findings |
|---|--:|
| the excepted subject holding three | **0** |
| a non-excepted subject holding three | **1, MAJOR, blocking** |

That was the baseline. What was missing was a predicate worth constraining.

---

## 2. What shipped

### 2.1 `domain/worlds.py`

`capability` joins `ENTITY_ROLES`. `CAN_DO`, `REQUIRES`, `TAUGHT_BY` and `COSTS` become named
constants. `capabilities()`, `capabilities_of()` and `requirement_depth()` read them back;
`requirement_depth` counts **edges in the longest chain** and is cycle-safe. Three new sentences in
`_record_sentence` — and exactly three, for the reason §1.2 gives.

### 2.2 `application/architect.py`

An **optional** `capabilities` array on `_WORLD` (`id`, `is_a`, `manifests_as`, `costs` required;
`requires[]` and `taught_by` optional, `additionalProperties: false`), an optional `capabilities`
list on the protagonist for what they start with, one rule, three gate complaints, three `report()`
counters. **Optional is load-bearing**: a world about standing, or a place, or a debt declares none,
and most should.

### 2.3 `domain/world_brief.py`

Capabilities get their own group, immediately after `cast`, instead of falling into `other` — the
bucket the module's own docstring calls *"never empty by design"*.

### 2.4 Before and after, on the same candidate

The fixture world rendered through `HEAD~1` and through `HEAD`: **54 → 72 records, 21 → 30
projected sentences, nothing removed.** The nine added lines:

```
cap_read_a_seam shows on the page as: He turns a thing to the light, once, and says a year out loud.
cap_price_unseen shows on the page as: He names a figure before the book is open, and it holds.
cap_price_unseen is taught by marta
cap_price_unseen needs cap_read_a_seam first
cap_sign_for_another shows on the page as: Two hands on one page and only one of them shaking.
cap_sign_for_another needs cap_price_unseen first
cap_sign_for_another needs second_seal first
silas can do cap_read_a_seam
silas can do cap_price_unseen
```

`cap_sign_for_another needs second_seal first` is the one edge where the inventory and §113's
ladder meet: a capability may require a **rung**. Nothing else collapses them — a rung is a
position in a recognised order, a capability is a member of a set, and a world may declare either,
both or neither.

**A world declaring no capabilities regenerates byte-identically.** Asserted over the pilot-2
regeneration pin, which now also asserts the three counters read zero.

### 2.5 The limitation this produced, stated rather than fixed

`is_a` and `costs` — *what the capability is* and *what it charges* — have **no projection
sentence** and reach the writer through the `state.describe` fallback:

```
cap_read_a_seam is_a he can see where two things were joined, and when
cap_read_a_seam costs His eyes go for an hour after, and he works blind through it.
```

That is notation with a sentence inside it, and `project()` is described in its own docstring as
*"the gate on the model being usable at all"*. It was not fixed here because `is_a` appears **550
times** and `costs` **156 times** across the 24 worlds already forged: giving either a sentence
would change every one of those packets and break the byte-identity rail this repository checks.
Fixing it is its own change, with its own regeneration decision, and it is named here so it is not
rediscovered as a surprise.

---

## 3. What was refused

- **A magnitude.** Task 3, below. No number was attached to anything; the schema still has exactly
  two integer fields.
- **Sentences for `costs`, `permits` and `member`.** Illegible in exactly the same way, and every
  one already emitted by prior worlds. §2.5.
- **A capability as a `change` node.** The handoff proposed it, and implementation refused it —
  §4.1.
- **Any instruction about how to write a capability.** The system may say a person can do a thing;
  it may not say a scene should show it off, make it impressive, or let them win with it.
  `test_the_capability_rule_asks_for_a_declaration_and_never_a_performance` asserts this rather
  than trusting it.
- **A floor.** Nothing in the gate or the report mentions a minimum. The operator's *"nine"* is a
  word for an inventory, not a threshold, and no test or counter treats it as one.
- **Any claim that a world with an inventory makes a better book.** The measurement says the model
  could not previously *express* one. That is a fact about the model and nothing more.

---

## 4. Two deviations from the handoff, both found in implementation

### 4.1 A capability is an ordinary subject with a role, not a `change` node

The handoff's adversarial pass established that a capability *could* be written as a `change` node
with `precondition`, `authorized_by`, `consumes` and `produces` edges, and that is true. It is
still the wrong shape: `change` models **one occurrence with many roles** and `_ROLE_PHRASE`
renders it as *"X happened"* — right for the morning somebody learned a thing, wrong for the thing
itself. The two coexist. `change` is still there for the acquisition.

### 4.2 Only three predicates got sentences

The handoff implied the illegible-predicate problem could be cleared in one pass. It cannot, for
the byte-identity reason in §2.5. Three predicates were new; three got sentences.

---

## 5. Three defects found in this session's own output

1. **The readers filtered canon**, so `report()` counted 0 capabilities for every forged world — a
   candidate is `PROPOSED` until `forge --pick`. The same trap caught the forge-side enforcement
   test, which passed its first assertion vacuously (no shapes in canon → no findings) until it was
   forged at `ACCEPTED_CANON`. The test now says so in its docstring.
2. **`requirement_depth` counted nodes where it documented edges.**
3. **The new sentences un-snake-cased ids** while the rest of the packet does not. Removed.

---

## 6. Task 3 — the magnitude: a memo, not a build. **The operator decides.**

The operator's phrase was *"nine unique abilities **or level 9 neural speed system**"*, and the two
halves are different objects. §2 is the first. The second is **a number attached to a named
capacity** — *Magnitude 12*, *level 9 neural speed* — and it was deliberately not built.

**What it would be.** One integer field on a capability (or on a person-holds-capability edge), a
predicate to carry it, a projection sentence, and a comparator that actually computes. Mechanically
small: a day, most of it tests.

**Exactly which rule it contradicts.** Two:

1. The forge's standing rule — *"Do not use levels, hit points, mana, experience points, currency,
   or any single number that means power"* — which is in the prompt today and which every forged
   world has honoured.
2. Stage-0 §113's resolution that **a rank ladder *is* the number**: bronze is 1, gold is 3, and the
   ladder was built as the countable ordinal the operator asked for. A magnitude is a *second*
   numbering, and two numberings for one idea is the ambiguity §113 closed.

**What is genuinely missing, and it is not the integer.** `numeric` and `threshold` are members of
`COMPARATORS` that **no code computes with** — every reader in the repository does string
membership, string printing, or the ordinal-only gate. A magnitude with no arithmetic behind it is
a decoration on the page, and a decoration is the thing *A Good Take* was already criticised for.

**What would have to be true for it to be worth adding.**

- A magnitude would have to be attached to a **named capacity**, never to a person. *Level 9 neural
  speed* names a capacity; *level 9 Silas* is the single number that means power, and it is
  refused. This is the operator's own reframing: *"the number is attached to the wrong thing."*
- Something would have to **compute with it** — a gate, a cardinality shape, a comparator that runs
  — so it is a fact with consequences rather than a printed digit.
- §113 would have to be reconciled in the ledger, not silently worked around: either a magnitude is
  a different axis from standing (a capacity's depth, not a person's rank) and both stand, or one
  of them is withdrawn. **Not both quietly.**

If the operator says yes, it is its own handoff, and it opens with which of those three it is
buying.

---

## 7. Task 4 — the counter, and its numbers

[`ability_inventory.py`](ability_inventory.py). **Descriptive, no bar, no pole, not registered in
`axes.COUNTERS`, no model anywhere in it.** Four numbers per book, over the book's own canon
(read-only, `mode=ro`) and its drafted prose via `corpus_io.generated_scenes`:
capabilities declared, capabilities the protagonist holds, capabilities named on the page, and the
scene at which each is first named.

```bash
uv run python research/quality-measurement/ability_inventory.py --book serial.db --book serial3.db --book serial4.db
```

| book | scenes | declared | held by protagonist | named on the page |
|---|--:|--:|---|--:|
| `serial.db` — pilot 2, world *First In Time* | 8 | 0 | *no protagonist declared* | 0 |
| `serial3.db` — pilot 3, *What Takes* | 8 | 0 | *no protagonist declared* | 0 |
| `serial4.db` — pilot 4, *A Good Take* | 8 | 0 | 0 (`nella_scur`) | 0 |

**Every number is zero and every zero is correct.** Each of these books was drafted before a world
could declare a capability. Pilots 2 and 3 predate stage-0 §112 and have no protagonist at all,
which the counter reports as `null` rather than `0` — *"nobody is the protagonist"* and *"the
protagonist can do nothing"* are different facts. Pilot 4 has `nella_scur` and reports a real zero.
The first non-zero row will come from the first book forged after §114.

**A counter whose only evidence is a zero has not been run**, so the naming half is exercised by
`--selftest` over a synthetic world — three capabilities, a protagonist holding two, prose naming
one in scene 2 — which asserts 3 / 2 / 1 / scene 2 and eight further claims, including that a
structural id part (`for` in `cap_sign_for_another`) is not a name. Eleven claims, all holding.

The naming rule is `worlds.key_nouns`' rule with its scope narrowed to one subject, importing that
module's own three constants so the two cannot drift. **It is crude and named as crude**: a
capability called `cap_read_a_seam` matches the common word *seam* wherever it falls. Reported as
measured — repairing a counter after its answer is known is the failure `platform_priors.py`
freezes its matchers to avoid.

---

## 8. Anti-scope

Nothing here touched the ladder, `rung_index` or the rise on the page (§113 owns those); no beat
function, `SIX_BEAT` change or arc template; no status sheet, `[STATUS]` line or graph line; no
judge, reader, persona, BCR, axis admission or pool change; no pilot database was written to; and
no claim is made that a world with an inventory produces a better book.
