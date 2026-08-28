# Serial Pilot 7 — the first book the listing loop produced by itself

**Status: ~~RUNNING, 2026-08-25~~ → COMPLETE, drafted 2026-08-25, settled 2026-08-28.**
§6 records what landed after the status line was last touched, and why this book is not
the fifth operator read's target. Companion to [`plan/serial-pilot-6.md`](serial-pilot-6.md),
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
uv run litharness --database serial7.db listing --writer halloran --scenes 6 --out runs/pilots/pilot7
uv run litharness --database serial7.db --writer halloran architect seed
uv run litharness --database serial7.db world accept --force        # <- and here it stopped
```

**`serial7.db` is the record of the failure and holds no prose.** §3.1.1 is why: the world it
seeded blocked every scene, the fix went into `world accept`, and the world was seeded again on
`serial8.db` under the same listing and title, which the loop had already written to
`runs/pilots/pilot7/`.

```bash
uv run litharness --database serial8.db init
uv run litharness --database serial8.db new "$(cat runs/pilots/pilot7/title.txt)" \
    --premise "$(cat runs/pilots/pilot7/listing.txt)" --scenes 6
uv run litharness --database serial8.db --writer halloran architect seed
uv run litharness --database serial8.db world accept
uv run litharness --database serial8.db --writer halloran --chapter-scenes 2 tick   # x N
```

**Six scenes at the 900-word default, two to a chapter**, rather than three chapters asked for
at 1,500 words each. `DraftPolicy.max_chars` is 8,000 and `_draft_policy` deliberately exposes
only the target, so a compliant 1,500-word scene would be refused as a runaway by the shape
gate. The market's chapter is ~1,500 words; the way to reach it today is grouping, not asking.

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

The draft the four steering readers saw, before any of them spoke
(`runs/pilots/pilot7/listing.json`):

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
the now-retired `render_revision_request` put it in the prompt beside the listing for exactly
that reason. The run remains historical evidence; production no longer sends raw appetite text
back to a writer, as `reader-architecture-program.md` records.

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

**It reproduced.** The second seed, on `serial8.db`, opened by writing `probe_crit`, `probe_a`
and `probe_b` into the world before it wrote a word of Cauldwell — the same behaviour, from the
same prompt, with a different world coming out of it. So this is not one agent's bad hour: **an
agent handed a write-only interface learns it by writing**, and every world this Architect seeds
will carry the lesson. Supersession (§139.3) handles the *redeclarations* the probing produces;
it does nothing about the probe subjects themselves, which reach canon as entities with no part
in the book.

**The fix that removes the reason to probe is a tool fix and not a rule.** `world vocabulary`
lists the predicates and roles a world's language admits and says nothing about the *shape* each
one expects — whether it takes `--value` or `--object`, what a criterion needs before it is a
criterion. Adding the shapes there is what the agent was looking for; a clause telling it not to
probe is the fourth-rule move §127 and §138 both refuse.

**Third seed, third time, and this one landed inside the genre's spine.** A book seeded the same
evening (`serial9.db`, *Patch Notes For Earth*, writer `ferreira`) declared a clearance ladder of
eleven rungs — and six of them are `rung_a`, `rung_b`, `rung_c`, `zz_one`, `zz_two`, `zz_three`,
chained straight on above `clearance_4`. **The probe names are in the ladder**, which is the one
structure §113 built so the genre's numbers could not be faked, and a standing target that ever
reached `zz_two` would put this system's own scratch vocabulary on the page. It did not here,
because the protagonist stands at rung two of eleven and two chapters do not climb six — so the
leak is latent rather than realised, which is the worst way for a defect to sit.

Supersession caught ten redeclarations in that world (`zz_crit manifests_as`, `rung_a
manifests_as`, `one_holder group_key`, and seven more, every one of them a probe subject). Ten
blocking findings that book never saw. It is also the measure of how much probing there is: ten
of 256 records were an agent correcting itself while learning the interface.

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

**And `dismiss` does not clear it**, which is the part that makes this a blocker rather than a
chore. The pre-flight gate (`gate_standing`) reads *stored* findings and honours dismissal; the
integrity gate re-derives them from canon on every attempt and never looks at their status. Four
dismissals, one `resolve` and one `revive` bought exactly one more refused draft each, and the
run went from one poisoned unit to two.

**What shipped, stage-0 §139.3.** `world accept` carries only the last declaration into each
slot; the ones it replaces stay the proposals they already were, so `promote_state_records`
keeps its *"only ever upward"* rail and canon is never rewritten.
`integrity.superseded` sits beside `detect_contradictions` and both call the new
`disagreement_key`, because two callers with two ideas of what a slot is would leave behind
exactly the pairs the detector fires on.

The four findings on `serial7.db` were dismissed as `accepted_intentional` rather than
`false_positive`, because the detector was not wrong: the records genuinely disagree, and
marking a correct detector false is the trade `cmd_dismiss`'s own docstring refuses. It did not
help, and the world was seeded again on a store where `accept` had the fix.

### 3.1.2 The agent's report was lost to an arrow

The second seed ran sixteen minutes, declared 278 records, and then exited on
`UnicodeEncodeError: '→'`. The store had already committed; what died was
`print(result.text.strip())` — the agent's closing account of what it built and what it left
open, which is the only human-readable thing a seed produces.

`_write_document`'s docstring has recorded this exact defect for the export path since the
first CLI provider ran: `print` goes through the console's own codec, cp1252 on this host, and
a book is made of characters cp1252 cannot represent. The operator surface never got the same
treatment. `_say` is that, and every place the CLI prints text a model wrote now goes through
it — the agent's report, the listing, the title, the readers' reasons.

### 3.1.3 Two seeds from one prompt produced very different worlds

| | first seed (`serial7.db`) | second seed (`serial8.db`, pass 1) |
| --- | --- | --- |
| records | 208 | 278 |
| rules | 6 | 10 |
| declared chains | **1, of eleven rungs** | **none** |
| `world check` complaints | 1 | 15 |
| features manifested | 20 of 20 | 25 of 36 |

Both ran the same request against the same listing with the same writer. The first built the
ladder the genre turns on; the second declared standings on rungs no chain contained, which is
`world check`'s loudest complaint and exactly the arithmetic §113 exists to make impossible to
fake. **A seed is one draw**, and nothing in this pipeline reads `world check` and decides to
keep going — the operator does, which is why a second `seed` pass was run here by hand.

**The second pass repaired it, and diagnosed the cause in one sentence**: *"the criterion has to
ride in `--value`, not `--order-key`, so every standing in the store had been counting against
nothing"*. Two ordinal chains now stand — the Register's five classes and the Hall's six
licences, Dan at the second class and no licence — and the check is down to the one malformed
legacy record the first pass left, which cannot be retracted. **377 proposals, 376 accepted, and
exactly one left proposed**: `probe_crit type`, the redeclaration that would have blocked every
scene of the book. That is §139.3's fix meeting the case it was written for, on the real thing
rather than in a test.

It is also the third instance of one cause. The agent probes because the interface is
write-only; the standings counted against nothing because `world declare`'s *shapes* are not
discoverable; and it says so itself. `world vocabulary` naming the shape each predicate expects
is the fix for all three.

### 3.2 The day's token ceiling cannot express an agent run

One `architect seed` spent **7.86M tokens and $10.69 in fourteen calls**, against
`BudgetPolicy`'s 5M-token day. Almost all of it is cache reads at roughly a tenth of the price,
so the token axis reads a 200-turn agent as four days of drafting while the dollar axis reads it
as ten dollars. The drafting run below therefore sets a deliberate token ceiling and a **dollar**
ceiling, which is the axis that means something when an agent is in the loop. `max_cost_usd_per_day`
is `None` by default and the module already says it is *"never the sole ceiling"*; what this run
found is that it is the only one of the two an agent respects.

### 3.3 One seed declared a protagonist and the other did not

`serial7.db`'s `world cast` reports `protagonist: null`; `serial8.db`'s names `dan_ferris`. So
on the first world every scene would have drafted with no point-of-view line — the control arm,
by accident — and on the second `planner.render_prompt` carries `Point of view: dan_ferris.`

The seed task asks for *"who is in it, what they can do, what getting better means here and what
it costs"* and never asks whose book it is, so whether the drafting prompt knows its protagonist
is left to the draw. Recorded rather than fixed: adding a clause is what §127 and §138 are both
about, and the honest reading is that this is the same variance as the ladder, in a second place.

## 4. The chapters

Six scenes, two to a chapter, drafted by `halloran` — **the first prose this system has produced
that was written by somebody**. Every scene before 2026-08-25 was drafted by a prompt with no
identity in it, because `make_plan_selector` had no way to pass one (§139.1).

The counters below are the handoff's task 1: *"the cramming arithmetic that broke the listing has
never been run on a scene. Draft one, count its longest sentence, and read it."* The listing's
tell was one 79-word sentence holding four clauses, produced by sixteen demands over a hundred
words. The scene prompt's floor is **28 demands**, or 32 with a dossier, over nine hundred.

**Twenty ticks, six drafts, six evaluations, six summaries, no park, no poison, no repair.**
6,054 words in three chapters of 1,977, 2,072 and 2,014 — the market's publication format
(~1,500 words a chapter) reached by grouping rather than by asking, because
`DraftPolicy.max_chars` refuses a 1,500-word scene as a runaway.

| | s1 | s2 | s3 | s4 | s5 | s6 | book |
| --- | --- | --- | --- | --- | --- | --- | --- |
| words | 993 | 981 | 1026 | 1043 | 1014 | 997 | 6054 |
| longest sentence | 51 | 63 | 60 | **68** | 49 | 44 | 68 |
| mean sentence | 12.7 | 12.9 | 14.5 | **20.1** | 17.5 | 15.6 | 15.2 |
| sentences over 40 words | 7 | 9 | 6 | 9 | 6 | 3 | 40 |
| number tokens / 1k | 18.1 | 26.5 | 22.4 | 12.5 | 14.8 | 17.1 | 18.5 |
| em dashes / 1k | 3.0 | 2.0 | 3.9 | 1.0 | 3.0 | 1.0 | 2.3 |
| dialogue ratio | 0.29 | 0.14 | 0.14 | **0.01** | 0.03 | 0.31 | |
| lyric index | 12.1 | 10.2 | 6.8 | 5.8 | 9.9 | 1.0 | |

### 4.1 The cramming arithmetic says the scene path is not cramming

**The listing was one demand per six words. The scene is one per thirty-one.** Sixteen demands
over a hundred words broke the listing and the tell was a 79-word sentence with four clauses
compressed into it. Twenty-eight demands (32 with the dossier) over a thousand words is five
times the room, and the longest sentence in the book is **68 words** — but it is not the same
object:

> His own hands went out of the world at the wrist and the standing lamp went out of the world
> and the sound of his boot did not, and two feet from his knee the thing folded itself down
> over Mirren Kadd and took what it had come for, and Dan Ferris stayed where he was and
> watched it done with his eyes open and his teeth shut.

Every one of the six longest sentences is one action stretched by `and`, at the moment of the
scene's worst thing. The listing's 79-word sentence was four separate demands satisfied at once.
**Length is the same and the cause is not**, which is the whole reason the handoff asked for the
sentence to be counted *and read* rather than counted.

**What the counters do flag is scene 4**, and they agree with each other: the longest sentences
(mean 20.1 against the book's 15.2), nine of them over forty words, and a dialogue ratio of
**0.01** against 0.29 and 0.31 either side of it. A thousand words with one line of speech in it
is the shape of a scene narrated rather than played out — §1a.3 item 6's *"summarising instead
of dramatising"* — and it is the crisis beat, which is where a book can least afford it. Nothing
here says the scene is bad; what the panel says is where to look, which is what a panel is for.

**No comparator, and this is the gap the numbers sit in.** `platform_priors.panel` was frozen
under §104 against RoyalRoad *listings*, and no census of this market's *chapters* exists. So
18.5 number tokens per thousand and 2.3 em dashes per thousand are descriptions of one book
with nothing to be high or low against. The one prior figure in the repository — our own
chapters' median em-dash rate of **11.78 per 1k** — puts this book at a fifth of it, and every
input changed at once, so that is two books and not a treatment.

## 5. What this found about the machinery

Six things, in the order they cost time:

1. **The listing loop had no caller.** Eleven measured rounds ran from scratch scripts; the
   artifact could not be produced by the system. §139.1.
2. **The drafter had no writer.** `make_plan_selector` could not pass a dossier, so every scene
   this project has ever produced was written by nobody. This book is the first that was not.
3. **An Architect that corrects itself blocked every scene** (§3.1.1), and `dismiss` could not
   clear it. Fixed at `world accept`; validated here on the real thing — 377 proposals, 376
   accepted, exactly one left proposed, and it was the redeclaration.
4. **The agent probes a write-only interface, and both seeds did it.** The fix is
   `world vocabulary` carrying each predicate's shape, not a rule telling it not to.
5. **A seed is one draw.** Two runs of one prompt gave one world with an eleven-rung chain and
   one with none, and one with a declared protagonist and one without. Nothing reads
   `world check` and decides to run again; a person did.
6. **`print` is cp1252 on this host**, and it killed a sixteen-minute agent run at the last
   line. `_say` is the operator surface's half of `_write_document`'s rule.

### 5.1 The readership on chapter one

`litharness readers --scene scene-1`: **4 of 4 carried on**, and the caveat is §134's and is not
optional — continuation has returned 13/16, 15/16, 15/16, 16/16 and 16/16 across four earlier
rounds, so a full house is where the ceiling already was and is reported as a distribution
landing there rather than as a result.

What the four *said* is the part with information in it, because it is specific enough to be
wrong. All four named the same thing as the reason — the hand's tradeoff being on the page
already (*"can't hold a match or lift a patient"*) — and one named the withholding as the
opposite of the failure §136 measured: *"the one thing it withholds is withheld from me the same
way it's withheld from the queue, not because I'm expected to already know it."* That is
`house.CLARITY`'s corrected clause read back by a reader who had not seen it.

At the time of this pilot, the steering pool's hopes went onto the store and the now-retired
`planner.direction_for` path carried them into the **next** chapter drafted on this branch. The
rows remain evidence from the historical run, but current planning does not read them directly;
see `reader-architecture-program.md` for the qualified intervention boundary. Twice over, four
readers asked for the same two things:
that the hand's list of things it cannot do keeps deciding outcomes, and that literacy — Dan
being the only man who can read the arch — is the progression axis rather than the hand.

### 5.2 What is still owed

The handoff's task 2 — the same listings screened without their titles — is **not answered**, and
cannot be with the eight it names, which are gone. The arm is now a flag
(`--no-title-to-readers`) so both sides run from one code path; it needs a fresh set of listings
a side, which is one `listing` loop per listing and the reason it was not run here.


## 6. Settled, 2026-08-28: what landed after the status line stopped being true

The line above said RUNNING for three days after the run finished. What it was waiting on has
happened, and one thing has happened that the run could not have anticipated.

**The book exists.** `serial8.db` holds all six scenes with prose — 4,988 to 5,122 characters
each — drafted between 18:17 and 19:06 on 2026-08-25, with six scene summaries and 377 state
records behind them. `book-library/copy-costs-a-hand/` carries the three chapters, the listing,
the reading copies and two cover sets. §3.1.1's *"no scene can be drafted"* was a fact about
`serial7.db` and about that hour, and it is not a fact about this pilot's output.

**The tool fix §3.1 asked for is live.** It named the fix that removes the reason to probe:
`world vocabulary` listing predicates without saying what shape each takes. `application/world.py`
now gives every predicate its argument shape in the vocabulary itself — `world_rule` takes
`--value`, `consequence` takes `--object`, `costs` takes either, and so on down the list. The
clause telling an agent not to probe was refused, as §127 and §138 say it should have been; what
shipped is the missing information.

**`_say` landed** (`src/litharness/cli.py`), which is §5's operator-surface half.

**The steering path this book was written under is retired.** §2.1's traceable clause-by-clause
revision remains the historical evidence it always was, and the *"steered book leaves §61's
measurement set for good"* consequence in §0 is unchanged and permanent. What changed is that no
production path now sends raw appetite text back to a writer at all; `plan/reader-architecture-program.md`
holds the qualified-intervention boundary that replaced it.

**And the operator has read it.** On 2026-08-28 the operator called *Copy Costs A Hand* and
*Patch Notes For Earth* *"old generations"* they had *"already reviewed"*, which is why the fifth
operator read targets a fresh book (`plan/handoff-operator-read-5.md`'s correction block, and
`plan/serial-pilot-11.md`). That is a fact about what this book has already been used for, not a
verdict on it: no read of it was ever recorded as a `reader-read-*.md`, so whatever the operator
noticed while reading is a defect harvest that was never harvested. Recovering it later is
legitimate; inventing what it would have said is not.

**What §5.2 still owes is still owed.** The title-blind screen has its flag
(`--no-title-to-readers`) and has never been run, for the reason given there: it needs a fresh
set of listings a side. Nothing since has drawn them.
