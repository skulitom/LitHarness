# Serial pilot 25 — a second writer's concept in the third person, under the batched pass

Status: **running** (2026-09-02, late). Records to be read beside plan/serial-pilot-24.md §7,
which is the last chapter the operator has (draw3 of *The Ratchet Counts Down*), and against
the reads' families in plan/reader-read-17.md to -19.md. Nothing here is evidence; the
operator's read is what it answers to. Harness folder `runs/ab/pilot25/` (gitignored), its
EXPERIMENT.md written before the arm.

## 0. What this is, and what it is not

One writer, `tanaka` (the tutorial-dungeon, builds-and-broken-skills dossier), chosen because
a second writer is a second premise family (plan/reader-read-5.md §4.3 measured one premise per
writer under an empty brief) and pilot 24's writer `marsh` has now drawn the first-day arrival four times.
Empty brief, the operator's position since read 19 (third person), three exemplars, the strip
live, reviser off, the tells pass in its third version (stage-0 §199.3: one request per family
per scene) running on a chapter for the first time, the readership step last. **n is one.**
One draw is one description; it is not a treatment effect, a win or a bar
(`serial-pilot-15b.md` §0), and no pair is read against pilot 24, since the writer, the
concept, the listing and the pass version all differ.

## 1. The concept, as drawn

Three calls to draw it: the first two came back unparsed and the command exited on one line
with nothing kept, which is why `litharness concept` now spends one of its bounded draws on an
unparsed answer and prints the answer's length against the bound and its first and last words
(tests in `tests/test_concept.py`). The third parsed on its first attempt, so the fix did not
fire and the cause of the two failures is unrecorded. Settled at `runs/pilots/pilot25/concept.json`
(gitignored); recorded here verbatim:

