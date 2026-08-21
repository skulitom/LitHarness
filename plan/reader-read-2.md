# The second human read: Serial Pilot 1, chapter 1

**Status: DEFECT HARVEST, 2026-08-21.** The operator read the pilot and named five prose
defects. Recorded in the shape the first read's were, because a named defect from a human read
is one of only two ways an axis enters the registry — and all three axes the system measures
today came from one read of one book (`plan/reader-judge-loop.md` §2.1).

The operator's words are quoted and not paraphrased. The analysis under each is ours.

## The five

**1. The opening does not persuade.** *"The initial hook is too weak and doesn't persuade me
(the starting sentence) to continue reading."* And on the sentence itself: *"'Weigh Street took
its light late.' that doesn't make much sense i see what you are trying to say but it doesn't
read correct, it's not a good hook."*

The first sentence commits the book to geography and light. It is a *setting* opener where the
premise offers a *situation* one — a man who will die in two days, in a trade about to become
literal. The construction is also a personification that has to be unpacked before it parses
("the street received sunlight late"), which is a cost paid on the sentence a reader decides on.

**2. Nothing happens.** *"Not much seems to be happening, just looking and observing things."*
Chapter 1's first page is: the light, the porters, the chalked fee schedule, Marta counting the
float. The first action a character takes that changes anything is a customer arriving out of
turn, and the forgery — the thing the chapter is *for* — comes later still.

**3. Too many names, too early.** *"Too many names right at the start."* Counted, the first
page carries nine proper nouns: Weigh Street, the Corvessa assay house, Marta, Vance, the
Kelling ledger, Hesk Turrow, Bellow and Sons, the Vessil workshop, and the crown-and-hook mark.

**4. Words reaching for effect.** *"words tended to be more complex then they should have been,
as if trying to seem smart 'assay house door'??"* The named example is a three-noun stack where
"the door" would carry it. The register is doing work the sentence did not ask for.

**5. Phrases that do not mean anything.** Two, quoted:
- *"as though setting down a sleeping bird"* — a simile whose vehicle is stranger than its
  tenor. Setting down a ring is ordinary; setting down a sleeping bird is not an action most
  readers have a picture of, so the comparison explains the familiar with the unfamiliar.
- *"the hook's barb a shade blunt but blunt in the right way"* — self-cancelling, and then
  glossed correctly by the very next clause ("worn rather than badly cut"), which is the phrase
  it should have been.

## Why the directives did not catch them

> **Correction, 2026-08-21, after the craft arm.** The paragraph below originally said the tone
> note "was decomposed into locked constraints, and sat in every packet". **The second half was
> false, and it is the more important fact.** `plans.constraints_of` selects on `item.locked`,
> and the narrative planner's model — never told what the flag does — returned `locked: false`
> for every constraint it minted from the tone note. Measured on both Serial Pilot runs: the
> drafting prompt carried only the four verbatim-lane constraints, and not one word of "close
> third person", "dry, exact", "dramatize rather than summarize", "scenes end on movement or
> cost" or "avoid rule-of-three flourishes" ever reached a scene. The plan showed them.
> `litharness plans` reported them. They shaped nothing. Fixed in `narrative_planner.py`: a
> constraint a person directed is locked by construction, the mirror of the rule that already
> denied the lock to a machine.
>
> The analysis below stands but splits in two. Defects **1** and **3** are still genuine gaps —
> nothing in any directive addressed openings or name density. Defects **2**, **4** and **5**
> are now something worse than a gap: the tone note *did* address them, and the prose never saw
> it.

This is the part worth keeping. **None of these is disobedience.** The tone note reached the
plan and was decomposed into constraints: *"Voice: dry, exact, quietly funny. Prefer concrete
specifics to abstraction"*, *"Dramatize rather than summarize"*, *"Scenes end on movement or on
cost"*.

Read against the defects, three things follow.

- **Nothing in the direction is about a beginning.** Every constraint governs the whole of a
  scene or its ending. "Scenes end on movement or cost" has no counterpart for how one opens, so
  a scene that opens on weather violates nothing.
- **"Concrete specifics over abstraction" actively rewards defects 3 and 4.** A chalked fee
  schedule, a workshop name, a maker's mark and a street name are all concrete specifics. The
  constraint asked for texture and got texture; nothing bounded how much arrives before a
  reader has a reason to want it.
- **Nothing governs diction at the phrase level.** "Dry, exact" is a register, not a rule about
  similes or noun stacks, and defect 5 is two sentences that are dry and exact and still mean
  nothing.

So the remedy is not a firmer tone note. It is direction about **openings**, a **budget** on
what may be introduced before something happens, and a **phrase-level prohibition** — three
things the current eight directives do not express at all.

## Candidate counters

Nominations, not admissions. The registry's rail is an operator act over a measured
distribution, and none of these has one yet.

| defect | candidate counter | measurable? |
|---|---|---|
| 3, names too early | proper nouns introduced in the first 300 words | yes, deterministically |
| 4, noun stacks | three-noun compounds per 1k words | yes, with a POS tagger |
| 2, observing not acting | ratio of clauses whose subject is the viewpoint character acting, in the opening | partly; needs a parse |
| 1, weak opening | none — "does this make me read on" is the grab criterion itself, not a counter | no |
| 5, empty phrases | none obvious; a simile whose vehicle is rarer than its tenor is a corpus-frequency question | maybe |

Defect 1 is the important one to *not* turn into a counter. It is the thing §97's grab criterion
exists to name, and a proxy for it would be the shallow metric §1a.1 warns against — easy
because it is shallow.
