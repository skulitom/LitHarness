# Serial Pilot 21 — the first draw shown the shelf, with a story-shaped brief and no reviser

**Status: PROTOCOL, 2026-09-02, written before the listing call.** The first book drawn after
stage-0 §196: the listing writer is shown the anchors' blurbs and the scene writer is shown two
anchor openings as *how this shelf sounds* (`--exemplars book-library`, order *The Primal
Hunter* then *Defiance of the Fall*), the reviser is off, the brief is a story rather than a
list, and everything §195 shipped is still live (the opening beats, `--person first`, the
re-signed listing clause). Writer `marsh`, the same as pilot 19, so that pilot 19 is the
nearest description to read this one against — and they are two draws, never a treatment
effect (`serial-pilot-7.md` §0).

## 0. What this is, and what it is not

A description of one draw under a reversed rail. Read 15 is the readout that decided the
reversal and the operator's next read is the readout of this; the panel is void for the
question (§195.5) and is not asked. The coordinator's gate before the seed is §183's checklist
plus one new item: the leak gate's row on every accepted scene, which says whether any run of
eight words came from an exemplar (it refuses the draft if one did, so an accepted scene's row
reads clean by construction, and the row is what proves the gate ran).

## 1. The draw, as it was set up

- **Writer:** `marsh`. **Person:** first. **Shape:** six scenes, two per chapter.
- **Brief** (`runs/pilots/pilot21/brief.txt`): pilot 19's situation retold as a story with a
  turn and a want — Owen, twenty-three, the walked-out degree, nights at the depot, the dead
  fighting game; the Monday message and the sheet; the line nobody else has; the first thing
  through the floor moving like an opponent he has beaten a thousand times; off nights for
  good, and a ladder he is already ahead on. Read 15's first item was the listing as a list of
  facts, and the cause was the brief's shape; this is the fix at the brief.
- **Exemplars:** `book-library/PrimalHunter`, `book-library/DefianceOfTheFall` (the shelf's
  `exemplars.json` names the order), 1,630 and 1,563 words, both blurbs on disk; shelf digest
  `dd832792c5476b1a`.
- **Reviser:** off (the default since §196).

```bash
uv run litharness --database runs/pilots/databases/serial21.db init
uv run litharness --database runs/pilots/databases/serial21.db \
    --roster-database C:/DEV/LitHarness/runs/roster/roster.db --chapter-scenes 2 \
    --exemplars book-library \
    listing --writer marsh --brief-file runs/pilots/pilot21/brief.txt \
    --scenes 6 --person first --out runs/pilots/pilot21
# the gate, then the pilot-15b recipe with --exemplars book-library on the seed and the ticks
```

## 2. What is refused before the draw

Pilot 19 §2, and one more: **no exemplar text is read into any record this file cites.** The
job payload names the exemplars by digest; the frozen prompt holds their text inside a
gitignored store and nowhere else.

## 3. The listing

**Drawn 2026-09-02 in one draw, with the two anchors' blurbs shown above the brief**: *The
Line Nobody Else Has*, 121 words, three paragraphs, first person,
`runs/pilots/pilot21/listing.txt`; serial21.db, book `d5635294`.

**It has the shape read 15 asked for and the anchors' blurbs have.** Paragraph one is the life
before in one sentence (a year short of a chemistry degree, nights at a depot, the dead
fighting game). Paragraph two is the turn: the System on every screen, a sheet and a class to
pick, the line nobody else's carries, the first monster out of the floor moving like an
opponent beaten a thousand times. Paragraph three is the want and the promise: off nights for
good, and a ladder that starts where he already stands. Pilot 19's listing was six sentences
of fact in one paragraph; this is a situation, a turn and a want. Two draws, and the brief
moved between them as much as the blurbs did, so this is a description of what the brief and
the blurbs together produced and not an effect of either.

**The coordinator's gate, §183's checklist — PASS.** The sheet and the class to pick; the
line nobody else has, and what it does; System, sheet, class, monster, ladder in plain words;
the life before as one sentence; first person; no machinery words, no dashes, no title inside
the listing; the want in the last line.

