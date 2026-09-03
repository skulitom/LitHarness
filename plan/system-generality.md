# Will the system layer fit any LitRPG story, and any future one?

Status: **design note and plan, 2026-09-03**; the operator decided the same morning that the layer is made general (§4); the five phases closed the same day and §5 records the fit census that measures what they left. Written first for his question
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

### Phase 2 — typed attributes on any owner (done: stage-0 §204; several sheets per book wait for phase 3)

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

### Phase 3 — displays as declared views (four slices done: stage-0 §205, the default sheet retired and a book's own evidence declaring its columns; §206, a sheet declaration naming its owner so a book carries several sheets; §207, the choice display, a way saying what it looks like and what it needs; §208, the notice, a gain phrase on the graph line asked for where a beat names a gain. Closed without a view node, stage-0 §209: the four slices gave every declared display a home on the predicates the vocabulary already had, so a node would be a second declaration of the same facts. The readout on request is owed, a furniture ask now that owners exist)

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

### Phase 4 — moves and rules as declared shapes (measured: the system-displays changes census, 570 of 596 written changes rise, the commonest fall a spend; first slice done: stage-0 §210, a grant the rungs hand out and a grant paid in it; second slice done: stage-0 §211, a system grows after the seed and the sheet it minted follows it, after the growth census found a quarter of the bracketing stories past eight named things on a sample alone.; third slice done: stage-0 §212, a change of kind as one declared change whose effects the sheet folds and whose scene is asked to print the line after it, after the evolution census found it the genre's second commonest notice. Phase 4 is closed at the model level; a gate on the change's line waits for a first observation. Drawn once, stage-0 §213: the seed took up every shape and the chapter printed one unmoving line twice, for two seed faults that acceptance now refuses (§213.1) and one open question, a change scheduled in the zero-padded key space never lands in a scene, which is §165's and stays open)

Beyond gain, deepen, rise and choose: a signed change (a loss, a level down, a spend of
points), a merge (two capabilities into one, as a change that retires two and grants one),
and system growth (a capability declared mid-book is a new system digest in a revision
chain rather than a refused draw). *Numbers go up* becomes a declared monotonic shape on an
attribute that the §113 counters read, so a book whose numbers legitimately fall (a curse, a
debt) declares the exception rather than fighting the engine.

### Phase 5 — the floor generalised (done: stage-0 §209; the floor asks for a display the book can print, a sheet with a snapshot or a standing on a declared ladder with its line)

`has_starting_sheet` and `speaks_system_voice` ask for *at least one declared view the writer
is asked for* instead of a numeric snapshot. A numberless progression book declares a ladder
view with names; a dungeon-core book declares a place-owned sheet; a crafting book with no
system declares nothing and is not asked. Last, because it is the guarantee the earlier phases
must not break.

### What is not in the plan

Genre modules (a quest module, an inventory module, a notification module). A model that
ranks or prefers displays. Any change to how the corpus is used. The reviser.


## 5. The fit census, and the gaps it ranks (2026-09-03, stage-0 §217)

With the five phases closed, the question §1 opened was measured instead of argued:
`research/quality-measurement/system-fit/` declares sixty sampled market stories' shapes,
and the four shelf anchors', into fresh stores through the world CLI and reads the house's
own answer. `FINDINGS.md` there owns the numbers; the reading is that the house declares most
of what a window holds and almost every story also prints a line the house has no word for.
The ranked gaps, and what each is in this note's terms:

1. **The notice** for anything but a gain or a rise: the System speaking, a welcome, a
   warning, a quest given, a title, a zone. A `change` node with a `manifests_as` line is the
   declared shape; §218 asks the scene it lands in to print it under the book's bracket.
2. **Plain columns beside a system's grants**: a pool, a currency, a class or an age on the
   line with the grants. Refused on purpose at completion (§165.2's branch); the census earns
   the reversal. The second slice.
3. **The quest card**: the notice's twin with counters; a change the System announces, its
   counters paired columns already. Not earned separately until the notice has been drawn.
4. **The readout on request** (§209's owed item): every fact declarable since §206, nothing
   asked for.
5. **Another screen**: a menu, a store, a board; several displays the census does not
   separate.

Below these, the draw's own rules (five to eight grants, a graph not a list, a depth
somewhere) refuse every hand-declared system in the sample at completion; whether a declared
system may be a list, held-or-not or three grants wide is a decision for its own entry. §2's
table above is the design-time reading; the census is the measurement, and where they
disagree the census wins.
