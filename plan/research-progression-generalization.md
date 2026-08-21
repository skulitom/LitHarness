# Research brief: generalizing world systems, abilities, and progression

*Handoff prompt. Self-contained — you need no prior context from this project.*

---

## What you are being asked

Build the **general model of fictional progression**: the smallest set of primitives that can
express any system by which people, creatures, places or things in a story get more capable,
differently capable, or capable at a cost — and the rules governing what happens when a world
runs more than one such system at once.

This is a modelling problem, not a survey. A survey is your input, not your output.

## Why the obvious answer is wrong

The obvious model is a character sheet: levels, hit points, mana, currency. It is wrong in a
specific and instructive way — it privileges one genre's accounting so thoroughly that a world
without combat cannot be described in it at all, and it makes *absence* expensive: a story with
no system has to opt out of a model that assumed one.

We already know some of what a better model needs, from a first pass:

- **Systems** are plural. A world may run magic and body cultivation side by side with
  contradictory internal logic. It may run one. It may run none.
- **Ladders come in at least two shapes.** *Tier* ladders are ordered named rungs (bronze,
  silver, gold) where each rung has an appearance you can see. *Depth* ladders have rungs that
  are successively deeper readings of a single concept — the rung *is* a claim, not a name — so
  a story can run a long way on two or three ideas reread rather than a widening list of powers.
- **Carriers** are objects that hold power and change hands; sets of them make completeness a
  progression axis of its own.
- **Bonds** are compound entities: a pairing that holds abilities neither partner owns.
- **Agencies** — gods, alien forces, the system itself, AIs, spirits, institutions — grant and
  own systems, and their aesthetic is what couples them to the abilities they grant.
- **Relations have arity.** "Held by" admits one holder at a time; "has trait" admits many.
  Conflating those is the difference between catching a real impossibility and refusing an
  ordinary fact.
- **Visibility is a separate axis from truth.** What is true, what the character knows, what
  other characters know, and what the reader knows are four different things, and systems with
  concealed natures depend on the gap.

Treat that list as a **hypothesis to attack**, not a foundation. We expect it to be
under-general in ways we cannot see from inside it.

## Where to look

Go wide, and deliberately past fiction:

- **Tabletop RPG design.** The richest source by far — decades of formalized, playtested
  progression models with explicit disagreements: class-and-level, skill-purchase, aspect and
  trait systems, advancement-by-failure, advancement-by-belief, diceless and narrative systems.
  These are literally competing answers to your question.
- **Video game and board game progression.** Skill trees, tech trees, roguelike meta-progression,
  deckbuilding, collection and gacha economies, crafting and automation games, prestige loops,
  Metroidvania ability-gating (where the "stat" is *access*, not power).
- **Prose traditions with strong progression grammar** — litrpg, cultivation and xianxia,
  academy and apprenticeship stories, heist and crew competence arcs, sports and training arcs,
  detective competence, and hard-magic fantasy where the system is the argument.
- **Real-world rank and credential structures.** Guild hierarchies, martial arts grading,
  chess and sports rating systems, military rank, academic degrees, professional licensure,
  apprenticeship. These are progression systems that had to survive contact with reality, and
  their failure modes are documented.
- **Expertise and learning research.** Deliberate practice, chunking, conceptual change,
  threshold concepts, the structure of misconception. Directly relevant to depth ladders and to
  what a "breakthrough" actually is.
- **Knowledge representation.** Property graphs, RDF, cardinality and arity constraints,
  ontology design patterns, type systems. Your deliverable *is* an ontology; borrow the tools
  and the known failure modes.

## Questions worth chasing

Not a checklist — the ones that look most likely to break the hypothesis:

1. **Is a ladder always ordinal?** Find systems where advancement is lateral (breadth, not
   height), cyclical, or a trade — where specializing forecloses. Does "ladder" survive?
2. **Is progression monotone?** Systems where you lose to gain, where power corrupts or ages or
   is taken back, where the arc is decline. Does the model handle a downward ladder without a
   special case?