**The browsing pool: 3 of 4 would start it, 1 passed.** The pass is `magic_m`'s typicality
item again, the same reader that passed on pilot 19 (*I've read that opening a dozen times*);
the three starts name plain nouns, a small edge that has to be earned, and a blurb that says
what he wants *instead of being coy about it*.

**One residual, recorded and not acted on.** The title is built on an absence — *Nobody Else*
— which is the family read 15 named in the prose (*nobody bowls in*) and §179's clause
forbids at the reviser, and the listing carries it once more (*a line I have not found on
anybody else's*). The title loop carries no such rule and the title passed its two frozen
predicates; the anchors' titles are noun phrases. Left standing, because the readout of this
draw is the operator's read and a title the coordinator retitled by hand would be the
coordinator's.

## 4. The seed and the chapter

**The seed** (one draw, clean check, accepted without `--force`, 189 records): *the System* as
the sole issuer of Rank and of seven kept grants — Push, Hold, Step, Mend, and behind the
fork Break, Sift, Bind — each bought once with a night of dead sleep and never spent back; a
printed line of the ladder's word and the seven grants and nothing else; the fork (*the
Class*: Hand opens Break, Wall opens Bind, Eye opens Sift) at Entrant, the second rung, so the
choice is reached inside chapter one; Danny Poole's edge as a line under the columns that
reads a move a beat early, which works on a riser and a fist and not on a person deciding
whether to lie; Cormack Freight pricing a day shift at a rung and a Registry that cannot read
a sheet; and a rival already a Contender.

**The system completed on the first draw after §196's two seed-side sentences**: seven grants
inside the bound, the sheet's columns the system's own, `world check` clean with no gap, the
scale and digest minted at `world accept`, and canon holding scheduled snapshots at rank two
and at Push one. Pilots 19 and 20 both drew a system the completion refused; this is the first
pilot whose progression beats speak the system's own vocabulary and whose fork can print as
the `[OFFER]` line where it opens.

**Chapter 1 (draw 1):** two scenes, 1,970 words, both accepted on the first attempt, the
leak gate on both decisions reading *no run of 8 words is shared with any exemplar shown*,
the frozen request carrying both anchor chapters and the prohibition, and the beat in the
system's own vocabulary for the first time (*Push moves here*). Published to
`book-library/the-line-nobody-else-has/`.

## 5. The loop, as the operator set it

**The operator, 2026-09-02, verbatim:** *"once you put all the necessary fixes and regenerate
it, could you hand read again? I feel like you understand the flaws much better than previous
models and you go much more indepth on your analysis than me. Then we could repeat the loop."*

So the loop from here, on this settled listing unless a read finds the listing itself at
fault: the coordinator hand-reads each draw's chapter 1 in depth against the two anchors,
routes every defect (enforcement, gap, structural), makes the fix that is structural rather
than a clause wherever one exists, redraws under the same listing, and reads again. Each draw
is recorded below as §5.N with its read, its routing, and the fix that followed; the
operator reads at milestones and his read is what the loop answers to. **The coordinator's
read is a diagnostic and never evidence** (§95, and the standing frame of every read file):
an LLM reading prose is what this project measures with, and this one steers but certifies
nothing. Two draws under one listing are two draws (`serial-pilot-7.md` §0).

**Amended after read 16 (2026-09-02), on the operator's direction — verbatim:** *"can you also
hand read to examine how to make it more interesting and engaging? including more creative
world and story"*. From draw 4 on every read has a second half, on fixed questions: what
makes a reader want chapter 2 (a win paid early, a clock, a rival, a choice the reader would
argue about); how far the book promises to go and whether the reader can feel the scale; what
is mysterious about the system and whether anybody in the book wonders about it; what the
twist on the standard shape is; whether there is a laugh; and what the person wants beyond
the next rung. The operator's example premise for the second question — a system-apocalypse
Earth, a botched portal spell survived on stats for years, emergence on the far side of the
universe under a competing system with some old abilities kept — is recorded in the track's
next entry as the shape the pipeline cannot yet invent or print, and the concept stage and
the two-system sheet are the fixes it names.

### 5.1 Draw 1 — the coordinator's read

**What moved, and it is the largest move any draw has made.** The system speaks. The Monday
message arrives as five lines the reader reads with Danny (*READ TO THE END. THIS WILL NOT
CLEAR UNTIL YOU HAVE.*), the sheet shows a column of seven grants at zero with three greyed
words under them, and the offers arrive as the system's own text — *PUSH, offered, because
you reached for it with the body you have and it did not come up. Price: one night's sleep.*
— which is the best invention in any draw so far and is *Defiance*'s shape (the boxes with a
manner) transferred without a word of its text (the leak gate says so). The progression is
felt: he pays a night on the concrete for a one, the pallet comes up in the morning, and in
scene two the one moves the thing and does not put it down, so HOLD is offered on his knees.
The chapter ends inside the fight, on an offer unanswered, with the count *Ankles. Ankles.
Up.* running. The sheet reaches the page at word 250, not 850. Ade is a real foil (*Fifty-one
years old. That's what they wrote out of me.*). The voice is looser than pilots 19 and 20
(*said something out loud that my mother would not have enjoyed*; *the machine's idea of
tea*). Read beside *The Primal Hunter*'s chapter one, this is the more eventful chapter and
the faster one.

**What is still the machine's, counted where a count exists.**

1. **Definition by absence, worse than before**: 18 *nobody / nothing / never / no one*
   tokens in 1,970 words — *Nobody has ever paid me for that. Nobody has ever asked.*; *Not
   cracked. Not lifted. Not so much as swept different.*; *holding his own nothing*; *nothing
   at all, no dreams, none*; *watching and nobody watching, both at once*; *not damaged, and I
   was*; *not a number and not a door*. The one clause against this family (§179) lived on
   the reviser, and the reviser is off, so nothing reaches it now. It did not reach it when
   it was on either (§187).
2. **The same simile shape, seven times**: *the way you do when you already know*, *the way a
   wall comes up*, *the way a bright window stays in your eyes*, *the way you don't tell
   anybody the combo*, *the way water goes out of a sink*, *the way you know a sneeze is
   coming*, *the way you take a pallet*. Unchanged from pilots 19 and 20; neither anchor does
   this once.
3. **The turned last line and the narrator announcing his moves, fewer and lighter**: *which
   turned out to be an amount you could measure and be embarrassed by*; *That is not bravery,
   it is that the lane is the lane*; *I did not fall so much as arrive on the concrete*; *I
   want to say I weighed it. What I actually thought about was…*; *That is what I remember
   first: not the thing, but…*; *That is the thing.* About eight where pilots 19 and 20 had
   one per paragraph.
4. **Still nobody exclaims.** Zero exclamation marks. Zac's panic did not transfer; Danny is
   controlled and dry, which fits a night-shift man and is still cooler than the shelf.
5. **A markdown leak**: *\*\*Nobody\*\** in the prose, the emphasis markers printed as
   asterisks in the pastable chapter. Mechanical; no rule or strip reaches it.

**Routing.** Item 5 is structural and cheap: the em-dash strip's neighbour, a deterministic
strip of emphasis and heading markup before the ladder, counted like the marks. Items 1 to 4
are the register the exemplars have moved partly and the clauses never moved; the one lever
still unpulled on them is the shelf's size — draw 1 showed two openings, and the shelf holds
four. Draw 2 therefore changes two things, recorded as two: the markup strip, and
`--exemplars-limit 3` (adding *Randidly Ghosthound*, 2,033 words). Two draws, never a treatment
effect; the read decides whether the register moved again.

### 5.2 Draw 2 — the coordinator's read

**Run through the settled-listing harness** (`runs/ab/pilot21-loop/draw2/`, arm.json: the same
listing byte for byte, `marsh`, first person, `--exemplars-limit=3`, the markup strip live),
a fresh world — *the Bracket*, a Grade ladder, Wind as the resource, Guard, Reach, Read,
Counter and Stagger as the grants, a four-way class (Brawler, Runner, Warden, Wild) with a
deadline — completed at accept with no gap; 1,925 words in two scenes, both accepted first
time, the leak gate clean on both, `markup_removed` on the record.

**What moved.** This one is more *story* than draw 1: Danny reads the thing's three moves
before it makes them and calls them for Kesh; he could step out of the overhand and takes it
for her instead, and Guard goes from nothing to one *"and it had cost me exactly one thing:
standing still for a hit I could have avoided"* — a choice with a price, on the page; Kesh
finishes it with the bay bar and her Grade goes to two while his stays at one, because the
Bracket counts the finish and not the calling, which is the system's rule arriving as an
injustice the reader feels; and the Standing Office inspector walks up the ramp with a
licence application whose every field must be read out in front of an officer, which is the
chapter's unanswered offer and a real threat to the one line he has not told anyone. The
simile shape fell from seven to two; absences from eighteen to thirteen; the sheet is opened
by shutting his eyes, which is a nice diegetic touch; the boss-pattern line (*like a boss
pattern in a game with no more coins in it*) is the genre's own idiom.

**What did not move, and it is now two families.**

1. **The narrator's honesty move**: *That is the only way I can put it.* — *I want to be
   honest about that, because it has mattered since.* — *That is what people get wrong
   afterwards.* — *I would like to say I thought about the fairness of that. What I actually
   thought…* Draw 1 had *I want to say I weighed it. What I actually thought about was…* — the
   same construction, verbatim in shape, two draws running. The narrator keeps stepping out
   of the scene to vouch for his own account.
2. **Definition by what a thing is not**, thirteen: *Not a crack. That is what people get
   wrong afterwards. The steel did not break, it did not buckle* — *It had no face I could
   describe to an inspector. It did not bleed, later, when it should have.* — *Not through a
   hole.* — *It did not stagger and it did not stumble; it simply had nowhere in its list* —
   *Every field. Not the head of it. Every field.* Some of these are earned (the sheet's
   zeros); the habit is the model's.
3. Zero exclamation marks, again. Kesh breathes out through her teeth; nobody shouts.

The system's own voice thinned this draw (*There would be a sheet, it said. Only I could read
mine.* — reported, where draw 1 printed it), which is variance between two draws and not a
regression to fix.

