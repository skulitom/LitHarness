# Volume pilot 1 — *The Order Stays Open*: the first whole-volume draw, read and debugged

Status: **arc 1 of 4 drafted and read (24 scenes, 25,901 words); the draw stopped at the arc-2 outline** (2026-09-07). The run folder `runs/volume1/` (gitignored) holds the store, every command, the driver's log and this record's sources; the reading copy is on the shelf at `book-library/the-order-stays-open/`. This file is the coordinator's read and is a diagnostic (§95): the operator's read is what it answers to.

## Part 1 — the read, chapter by chapter

DEFECT HARVEST. Descriptions, not scores; n is one; nothing here becomes a prompt, directive,
finding or plan item (stage-0 §97.1). The coordinator's read is a diagnostic; the operator's
read is what it answers to.

Recipe: concept `--scenes 24` (tanaka, third person, empty brief, three exemplars), listing,
`tools/volume_run.py --arcs 4 --chapter-scenes 2 --arc-chapters 12 --grow-every 1`.
Interventions are in INTERVENTIONS.md. Attempt 2's seed: 358 records, twelve-rung Mark
ladder with seven grants (Credit two a Mark; Grace, Reading, Overlay, Invigilation,
Deferment, Statement), a fork at Mark Three (The Second Paper), the Marginalia's Gloss
ladder after the turn with Holdings carrying over; protagonist Wes Halloran.

## Pipeline findings (before any chapter)

1. **The accept preview read an unfinished world.** Attempt 1's seed put `mark_one` in the
   numeric rank column; `world check`/`world accept` previewed clean, accepted, and the same
   check named two faults a minute later. Cause: the preview ran before accept minted the
   drawn system's scale, and until then the rung column reads as an ordinal. Fixed
   (`application/world.as_accepted`), regression test added.
2. **A 24-scene concept overflows its output bound.** The first concept draw came back
   unparsed at 9,093 tokens against the 4,000 bound; the second parsed. Every earlier
   pilot drew `--scenes 6`. The bound should scale with the arc, or the shape should be
   shorter.
3. **Readback quirk the Architect had to work around.** With `wes entity_role protagonist`,
   `world cast` reports `protagonist: null` and `world abilities` omits him, because both
   views look for the `cast` role and `entity_role` is a single slot (the Architect's own
   note in the seed output; already in memory as a `world` gap).
4. **`architect grow` reads one scene, not a chapter.** `render_grow_request` is handed the
   latest drafted scene's prose under the label "the chapter just drafted"; at two scenes a
   chapter the Architect never sees the chapter's first scene.

5. **The Architect keys its schedule in two spaces and one of them is unplaceable.** Of the
   seed's keyed records, 23 carry digit keys (`0110`…`0900`: five `type=change` notices,
   seven `disclosed_to` reveals, four `stands_at`, `chose`, snapshots) and are omitted from
   every scene's packet as "not in the scene key space this cutoff reads"; 10 carry
   `s000005`-style scene keys and slice correctly. The vocabulary itself says both: `type`
   asks for "a scene key like s3", `chose` for "zero-padded digits". Consequence for a
   volume: every scheduled notice and reveal the Architect declared in digits never reaches
   a writer, so the disclosure schedule is decoration (stage-0 §165's class, now with the
   cause in the vocabulary text).
6. **The seed's own schedule contradicts itself.** The scheduled snapshots run rank 3 at
   s9, rank 1 with Overlay at s10, rank 4 at s14, rank 1 at s15 — the s10 line is a Mark
   the book has not lost yet. The audit's fact timeline flags it as a value returning; the
   page has not reached it, so it is the schedule's defect, not the prose's.
7. **A debt ledger that opens eight debts in two scenes, all due at the arc's end.** The
   summariser opened eight promises beside the concept's four, every one hinted "by the
   end" and so due at s24; the ledger will report them overdue together at the arc's close
   whether or not the page pays them, and their subjects are the summariser's phrasing
   (`wes's_first_numbered_status_line`), not the book's.

## Chapter reads

### Chapter 1 (scenes 1–2, 2,023 words) — read 19:05 UTC

**What works.** The arrival is the concept's and it is staged: the doors saying RANK ONE
down the row, the kettle saying it, then the plant in the cage saying RANK FOUR and "the
silence after that had a shape to it". The order is one concrete sentence (SAY ALOUD THE
RANK OF THE NEAREST MADE THING TO YOU) and the reader can do the arithmetic Marisol does.
The first use is an act: the bar sits at empty and nothing comes; the lamp reads him "the
way a finger goes down a column" and does not find the line; he crosses a corridor during
a count and makes a nurse say two words with her hair gone white in the light. The status
line prints Wes's own vocabulary, once per scene. The hook is the listing's: bottom of the
board, and holding.

**What a reader will hit.**
- *Head count.* Scene 1 puts six people in corridor B on the monitor; scene 2 finds five
  standing, Amara kneeling and Denny down — seven. Nobody arrived between.
- *The line printed with nothing moved.* Scene 2 closes on the same status line scene 1
  printed, every number the same; the genre prints on a move (§233).
- *The system's name is off the page.* Listing and world say invigilator; both scenes say
  lamp, light, thing. Fine as Wes's ignorance, but the word has to arrive.
- *Tells.* Located-habit similes at three or four a thousand words ("the way a thing does
  when it is measured off you", "the way a finger goes down a column", "the way you do at a
  door you are already through"), absence in narration ("nothing was coming out of him",
  "There was nothing slow in them"), the turned last line on most paragraphs. Counter
  reported 21 excess shapes on scene 1, observation only.
- *"He did not say them" / "Yours has run out"* — the exception is shown twice and
  explained never, which is right for chapter 1; the debt is open.

**Pipeline.** Scene 1: one attempt, 69 s, $0.47, 41k tokens, all gates PASS; 23 packet
omissions (finding 5). Scene 2 similar. The two scenes together are a Royal Road chapter
at 2,023 words against the market's 2,053 median.

### Chapter 2 (scenes 3–4, 1,952 words) — read 19:12 UTC

