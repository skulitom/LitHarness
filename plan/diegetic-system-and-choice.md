# The system had no fork and no reader, so the furniture arrived as a narrator's overlay

**Status: design record, 2026-08-30, written before the code and kept as the decision trail for
stage-0 §173.** Commissioned by read 10's central item on serial pilot 15b draw 4
(`plan/serial-pilot-15b.md`, "Read 10 fails the book"). The operator's direction is recorded
verbatim there and in `plan/house-genre-constraint.md`; **no word of it is in any prompt** (§97.1),
and the example sentence they supplied informs this design through the designed channel only.

## 1. What the read names, in the machinery's own terms

Two facts about the shipped contract, neither of which is a defect in the code that produces them:

- **§161.3 anchored the printed line to a number-move.** *"Print that line exactly once: where one
  of its numbers changes, or at the scene's end if none of them does."* Every clause of that is
  correct against the defect it was written for — a footer reports a change after the reader has
  left the moment — and its anchor is an **event in the machinery**, not a person. A line that
  appears because a number moved is a line the narrator emits. Read 10 calls it noise, and the
  contract is why.
- **`SystemDef` models an ability graph, a named ladder and one magnitude scale, and nothing
  anywhere models a moment where the system offers N and the character takes one.** The queued
  gap is already on the record (`plan/house-genre-constraint.md`, the schema note at the end;
  §166.3's *"a schema that gives a system a class concept can land without touching this text"*;
  §166.5's *"sits with the queued class/concept extension"*). The operator's original awe direction
  — *"i wonder what I would get and pick"* — is a choosing-among-options effect, and there is
  nothing in the model for it to be an effect **of**.

The two are one item. A system with no fork has nothing for a character to deliberate over, so the
only thing the interface can do on the page is report; and an interface that only reports has no
reason to be opened by anybody. **Deliberation is the business that makes reading the sheet a
scene rather than a caption.**

## 2. The choice point, as an object

`domain/gamesystem.py` gains two frozen dataclasses and one field on each of the two it already
has. Nothing is stored that is derivable, and nothing already on disk changes.

| thing | what it declares |
| --- | --- |
| `Option` | `option_id`, `name`, `grants` (ability ids of this system), `costs` (world-fact prose, optional) |
| `Choice` | `choice_id`, `name`, `options`, `opens_at` (a rung id, or `None` for open from the first) |
| `SystemDef.choices` | the forks, `()` by default and sorted by id at construction |
| `CharacterSheet.picks` | `(choice_id, option_id)` pairs, `()` by default |

**What makes it a choice rather than a checklist is foreclosure, and foreclosure is computed
rather than asserted.** An ability named in any option's `grants` is **gated**: `legal_moves` does
not offer it until the sheet holds the pick that opens it, and `_openers` skips it so a starting
sheet cannot hold one. So a fork changes *what is arithmetically possible*, which is the only
definition of a build fork this repository can check.

**The options are visible from page one, and that is the awe mechanism already half-built.**
`SystemDef.columns` prints every declared ability including the ones nobody holds — §160 wrote
that with the operator's awe direction quoted beside it. A fork's grants are ordinary declared
abilities, so all of them already sit on the line at 0 where the reader can see them, and exactly
one branch will ever light up. Nothing new had to be rendered for the reader to be able to want
one.

**A pick prints nowhere on the status line, and that is §160.3's split rather than an omission.**
`extraction`'s field pattern is `(?P<name>\d+)` — digits only — so a class name cannot ride a
column at any width, exactly as a rung's name cannot. §166.3 already settled where it may go
instead: *"The clause reaches numerals only, so a class name is governed by nothing in it."* A
pick is spoken in prose, carried in the packet as a world fact, and read back off its own edge.

**A fourth `AdvanceKind`, and §160's closure argument survives it.** That enum is documented
"closed, and small on purpose: a beat names one of these, and a vocabulary that grew would be a
vocabulary a beat has to choose within." The beat does not choose — `genre.beat_text` rotates by
schedule position (§161.4) — so a fourth member is one more position in a cycle rather than a
decision. And `_named_moves` **drops** a `CHOOSE`: a fork is not a quantity that moves, and naming
one in the progression beat would say a number moved when none did. The fork belongs to the
interaction beat below.

### The records, and why two of the five slots are reused

| predicate | subject | `--object` | `--value` | `--order-key` |
| --- | --- | --- | --- | --- |
| `offers` (new) | the fork | the option | — | never |
| `grants` (new) | the option | the ability | — | never |
| `chose` (new) | the person | the option | the fork id | when they took it |
| `governed_by` | the fork | the system | — | never |
| `requires` | the fork | the rung it opens at | — | never |

`chose` is `stands_at`'s shape on purpose: object the thing reached, value the ladder-or-fork it
is reached *on*, because a world may run several forks and an unscoped pick would splice them —
`PRECEDES_PREDICATE`'s own recorded reason. `requires` carries the opening rung because the
`Need` machinery already means exactly "this cannot be had before that", and a second predicate
saying it would be a second answer.

**No new entity role.** A fork is identified structurally — a subject `governed_by` the system
carrying `offers` edges — the way a criterion is identified by its comparator. `ENTITY_ROLES` tags
subjects a *counter* has to find; nothing counts forks, and a role that no reader reads is one
more thing an Architect can get wrong.

### The digest moves only for a system that has a fork

`SystemDef.digest` gains a `choices` key **only when `choices` is non-empty**. `SYSTEM_DIGEST`
exists to make drift a question a reader can ask (§160); a schema addition that changed every
existing system's digest would report drift that did not happen, on every sheet that cites one.
This is §160's own byte-identity rail — `test_a_holding_with_no_number_reads_exactly_as_it_always_did`
— applied to a hash instead of a sentence.

### What `check_draw` complains about, all membership or arithmetic

Two to four options (a fork of one forecloses nothing; a menu longer than four is not one anybody
reads on a page); unique option ids across the whole system and unique option names inside a fork;
every granted id a declared ability; every option granting at least one; **no ability granted
twice**, within a fork or across two, because an ability behind two gates has two answers to "is it
locked"; `opens_at` a declared rung; printable names, on `_printable_label`'s existing rule, because
a fork's name and its options' names reach a scene plan as book data.

**Nothing ranks an option** (§61(5)). `pending_choices` returns declaration order, `legal_moves`
orders nothing, `check_draw` asks about coherence, and there is no function anywhere in the module
that scores, compares or prefers. `test_nothing_in_this_module_ranks_an_option` asserts that over
the module's public surface rather than about one function, which is §160.5's shape.

**A pick is irrevocable.** `choose` raises on a fork already taken. That is the whole of what makes
the deliberation matter, and there is no retraction here for the same reason there is no
`world retract` (§160.5, still owed).

## 3. The furniture, re-aimed from the change to the person

Two moves, at two altitudes, and the cheaper one carries most of the weight.

**(a) The placement anchor, rewritten in place at zero demands.** `application/planner.py`'s
`status_example` branch sits exactly at its measured ceiling of 4 (§164), so the change is a
rewrite rather than an addition:

> ~~This book states its game state on the page, in this form, which is the state as it stands~~
> **The people in this book can read their own state, in this form, which is the state as it
> stands**
>
> ~~Print that line exactly once: where one of its numbers changes, or at the scene's end if none
> of them does.~~
> **Print that line exactly once, where somebody in the scene reads it; failing that, where one of
> its numbers changes, or at the scene's end.**

The cardinality §161.3 called load-bearing is untouched — `extract_state` runs `finditer` and mints
one canon record per match, so two lines at one position are the contradiction shape the gate then
refuses — and both fallbacks survive, so the guaranteed emission the footer bought is still not
given up. What moves is which of the three placements is *first*.

**(b) The interaction beat, at the plan altitude, which is where the budget is not.**
`plan/house-genre-constraint.md` named this hazard before anyone drafted a clause: *"show progress
immediately" as prompt text is a §138 formula waiting to happen. The altitude that avoids it is
structural — the planner's beat sheet.* §157 proved the move and §161.4 sharpened it. A scene plan
is book material, rides in the user prompt rather than the system message, and **costs no demand in
any row of `tests/test_prompt_budget.py`**. So the interaction beat is free where a clause is not,
and that is the whole reason it is the vehicle.

`domain/genre.py` gains a second scheduled item beside the progression beat:

- **the reading form** — *"The state this book prints is opened and read here by the person it
  belongs to, and what it says is business in the scene."*
- **the offer form** — *"{fork} stands open here, and the person it belongs to weighs {options}
  against each other on the page."*

Both are material rather than adjective, on §155.3's rule: they name a thing that happens, carry no
quality word, are pronoun-free (§155.3's first draft would have written a male protagonist into
every scheduled scene of every book), and drop any book-data name colliding with
`house.MACHINERY_WORDS` — a name off a book's own declaration is data no ceiling test can reach,
which is §161.4's recorded boundary.

**When it fires**, and the schedule is deliberately not a second cadence:

| condition | what the scene plan gains |
| --- | --- |
| the book prints no line at this position | nothing |
| not a scheduled ordinal (`beat_ordinals`) | nothing |
| a fork stands open at this position | the offer form |
| the opening scene, no fork open | the reading form |
| any other scheduled scene, no fork open | nothing |

So a book with no fork gains exactly **one** interaction beat, in the opening — the smallest
addition that answers read 10's comprehension item — and a book with forks deliberates for as long
as a fork is open, on the cadence the progression beat already runs at. "A large part of the story"
becomes a condition the world declares rather than a number this file picks.

**The `reads` gate is `status_example is not None`**, the same value the planner already computes
for the furniture ask. A book that is not handed a line cannot be asked to have somebody read one,
and deriving the gate from a second reader would be a second answer to "does this book print".

**Three rails are kept intact by construction, not by care:**

- **§165's order-key spaces** — the fork is read through `gamesystem.sheet_of(..., at=...)`, whose
  `within` is already `comparable` then `<=`. A scheduled `chose` in the schedule space is canon,
  readable, and never folded as past.
- **§167's record-implies-disclosure** — a fork opens because the **sheet's own rung** has reached
  `opens_at`, never because the book passed a position. That is §110's rule ("a schedule is a
  statement of intent, and intent is not an event") reached without a new mechanism. A fork whose
  rung the character has not reached is not pending, so the plan cannot name a branch the book has
  not arrived at.
- **§166's prose licence** — a fork's name and its options' names are names, not numerals, and
  §166.3 states in terms that the clause reaches numerals only. Nothing in the licence moves, and
  the licence's own text is byte-identical.

## 4. Standalone comprehension, and the half this does not reach

Read 10: *"Impossible to understand what is happening in the chapter if you haven't read the
overview."*

**What the interaction beat carries.** A character who opens their own state and reads it teaches
the interface by using it: the labels are spoken where they are used, the numbers are read by
somebody who cares what they say, and the fork's options are named on the page in the scene that
schedules the deliberation. The teaching material was already reaching the writer — an ability's
`manifests_as` renders into the packet as *"shows on the page as:"*, 33 times per scene (§168.5) —
and what was missing was an **occasion to spend it**. The beat is the occasion. Chapter 1 gets it
always.

**What it does not reach, stated rather than claimed.** The rest of read 10's comprehension item is
the chapter's *premise* — a signature device whose in-world reason is never given, a listing the
chapter leans on for its stakes. That is the premise/protagonist altitude read 3 put above
direction entirely, and no beat, clause or schema reaches it. It is the fresh-premise draw's, and
naming it here is the whole of what this track does about it.

## 5. What is refused, each with its reason

- **A model ranking, scoring or recommending an option** (§61(5)). The pick is drafted under
  constraints like everything else; the deliberation is the story surface and never an
  optimisation. There is no scoring function and the test asserts over the module's exports.
- **Extracting a pick from prose.** The one parsed surface is a digits-only status line; §160.3
  refused widening it to carry a name, and a second parse surface for one predicate would be a
  second answer to "what did this chapter establish". A pick reaches canon by declaration or by
  `choose`, exactly as a system does. Named as a residual: a drafted chapter can dramatise a pick
  and canon will not know.
- **A class column, a class number, or "Level N" of any kind.** §160.3's three conditions hold
  unchanged: every integer still names one ability, and a person's only number is still their rung.
- **Auto-granting an option's abilities on the pick.** A fork changes what is *possible*; the gain
  is still an advancement with its own position and its own beat. Granting three columns at once
  would collapse the progression the schedule exists to spread out — the `progression` block's own
  recorded argument, one object along.
- **A new clause in `house.py`.** The floor sits at `HOUSE_BUDGET` and three rows stand on it at
  their ceilings; §171.4 records that the next clause added there raises four numbers. Everything
  here lands in a plan item or in a rewritten sentence, and the one raise it does take is a single
  role's.
- **A second entity role, and any change to `worlds.NODE_TYPES`.** A fork is an ordinary subject
  found by its own edges.
- **A retraction or a re-choice**, for `world retract`'s reason, still owed since pilot 14 §10.
- **Any bar.** Two-to-four options and the label rules are arithmetic about a printed menu, not a
  claim about how many ways a system should fork. §61's four attainability checks have nothing to
  run on, and there is no distribution of forks to place anything in.
- **A detector reconciling a `chose` edge against prose**, on §160.5's reason unchanged.

## 6. What it costs, in the open

One demand, in one role. `world_agent._SYSTEM` gains a sentence naming the fork, because a schema
nothing seeds is §160's own history repeating — that entry shipped a system object with no
declaring path and it took §163 and §165.2 to make one reachable. The three predicates are also
written into `world vocabulary` with probes, which costs nothing: that command's output is a tool
result, not a counted prompt. `tests/test_prompt_budget.py` carries the raise with the reason, and
no other row moves.

## 7. Anti-scope

No model is called and no book is drawn. Nothing here measures a chapter, declares a bar, admits an
axis or promotes a research claim. No corpus is read, so RS1 is untouched. No `runs/` database is
written. Nothing the operator said is in any prompt. Whether a world declares a fork, and whether a
chapter that carries the interaction beat reads differently, are the next pilot's to find — this
note claims **shipped, unmeasured** and nothing further.