**Routing.** Items 1 and 2 are the narrator's *stance* — a man vouching for his account from
outside it — and no exemplar has displaced it in two draws, because a dossier says what its
writer loves and nothing about who is talking. Read 15 §4.3 named the lever: write the stance
into who the writer is. Draw 3 therefore changes one thing: the writer, a hand-declared
recruit whose dossier is the man telling it to a mate at the bar the same night, checked legal
against the roster's rail. Same listing, same shelf, same three exemplars, strip live. One
change; two draws; the read decides.

### 5.3 Draw 3 — the coordinator's read, and the milestone

**Run through the harness** (`runs/ab/pilot21-loop/draw3/`): the same listing byte for byte,
writer `barlow` (the stance dossier, hand-declared and accepted 2026-09-02), first person,
three exemplars, the strip live; a fresh world (the Registry and its assessors, Grade with
Rated as the first word that pays, Wind as the resource, Hard Hands, Carry, Long Sight, Read
Ahead, Set Up, Weak Point as the grants) completed at accept with no gap; 1,969 words, both
scenes accepted first time, the leak gate clean on both, on the shelf at
`book-library/the-line-nobody-else-has--0ffc8699/`.

**The voice moved, and it moved the way the dossier said.** *Right, so the depot.* — *Bleep,
chute, bleep, chute.* — *I used to tell people that as a joke about myself. I had the timing of
it down.* — *"Rated," he says. "Tuesday." / "Get lost."* — *"Since about nine seconds ago,
Ollie."* — *He was made up for me. That is the horrible part.* — *my heart going like a rabbit*
— *like a lad reading a shopping list* — and a refrain the writer made and kept: *the world
ends and the vans still come at four.* This is a person telling it. Ollie, who climbs faster
because he does not ask what a column costs, and Marek, who told the Registry twice he will
not be climbing, thanks, are alive in three lines each. The story is the best of the three
draws: the monster taped off in bays six and seven for two nights with the word TWO-STEP
standing over it, which to everyone else is a name and to Danny is a move list; the racking
collapse that is not the monster; Carry going from nothing to one while he holds a tonne of
somebody's Christmas off a girl's leg; the assessor reading sheets aloud with demonstrations;
Danny skipping his one secret column in a flat voice and the sweat going down his back; going
in *on the stop* with the cage; and the assessor who saw him go early, will put him at Rated
tonight, cannot file a sheet she cannot account for, and turns a figure round on the table
that is more than he makes in a year of nights. The chapter ends on that figure.