3. **Who progresses?** Individual, pair, crew, sect, lineage, institution, *place*. Bonds
   already break the individual assumption. How far does it break?
4. **What authorizes an advance?** A system that decides, a peer who recognizes, an internal
   state that changes, an object acquired, a rite performed. These have different narrative
   consequences and may need to be different primitives.
5. **What happens when two systems meet?** Exclusivity, conversion, interference, dominance —
   and the case worth special attention: **one system is a lie about another**, a game-like
   interface over something that is not a game. How common is that, and can the model hold it?
6. **Where does cost live, and is it paid on the page?** Systems whose costs are invisible read
   as wish fulfilment. Is "cost" a primitive or a relation?
7. **Who can see the state?** Map the legibility gaps: opaque to the protagonist and legible to
   the reader, and the reverse. What does each gap buy a story?
8. **What does progression do for a reader?** Separate the *mechanism* from the trope —
   anticipation from a known ladder, legible causality, identity change, completionism,
   vicarious mastery. Which mechanisms are doing the work, and which are decoration?

## What to deliver

1. **A survey matrix.** Twenty-plus systems from at least four of the source domains above,
   scored on whatever axes your analysis actually produces. The axes must be earned by the data,
   not assumed in advance.
2. **The primitive set.** Minimal. Each primitive justified twice: by a system that *requires*
   it, and by a system that does fine without it. A primitive that no surveyed system needs
   alone should be cut and the cut recorded.
3. **A relation vocabulary with arity.** For each relation, whether it is functional (at most
   one target per subject at a time) or multi-valued, and what the violation *means*.
4. **Interaction rules for multi-system worlds**, including the lie-about-another case.
5. **A falsification section — the one we will read first.** Five or more real systems your
   model *cannot* express, stated plainly, with what each would cost to admit. A model with no
   falsification section has not been tested.
6. **Three worked encodings, end to end.** One combat-driven, one with no combat at all (a
   crafting, scholarly or social system), and one that breaks an assumption — collective,
   declining, or involuntary progression.
7. **A failure-mode catalogue.** Power creep, stat inflation, systems that stop mattering after
   the first act, unearned advancement, ladders that never move, illegible rules. For each: the
   **checkable signature** — what a reader or a program could observe in the text that indicates
   it — because we intend to build detectors.
8. **A rejection list.** Common primitives you recommend *against* adopting, with the reason.

## Rails

- **Every primitive must be expressible as records of the shape** `(subject, predicate,
  object, value, story-position, authority, visibility)` — or you must say explicitly what it
  needs that this shape lacks. That exception list is a finding, not a failure.
- **Absence must be free.** A world declaring none of this must pay nothing. Any primitive that
  is mandatory, or that has a default which asserts something, is wrong by construction.
- **Every primitive must be legible in prose.** If it can only be conveyed by printing a stat
  block, it fails — a stat block is the thing being generalized away from. Ask of each: how does
  a reader *see* this without being told it?
- **Every ladder shape needs an anti-stasis property**: a checkable statement of what "it moved,
  and the movement said something new" means for that shape. The known failure is a character
  who visibly deepens while the text says nothing it had not already said.
- **No human-subject research.** Do not propose reader surveys, interviews, panels, or
  annotation by people. Measurement here is model-based only. Analysis of published work and of
  its formal structure is fine.
- **Name works freely as objects of analysis; the model must be genre-neutral.** The output must
  not encode any single work's setting, system, or voice, and must be stated in neutral
  vocabulary that no source could claim.
- **Say what you are unsure of.** A confident taxonomy that quietly papers over three awkward
  systems is worth less than a smaller one that names them.

## How we will judge it

By the falsification section and the non-combat encoding, before anything else. A model that
elegantly expresses every litrpg and cannot express a story about a cabinetmaker getting better
at cabinets has reproduced the problem we are trying to leave behind.
