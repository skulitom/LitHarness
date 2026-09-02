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