**What works.** The corridor is worked person by person and each one arrives with a voice
and a rule: Ruthanne copying orders onto a receipt roll because "it won't say a thing
twice" (ASKED AND ANSWERED is on the page, the Proctorate's manner exactly as the concept
had it), Reyes reading the order like a quote he has been handed ("Somebody sat down and
picked made thing over object … Something that writes can be argued with"), Tobias
answering "Rank nine" to prove the count cares that you said something, Grigor half a
second late at everything. The kill is the yard's: unit fourteen said Rank Two, a door
"doesn't have to be anywhere or decide anything", and the rod comes away "with no more
argument than a pen out of a cup". The status line printed with nothing moved is turned
into the chapter's point ("the score had not been asked").

**What a reader will hit.**
- *Every door said Rank One.* Scene 1 has every roll-door in the yard saying "the same two
  words" and only the plant saying something else; scene 4's unit fourteen said Rank Two.
  Defensible (Wes was at the desk, fourteen is inside corridor B) but the sentence in scene
  1 is absolute.
- *Head counts again.* "It wiped the first one off five panels" then "six of them were
  standing" with Grigor arrived; with Wes that is seven. The concept's "six survivors"
  excludes Wes, and the prose does not say so.
- *The status line printed four times with no number moved* (twice a chapter). Scene 4's
  is earned by the sentence after it; scene 3's is furniture.
- *Ruthanne's "flat court voice"* — her trade is implied and never said.
- *Tells* at the same rate as chapter 1: five located-habit similes, two "like X going into
  water" shapes, absence in narration. Reads well anyway at popcorn speed.

**Pipeline.** Scenes 3 and 4: one attempt each, 94 s and 71 s. Chapter at 1,952 words.
First Architect grow runs after this chapter (cadence 2).

### First grow (after chapter 2) — 367 s, 25 records proposed, 35 accepted

The Architect declared the law scene 4 stated (`rule_unasked`: the Proctorate pays for an
answer to an order it hung and for nothing else), the door and the receipt roll as carriers,
Reyes's read and Ruthanne's ledger as claims the reader holds, and one new question. Its own
report names finding 5 from the inside: "my three scene-4 reader disclosures landed in
schedule space, so no scene cutoff reads them as already made … a writer working from
disclosure state alone could have Wes take the rod twice." `domain/worlds.py` documents this
as the deliberate cheap side of an asymmetry: nothing in the pipeline writes a `disclosed_to`
record at a scene position, so an Architect's reveals stay hidden for the whole book until
"a disclosure channel somebody decides on" exists. On a 24-scene arc that is the difference
between a mystery paid on schedule and one the writer is never told is due. Also from the
grow: the crew stands on the Marginalia's Gloss ladder from the seed, "the word never
printed in four scenes", and Ruthanne was moved to its second rung at a schedule key with
no notice line. `world check` now lists these records under `unplaceable` (28 after this
grow).

### Chapter 3 (scenes 5–6, 2,130 words) — read 19:20 UTC

**What works.** The numbers go up on the page and the reader can check them: Mark 1 with
Credit 2, the first free reading (READING ENTERED ON YOUR RECORD. NO CREDIT TAKEN), the rod
going cold after one use, "nearest is a thing you can arrange" and Rank Two said with a palm
on the door, MARK TWO with "the figure in his corner reading four", one Credit spent on
Grace, CREDIT REMAINING, THREE. Two Credit a Mark, minus one, is the line printed. The
Second Paper is offered at the third Mark with its three ways and their prices, and
Ruthanne's second column ("what it said to somebody else") is the book inventing its own
instrument. Wes's "I've walked round all night with a price I hadn't named yet" is the
listing's hook paid.

**What a reader will hit.**
- *Reading vanishes.* Scene 5 prints Reading 1; scene 6 says "the word READING had stood an
  hour ago. The line was ruled and empty again" and prints Reading 0; the Second Paper text
  says he "had had [it] for an hour and did not have now". The world declares Reading a
  held grant and the grow's own note says `q_rod_kept` guarantees it survives the strike;
  the outline for scene 23 depends on Reading being the one column the strike cannot take.
  The page has now established the opposite. The audit's status census names it
  (`decreases`: Reading 1 -> 0, scene 5 -> 6).
- *"In three days' time somebody was going to hand him a choice of three doors"* — nothing
  on the page or the panel says three days.
- *Rank Two at unit fourteen.* The door under his hand is the dropped door in corridor B;
  the yard's doors said Rank One on the first night, fourteen said Two; fine, but the reader
  has to remember chapter 2's one sentence to follow the arithmetic.
- *Tells* as before, five located-habit similes and the absence family in the rod
  paragraph ("No seam, no switch, nothing a hand was meant to find").

**Pipeline.** Scenes 5 and 6 on the first attempt, 34 s and 190 s. The page's scene-5 and
scene-6 snapshots match the seed's scheduled `s000005`/`s000006` lines exactly and share
their record ids, so `state` shows them as `given`, not `read`: the schedule is what the
writer was handed and what it printed. The schedule's `s000010` line (Mark 1, Credit 2,
Overlay 1, after Mark 3 at `s000009`) will be handed to scene 10 the same way — finding 6
is now a prediction: watch scene 10.

### Chapter 4 (scenes 7–8, 2,170 words) — read 19:30 UTC

**What works.** The plant is a room, not a monster: "A one holding a four. It's a garden
trellis round a bear", the cold taking the warmth out of the air "between one breath and
the next", the mesh going "to a grip", Amara hauling him out with her coat doubled round his
forearms. The stack rule is demonstrated the way a LitRPG reader wants it — three palms on a
Rank One door inside one second, three corners go up by three, "It pays the order. Not the
person" — and it has a cost the page shows (the dent in unit nine) and a consequence that
walks in (counting out loud brings a lamp). Grigor's "Rank six … in the voice of a man
reading a bus timetable at gunpoint" pays Tobias's test from chapter 2. Two more lamps on
the road at the close.

**What a reader will hit.**
- *Head counts, third time.* "Six green rectangles up the length of corridor B" then "five
  people in a corridor shouting a countdown" then "five people breathing in it" with seven
  present. Nobody left.
- *Refrains.* "at a reader's pace, four legs, waist high" is now in scenes 2, 4 and 8; "in
  the same flat voice it had used on the people" in 6 and 8; Grigor arrives "with his coat
  still half on and his panel swimming" in 5 and 8; "the way a match goes into water" in 4
  and 8. A reader on a phone notices the second time. The audit's refrain census lists
  57 word runs said in more than one scene after eight scenes.
