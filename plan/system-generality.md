# Will the system layer fit any LitRPG story, and any future one?

Status: **design note and plan, 2026-09-03**; the operator decided the same morning that the layer is made general (§4). Written first for his question
(*"we should keep our system flexible ... most LitRPG doesn't list skills at zero ... will our
system be able to fit any possible LitRPG story out there, and any future potential LitRPG?"*).
Nothing here is built. The counts this note relies on live where they were made (stage-0 §201
for the status-window census; §113, §114, §160 to §171 for the system layer's decisions);
this note points and does not restate.

## 1. What the system layer is today, as shapes

Read off `domain/gamesystem.py`, `domain/extraction.py`, `domain/genre.py`, `domain/worlds.py`
and `litharness world vocabulary` on 2026-09-03.

- **Records.** Subject, predicate, object, value, order key. Roles: cast, creature, place,
  institution, carrier, agency, system, protagonist, capability. Node types: criterion,
  constraint, cardinality constraint, change, **view**. Comparators: ordinal, numeric,
  threshold, equality, set inclusion, pareto, replacement equivalence. Visibility per record and
  per sheet (`pov_visibility`, `visible_to`).
- **A system** (`SystemDef`): one named ladder of ranks (ordinal, named, a `precedes` chain);
  five to eight abilities as a set, each with an integer magnitude per person from 0 to a
  scale maximum of at most 99; prerequisites (an ability or a rung, with a threshold); forks
  (`Choice` with two to four `Option`s that `grant` abilities, opening at a rung); `costs`,
  `price`, `manifests_as` as one line each. Content-addressed and immutable: a system that
  changes is a different system.
- **Moves.** Four: gain, deepen, rise, choose. Nothing loses, spends, splits, or merges.
- **The printed surface.** One status line per book: the rung's index and every ability's
  magnitude, digits only (the parser is `(?P<name>\d+)`), paired `current/maximum` fields
  allowed; printed as furniture on a change, with a declared phrase per predicate
  (`graph_line`); one `[OFFER]` line for a fork standing open; one printing system at a time.
  The rung's *name* rides the graph line and never the sheet; a pick prints nowhere on the sheet
  (§160.3). Every declared ability prints, held or not (§160's awe line).
- **The floor.** A book must hold a starting `status_snapshot` of numbers or it does not draft
  (`genre.has_starting_sheet`); a system one predicate short is reported (`system_gap`).
- **The concept stage** (§197, §198): manner, look, steps, strongest known, what a step buys,
  a second system after the turn with what carries over.

That is a specific LitRPG: a ladder, a small ability graph with depths, forks, one always-full
numeric line, owned by persons. It was built by measurement against our own defects (§113 to
§171), each entry answering a read, and not against the genre's space. The docstring on
`extraction.Sheet` records the earlier version of the same lesson: *the vocabulary was welded
in, and that made the model a genre* (`Level | HP | MP | Gold` was a literal; `DEFAULT_SHEET`
still reproduces it).

## 2. The genre's conventions against those shapes

A reader's taxonomy, from the shelf, the market corpus's titles, and the operator's own
description (screens at class advancement, options related to the class, no skills at zero).
*Fits* means the arithmetic and the print both hold today; *partial* means one of them does;
*no* means the model has no slot.

| convention | today | the structural reason |
| --- | --- | --- |
| level, attributes, paired HP/MP | fits | columns and paired fields; level is the rung index, attributes are "abilities" with depths (the semantics are off, the arithmetic holds) |
| a skill list with skill levels or proficiency | partial | at most eight abilities, integer depths to 99, no percent; every one prints, held or not |
| class, title, race as names with effect | no | the sheet is digits only; a class is a pick spoken in prose (§160.3); title and race have no slot |
| class advancement screen: pick one of N offered for what you did | partial | `Choice` with two to four options gated at a rung, grants, one `[OFFER]` line; no conditional offers from the sheet's own history, no option text, no rarity or hidden option |
| notifications (*you have learned*, *ding*, quest complete) | partial | one graph line on a change with a declared phrase per predicate; no event kinds beyond the four moves, no queue |
| Identify or Appraisal (others' levels, a monster's rank) | partial | sheets carry visibility and creatures carry rank notes, but only the protagonist's line prints (§170) |
| quests, achievements, a shop, currency, free points to allocate | no | no quest or shop object (the promise ledger is story-level); a currency is a number with no economy; no spend move |
| EXP to next level | partial | a paired field prints it; a rise is by prerequisite thresholds, not by accumulation, so the arithmetic of *level at 500* is not modelled |
| numberless progression (Copper to Gold; realms; levels only) | partial | the ladder alone is fine, but the floor demands a numeric snapshot and prints the rung as a number |
| VRMMO framing (menus, logging out, NPCs, guilds) | neutral | institutions and places hold; the frame is manner and look |
| dungeon core, base or kingdom building | no | sheets belong to persons (`CharacterSheet.character`, the counted-in-a-person licence) |
| pets, party members, several sheets at once | partial | sheets per character exist; one prints; no party screen |
| items with stats, rarity, description boxes | no | no item object with attributes; the carrier role and cardinality shapes hold possession only |
| several systems at once | partial | two declared, one prints; the sheet swap is not built (§197) |
| skill evolution or fusion; a system that grows mid-book | no | the ability set is fixed at draw and the system is content-addressed |
| percentages, derived stats, multipliers, resistances | no | integers 0 to 99 |
| level-down, death penalties, any loss | no | moves add, climb or choose; only a fork forecloses |
| the hidden or unique class, the exception | fits | `edge`, `exception_to`, visibility |
| the System as a character that bargains or asks | partial | manner and price are text on the system entity; the concept's *wants* is prose |
| a screen with text (a class or skill description on acquisition) | no | `manifests_as` is one line; no description display |

The pattern in the table: what fits is what the reads have so far asked for; what does not fit
is either a *name where a number is*, a *list where a fixed row is*, an *owner that is not a
person*, a *display that is not the line*, or a *move that is not one of four*. None of those
is a genre feature; each is a place where the model has one shape and the genre has several.

## 3. What flexibility is, and is not

**It is not more fields.** A quest module, an inventory module, a notification module would
weld five more vocabularies in, and the next book (a future LitRPG that has none of them and
something else) would meet the same wall. The `Sheet` docstring's lesson scales: every genre
constant becomes a book that cannot be written.

**It is three generalisations of what is already there**, each of which the vocabulary half
anticipates:

1. **Typed attributes on any owner.** A value is a number, an ordinal on a ladder, a name from
   a declared set, a line of text, a paired current/maximum, or a set of references; the owner
   is any role (a person, a place, an institution, an item, a creature). The comparators
   already cover the checks (ordinal, numeric, threshold, set inclusion); the cardinality shapes
   already cover exclusivity (§200's per-ladder key is one). Today's magnitudes and rungs are
   two of these types on one owner.
2. **Displays as declared views.** The status line is one display: a template over attributes,
   a trigger (on a change, on a request, on an event), a voice. A choice screen, a notification,
   an Identify readout, an item box, a quest card are other displays the *world* declares:
   which attributes, in what words, in what order, when, and whether unheld things show. The
   node type `view` exists in the vocabulary and nothing owns it. Extraction reads back what the
   page printed against the display's template, as `Sheet.pattern` does for the line today.
   Under this, *print skills at zero* stops being a code decision (`SystemDef.columns`) and
   becomes a display's declaration, with the default the shelf shows: nothing unheld on a
   sheet, and the wanting carried by the choice display, offered at an advancement, its options
   related to the class, which is the operator's own description of the genre.
3. **Rules as declared shapes.** *Numbers go up* is a monotonic shape on an attribute (§113
   hardcodes the effect); *a rise needs a threshold* is a comparator; *an option is offered
   only if the sheet's history holds X* is a predicate over records; a loss is a `change` node
   with a sign. The engine checks arithmetic, cardinality and monotonicity the world declared,
   and carries no convention as a constant. `DEFAULT_SHEET` is the last such constant and would
   retire.

**What stays fixed regardless**, because it is what made the layer work: a change is a record
with an order key; record implies disclosure; systems are content-addressed; no model ranks;
the counted-in-a-person licence generalises to counted-in-an-owner rather than loosening; the
floor's guarantee (a LitRPG book is always asked to speak its system) generalises from *a
numeric snapshot* to *at least one declared display the writer is asked for*, so a numberless
book declares a named-ladder display and a dungeon-core book declares a place-owned sheet.

**The costs, named.** The round trip template-to-pattern for arbitrary displays is the hard
part (the line's is one regex; a list display needs a print rule: what moved, the top few, what
the scene named). The ability cap of eight exists for the writer's prompt budget and the
system-voice example, so a list-shaped attribute needs a budgeted print rule rather than a
higher cap. Every consumer of `SystemDef` (the progression beats' rotation, the outline's
standing milestones, the numbers-go-up counters, the concept stage's fields) is built on the
current shape, so the current shape must survive as one *profile* of the general model (a
ladder, a graph, one line) and every book on disk must read identically after, which is the
ratchet §160 set.

## 4. The plan (2026-09-03, on the operator's decision: *"we definitely shouldn't have one specific LitRPG system"*)

The operator's second point sharpens the target: *Level | HP | MP | Gold* was wrong because it
was not general, and HP, MP and Gold are barely used in the genre besides. So the target is
**no default vocabulary at all**: `DEFAULT_SHEET` retires rather than being replaced, and a book
that declares no display prints no line. Every constant that names a genre convention is a
book that cannot be written.

**Invariants that hold through every phase** (the ratchet, §160's):

- Every book on disk reads identically after each phase: the golden fixtures, every store the
  suite replays, and the three pilot-25 stores (extraction of their chapters returns the same
  records before and after). A phase that cannot show this does not land.
- `SystemDef` survives as one *profile* of the general model (a ladder, an ability graph, one
  line), so every consumer built on it (the progression beats' rotation, the outline's
  standing milestones, the numbers-go-up counters, the concept stage's fields) keeps working
  until the phase that generalises it, and is then a caller of the general thing.
- Measurement first, a §-entry per phase, tests named in the entry, no bar without the four
  checks, and the corpus stays on the measurement side (RS1): the census sets defaults by a
  decision recorded in the entry, never by text reaching a prompt.
- One sustained job at a time on the box.

### Phase 0 — the market's display conventions, measured

`research/quality-measurement/system-displays/` (PREREG.md, `system_displays.py`, FINDINGS.md).
Over the LitRPG shards through `corpus_io.royalroad_chapters`, chapters one to three of each
story, using `progression_cadence`'s furniture classifier for what is not prose: the share of
chapters carrying any display; windows (a run of furniture lines) with their field count and
the share of fields at zero, N/A or blank; single notice lines per thousand words, split by
the cadence census's families (level up, capability gain, stat delta, other); choice screens
(a run naming options) and how many options; item boxes and quest cards by a heuristic,
reported as such. Distributions, no bar. The reading fixed before spend: what the defaults of
phases 1 to 3 are set to (unheld shown or not; how many fields a first window carries; whether
a choice display is a first-chapter object). The MirrorBench interpreter; a CPU job.

### Phase 1 — the line is a declared projection of the snapshot (done: stage-0 §203)

`domain/extraction.Sheet` gains a projection: the snapshot stays a full mapping per subject
per position (state is unchanged), and the *printed* line carries the rung and the held
columns, unless the sheet declares `show_unheld`. The template becomes label-value pairs in
declared order and the parser reads pairs generically, so an omitted column is an unchanged
value rather than a parse failure. `SystemDef.columns` keeps declaring the full column set;
`sheet_declaration` writes `show_unheld: false` for a newly drawn system and a sheet on disk
without the key means `true`, which is how every book on disk reads identically. The awe
effect moves to the `[OFFER]` line, where the operator says the genre keeps it. Tests: the
round trip for a projected line; a book on disk unchanged; a snapshot read back through an
omitted column. §-entry: what the three pilot-25 chapters print under it.

### Phase 2 — typed attributes on any owner

A sheet field gains a `type`: `number` (today, the default), `paired` (today), `ordinal` (the
value is a rung of a declared ladder and prints as its name, which is §160.3's split resolved
by declaration), `name` (one of a declared set of entities, printing its `is_a`: a class, a
title, a race), `text` (one line), `set` (references with optional depths: a skill list). The
parser and the renderer are derived per type from the one field list, as today. Snapshots may
hold strings and lists where the type says so; the contracts' `value` is already any JSON. The
owner of a snapshot may be any subject (a place, an institution, a creature); the protagonist
tie-break (§170) stays the rule for *which* sheet the writer is asked to print by default.
The ability cap of eight stays for the drawn profile; a `set` field carries a budgeted print
rule (what moved, what the scene named, the first few) instead of a higher cap. The
numbers-go-up counters and the `stands_at` chain are unchanged: an ordinal field prints the
same rung they count.

### Phase 3 — displays as declared views

The vocabulary's `view` node type gets an owner. A view is a subject with `type view`, a tag
(`is_a`), a voice (`manifests_as`), a field list with per-field show rules, a trigger (on a
change, on a request, at the opening, on an event kind) and an owner scope. The status line
becomes the first declared view, the graph line the second, the offer the third; the seed
declares them from the concept's *look* and *manner*, and `DEFAULT_SHEET` and its three
back-compatible names retire (their sixty-one call sites move to the book's own views, and
the golden fixtures gain declared views that render the lines they already hold). New views
the world may declare: a notice (one line for an event kind, in the system's words), a
readout (another subject's sheet, for Identify), a box (an item's or a place's attributes). The
writer's furniture ask enumerates the views due at the position; extraction parses each by
its tag and template. The choice display gains option text and conditional offers (an option
`requires` a record on the chooser's own sheet), which is the class-advancement screen.

### Phase 4 — moves and rules as declared shapes

Beyond gain, deepen, rise and choose: a signed change (a loss, a level down, a spend of
points), a merge (two capabilities into one, as a change that retires two and grants one),
and system growth (a capability declared mid-book is a new system digest in a revision
chain rather than a refused draw). *Numbers go up* becomes a declared monotonic shape on an
attribute that the §113 counters read, so a book whose numbers legitimately fall (a curse, a
debt) declares the exception rather than fighting the engine.

### Phase 5 — the floor generalised

`has_starting_sheet` and `speaks_system_voice` ask for *at least one declared view the writer
is asked for* instead of a numeric snapshot. A numberless progression book declares a ladder
view with names; a dungeon-core book declares a place-owned sheet; a crafting book with no
system declares nothing and is not asked. Last, because it is the guarantee the earlier phases
must not break.

### What is not in the plan

Genre modules (a quest module, an inventory module, a notification module). A model that
ranks or prefers displays. Any change to how the corpus is used. The reviser.
