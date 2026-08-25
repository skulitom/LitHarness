# Serial Pilot 7 — the first book the listing loop produced by itself

**Status: RUNNING, 2026-08-25.** Companion to [`plan/serial-pilot-6.md`](serial-pilot-6.md),
which is the last pilot asked for as a read rather than as an arm, and to
[`plan/handoff-listing-loop.md`](handoff-listing-loop.md), whose three tasks this run is the
occasion for. The machinery is stage-0 §139.

## 0. What this run is, and the two readings it may not be given

**It was asked for as a read.** The operator: *"Once you think we have something working let me
know and i can read your title, overview and chapter choices"*. So the purpose is a title, a
listing and chapters in front of a person, and everything counted below is a description of one
book.

**It may not be read as a quality claim.** §61's bar is a blinded, position-swapped win rate
against matched published prose; this is one book, six scenes, no comparator and no blinding.
The operator's own read of it is a **defect harvest and not data** (§95's scope axiom, and the
four reads in `plan/reader-read-*.md` are the precedent for what a read of ours becomes).

**It may not be read as a comparison to Serial Pilot 6 or to *A Good Take*.** Every input
differs at once — the world is seeded by an agent under a listing rather than forged, the writer
is a named cast member for the first time on the scene path, and the listing was written by the
loop rather than by an operator. Where a counter here sits beside an earlier pilot's it is a
description of two books and never a difference between two treatments.

**It is a steered book, and that has a consequence that outlives it.** The steering pool saw the
listing and the writer revised it. §128 and `domain/pools.py`: *a steered book leaves §61's
measurement set for good*. Nothing here may later be used as a measurement-set book.

## 1. What produced it

```bash
uv run litharness --database serial7.db init
uv run litharness --database serial7.db listing --writer halloran --scenes 6 --out pilot7
uv run litharness --database serial7.db --writer halloran architect seed
uv run litharness --database serial7.db world accept --all
uv run litharness --database serial7.db --writer halloran --target-words 1500 tick   # x N
```

**No brief**, which `overview.render_overview_request` renders as *"Anything you would most want
to read"* and which is the control the forge kept for the same reason. §136 measured a
two-word shelf label outweighing every rule in the prompt, and the genre is already in the
dossier: `halloran` writes *"people who wake up somewhere impossible and have to survive the
afternoon"*.

**One writer, chosen by a person and not by a model.** Which roster to run is an operator act
(§84); no model ranked the four, because §137 leaves the gate that would license a comparison
between writers with no key.

## 2. The listing, and what the readership did with it

    Copy Costs A Hand

    The thing on the stairs eats light, and Dan is out of matches. Yesterday he was a
    hospital porter, moving beds down a night ward. Tonight he is in the dungeon under a
    city that sells magic by the vial, and the only spell he knows took his hand off at the
    wrist. It grew back wrong, and the wrong hand does what the old one could not. He can
    copy a monster's power by watching it kill someone, so he has to stand close enough to
    be next, and every copy costs him another piece. He wants the surface, his ward, and one
    boring shift.

**106 words**, against the market's 40–146 and median 100. Zero em dashes, zero floors or rank
positions, third person. The four measurement readers all said `start_reading` — 4 of 4 — which
is a number with §134's ceiling written across it and is reported for that reason rather than
believed.

**The title was looked up and is free.** Nine web searches, no work of any kind carrying it, no
near miss. Nothing was abandoned, so the retry path is untested against a real collision.

### 2.1 The steering pool's direction is legible in the revision, clause by clause

The draft the four steering readers saw, before any of them spoke (`pilot7/listing.json`):

> The thing on the stairs eats light, and Dan is the only warm thing left in the dark. He is a
> hospital porter who fell asleep on a night shift and woke under a city that runs on a
> dungeon: monsters below, guilds above, magic sold by the vial. His first spell takes his hand
> off at the wrist. His second grows it back wrong, and stronger. He can copy any power he
> watches kill someone, and down here everything is trying to kill him. He wants out. Then he
> wants whatever put him in, and the way to it runs deeper.

**Three changes, and each has a reader sentence behind it.** This is the first time in this
project that a reader-in-the-loop edit has been traceable to what a reader said, rather than
inferred from a rate.

| what changed | what a reader had said |
| --- | --- |
| *"so he has to stand close enough to be next"* — added | *"Copying has to be earned by nearly dying under the thing that owns the power. If watching is enough, it's a shopping list."* |
| *"every copy costs him another piece"* — added | *"I want scar accounting, not a montage"*, and eleven more sentences saying the same thing |
| *"Then he wants whatever put him in"* — **deleted** | *"Pay the first want before selling me the second"*, and *"the turn happening off-page"* named under dreading |

The third is the interesting one, because it is a **subtraction**, and this project's recorded
lesson about instruction text is that subtraction is what works (§135, §138). Nothing told the
writer to cut; four readers said they did not want to be sold the second want yet, the material
reached the writer as *what people said* rather than as instructions (`Anticipation.render`'s
rule), and the writer cut it.

**What it did not do is make the listing longer.** 101 words to 106, where the reader material
was 25 hopes and 25 dreads. §133 measured a wish list rendered into a *system* prompt at two
thirds of everything the writer was told, and the draft that came back serviced it;
`render_revision_request` puts it in the prompt beside the listing for exactly that reason, and
this is the first evidence the arrangement holds under a large one.