**What is still the machine's, and it is now small enough to name in one line each.**

1. **The confessional aside**, three times: *I want to be honest about this bit* — *I want to
   be straight with you about what I did* — *I want it on record that I was terrified*. Two
   writers, three draws, one construction; in this voice it reads as character more than
   scaffolding, and it is still the construction the model reaches for whenever a first-person
   narrator has done something.
2. **Definition by what a thing is not**, fifteen tokens, of which about half are earned by the
   sheet's noughts and the fight (*I did not go on the step, I went on the stop*) and half are
   the tic (*That is the bit nobody tells you*; *Not a pause, a stop*; *the noise it made I will
   not be describing to you*).
3. **Tense drift**: scene two slips into the present for stretches (*Marek's roaring*; *she
   says*; *The shift's screaming*), which the bar-telling stance licenses and the anchors never
   do; a reader may hear it as looseness rather than voice.
4. Zero exclamation marks, still; the narration is loud now (*Marek's roaring*) and the
   narrator himself never is.

Simile shape: one. Interior verbs: two. Absent: the turned last line as a habit (the few that
remain are the refrain and character), the proof-of-seeing, the narrator announcing his moves
beyond item 1.

**The milestone.** Three draws under one listing: draw 1 gave the system its voice, draw 2
gave the chapter its story, draw 3 gave the narrator his. The two families that remain are
named above and no structural lever the coordinator can pull tonight reaches them without a
clause. This is the draw to put in front of the operator beside *The Primal Hunter*, with draw
1 for contrast. Read 16 is his.

### 5.4 Draw 4 — after read 16

Read 16 (`plan/reader-read-16.md`): *"overall greatly improved"*, and three items that are one
family — the narrator's British depot idiom and trade compression (*he is days*, *on a double*,
*made up*, *three shifts a day have walked flat*), which a reader from anywhere else cannot
parse and the anchors never use. The cause is draw 3's dossier: a mate at the bar shares the
narrator's words. Draw 4 changes the listener and nothing else: writer `carver`, whose dossier
is barlow's stance told to a mate from the other side of the world who reads these books and
has never set foot in a depot. Same listing, shelf, three exemplars, strip.

*(the read, after the chapter)*