- *Reading confirmed gone* ("Wes did not have Reading any more; the rod … had gone cold at
  the office desk and stayed cold"): chapter 3's transient reading of a held grant is now
  the book's rule.
- *"His order from the seven o'clock wave"* — the wave was "at some minute nobody caught";
  seven o'clock arrives only here.

**Pipeline.** Both scenes first attempt, 70 s and 87 s. Status line unmoved twice, which
is right (nothing of his moved). Second grow runs after this chapter.

### Second grow (after chapter 4) — 517 s, 31 proposed, 27 accepted

The Architect turned the chapter's furniture into rules with second-order costs
(`rule_overpay`: answers past what a fixture is ranked to carry go into the fixture, the
dent; `rule_heard`: a lamp turns toward an answer spoken aloud; `rule_count`;
`rule_one_board`: a door and a man on the same twelve rungs, which closes a hole the page had
been standing on since chapter 2). It read the new `unplaceable` list in `world check` and
said so twice: it added nothing to it, and "the page is running on things the record says the
reader has not been told, and that gap widens with each chapter". Two things to watch:
- It opened `q_row_d` with the answer "the grey box is a Rank Nine and is the housing the
  roll was opened out of", reveal scene 10. The page has the plant say RANK FOUR in three
  chapters and the outline has it stay a Four. A hidden answer that contradicts the page's
  stated number is the world drifting from the book, not the book from the world; keyed in
  schedule space it will never reach a writer, so it is decoration unless a later grow
  builds on it.
- Four consequence records were left proposed because a later declaration filled the slot;
  every later `world accept` will report them again.

### Chapter 5 (scenes 9–10, 2,087 words) — read 19:40 UTC

**The scene-10 prediction.** The schedule's `s000010` line (Mark 1, Credit 2, Grace 0,
Overlay 1) reached the page as numbers and not as rank: the writer printed Mark 3 | Credit 2
| Grace 0 | Overlay 1 and invented a reason for Grace going to nothing ("there was no longer
anything in the world it was the key to"). So the sheet the writer is handed drives the
numbers, the rank held, and a contradiction in the schedule became a paragraph of
explanation on the page. The Credit arithmetic is right throughout: Mark 3 pays two (five),
one on Grace (four), Overlay costs two (two).

**What works.** Wes reads the plant as an engineer ("Coils ice. Something that pulls that
hard out of a room has to shed what it takes") and the cycle is the way in; Reyes holds the
gate and is burned; "Take two off me and put them on him" gets ASKED AND ANSWERED and
Ruthanne's "It has never once gone across" is the rule the reader feels. The Second Paper
is a real choice with keys and prices, sat once, and the shutting of the other two ways
zeroes the Grace he bought for them. Marisol's "Which paper did you sit" before names.
Seven panels counted correctly at last.

**What a reader will hit.**
- *Scene 10 opens by saying scene 9's close again*, nearly verbatim ("The panel had gone
  blank in front of his face at the end of row D … Behind the mesh the plant knocked once
  and started taking the room back"). Inside one chapter that reads as a stutter. The
  audit's new `seams` view names it (19 shared words, same chapter) and finds a smaller one
  at 2 -> 3.
- *Reading, three ways.* Column 0 since chapter 3, "ENTERED" against the Reader Paper,
  Ruthanne's "Entered, Mr Halloran. Not lent." The book has now made the vanished column a
  plot point; whether a reader follows it depends on remembering one line from chapter 3.
- *"Since Thursday"* is the first weekday named; chapter 1 said "an ordinary weeknight".
- *Refrains:* "at a reader's pace" again, "without weather" (chapter 3's "no weather in it").

**Pipeline.** Scenes 9 and 10 first attempt, 46 s and 134 s. Grace fell 2 -> 0 and Credit
4 -> 2 between the scenes; both are purchases the page explains, and the census lists them
as falls without judging.

### Chapter 6 (scenes 11–12, 2,275 words) — read 19:48 UTC

**What works.** Sowden arrives as a rule with a jacket on: a Mark Four who lets his orders
die in the middle of the lot because "It's the only thing four's good for. I can stand
where I like", and his "Asked and answered" grin is the first thing that frightens Wes.
The tag man's death is staged exactly as chapter 1's (the plain look, the hand up "not
fast"), and it lights the rod, which the book set up two chapters ago. The reading pays
twice: SOWDEN, C. SECURE THE PLANT ROOM … AND HAND IT UP BY FIRST LIGHT, and Ruthanne
turning back three feet of paper to the Mark Two list — "Nothing under a six can put a
man's name on an order" — so the reader learns the rule from the ledger the book has been
keeping. The second reading on the plant (two orders overlaid, DO NOT ANSWER UNTIL YOU ARE
ASKED BY NAME, STATE WHO OPENED—) empties the rod mid-sentence. The plant printed four bars:
the page held its Four against the Architect's hidden Nine.

**What a reader will hit.**
- *"For the first time in four days."* The timeline has moved from Thursday night to a
  fourth day without a morning or a night the reader saw; chapter 5's dusk to chapter 6's
  "the hour the shift used to change" is one cut.
- *Refrains, now unmissable:* "like a match into water" (scenes 4, 8, 12), "at a reader's
  pace" (2, 3, 4, 8, 11, 12), "the way a page shows through a page" (5, 12), "not fast" at
  both deaths, Grigor "half a beat late" every entrance. The census after twelve scenes will
  say how many.
- *Grigor at the gate "talked to anybody who stopped"* is asserted as the leak that told
  Sowden about Wes; nothing earlier showed him talking to anyone outside the crew.
- *Reyes "could take one end of a thing with his left hand and nothing at all with his
  right"* — consistent with chapter 5's burn; the first cost the book keeps.

**Pipeline.** Scenes 11 and 12 first attempt. Status line printed once, unmoved. This is
the arc's midpoint; the third grow runs after it.

### Third grow (after chapter 6) — 536 s, 37 proposed, 33 accepted

The Architect recorded what the chapter paid out (Sowden as a Mark Four with a crew, the
plant at Mark Four with two dead orders) and turned Ruthanne's deductions into rules (a name
on an order needs Mark Six; a thing under a gag answers only a question carrying its name,
which it names as the grant `query`). Two things to watch:
- It declared `ch_rod_twice` taking Wes's **Reading to 2** with a System line ("READING 2.
  SECOND READING TAKEN INSIDE ONE NIGHT. INSTRUMENT EMPTY."). The page has printed Reading
  0 since chapter 3 and built a plot point on the empty column. If the change is keyed in
  scene space the next scene is asked to print a line the book has spent three chapters
  contradicting; if in schedule space it never arrives. Either way the world and the page
  now disagree about one column. Watch scene 13's line.
- It invented a Mark Six, Owen Merrit, who "opened a roll that was not his while the plant
  watched", as the answer to why a six spends a four — a name the outline does not know.
  The Architect's own note: "There is no retraction, so if either is wrong they will need
  declaring over rather than removing."
- Same four consequence proposals reported again as left proposed.
  Checked: `ch_rod_twice` is keyed `0130`, schedule space, so no scene is asked to print
  the Reading 2 line; the page keeps its 0 and the world its 2. `unplaceable` is 33 after
  three grows (28 after one): the Architect reads the list, names the problem in its own
  report, and keeps keying in the space the vocabulary tells it to.

### Chapter 7 (scenes 13–14, 2,229 words) — read 19:58 UTC

**What works.** The plant kill is the book's best set piece and it is built out of rules
the reader already holds: three orders banked one under the other (Overlay deepened to 2
for every point he had, "Broke, and I can hold three"), the turn learned by standing in the
room, Reyes counting out loud on purpose because "I know what it brings", "Four. One. Two."
with a palm on the housing, the first payment a rung, the second Credit, the third with
nowhere to go on Wes — "It went into the plant." The lamp that came to the count goes out
with it, the rod warms, the plant still says RANK FOUR "smaller", and Amara's hands are the
price kept from scene to scene. Mark Four printed; "The lamps still turn. They do not
stop." "None of them had been asked" closes the chapter on the crew.

**What a reader will hit.**
- *Overlay becomes a consumable, exactly as Reading did.* He paid every Credit to deepen
  Overlay to 2 in scene 13; after the kill the line reads Overlay 0 "ruled flat with a
  price printed beside it, the same price it had cost the first time". The seed's scheduled
  `s000014` line says overlay=0, credit=4, rank=4, and that is the line printed to the
  digit, with the page inventing a reason. Two held grants have now been spent like charges
  because the schedule's numbers, not the world's edges, are what the writer is handed.
  The audit's status census names both falls (Overlay 2 -> 0; Reading 1 -> 0).
- *Refrains:* "like a match gone into water" for the fourth time, "brightness enough to
  make a page" for the fifth, "the way the inside of a mouth is warm", "at their reader's
  pace". These are now the book's most recognisable sentences.
- *The second order's text* appears only in scene 14 (SAY ALOUD THE RANK OF THE ROW YOU
  ARE STANDING IN); scene 13 gave it as "the second came down an hour later" with no words.
- *"All week"* — the timeline has reached roughly day five without a named day since Thursday.

**Pipeline.** Both scenes first attempt. The world now holds Reading at 2 (third grow) and
the page at 0; the world holds Overlay at 1 or 2 and the page at 0. The sheet reader will
record the page's 0s at `s000014` merged into the seed's given row.

### Chapter 8 (scenes 15–16, 2,170 words) — read 20:05 UTC

**What works.** The turn lands as the concept wrote it and better: ANSWERABLE UNTIL SIX is
the first hour the Proctorate ever gave, Wes spends a held order on a question ("If a held
order can go off in my hands I want to be standing in front of it when it does"),
handwriting crosses everything he can see, STRUCK FROM THE ROLL, seven panels go out at
once, and the margin copies his sheet "the way a clerk copies a thing over before filing
what it came from" — Marks to one, Grace and Overlay ruled flat, Reading kept because it
was never sold. The debt due by scene 16 is paid on scene 16: Denny Sarr is filed, his
bar "a hair off full" and moving, "Sarr, D." in the corner; "We were told nothing and we
filled it in ourselves. That is what wrong is." The blank line under the note is the
second system asking without asking.

**What a reader will hit.**
- *Reading, again.* Column 0 for nine scenes, then 1 after the strike with the explanation
  that it was never charged for. It works as a reveal only if the reader took chapter 5's
  "ENTERED" line seriously; otherwise it reads as a number coming back.
- *"Every panel in this yard went dark except two men's down in row A"* — Sowden's crew was
  six at the gate in chapter 6; two remain without the page saying where four went.
- *Refrains:* "the way a page shows through a page" (third), "bright enough to make a page of
  the whole row", "since Thursday" ×4 in one chapter.

**Pipeline — finding 8, the largest so far.** Only scenes 1–4 wrote state from the prose.
The outline's schedule, promoted to canon by the driver's first `world accept`, both drove
the sheet (every printed line from scene 5 on equals the schedule's line where one exists)
and silenced extraction (its records carried no registry version). Repaired on the store
and fixed in code (see INTERVENTIONS.md). The audit's sheet-versus-page view, run at scene
16 with a scene-space cutoff, lists 20 mismatches: the world's edges hold Credit 2, Grace 0
and Overlay 0 throughout while the page bought and spent them; the world holds Mark 4 at
scenes 15–16 where the page is struck to Mark 1; Reading 0 against the page's 1.

### Fourth grow (after chapter 8) — 277 s, 16 proposed, 12 accepted

Recorded the correction the chapter made (`claim_kill` falsified, four people now believe
`q_denny`), opened two questions with reveal scenes (18, 20), no new rules. Its watch list:
"marginalia, gloss, ink, objection, concession and countersign have never reached the page
in sixteen scenes" and the Gloss ladder with the whole crew at rung one is "the largest
unpaid debt in the world". The same four consequence proposals reported again.

### Chapter 9 (scenes 17–18, 2,304 words) — read 20:12 UTC

**What works.** Sowden's takeover is a rule read aloud ("Nobody's hanging an order on a
name that isn't there to hang it on. Watch") and Wes's answer is the yard's arithmetic
again: give him everything but the room a Four will not walk into. The shutter coming down
on Grigor's roll and Grigor outside it, then Wes walking through a live count with a dark
panel ("its light went over him the way a light goes over a wall") and cashing the first
holding on the fence — "Four days old and it paid like it was hung this morning" — is the
concept's carry-over paid on the page, with the margin's "We honour it. Paid at the terms
as written." Sowden pricing what he saw closes the chapter on the next threat.

**What a reader will hit.**
- *Reading flips again.* Chapter 8 kept Reading 1 because "it never charged me for that";
  chapter 9 prints Reading 0 with "Reading had gone with the rod's last light in corridor
  B". The column has now read 0, 1, 0, 1, 0 across chapters 3, 5, 8 and 9 with a different
  rule each time. This is the book's one running continuity fault, and the census names
  every fall.
- *Sowden's crew is six, then two, then five.* Nobody left on the page.
- *"He's paid me twice"* — Sowden hanging orders on Grigor is consistent with the
  Invigilator Paper he sat (chapter 6); the page never says that is why he can.

**Pipeline.** Extraction resumed after the repair: scenes 17 and 18 wrote their snapshots
from the prose (six read records now) and the sheet reader wrote its first `can_do` edge
"read off the status line". Both scenes first attempt.

### Chapter 10 (scenes 19–20, 2,263 words) — read 20:20 UTC

**What works.** The concept's first debt is paid on the scene it was due: the dying plant
speaks the charter line ("NO CANDIDATE WHOSE ANSWER IS OWED TO A ROLL OPENED BEFORE THIS
ONE MAY BE CALLED AT A BAR … HALLORAN, W. OWED TO A ROLL OPENED BEFORE WE CAME TO THIS
PLACE … I HAVE STOOD OVER THIS WORKED BEFORE") and Reyes reads it: "it isn't that you're
exempt … You're spoken for … That's a clerk's line, and clerks close lines." Then the fight
is the dropout's, not the System's: the receiver, the seized stop valve, the bolt cutter
through the wheel, the fan bank pushing a knee-high white down a lane the width of a van,
Sowden walking out last "at the pace of a man reading". "It costs less than it did an hour
ago. That's what we paid."

**What a reader will hit.**
- *"A second that had cost Wes two rungs he no longer had"* — the plant kill paid one rung
  (three to four); the strike took three. Neither is two.
- *"The last week of the year"* is the first the reader hears of December, ten chapters in.
- *Refrains:* "the way a car door goes when somebody leans on it from the inside" (chapter
  7 again), "bright enough to make a page" (sixth), "the way heat comes off a fire, wrong
  side out".
- Status line printed twice unmoved; the second is a beat ("One point in a corner, and
  nothing left on Earth that would sell him anything for it").

**Pipeline.** Both scenes first attempt; the fifth grow runs after this chapter and is the
first under the accept fix.

### Fifth grow (after chapter 10) — 551 s, 35 proposed, 30 accepted

The first grow under the accept fix (nothing planned was pending, so nothing to leave).
The Architect **grew the system**: a new grant, Carriage, "the count of orders standing
open off the panel", entering at scene 21 with its own System line, and it says why — Wes
holds Overlay at zero, so the page's three hanging orders were a contradiction the sheet
could not hold. `world check`'s `grown` confirms the sheet carries the new column. Two
things to watch: scene 21 is now asked to print a column the first twenty scenes never
had (§231's shape, this time by design), and the reveal keys it wrote this time are scene
keys ("read back as reached") — the `unplaceable` list taught it the format. It also
found the other half of finding 5 from the inside: "every reader disclosure declared
before today sits on a schedule-space key … Those old keys cannot be moved — the record is
blind to position, so a corrected key is dropped as already on record." There is no
re-keying path. The invented Mark Six (Merrit) now drives a hidden answer for scene 25,
past this arc's end; the arc-2 outline reads the state, so he may arrive by the world's
door rather than the plan's. Five consequence/manifestation proposals left behind.

### Chapter 11 (scenes 21–22, 2,194 words) — read 20:30 UTC

**What works.** The grown column arrives on the page exactly as the fifth grow declared it
(`[PROCTORATE] CARRIAGE ENTERED ON YOUR RECORD. CARRIAGE, THREE. NO CREDIT TAKEN.`) and the
book makes it mean something at once: "It counts what you walked away from … the only
line on you that rises without you buying it." The Mark Six clause paid to a dark name
(SUPPLY STANDS AT THIS ADDRESS UNTIL DISCHARGED) turns the yard into a place Sowden's men
come to trade, which is the outline's scene 21 to the letter. Then the Proctor-General
walks in — the concept's debt due by scene 22, paid at scene 22 — names all seven, puts
them back on the roll ("That's not mercy." "No."), hangs one order on every panel on the
road, and stands there. Tobias answering "Sowden" and the order coming straight back
("That's not it doing that. That's him") is the best rule-demonstration since chapter 2.

**What a reader will hit.**
- *Mark 4 again.* Since the strike the line has read Mark 1; here "Four white bars where
  there had been one" and Ruthanne's "this morning you are Mark Four because you said
  four". The world's edges never recorded the strike (no `stands_at` was read from the
  page's Mark 1), so the writer was handed Mark 4 and wrote a reason. The sheet-versus-page
  view named this at scenes 15–20 before the page rationalised it.
- *Carriage 3 with "two sentences left on that fence"*, explained as counting what he walked
  away from; then Carriage 4 when a new order is hung. Consistent, but the reader has to
  accept a column that counts the past.
- *The status line gained a column mid-book* (§231's shape by design); the census will list
  two column sets from here on.
- *"Four days ago that man told us to walk out the gate"* — that was this morning (chapter
  9); the strike was four days ago by the book's own clock.

**Pipeline.** Both scenes first attempt. The grown grant printed on schedule because the
Architect keyed it in scene space; the same Architect could not re-key its earlier
reveals.

### Between chapters 11 and 12 — the run parked (finding 9) and a ledger miss (finding 10)

- **9.** Scene 23 was refused three times and parked: the page's status line, now
  carrying Carriage, and the outline's milestone at `s000023`, promoted to canon by the
  first grow's accept, were two values at one position. Finding 8's other half. Repaired by
  demoting the planner's ten records (INTERVENTIONS.md) and resumed.
- **10.** The ledger reports `the_mark_nine_proctor-general` overdue at scene 23: opened at
  scene 1, due by 22, still open. The Proctor-General walked in on the page at scene 22 and
  named all seven. The summariser did not report the payment, so a debt the page paid on
  its due scene is carried as unpaid; the audit's promise view will show it as overdue at
  the arc's end, and the outline for arc 2 will read the ledger and may plan to pay it
  again.

### Chapter 12 (scenes 23–24, 2,140 words) — read 20:45 UTC — arc 1 closes

**What works.** Reinstatement as confiscation without the word: the panel comes back blank,
"Four rungs down to one", Reading kept because "There is no line to take it back under".
One order on six panels with Wes's name in it, refused out loud by the three who owe him
most, and Tobias dying of the thing he proved in chapter 2 — a wrong answer is free, a slow
one is not ("half a second after"), the lamp's hand up "not fast, the way you do at a door
you are already through" from chapter 1. The rod's free reading on a Mark Nine prints the
roll: names ruled through, a rung beside each, "SARR, D. Ruled through. Against a two at
this address" — the hidden answer the seed dated to scene 24, paid at scene 24. The
Marginalia's first question ("Is what he read true?"), seven answers, "You are at the first
of six … the only names on it", and the Proctor-General's exit line. The arc ends on the
next debt: Denny, filed, with his bar going.

**What a reader will hit.**
- *Seven.* "We hear seven" after Tobias is down: Marisol, Reyes, Ruthanne, Amara, Grigor,
  the depot man and Wes. The count is right; whether the book meant the depot man to take
  Tobias's place is not said.
- *Refrains in one chapter:* "the way a page shows through a page" twice, "at a reader's
  pace", "since Thursday" three times, "which was where Grigor stood in things".
- *Reading 1 with Carriage 4 on a blank sheet* — consistent with chapter 11, and the
  reader has now been asked to hold four different rules for one column across the arc.

**Arc 1 as a whole (24 scenes, ~25,800 words).** The story makes sense read end to end:
the exception is shown, used, priced and explained; the four concept debts are paid on or
before their scenes (rod by 12, filed by 16, exception by 19, Mark Nine by 22); the turn
arrives at the arc's two-thirds and the second system speaks at the close. What a reader
carries as faults: the Reading column's five reversals, Mark 4 reappearing after the
strike, head counts, a vague clock (Thursday, "four days", "a week", "the last week of the
year"), and a handful of similes said in nearly every chapter.

### The readership at the arc's end (scene 24, four simulated readers, 127 s)

Four of four carried on against a named rival; every one named the roll reveal ("twelve
Marks total, every rung is a dead man's vacancy, Denny's is the one Wes is standing in")
as the reason, two named the blank line, one named that "every rule got earned … none of
it was ever explained at me". What they expect next is the slanted hand acting on the
answer; what they hope for is Carriage as a real ladder, asking-by-name as a learnable
technique used on Denny, the twelve places holding as a hard constraint, and Amara getting
one good thing. Recorded beside the read, never a score (stage-0 §95); the arc-2 outline
was drawn from the state and not from this.

### Arc 1, read by six lenses on Opus (47 agents, 18 min) — HARVEST-arc1.md

The six readers raised 51 findings; 40 went to a skeptic each; four survived refutation,
two of them story-breaking and both missed by my chapter-by-chapter read:
- **The held orders are spent twice** (plot, chapters 6–11). The book's only currency is
  counted out loud (four, three, two), and the count reuses a sentence already cashed:
  chapter 9 spends NAME THE LOWEST RANKED THING YOU HAVE TOUCHED TODAY for one Credit,
  chapter 10 lists it among the three still held, and chapter 11 has Wes re-answer the
  chapter-7 "highest ranked thing within reach" order, palm on the same housing, to buy
  Carriage and Mark Four. The four are never itemised at the moment they are claimed.
- **Sowden's tag man is culled in chapter 6 and back on his feet in 9 and 10** (cast).
  Chapter 6 fuses "tag man" and "the man with the marker" into one person and kills him;
  chapter 9 has both alive; chapter 10 lets the frost take him and then calls the object on
  the ground "the dead man's marker" without a death.
- **Sowden's crew arrives twice** (chapters 5–6: three strangers at dusk, then six through
  the gate at shift change followed by an afternoon).
- **A first-light event is "last night" eleven paragraphs later** (chapter 9).
World-rules, debts and reader lenses produced no survivor: the Reading-column objection
and the Mark-reveal objection were both refuted as distinctions the book states in
dialogue before it needs them. Seventeen findings were carried unverified (the ones a
skeptic would have been worth: the two-rungs arithmetic, the stopwatch in two hands, the
margin holding three orders then two with none spent, the corridor-B headcount). The
harvest's "what the next arc must carry" list is the continuation brief a planner would
want and the arc-2 outline did not see it.


## Part 2 — interventions and named confounds

The whole-volume draw of *The Order Stays Open* (writer tanaka, concept `--scenes 24`, third
person, empty brief, three exemplars, `tools/volume_run.py`, 2026-09-07). Everything a
person did to the run, so the read can tell the pipeline's behaviour from the operator's.

## Attempt 1 (18:06–18:19 UTC) — stopped by hand after the seed

- The Architect's seed (625 s) put a rung id (`mark_one`, `mark_three`) in the numeric
  `rank` column of both of `wes`'s status snapshots. `world check` and `world accept`
  previewed clean and accepted 304 of 305 proposals; the same `world check` a minute later
  named two snapshot faults.
- Cause (reproduced on a scratch copy): the preview ran over the proposals *before* accept
  minted the drawn system's `magnitude_scale`/`system_digest`, and until a drawn system has
  its scale its rung column reads as an ordinal that may hold a rung id. Fixed in
  `application/world.py` (`as_accepted`: both previews now read the world as accept will
  carry it), regression test in `tests/test_seed_completion_bounds.py`.
- A hand redeclare could not replace accepted canon and `--force` would have put two
  snapshots at one position (a blocking contradiction on every scene), so the driver was
  killed by PID during its first tick (the arc outline). The store is kept as
  `attempt1/serial.db`; spend ≈ $6 (seed) + one outline call.
- The driver gained `--seed-attempts`, the documented `world declare` repair from the
  fault's own message, and a post-accept `world check` that stops the run if an accepted
  world still reads faulty.

## Attempt 2 — fresh store under the fixed preview

Same concept, listing, writer, person and shelf; a fresh store; the pipeline at the
working tree recorded in `run.json` (`tree_at_start`). The seed is a fresh draw, so the
world differs from attempt 1's; nothing here is a pair.

## Cadence (18:55 UTC, before scene 1 landed)

The seed took 845 s and the arc outline 592 s. A grow after every chapter would put twelve
Architect calls of that order beside each arc's twenty-four scene drafts, roughly doubling
the wall clock of a four-arc run, so `control.json` sets `grow_every` to 2 (a grow after
every second chapter, six per arc). The drafting loop writes the page's `stands_at` and
`can_do` edges itself (stage-0 §236); the grow's reconciliation runs at half cadence.

## Working tree during attempt 2 (named confounds)

The pipeline is re-imported at every step, so edits to `src/` while the run is live change
what later steps run. Edits made during attempt 2, all additive and none on the drafting
path: `application/world.py` gained `unplaceable_positions` and `check()` gained an
`unplaceable` key (read by `world check` after each grow, reported and not gated);
`application/bookaudit.py` and `tools/volume_run.py` are not imported by any tick. The
`as_accepted` preview fix landed before attempt 2 started. `run.json` records the tree at
start and at finish.

## Store repair at 19:57 UTC, after chapter 8 (scene 16)

`state` showed four records read from the prose in sixteen scenes, all from scenes 1–4. Cause,
reproduced on the live store: the arc outline mints its progression schedule (`milestone-*`
snapshots and `standing-*` edges) as PROPOSED records with no `predicate_registry_version`;
the driver's `world accept` after the first grow promoted them beside the Architect's
proposals; `extraction.has_story_vocabulary` then read ten canon keyed records with a
foreign version and abstained for every later scene (the Book Zero silence its docstring
describes). Two consequences the chapters showed: the writer was handed the schedule as
canon (the sheet followed the schedule's numbers to the digit, including its self-
contradictions), and nothing the page did with Credit, Grace, Overlay or the strike reached
the world's edges.

- Repair on the store: `runs/volume1/attempt2-before-version-repair.db` is the backup; the
  ten canon `milestone-*`/`standing-*` rows had `predicate_registry_version` set to
  `litharness.planned-position.v0` in `record_json`. Record ids do not derive from the
  version, so identities are unchanged; no event was written (there is no path for one).
  They stay canon: demoting them would hand scene 17's writer a Mark 1 line from scene 4.
- Code: `application/outline.py` now stamps the schedule with `PLANNED_POSITION_VERSION`
  (test in tests/test_outline.py); `world accept` leaves planned proposals as the
  outline's schedule and says so (test in tests/test_world_slots.py). Both landed while the
  run was live; the accept change first applies at the fifth grow.
- Extraction should resume at scene 17. `state --subject wes` read-provenance counts are the
  check.

## Extraction fix at 20:38 UTC, after chapter 11 (scene 22)

The page printed Mark 1 from scene 15 to scene 20 and no `stands_at` edge was minted, so
the world's edges kept Mark 4 and scene 21's writer was handed it ("this morning you are
Mark Four because you said four"). Cause: `_standing_from_line` skipped any rung already on
record for the subject, and the un-keyed opening standing at Mark One counts everywhere.
`domain/extraction.py` now skips only the rung the placed edges put the subject on as of
that scene (`_standing_now`); a return to a rung once held is minted at its position.
Regression test in tests/test_extraction.py; the progression gate and planner tests pass.
Live from scene 23 on; scenes 15–22 keep the record they have.

## Parked at scene 23 and resumed, 20:28–20:30 UTC

The scene-23 draft was refused three times by `state.contradiction.v1`: the page's line
(with the grown Carriage column) and the outline's canon milestone `milestone-s000023`
(without it) were two values at one position. Same root as the 19:57 repair: the
schedule had been promoted to canon. Repair: backup `attempt2-before-demotion.db`; the ten
`milestone-*`/`standing-*` records demoted to PROPOSED in the column and in `record_json`
(what the outline minted and what the fixed `world accept` would have left); finding
`f-986851591c67ffd859320b47` dismissed as a false positive; exception
`exc-8bdabd1cea055520bd8fe8ae` resolved with this note; job `beat-c1754c2275ca4d1a30443c18`
revived; driver relaunched at 20:29:53 (pid in driver.pid), resuming at 22 of 24. Cost of
the stop: three refused drafts (~$3) and eleven minutes.

Consequence for the world: the Marks the page climbed at scenes 6, 9 and 14 now stand
only in proposals; canon's placed standing for Wes is the opening Mark One, which is what
the page prints after the strike and reinstatement. From scene 23 the extraction fix
mints a standing whenever the line's rung differs from the placed edges'.

## Parked again at 20:32 UTC, converged at 20:33

After the revive, the scene-23 draft was accepted on its first attempt (all gates pass;
`why --scene scene-23` shows attempt 1 accept) and the tick still reported the job parked
with the old finding text: the job's recorded attempts read (1 retry, 1 accept, 2 park),
so the first run's attempt-2 park decision was applied again after the revived attempt 1
accepted. A second `revive` and one manual tick (the driver's exact argv) ran the
post-acceptance evaluation and left no job parked; the driver was relaunched at 20:33:39
resuming at 23 of 24. Observation, not fixed: a revived unit whose earlier attempt number
already carries a park decision can be re-parked by that stale decision after it
succeeds. Cost: one manual tick, no draft.

## Third resume, 20:36 UTC

The stale park re-applied once more after the manual tick, so the driver's probe now tells
a parked `scene_draft` whose scene is accepted at head (a row nothing claims and nothing
re-enqueues) from a park that needs a person, names it once in progress.log and carries
on. No store write was made for this: the row stays parked, marked stale in run.json.
Relaunched at 20:36:27 resuming at 23 of 24.

## Arc-2 outline timing out, 20:41–21:30 UTC

The second arc's outline job ran past `CONCEPT_TIMEOUT_SECONDS` (900 s) twice; each
timeout is a transient failure that refunds the attempt and requeues, so the driver would
have spent five fifteen-minute tries before stopping. Paused the driver during the third
attempt, raised the constant to 1800 s in `application/outline.py` (the Architect's grow
already carries 1800 s), and unpaused; the next attempt runs under the new value. The
first arc's outline took 592 s; an outline drawn against twelve chapters of state is a
call that grows with the book.


## Part 3 — the six-lens harvest (Opus, 47 agents)

DEFECT HARVEST — arc 1 — descriptions, not scores; n is one; nothing here becomes a prompt

## Plot

- **Chapters 6, 7, 9, 10, 11 — the held orders are spent twice.** Quote (ch10): "One wanted the lowest ranked thing he had touched. One wanted a made thing that had stopped working." The ledger of held orders — the book's only currency, counted out loud as four, then three, then two — lists a sentence that was cashed on the page one chapter earlier ("He took the second one down. NAME THE LOWEST RANKED THING YOU HAVE TOUCHED TODAY", ch9), and in ch11 Ruthanne identifies the remaining "names a thing" order as "Highest ranked within reach", which Wes already answered at the plant housing in ch7 and now answers again, palm on the same housing, same word, to buy Carriage and Mark Four. Skeptic's note: the ch7 "made thing that had stopped working" leg is wrong — ch8 hangs a separate, genuinely unanswered order with that wording — but the ch9 double-list and the ch11 re-answer both stand, and the four are never itemised at the moment they are claimed.

## Cast

- **Chapters 6, 9, 10 — Sowden's tag man is culled and comes back twice.** Quote (ch9): "He went through the line between the tag man and the one with the marker, close enough to knock a shoulder". Chapter 6 fuses tag man and marker man into one person ("The tag man was six doors up row A with a marker in his teeth and a tag in his fingers") and kills him under the floodlight; ch9 has them alive as two men in a count, and ch10 puts "the tag man with his marker still in his fist" at the gate, gives him a line, lets the frost take him, and then calls the object on the ground "the dead man's marker" without ever showing him die. Skeptic's note: no line anywhere introduces a replacement tag man or hands the tags on, and the arc's own softening — the culled are filed, not killed — does not put a filed man back on his feet, since Denny Sarr stays a body under a blanket.

## Time and place

- **Chapters 5, 6 — Sowden's crew arrives twice, at two hours, in two headcounts, through two entrances.** Quote (ch6): "They came in at the hour the shift used to change, six of them through the gate". Chapter 5 ends with three strangers at the mesh at dusk and Marisol asking "Which paper did you sit"; ch6 opens on the same line and the same clipboard staging with six people through the gate, then runs forward through "the shape of the whole afternoon" of clearing row C. Skeptic's note: the hour alone could be reconciled at a yard on overnight shifts, but an afternoon cannot follow a dusk arrival, and no character ever refers back to a first party of three.
- **Chapter 9 — a first-light event is called "last night" eleven paragraphs later.** Quote: "the receipt roll's twelve unwound feet still in his fist from last night". The roll unspools and goes under the closing shutter in the daylight that opens the chapter; after one scene break, continuous with the same shutter and the same men outside, those twelve feet are last night's. Skeptic's note: the second half does carry "one column that had read nothing all night read one", which only moves the error rather than fixing it — a first-light event is then yesterday morning, not last night — and the same sentence strands the paper in two places, since Ruthanne was winding it back on indoors.

## World-rules

No finding survived. Two of the biggest world-rule candidates — that Reading's column contradicts the rule that it cannot be taken back, and that the Mark ladder's climax contradicts eleven chapters of paid answers — were both refuted on the page: the book distinguishes the record entry from the rod's consumable charge, and distinguishes Credit from Mark, and it states both distinctions in dialogue before it needs them.

## Debts

No finding survived. The four named debts land at or before their due scenes.

## Reader

No finding survived at the level of contradiction. The two candidates that got closest — the closing sheet reading as a reset to chapter one, and the invigilator arriving in fixed phrasing — both fail on the text: three of nine columns differ at the close (Carriage is the arc's actual rising line), and the eleven-word invigilator formula appears exactly once, at a destruction rather than an arrival.

## Refuted

- Wes reads strangers' orders in ch2, making the rod redundant — ch2 names the back-glimpse "which is not reading", and it fails on the page; Wes has to get the order out of Ruthanne's mouth.
- Wes climbs into Denny's rung though ch8 said the place is held — the held-place clause is Wes's exemption from being called at a bar, and Denny was called at one.
- The exception's explanation postdates what it explains — the qualifying fact is the roll's opening date, not when Wes was entered on it.
- Reading reads 0 while the book says it can never be taken back — the rule is about charging back a record entry, not about the column's value; ch5 stages and answers this objection.
- The Mark reveal contradicts eleven chapters of Marks bought by answering — only Wes's Mark ever moves; everyone else gains Credit and stays at Mark One.
- Sowden proves nothing hangs on a dark panel then pays Grigor on one — Tobias's panel is absent, Grigor's is dark but present, and the narration marks the difference in the sentence before.
- Grigor is paid after being struck off — he loses his panel with the others, spends a night on Sowden's side, and returns with one; the narration flags it as the anomaly it is.
- Corridor B's six survivors shrink to four — Ch8 has eleven mouths on Ruthanne's roll; the arc never defines its crew as the complete set of corridor B.
- Four days are claimed over an unbroken chain — ch5's dusk, ch6's dark, ch7's small hours and "since Thursday" put nights on the page.
- "Four days" is stamped on intervals that cannot all be four days — the ch11 line describes a stretch of column a thumb travelled, not the record's length.
- The Marginalia's four honoured orders include spent ones — counted as orders Wes walked away from, the four are exactly right; the ch7 three are correctly absent.
- Reading is taken back in ch9 — Reading reads 0 from the end of ch3 onward; ch9 is the fifth printing of it.
- The sheet is stripped to zero twice and ends where ch1 started — ch1 reads Credit 2 / Reading 0 / no Carriage; ch12 reads Credit 0 / Reading 1 / Carriage 4.
- The invigilator arrives in the same eleven words every time — the phrasing occurs once, describing a destroyed lamp; no two arrivals share wording.
- Twelve Marks cannot seat a planet of Mark Ones — "twelve of them" counts rungs, and seven names share the bottom rung forty lines later.
- The plant's answer is ungrammatical and unremarked — it is the object-plus-participle of "I have seen this done before", and four characters react to it across half a page.
- The founding non-answer has no reason on the page — ch1 gives it an explicit because, and the kill on the monitor happens after the decision, not before.
- Sowden's plan to sell the exemption has no consequence — the next chapter puts the yard's name on every panel on Earth, hung by something high enough to print a name.
- Six are struck off for what only Wes did, unexplained — the Proctorate's own order names the relation ("STRIKE HALLORAN, W. FROM YOUR ACCOUNT") and the charter line is stated in ch10 before it is needed.
- Reading goes 1, 0, 1, 0, 1 against a rule stated twice — the column follows the rod; ch5 reads 0 and says so aloud.
- Four open orders on a panel paid to carry three — Overlay caps what hangs live and stacked; carried orders are a separate count the book names as Carriage.
- The rod's charge is stated three ways and used twice on one death — the Sowden panel and the cage are one lighting; ch7 says so twice.
- Overlay vanishes and Credit jumps at the plant kill unaccounted — same-second landings pay per mouth (established ch4), and bought columns are takeable where entered-free ones are not.
- Ruthanne says rank two for a Mark One, Wes for a Mark Two — Ruthanne is never shown being paid for that answer; her payout is a scene earlier, for a different order.
- Eleven witnesses in a yard of seven — seven is the struck-off crew, not the population; three road strangers and six depot men are on the page.
- The closing seven miscount and swap Tobias for a stranger — seven voices are countable; Tobias is culled on the page; the depot man is established across three ch11 scenes.
- Sowden vanishes after ch6-10 — ch10 is his exit scene, and his errand's consequence is stated aloud in it.
- Denny is "the whole of him" in the lamp while his body lies in unit twelve — the collision is staged deliberately, and ch12's roll settles it at the highest authority in the book.
- A week in one mouth, four days in the next — one clock in two units, inside a stated calendar week anchored to Thursday.
- A three-day forecast pays out the same day — ch5 is a later day; "since Thursday" cannot be said on Thursday.
- Four indoor corridors but outdoor rows — "the outside of row A" distinguishes a building's exterior from its interior; corridor B is entered by a fire door.
- Grigor's panel anomaly is never returned to — ch11 and ch12 both single him out on exactly that verb, "counting".
- Sowden set up to sell Wes and then gone — refuted with the ch10 rout and the chain from his named order to the man in the grey suit.
- The rod's price to use twice is never named — it is paid in two ruined hands, a lost scouting advantage, and the missing half of the sentence the finale turns on.
- Ch11 remembers the plant as only a knock — the recap's scope is the question that was asked, not the charter speech the plant volunteered.
- The plant is both ancient authority and broken chiller with no bridge — the voice is identified as the Proctorate's own, and ch6 gives the plant a panel with a standing gag order on it.

## Unverified

- Nine bars and a Proctor-General arrive with no ladder for the reader to measure them against (ch6, 11, 12).
- Chapter five replays its own last two paragraphs after the section break (ch5).
- Both of the book's biggest turns are proved from a document the reader never saw (ch3, 6, 11).
- The core survival rule is stated two opposite ways in consecutive chapters (ch2, 3, 4).
- The Second Paper's three branches arrive as a paragraph read off a paper roll (ch3, 5).
- The reading-rod's price is stated, immediately broken, and never named (ch3, 6, 7, 12).
- Seven grants are bought and argued over; one of them ever fires (ch3, 5, 7, 8).
- Grigor confirms a payment he is standing there unable to see, then changes sides on it (ch9).
- Chapter 6 replays chapter 5's closing beat with different numbers and a different hour (ch5, 6).
- The plant kill is twice described as costing two rungs when it paid one and the strike-off cost three (ch7, 10, 11).
- The wave that gives everyone the same sentence is flagged and then dropped (ch2, 4, 5).
- Wes credits the cage's three words to the reading he spent on Sowden (ch6, 7, 10).
- The stopwatch is in Marisol's hand and Reyes's hand inside the same scene (ch4, 7, 8, 10).
- Corridor B holds six survivors on arrival and four for the rest of the book (ch1, 2).
- Grigor's first paid order is his third (ch3, 6).
- The margin holds three orders in chapter 11 and two at the end of chapter 12, with none spent between (ch11, 12).
- Reyes's terms for giving up the Invigilator Paper are never settled (ch5, 7, 12).

## What works

- The three-orders-in-one-second kill is assembled entirely from rules laid earlier: the chapter 4 dent in unit nine, two priced purchases of Overlay, Ruthanne's roll supplying the plant's rank, and Reyes's crouched guess at the lamps'. The payment with nowhere to land going into the fixture is a consequence, not a rescue.
- Tobias Ng is planted, used and killed on his own terms. He establishes in chapter 2 that the system does not check whether you are right, the crew exploits it in chapter 5, and chapter 12 kills him on the one variable he never tested — a slow answer rather than a wrong one — in chapter 1's exact staging.
- Physical consequences persist and constrain later scenes: Reyes cannot press the stopwatch crown, Amara cannot do her own buttons, Wes can point at things and not hold them, which is why he needs someone else at every gate and valve for the rest of the arc.
- Ruthanne's receipt roll turns the system's never-repeats property into a source of tension, and the hour she rules a second column for what it said to somebody else is the cleanest character-and-mechanic beat in the arc; the roll is what wins the arguments in chapters 5, 6 and 11.
- The strike-off's stake is economic and concrete — "everything anybody eats now comes off an order somebody answered" — which is what makes the crate, the shutter, Grigor's defection and the trade at the fence read as pressure rather than incident.

## What the next arc must carry

- Denny Sarr is filed, not dead: his bar is still running inside a dead lamp, Amara knows it, and the arc's last exchange makes retrieving him the stated next objective.
- The exception is unfinished. The plant supplied the mechanism (Wes's answers are owed to a roll opened before the Proctorate reached Earth) but not the why-him; the closing instruction is to ask who the answers are owed to and whether their terms have been read.
- Two open orders remain in the margin, honoured at Proctorate terms, plus Carriage at four — the line that rises without being bought and is printed against a rung Wes does not hold.
- The Marginalia's ladder: six rungs, seven names on the bottom one, its own seven grants and its own fork, none of it yet exercised on the page.
- The Proctor-General walked off the property conceding jurisdiction but not reach ("That is not the same as somewhere I cannot reach"), with a standing supply clause honoured at the address behind him.
- Who opened the roll at Kestrel Self Storage, and under whose name, is still unanswered — Tobias died giving a false answer to it, and Wes holds only three words of the order.
- The reading-rod holds one charge per death within reach and is currently warm off Tobias; whatever it is spent on next is the only instrument for reading another authority's paperwork.
- Sowden is routed and off the property but not resolved: his crew traded at the fence, heard the roll read aloud, and left; his named order came from something high enough to print a name, which the arc never identifies.
- Grigor's panel behaved differently from the other six through the strike and the restoration, and he has never said what he saw in it.
- The Mark ladder is now known to be dead men's vacancies, twelve rungs deep, with a Mark Nine standing on nine ruled-through names — a fact the yard can act on and the Proctorate has not denied.
- Sowden's tag man and the corridor-B headcount need a decision before the continuation reuses either: as written, both are ambiguous about who is alive.