## 3. The world, and the two things the seed found out about its own tools

**Cauldwell**, a city that sells magic across a counter by the vial and stands on a worked hole
it calls the Well. **208 records, six rules, ten capabilities, one chain of eleven rungs, six
people.** The rule the book turns on is the Architect's own sentence: *a copier keeps every
trick he ever takes — what he loses is never power, it is the person he was*, which is
`house.ACCUMULATION` arriving as a world rule rather than as a phrase in the prose. The clause
was taken *off* the listing call on 2026-08-25 because a keep-power became the central hook in
seven listings of eight against zero of ten in the market (`overview._system`'s docstring); it
stayed on the Architect, which is where accumulation was argued to belong, and this is the
first world seeded since that split.

Three of the ten capabilities are held by nobody — *choosing which arm to offer*, *spilling the
dark back out of a closed hand*, *running two wrong parts at once*. That is §114's inventory
being used as headroom rather than as an inventory, and it is what the first chapters are
pointed at.

**The ladder is eleven rungs and the book's own record writes down only six.** Dan stands at
eight; the woman who sold him the vial stands at four; everything living in the Well is at
eleven. So the ceiling is above what anybody in the world has written down, which is the
operator's *"part of the appeal is you don't know where the top is"* satisfied by a fact about
the record rather than by a rule against ceilings.

### 3.1 An agent that learns its tools leaves the lesson in the world, permanently

The Architect's own closing report:

> I probed the CLI's record shapes before I understood that declares append with no retraction
> path, so three scratch records are permanently on this branch [...] `world check` will exit 1
> on this branch forever and `world accept` will need `--force`.

It is right, and it named the defect before anybody looked. `worlds.validate` iterates every
record, so a later corrected declaration does not supersede a bad one — there is no tombstone
and no retraction. **The world of every book this Architect seeds will carry whatever it typed
while learning the interface.** Here that is one invalid consequence domain, and the cost is
that this branch's coherence check is permanently red and that `accept` had to be forced on a
world whose only complaint is a scratch record.

Two directions, neither taken here: a `world retract` writing a superseding tombstone that
`validate` reads, or a probing mode whose declarations never land. The agent is already told to
run `world vocabulary` first and did; the vocabulary tells it the predicates and not the shapes.

### 3.1.1 And the real cost is not the check. It is that no scene can be drafted.

The first tick failed, the second parked the beat, and the exception named four **blocking**
`state.contradiction.v1` findings — every one of them an append artefact:

| finding | what it is |
| --- | --- |
| `q_probe asks` holds 2 values | scratch probe |
| `q_probe claim.content` holds 2 values | scratch probe |
| `rule_probe world_rule` holds 2 values | scratch probe |
| `crit_glasses manifests_as` holds 2 values | **the Architect redeclaring its own criterion with better text** |

`detect_contradictions` is right and is not the thing to change: it groups canon on
`(subject, predicate, object_ref, order_key)` and two values at one position is exactly the
defect it exists to catch. What is wrong is upstream — **`world accept` carries every proposal
to canon, including the one a later proposal was written to replace**, so an agent that
improves its own declaration ships both versions and the book refuses to start.

**This is the shape §126 forbids, introduced by the machinery built to remove it.** The
Architect exists so that a world is not filled in once by a person; the price of it correcting
itself is that a person must `dismiss` one finding per correction and `revive` the beat before
a single word can be drafted. Here that was four dismissals, one `resolve` and one `revive` —
all recorded, none of them a judgment about the story, and every one of them a human in the
production loop.

**The fix that fits what is already here**, for whoever takes it: accept only the *latest*
proposal per `(subject, predicate, object_ref, order_key)` into canon and mark the ones it
replaces superseded. That is the retraction path the Architect said it needed, it costs no new
verb, it matches what the agent already believes it is doing when it redeclares, and it leaves
`detect_contradictions` untouched — the detector keeps its licence and stops being fed
supersessions. It is a change to what `accept` means, so it belongs in the decision log before
the code.

**Not done in this run.** The four findings were dismissed as `accepted_intentional` rather
than `false_positive`, because the detector was not wrong: the records genuinely disagree, and
marking a correct detector false is the trade `cmd_dismiss`'s own docstring refuses.

### 3.2 The day's token ceiling cannot express an agent run

One `architect seed` spent **7.86M tokens and $10.69 in fourteen calls**, against
`BudgetPolicy`'s 5M-token day. Almost all of it is cache reads at roughly a tenth of the price,
so the token axis reads a 200-turn agent as four days of drafting while the dollar axis reads it
as ten dollars. The drafting run below therefore sets a deliberate token ceiling and a **dollar**
ceiling, which is the axis that means something when an agent is in the loop. `max_cost_usd_per_day`
is `None` by default and the module already says it is *"never the sole ceiling"*; what this run
found is that it is the only one of the two an agent respects.

### 3.3 The world declared no protagonist

`world cast` reports `protagonist: null`, so `planner.render_prompt` receives
`point_of_view=None` and every scene is drafted with no point-of-view line — the control arm,
by accident. The seed task asks for *"who is in it, what they can do, what getting better means
here and what it costs"* and never asks whose book it is. Recorded, not fixed: adding a clause
is what §127 and §138 are both about, and the cheaper reading is that the listing already names
Dan and the Architect declared him without the label.

## 4. The chapters

Filled in when they exist.

## 5. What this found about the machinery

Filled in at the end.