> Who they were the day before: A 26-year-old physics PhD student who paid his rent marking
> first-year problem sets and invigilating undergraduate exams.
>
> What they alone have, from the first chapter: He alone is shown a marking scheme before the
> marking happens — the itemised list of what the Invigilation will award in the encounter in
> front of him, and how many marks for each item; every other person alive is shown only the
> result afterwards.
>
> The first time it works, in chapter one: Twenty seconds after the light in the sports hall
> changes, standing at the head of aisle C during a first-year mechanics exam, he sees a scheme
> hanging at eye height over desk 114 — CANDIDATES ASSESSED ON: MOVEMENT FROM THE SEAT (1) /
> CONTACT WITH THE INSTRUMENT (2) / REMOVAL OF A FELLOW CANDIDATE FROM THE HALL (6) — while
> three hundred and twelve students see only a countdown, and he works out that sitting still
> is being marked zero.
>
> What they want, in their own words: To submit before the deadline, take the postdoc, and be
> first name on a paper instead of the man at the front of the hall telling other people when
> to stop writing.
>
> The system, The Invigilation. How it shows itself: Exam-board register: clipped, impersonal,
> always the passive and always third person — it says 'the candidate', never 'you'. It
> announces time remaining, states results, and will not clarify a scheme it has already
> published. It wants something: answers not on its own scheme, which it harvests to revise
> the paper for the next cohort, so a candidate who solves an encounter in an unlisted way is
> rewarded once and then written out.
>
> What it looks like: Assessed ground goes the flat grey-green of a sports hall in exam season,
> lit wet-chalk pale from no source; text stands in thin black serif capitals at eye height
> where the desks would be, hanging in air; a bell that is felt in the teeth marks the start
> and the end.
>
> How far up it goes: 10 steps. Where the strongest person anyone has heard of stands: Band
> Seven — the Invigilation's public board carries exactly one, a prior-cohort candidate listed
> only as ROOKE; the best human on day one is a Band Two, and the fittings for Eight, Nine and
> Ten are displayed as empty outfits nobody has ever filled.
>
> What a step up buys: Power, with respect as its shadow. Each band issues a fitting — Band
> One is a grey coat, Band Two the gloves that go with it — and the fitting is where that
> band's abilities live. It is worn, public, and cannot be counterfeited, so everyone reads
> your rank off your clothes before you open your mouth.
>
> What kills people here, in the first days: Chaperones — two-and-a-half-metre jointed figures
> in grey with nothing where a face goes, one assigned to each assessed space. A Chaperone
> withdraws any candidate who spends sixty seconds attempting no item on the scheme.
> Withdrawal is death and leaves a chalk outline on the floor with the candidate's number in
> it.
>
> Where it first reaches them: In the sports hall he is being paid £11.40 an hour to
> invigilate: the first Chaperone comes down aisle C ninety seconds into the change and
> withdraws the student at desk 41, who has done exactly what he was trained to do and stayed
> in his seat with his pen down.
>
> The turn, inside the first arc: He strikes a line off a published scheme with the dead
> invigilator's red pen and clears a whole assessed zone by making the thing that kills there
> worth zero marks — and the Invigilation revises the scheme mid-cohort in his name (METHOD
> DEMONSTRATED BY CANDIDATE 0-0-4 WILL NOT BE CREDITED), which pulls him out of the cohort and
> under the body that writes the schemes, as its lowest-ranked marker.
>
> A second system after the turn, The Board. How it shows itself: First person plural, on
> paper — actual sheets that arrive folded, in a hand with marginal annotations, addressed to
> him by name and not by number. Where the Invigilation refuses to clarify, the Board only
> ever asks questions, and waits for the answer before anything happens.
>
> What carries over from the first: His band and his fitting carry over unchanged — he stays
> a Band Two among people wearing Five and Six — and so does the exception, except that he
> now meets schemes from the other side: as unsigned drafts he is expected to put his name to
> before they are published to a hall.
>
> The first arc opens: Scene 1 — sports hall, forty minutes into a first-year mechanics paper,
> three hundred and twelve seated students and one invigilator walking the aisles. The light
> goes grey-green, the paper on every desk is overwritten, a scheme hangs in front of him
> alone, and by the time he has finished reading it a Chaperone has taken desk 41.
>
> Its middle: Scenes 3–4 — outside on campus with the survivors he shouted out of the hall,
> he sees the public board for the first time and is near the bottom of it despite
> everything, because damage is what pays elsewhere; then the Retake, a previous cohort's
> candidate left standing in the science quad, still trying to answer, beats the four of them
> outright — and is only got past when he reads that the encounter awards nothing at all for
> killing it and six marks for finishing its paper for it. Its fitting comes off it: a
> marker's red pen that strikes one item off a scheme, for everyone in the space.
>
> It closes: Scene 6 — the revised scheme goes up naming his method, the survivors he
> collected are re-cohorted away from him under a new invigilator, and a folded sheet of
> paper is handed to him by something that walked rather than appeared, asking a question and
> waiting for an answer.
>
> What the book owes, and the scene each is due by: how many of the three hundred and twelve
> walked out of the hall (by scene 3); why the schemes are shown to him and to no one else
> alive — the hall's scheme is addressed to the invigilator's position, and he was the only
> person standing in it (by scene 4); what striking a line off a scheme costs — the struck
> item is deducted from him (by scene 5); the student at desk 41, the outline returned to and
> the number matched to a name on the register still in his hand (by scene 6).

**Read before the listing was drawn (a diagnostic).** Every §198 field is filled with a thing
and not a label, which pilot 24's first concept was not. The person before is one the
readership has lived (a PhD student marking problem sets for rent). The ladder arrives with
outfits unasked (bands issue fittings; a coat, then gloves; the rank read off the clothes),
which is the operator's own progression direction landing from a dossier that never names
it. The threat is a rule a reader can hold in one sentence (sixty seconds attempting nothing
and the Chaperone withdraws you), it kills on the page in scene 1, and it kills the student
who did what he was trained to do. The system's manner is the exam board's passive, and it
wants something (unlisted answers to harvest), which makes the turn a real reversal rather than
a promotion. The second system differs in manner (paper, questions, the plural) and not only
in name. The four debts are concrete and dated.

Three risks, named before the draw so the read can check them. First, the exception is an
information advantage (he sees the scheme first), the family both pilots 19 and 20 converged
on (*see it coming*; plan/serial-pilot-20.md §3 records the exception slot converging one level
below read 5's premises), and a chapter built on reading a scheme is a chapter of reading where
the shelf's are chapters of doing; the concept's own first use is a deduction (sitting still
is marked zero) that must become an act (shouting them out of the hall), and whether the act
is on the page is the read's. Second, the vocabulary is British academic (invigilate,
marking scheme, first-year mechanics paper, £11.40 an hour): reads 16 and 17 both harvested
British idiom as a family, and *invigilator* is the system's own name, which no rail asks to
redraw. Third, the exam-board register is a comedy of manners waiting to happen, which the
popcorn direction can carry only while the Chaperones stay frightening. No redraw was made on
any of these: the name rail is the only rail (§198.1), the first clean draw is kept, and my
taste is a diagnostic and not a selector (§61(5), §105).

## 2. The listing

Drawn from the concept in the third person with the three exemplars' blurbs as register and
the rival pool for the readers; the length rail redrew it twice (37 and 34 words over the
shelf's 27) before it settled. *Marks For Moving*, 120 words, the title free of collisions,
four of four readers starting ours against a published rival, each naming the rule (marks for
moving, nothing for sitting still) and the pen as the reason. Settled at
`runs/pilots/pilot25/listing.txt` (gitignored); verbatim:

> He was a physics PhD student paying his rent invigilating undergraduate exams, walking the
> aisles when the hall went grey and the Invigilation started grading everyone inside it. A
> marking scheme hangs over one desk, marks for moving, more for a weapon, nothing at all for
> staying seated, and staying seated is what the faceless grey thing in the doorway kills a
> student for. Nobody else alive sees a scheme before the marking. He wants his thesis
> submitted and the postdoc after it. He gets a coat with what he can now do written inside
> it, a red pen that strikes an item off a scheme for everyone in the room, and a board he is
> near the bottom of.

**Read.** Every sentence carries a thing (the hall going grey, the scheme over one desk, the
grey thing in the doorway, the coat, the pen, the board), and the prizes are on the page as
objects, which read 18 asked for. Two seams for the operator's read: *Nobody else alive sees a
scheme before the marking* is the absence family (read 19's *x nobody y*) in the listing,
where no tells rail runs (the listing loop's rails are length, the coordinator's chains and
the name); and the tense moves from *He was ... walking* to *hangs ... kills ... wants ...
gets* inside one paragraph, where the shelf's blurbs hold one tense. Neither was redrawn: no
rail asks, and a redraw on my reading would be a selection (§105).


## 4. Draw1b — the chapter, its counts, and the read

**What ran** (`runs/ab/pilot25/draw1b/`, 2026-09-02 22:31 to 22:56 UTC, tree 150d467 clean
at start and at finish). The seed in 956 seconds, `world check` and `world accept` clean under
§200's preview, the outline, two scenes on the first attempt each, the pass on both, the
shelf (`book-library/marks-for-moving--38700be7/`), the readership. Thirty-one calls,
$10.01. Four of four readers carried on against a named rival, every one naming the mark
scheme as the reason and three of four naming the boy who folded his hands.

**Counted, per scene, from the decision rows** (per thousand words, before and after the pass):

| scene | absence | paradox | the way | echo | chained and | long | said again / left / calls | spend |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| scene 1 | 3.2 to 3.2 | 0.0 | 2.1 to 0.0 | 1.1 to 1.1 | 2.1 to 1.1 | 6.3 to 1.1 | 7 / 4 / 9 | $1.57, 413,693 tokens |
| scene 2 | 5.0 to 5.0 | 1.0 to 0.0 | 3.0 to 1.0 | 3.0 to 1.0 | 6.0 to 1.0 | 10.9 to 1.0 | 12 / 8 / 11 | $1.93, 506,211 tokens |

Beside pilot 24's draw3 (twenty-six and thirty-five calls, $4.46 and $5.98): a third of the
calls and a third of the spend for more sentences said again (nineteen against sixteen) and
fewer left (twelve against twenty-two). The harness tax is unchanged at about forty-six
thousand tokens a call; the batching is what moved.

**Counted on the whole chapter, beside the shelf:**

| family | shelf's ceiling | draw1b | pilot 24 draw3, for scale |
| --- | --- | --- | --- |
| absence | 2.6 | 4.1 | 3.1 |
| paradox | 0.0 | 0.0 | 0.5 |
| the way | 0.6 | 0.5 | 1.5 |
| echo | 1.0 | 1.0 | 2.0 |
| chained and | 0.5 | 1.0 | 3.1 |
| long (over 35 words) | 0.0 | 1.0 | 6.1 |

1,955 words; sentence census: median 10, ninetieth percentile 29, longest 48, one sentence
in a hundred and forty-five over forty words. The shelf's three run median 10 to 16, longest
30 to 35. This is the first chapter drawn in this house whose sentence-length shape sits
inside the shelf's on the middle and near it at the top; the two that remain over thirty-five
words are the coat lifting (*It weighed what a coat weighs, and it swung, ...*, 48 words) and
the second reading of the sheet.

**The absence family did not move on either scene, the third scene running.** The
batched ask for it (*Say what is there rather than what is not*) has now had every rewrite
refused on draw1's refused scene and both of draw1b's, with the other five families moving
under the same batch shape. Of the eight absence sentences the counter finds on the chapter,
four are lines of speech (*Nothing at all for sitting down*, *So nobody stops*, *Nobody has
to be any good at it*, *Grip, nothing*), where the absence is the fact being said and no
rewrite can keep the fact and lose the word; the shelf's own absence sentences are narration.
That is a conjecture from one chapter and a hand count, recorded as one (§199.5); the fix it
points at (the family reads narration and not speech, on both sides of the ceiling) is not
built on it.

**The read.** The person is the readership's and the edge is his in the first paragraph
(*he could read a mark scheme the way other people read a bus timetable*; the thesis, the
postdoc in October, eleven pounds forty an hour). The arrival has the concept's look and it
is the best arrival in twenty-five pilots: the colour flattening to grey-green, the bell
behind the teeth, the clock gone and then the fire door, the scheme in ruled serif capitals
with marks in a column *exactly as the department did it*. The first use is the deduction
the concept promised and it is an act on the page (*REMAINING SEATED, NO MARKS AVAILABLE* read,
and *Get up* shouted, cracked), and the threat kills the person who did what he was told,
which every reader named. The sheet does work for the first time in this house: the coat that
will not lift, CARRY 2 read *the way he read a student's working when the answer was wrong and
the method was fine*, the coat lifting; then GRIP 0 and the chair sliding out of his hands
*like a bar of soap goes*; the first-year the size of a door hitting the figure for six and a
line arriving *after the fact, saying what he had been paid*. The column of people
*committing an offence continuously, so that not one of them was ever the one who had
stopped* is an invention with the rule inside it. The close is the concept's turn arriving
early and small: the revised scheme with his method struck through and his number under it,
and a new item, *VACATING THE ASSESSED POSITION, TEN MARKS*, which is a threat with a price on
it and the first chapter close here that is an offer a reader can do arithmetic on.

**What a reader will hit, by the reads' families.** *To nobody, in the voice of somebody
establishing an alibi* and *nothing at all where a face goes* are the absence habit in
narration. *Because that is what a body does* is the narrator's gloss addressed to nobody,
read 17's question again, once. *Like a bar of soap goes* is a phrase no native hand writes,
and it is the pass's: a *the way a bar of soap goes* simile said again without the words and
kept because the counter found no shape in it; the pass can leave a sentence worse than the
counter can see, and this is the first such sentence found. The status row has eight fields
and five zeros, unglossed (READING, CALLING, SETTING, TIMING, STRIKING), though two of the
eight do work on the page. He stands *at the back of the hall by the spare pens* and the
scheme hangs *a pace in front of him* over *the square of floor where the front desk should
have been*, which puts him at both ends of the hall in one paragraph. The setting's words are
British (rota, resit, first-year, the rowing club fleece) and *invigilating* is explained only
by its company. None of these is a sentence the counter finds, and the operator's read is
what they answer to.

**What the concept bought.** Every §198 field is on the page: the look (the grey-green, the
serif), the threat's rule and its first reach in the first scene, the first use as an act, the
pays field as a coat that lifts a coat. The turn arrives in chapter one rather than at the
arc's end, which the outline placed; whether that spends the arc's middle early is scene 3's
to show.

**One draw, one description.** Nothing here is a treatment effect against pilot 24 or
against draw1, and no bar is declared: the counts sit beside the shelf's, the read sits beside
the reads' families, and the operator's read is the readout.
