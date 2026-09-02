"""The book overview: what a reader sees before they open chapter one, and who writes it.

**This replaced the retired Forge's pitch stage.** A world used to be assembled by an Architect with
its own identity and its own rule essay, K at a time, and an operator picked one — which is a
human production step, and §126's objective is fiction produced *without* a human production
loop. The operator, 2026-08-24: *"we just don't need a forge"*, and *"we need to pass to the
writer we are writing book overview and they are tasked in creating a compelling idea readers
will love (with a hook). But the core loop of feedback should be the same (simulated reader)."*

So: one writer from `writers.CAST`, one overview, and the same two-pool readership that reads
the chapters. Nothing here ranks anything and nothing chooses between candidates — there are no
candidates. Appetite answers are experimental observations only; the production command no
longer sends their raw wording back to the writer. The measurement pool, which never steers,
says whether it would open chapter one.

**The task text is deliberately short.** Three rules in the retired Forge were assertions about
what this genre's reader wants, written into a prompt addressed to nobody. A cast writer who
reads the genre knows what a hook is, and `domain/house.py` carries the floor. Adding a
paragraph here about what makes an overview good would rebuild the rule essay one level up.

**It got shorter on 2026-08-25, and the length was the defect.** The first version asked for
"around two hundred words" and never used the word hook. Four listings came back at 207 to 257
words, every one of them opening on a world's administration and arriving at a person late; the
operator's reading was that none of them had a hook in it and that none read as this genre at
all. The listings this market actually runs are sixty to a hundred and forty words and *are*
hooks, so asking for twice that was buying room for the throat-clearing.
"""

from __future__ import annotations

import re

from litharness.domain.generation import CompletionRequest
from litharness.domain.writers import Writer

#: Frozen profiles, one per stage, so a draft and a revision are separable on the decision rows.
OVERVIEW_PROFILE = "writer.overview.v0"
TITLE_PROFILE = "writer.title.v0"

MAX_OUTPUT_TOKENS = 4000

#: The two words that chain one clause onto the next. Counting them is the whole mechanism:
#: no model is asked whether a listing reads as a list, and nothing here knows what the
#: threshold is — the caller supplies it, so this function is a property of a string.
_COORDINATORS = re.compile(r"\b(?:and|then)\b", re.IGNORECASE)


def coordinator_density(listing: str) -> float:
    """Coordinator tokens per hundred words of the listing's own length.

    The operator named this in the fifth operator read, reading a listing aloud as *"kind of
    like a list with constant 'and then', 'and then'"*. It is a shape property with a right
    answer, which is why it can be counted at all; `plan/reader-read-5.md` §4.1 is where the
    reading and its distribution live, and stage-0 §147 is the decision to refuse above a
    ceiling. Nothing here is a quality claim — a listing under the ceiling is not good, it is
    merely not chained.
    """
    words = len(listing.split()) or 1
    return 100 * len(_COORDINATORS.findall(listing)) / words


def keep_least_chained(drawn: list[str]) -> str:
    """Which of a bounded redraw loop's draws is kept: the least chained, earliest on a tie.

    A total order over one frozen counter, so this is arithmetic rather than a preference
    among candidates — §61(5) forbids a *model* ranking without containment, and no model
    reads anything here. Keeping the earliest on a tie makes the choice reproducible.
    """
    if not drawn:
        raise ValueError("a redraw loop that drew nothing has nothing to keep")
    return min(drawn, key=coordinator_density)


def chains_too_hard(listing: str, *, ceiling: float) -> bool:
    """Whether this listing chains harder than the caller's ceiling allows.

    The ceiling is a parameter and has no default here on purpose: its value is a policy
    decision made at the composition root, and this module stays a pure function of the text
    so that nothing about where the number came from can leak into generation.
    """
    return coordinator_density(listing) > ceiling

#: **Five instructions, and the count is the point.** With the house rules appended this
#: call made sixteen demands of a hundred-word artifact, eleven of them rules written for
#: scene prose: paragraph-level pronoun reference, puzzle-box move counts, what a scene must
#: move. Measured over nine calls, three writers, three arms, the longest sentence a listing
#: contained fell from 79 words to 33 when the scene rules came off, and the mean length fell
#: from 135 words to 83 when the budget came down with them.
#:
#: **One clause came back on 2026-08-25, deliberately, and the budget was raised for it.**
#: Taking the house floor off this call to stop the cramming also took off `READER`'s
#: numbers prohibition, which was the only thing standing against exactness spent on props
#: and durations. Measured across three rounds: with the floor, 25.9 number tokens per
#: thousand words; without it, 43.2 and 39.1, against 8.0 in the market's own listings. The
#: operator's reading of one of them was *"lots of specific numbers for no reason"* over
#: *"fails the intake test in nine seconds ... the third, where she rushes it, the way she
#: has rushed it for eleven years"*.
#:
#: This is what `tests/test_prompt_budget.py` is for: the clause was removed without
#: measuring what it did, the measurement says it earned its place, and putting it back
#: costs a ceiling raise that somebody has to write down.
#:
#: **Two clauses changed 2026-08-25 on ten market listings rather than six, and one of
#: them was simply wrong.** The length ask read "under a hundred words, and shorter is
#: better"; the market runs **40 to 146 words, median 100**, and we had pinned ourselves
#: to 74-92 with a median of 78. And the opening clause read "open on the person it happens
#: to", which a model satisfies by establishing who the person is: five of eight listings
#: began on a mundane job. The operator, beside Chrysalis, which opens after the transition
#: and names no prior life at all: *"isekai is good, we just don't have to mention their
#: job every time"*.
#:
#: **The genre-noun clause is the largest measured gap of the day and it names examples,
#: which is a risk taken deliberately.** Ten market listings average **3.8** of the genre's
#: own nouns each — magic, monsters, system, reborn, heroes, multiverse, skills, tutorial —
#: and eight of ours contain **one** between them. Nothing in this prompt forbade them; the
#: model avoids the furniture unprompted, which is the same defect as writing a listing that
#: reads as literary fiction. A named list invites a checklist and this project has measured
#: that failure before, so the count is what says whether it worked: if the next round comes
#: back at 3.8 by mentioning nouns rather than by being that kind of book, the clause goes.
#:
#: **The numbers clause lost its permission on 2026-08-25, the fourth instance of a failure
#: `house` had been given a standing constraint against hours earlier.** It read "an exact
#: number is worth its space only where the world itself counts it", and a dungeon floor is
#: something a world counts, so the clause licensed *floor ninety*, *eight ranks above him
#: on a ladder of nine*, *the ninth floor*. Measured across four rounds: floor numbers, rank
#: positions and the words ladder/rung appear in **0 of 10** market listings and **0 of 8**
#: of ours in round six, and returned at one to three of eight in rounds seven and eight —
#: which is when the genre-noun clause arrived. Naming the genre invited its countable
#: fittings, and the numbers clause was holding the door open for them.
#:
#: **And a blanket ban was the wrong correction, made and unmade the same hour.** The first
#: fix read "floors, ranks, counts of things and lengths of time are space the hook needed",
#: which would delete *"I need to finish this floor, is this going to be over soon?"* along
#: with *floor ninety*. The operator: *"we only want to mention ranks, numbers and skills if
#: it's relevant to what the protagonist is thinking of, especially the protagonist desire
#: ... oh i unlocked a new ability i wonder how i can grow it"*. So the clause is about
#: **ownership**: a quantity the narrator inventories is dead weight, a quantity the person
#: is counting and wants something from is the hook.
#:
#: It is written as a scope rather than as a list of instances, which is the distinction
#: the standing constraint in `house` turns on: a menu of nouns gets recited ("in a body,
#: in time, in risk" came back as "pays in blood, in sleep" five times in eight), and a
#: constraint on where something may appear gives nothing to reach for.
#:
#: **Then the clause was tested in every form, and the pattern is the standing constraint.**
#: Number tokens per thousand words, against the market's 7.2:
#:
#:     10.8  the clause with its permission, before the genre-noun clause existed
#:     16.5  the same clause, once genre nouns arrived
#:     47.2  the ownership clause. It half worked: four listings of eight tied a quantity
#:           to what the person wanted, which is what was asked for, and the total tripled
#:     42.9  a replicate of the same condition
#:     29.4  no clause at all
#:
#: The claim that a *scope* would not be recited the way a *menu* is did not hold: "they
#: earn their space where he is counting one himself" is a permission and was taken
#: maximally. But **the last row is what makes this a result rather than a defeat**: a
#: clause carrying a prohibition suppressed numbers *below* the no-clause baseline (16.5
#: against 29.4), and the pure permission raised them far above it. That is exactly what
#: `house`'s standing constraint predicts, measured on the clause that motivated it.
#:
#: So the untested cell is a prohibition with no permission attached, which round eight's
#: clause never was — it opened "an exact number is worth its space only where the world
#: itself counts it" and only then said what fails. That is what stands here now.
#:
#: **The operator's own framing is why saying nothing is right rather than merely untried.**
#: *"overviews don't usually have specific numbers ... They belong outside the overview at a
#: different density."* In the chapter they belong in the system's own window — Defiance of
#: the Fall opens on `[Low F-grade mass, ungraded energy]` and a roll table — where a number
#: is something the character is reading rather than something the narrator knows. So this
#: is not one rule tuned twice. It is two artifacts with two densities, and the density that
#: belongs to a listing is the market's: near zero.
#:
#: **The listing lost its clarity floor when it lost the house floor, and this restores the**
#: **half of it a listing needs.** Stripping `house` to stop the cramming took `CLARITY`
#: with it, and `CLARITY` is exactly *"a sentence a reader can take two ways has failed"*
#: and *"a thing the reader cannot follow is a thing that did not happen"*. Round eleven's
#: defects were all one of those two: *"mountain, small, clawed, and somebody else's meal"*
#: (which noun do the adjectives attach to), *"decided I was hers instead"* (one reading is
#: "to eat later"), and *"and still reading"*, *"whoever wrote the system"*, *"if I say it
#: out loud I get to keep what it can do"* — each asserting something nobody in the story
#: could know yet.
#:
#: **It is a second statement of a rule that has a canonical home, and that is recorded
#: rather than hidden.** The repository's rule about counts — one home, pointers elsewhere —
#: is the same rule for instructions. The honest version extracts it from `house.CLARITY`
#: the way `ACCUMULATION` is extracted, and that could not be done without reordering a
#: constant whose rendered bytes `tests/test_prompt_budget.py` counts. If `CLARITY`'s two
#: clauses are ever edited, this line is the second place to look.
#:
#: Second person joins the format line as a format fact: second-person-as-protagonist is
#: 0 of 10 in the market and was two or three of eight in every round of ours.
#:
#: So this call does not go through `writers.system_for`: the house floor governs the book's
#: prose, and a listing is not the book's prose.
#: **Two clauses of `house.CLARITY` came back on 2026-08-26, and they are a restoration rather
#: than a fifth rule.** Stripping the house floor off this call to stop the cramming took all six
#: of `CLARITY`'s clauses with it and only two were ever put back. Among the four that stayed out
#: are exactly the two the operator's read of *Patch Notes For Earth* named: *"wtf is a patch of
#: notes, nobody says that"* and *"sentences don't have relations to each other ... it reads more
#: like spaghetti mess"*. Those are the unmet-term clause and the paragraph clause, near enough
#: word for word what `house.CLARITY` already says — so this is text dropped by accident being
#: put back, not §127's fourth rule against the same complaint.
#:
#: **The genre-noun clause stayed, and a measurement is why.** The plan was to delete it: its own
#: docstring pre-committed to going if the count came back high by recitation, and two listings
#: carried 4 and 7 of the genre's own nouns. Then 42 published serials above a thousand followers
#: were counted (`research/quality-measurement/rival_pool.py`) and **the market's median is 2 with
#: a p90 of 6** — so a listing at 4 sits inside its own market, and a four-writer draw under this
#: clause came back at 0, 2, 3, 4 against that median. Removing the clause drove the same four
#: writers to 0, 0, 0, 0, which is the defect the clause was added for in the first place. The
#: clause was **measured on the wrong sample, not wrong**: ten hand-supplied listings said 3.8,
#: forty-two say 2, and it is judged against the second from now on.
#:
#: **The opening clause forbade both available openings, corrected 2026-08-29 on read 7 §4.1.**
#: It read *"Open where the trouble already is: not on an account of the world, and not on an
#: introduction to whoever it happens to"*, and the two prohibitions between them ruled out the
#: world and the person, leaving an **unowned situation** — which is an account of the world by
#: another route, so the ban that was supposed to stop world-first openings was the one the
#: model could satisfy while writing one. Its affirmative half named *the trouble*, owned by
#: nobody, and the permission is what got obeyed (§138). The result is pilot 13's first line,
#: *"The rain over Ambry Market has been sold to someone else, and Corin is carrying a jar of
#: it in his bag"* — the trouble leading, the person arriving in the subordinate clause. The
#: operator: *"who is someone else why are we saying this? why would the reader care?"*
#:
#: **The ban on the person was an over-correction of a defect that was never the person.** It
#: replaced *"open on the person it happens to"* after five of eight listings began on a mundane
#: job — but what the operator objected to was the biography, not the protagonist: *"isekai is
#: good, we just don't have to mention their job every time"*. So the prohibition is narrowed to
#: what was actually measured, the prior life, and the permission is deleted rather than
#: rewritten: §138 puts silence (29.4) above a permission (47.2) and a prohibition (7.0) above
#: both. Nothing now says where to open. By elimination what is left is the person as they are
#: now, and the demand five clauses down already requires what they are after.
#:
#: **This is placement only, and the operator's own rewrite did not become prompt text (§97.1).**
#: Demand count unchanged at 15, which is this role's ceiling and left no other move.
#:
#: **Two levers named and not pulled.** The material label is still *"What this book is to be
#: about"*, and §136 measured that heading turning two genre words into the book's subject
#: matter — a subject-matter frame over the only material in the call is a structural push
#: toward a topic rather than a person, and changing it would break the empty-brief control
#: §136 deliberately refused to touch. And **nothing in this task names the protagonist's
#: exception at all** — the hook direction is that a hook is an exception belonging to one
#: person, and read 3 already recorded that no step decides or records what is singular about
#: whoever the book is about. That gap is structural (a protagonist object, a brief), not a
#: clause: this role is at its ceiling and a clause is what §127 measured failing four times.
#: Shipped unmeasured; pilot 14 is what reads it.
#:
#: **The readership's structural half arrives here on 2026-08-30, and the finding is that it had
#: been written down for a week at roles that cannot act on it, in the form this file measured
#: worst** (§174). Read 10 failed pilot 15 on a protagonist who is neither relatable nor
#: aspirational, and the standing readership direction it converges with (2026-08-23) turned out
#: to be live prompt text in `house.READER`: *"If the person this happens to came from somewhere
#: like our own world, the life they came from is one a reader in their twenties has lived: a
#: degree they are not using, a job that covers the rent, a thing they know far too much about
#: for no professional reason."* Three things were wrong with it and none of them was the
#: direction:
#:
#: 1. **This call does not carry the house floor** — the decision three paragraphs up — so the
#:    one call that decides who the person is never saw the clause. Every role that did see it
#:    receives the person already named by this listing, and by §154 an artifact fixed upstream
#:    of a call lands with whatever force its sign would give it multiplied by zero.
#: 2. **Its conditional is false in exactly the case the direction was written against.** A
#:    village mender native to her own valley never *"came from somewhere like our own world"*,
#:    so the clause was silent on the premise read 10 rejected.
#: 3. **It is a permission enumerating three instances of what succeeds**, in the module whose
#:    own standing constraint forbids that and which has cut three clauses for being recited
#:    back. §138 measured the permission form of the numbers clause at 47.2 against a
#:    prohibition's 7.0, and §154 cut two reader-state permissions out of the same constant.
#:
#: So the clause changes altitude and sign, and **the demographic does not travel**: what a
#: prompt gets is the structural consequence — the person is not already good at what the book
#: will ask of them — and the audience that consequence follows from stays in `PLAN.md` and the
#: ledger, where a targeting decision belongs and where §97.1 keeps the operator's words. The
#: positive half of the direction (a degree, a job, an obsession) is deliberately not written:
#: its permission form is the one this file already measured producing five mundane-job openings
#: out of eight, and the demand two lines above it exists to keep that biography off the page.
#:
#: **Placed on the person clause rather than beside the prior-life ban, and the reason is
#: addressability.** The ban keeps the years before the book off the page, so nothing about them
#: can be shown there; what a listing does say is who the person is now and what they are after,
#: and *already good at the book's own subject* is visible right there. Beside the ban it would
#: read as a third thing not to write, which is how a demand goes inert.
#:
#: This is not the exception lever named two paragraphs up, which is still structural and still
#: open. Ceiling 15 -> 16, raised on purpose in `tests/test_prompt_budget.py`. Shipped
#: unmeasured: no draw stands behind it, and the next listing draw is what reads it.
#:
#: **The implication clause was removed on 2026-08-30 (§187), from here and from `house.READER`
#: in the same edit.** It shipped at two addresses as one rule, so it comes out of both — leaving
#: this copy standing would give a removed rule its only home at the one production role that
#: stands on no house floor, which inverts the reason it was written. The measurement is
#: `plan/agent-impact/`: the audit finds every family still alive at read 13 clause-addressed and
#: no register clause moving a sentence metric across ten chapters, and the operator's word at
#: that report is to take the register clauses out of the prompts. §127's brake needs both and
#: has both. The clause now stands once, in `application/reviser.py`. Ceiling 18 -> 17 in
#: `tests/test_prompt_budget.py`. The word `implies` accordingly appears once in this task again,
#: with the genre-noun clause's sign, and the collision the paragraph below reads through is gone
#: rather than resolved — a later track adding a second sense back should re-read it.
#:
#: **The implication clause arrives here the same day as the floor's, and this is the address the
#: read actually named** (§179). Read 11 flagged two instances of a construction — a narrator
#: asserting an absence or a universal access the surrounding words already give — and **both are
#: in a listing**, not in a chapter. The finding is §174's one paragraph down, running the other
#: way: that entry moved a clause here because a listing decision could not be reached from the
#: floor, and this one adds a clause here because a listing *defect* could not be. A register rule
#: that lives only in `house` reaches every role except the one whose output the operator was
#: reading.
#:
#: **The sentence is byte-identical to `house.READER`'s, and that is a decision rather than a
#: copy-paste.** This file already carries two clauses of `house.CLARITY` as a recorded second
#: statement, and the reason given there — one home, pointers elsewhere, and if the canonical text
#: is ever edited this is the second place to look — applies unchanged. What is new is that the
#: identity is now *asserted*: `tests/test_implication_register.py` fails if the two texts drift by
#: a byte, which is the half the 2026-08-26 restoration had to do by hand. Extracting it into a
#: named constant would reorder a constant whose rendered bytes the budget file counts, and that
#: is still true.
#:
#: **The word `implies` now appears twice in this task with opposite signs, and the collision was
#: read before it shipped.** The genre-noun clause says to name the magic, the system and the
#: monsters *rather than implying them*; this one fails a clause that states what its own sentence
#: already implies. They do not meet: the first governs the book's subject matter, which a listing
#: must put in plain words, and the second governs a clause whose content the sentence carrying it
#: has already given. A listing that names its genre plainly and then spells out what that naming
#: implies fails the second while satisfying the first, which is the intended reading. The next
#: draw is what would show a model splitting the difference instead, and that is worth watching
#: rather than pre-empting with a fourth clause (§127).
#:
#: Ceiling 16 -> 17, raised on purpose and for one sentence, with the reason in
#: `tests/test_prompt_budget.py`. **A subtraction was looked for first, in the order that file
#: asks for, and refused**: every candidate here is either a format fact this market's listings
#: are measured on or a clause whose removal §138 has already measured the cost of. Shipped
#: unmeasured; the two instances that named the family are fixtures in a test and reach no prompt
#: (§97.1).
#:
#: **The house genre arrives here on 2026-08-30, and until it did, nothing in this call said
#: which kind of book was being sold** (§183). The genre is mandatory and the seed already
#: refuses a book that cannot speak system voice (`domain/genre.genre_block`), but the seed runs
#: *after* the premise exists: this is the call that invents what a reader is promised, and three
#: listings were refused at the coordinator's gate in one day for promising something else —
#: light fantasy (pilot 13), sci-fi horror with no interface in it (pilot 18), and an
#: institution's paperwork twice (pilot 17, refused on its own §116 ground and sharing this
#: surface).
#:
#: **The clause five lines down was read first and it is genre-agnostic by construction** (§154's
#: audit order). *"A reader scanning a list has to see what kind of book this is ... name the
#: magic, the system, the monsters, the dungeon in plain words rather than implying them"* asks a
#: listing to be plain about whatever furniture it has; any kind of book satisfies *what kind of
#: book this is*, and the four nouns read as instances of what to say plainly rather than as
#: things a book must contain. Pilot 18's listing named none of them and broke no rule. So the
#: gap is presence, not plainness, and the two clauses stand in that order: what the book has,
#: then how to name it.
#:
#: **Affirmative on purpose, which §138 is usually the argument against.** That measurement is
#: about *suppressing* an overproduced feature, and nothing can be forbidden into existence. The
#: precedent is in this same constant: the genre-noun clause is affirmative, and removing it took
#: four writers from 0, 2, 3, 4 of the genre's own nouns to 0, 0, 0, 0 against a market median of
#: 2. This defect is that shape — an absence measured at zero — so the clause is signed the way
#: the one measured against the same defect is.
#:
#: **What it deliberately does not say, each refusal costing nothing.** It names no shelf label:
#: §136 measured two words of genre-as-brief outweighing every rule in this prompt, and
#: `application/recruiter.py` reached the same conclusion at its own address on 2026-08-29 — the
#: house genre reaches a prompt as its mechanical floor and never as its name. It names no
#: quantity, so the numbers prohibition three clauses above governs the gain unopposed; §136's
#: own worst listing was furniture with numbers on it. And it supplies **no noun** for the thing
#: that is opened, so the book's own word is the model's to pick — which is what keeps §178's
#: return-side check meaningful rather than a check on a word this prompt handed over.
#:
#: **One sentence carrying two halves, and the accounting is reported twice so the counter is not
#: doing the arguing alone.** `plan/house-genre-constraint.md` names both — the furniture exists,
#: and a gain on it is on the page rather than deferred — and a listing failing either is refused
#: at the same gate for the same reason, which is why the terminator is one clause (§179.4's
#: shape, conjunction rather than subsumption). `house.demands` prices it at one; the assembled
#: system message grows 2,120 -> 2,356 characters, and §171 records that a demand bought by
#: evading this counter is not a demand saved. Ceiling 17 -> 18 in `tests/test_prompt_budget.py`,
#: raised on purpose, with the subtraction looked for first and refused there.
#:
#: **The empty-brief control is rewritten deliberately rather than silently**, which is the
#: hazard `plan/house-genre-constraint.md` recorded before this track existed. Nothing is put in
#: the brief field, `render_overview_request` renders the same default it always did, and an
#: empty brief is still empty — so the operator's content channel is untouched and briefed
#: against unbriefed is still a comparison of what was asked for. What is no longer controlled is
#: **genre presence**: every listing drawn from now on promises this house's book in both arms,
#: so §136's arm B is no longer a genre-free arm and no genre-noun or rank-vocabulary count
#: taken after this clause may be read against one taken before it. §183 carries the full
#: statement.
#:
#: Shipped unmeasured. No draw stands behind it; pilot 18's redraw is what reads it.
_TASK = (
    "You are writing the listing for a new serial: the few lines a reader meets on the front "
    "page of a serial-fiction site, and the only thing that decides whether they open chapter "
    "one.\n"
    "A reader meeting this has not started the book. Not an account of the world. The life "
    "whoever this happens to had before it began is one plain clause saying who they were the "
    "day before, and no more: a listing with none has given the reader nobody to stand beside, "
    "and one with more has become an account of it.\n"
    "Exactness spent on floors, ranks, counts and lengths of time is space the hook needed.\n"
    "A sentence a reader can take two ways has failed, and so has one that asserts what nobody "
    "in the story could know yet.\n"
    "The book this promises is one where the person opens something and reads their own "
    "capabilities in it, and the promise names one of them they did not have before; a promise "
    "missing either half is for a book this house does not publish.\n"
    "A reader scanning a list has to see what kind of book this is and what the person is "
    "after: name the magic, the system, the monsters, the dungeon in plain words rather than "
    "implying them, and say what the person is trying to get.\n"
    "Whoever this happens to did not spend the years before the book mastering one trade: a "
    "person who arrives already good at what the book will ask of them has nowhere to go.\n"
    "A term the reader has not met needs a reason to be there before it needs anything else, "
    "and then a consequence rather than a definition: the sentence carrying it says what it "
    "does to somebody.\n"
    "A paragraph holds together or it is not a paragraph: a sentence that could be lifted out "
    "and dropped anywhere in the listing has failed.\n"
    "No title, no headings, no tags, no word about the author, and no dashes: this market's "
    "listings punctuate with full stops and commas. The person this happens to is he or she or "
    "I, and never you. About a hundred words."
)


def _system(writer: Writer | None) -> str:
    """Who is writing, then the job. No scene floor: see `_TASK`.

    **`house.ACCUMULATION` was appended here and then removed, and the removal is the same
    finding as the numbers clause.** It says what a *reader* collects over a book, what the
    person keeps, and in a hundred-word listing the model made that the *protagonist's
    superpower*: a keep-power was the central hook in **seven of eight** listings with the
    clause and **one of eight** without it, against **zero of ten** in the market. All four
    writers arrived at the same meta-ability, which is the operator's *"reads a bit too much
    like ticking boxes"*, and it is why nobody started weak: each was handed the power at the
    top rather than acquiring it.

    So the clause stays in `house` for the scene path and the Architect, where accumulation
    happens across chapters, and leaves the listing, where it becomes the premise. Same
    lesson as the number density: one rule, two artifacts, two densities.

    The reasoning for referencing rather than restating it was sound and is kept for
    whatever appends it next: it was the one clause of the
    floor a listing genuinely needs — a mechanic that spends its own capability is the
    thing this genre's reader is least here for — and one object with two callers is what
    keeps it from becoming two rules that drift.
    """
    return f"{writer.render()}\n\n{_TASK}" if writer is not None else _TASK


#: The line a first-person book's listing carries, as material under the brief rather than as
#: a rule in the system: the task already allows "I" and forbids "you", so this says only which
#: person this particular book is told in. Nothing about how; the person is a position, the
#: same class of fact as `Point of view:` in the scene prompt.
FIRST_PERSON_ASK = "Told by the person it happens to, as I."


def render_overview_request(
    brief: str,
    writer: Writer | None = None,
    *,
    person: str | None = None,
    blurbs: str | None = None,
    concept: str | None = None,
) -> CompletionRequest:
    """One overview, from a brief that may be empty.

    `person` is `"first"` for a book told in the first person and otherwise `None`; the first
    person appends `FIRST_PERSON_ASK` under the brief and nothing else changes, so every listing
    drawn before this parameter existed renders byte-identically.

    `blurbs` is the exemplar shelf's listings block (`exemplars.render_blurbs`), shown above
    the brief as how this shelf's listings sound (stage-0 §196), or `None` for the prompt as it
    was. It is material in the user message and not a rule in the system: the block says whose
    it is and what it is for, and the task's demands are untouched.

    `concept` is the book as its writer conceived it before this listing
    (`concept.Concept.render_for_listing`, stage-0 §197), shown under the brief as material:
    the listing is written from it and the task's demands are untouched. `None` renders the
    prompt as it was.

    An empty brief is legitimate and is the control the retired Forge kept for the same reason:
    a book built from no direction at all is what a directed one is read against.

    **A genre label is the worst thing this field has held, and it outweighed every rule in the
    prompt.** Measured 2026-08-25, four writers, both arms: with the brief `progression fantasy`
    the four listings used thirteen rank words between them and three of the four reached for
    this system's own `ladder` and `rung`; with no brief at all, one rank word and none. One
    genre-brief listing came back at 59 words with twenty-two terms four readers could not cash,
    every one of them furniture — bronze, iron, rung, rank trial, bell-keeper, proctors.

    The cause is the framing plus the redundancy. This renders the brief under *"What this book
    is to be about"*, so two genre words arrive as the book's subject matter and the model
    writes the genre's furniture instead of a story. And the genre is already in the cast:
    every dossier in `writers.CAST` names what that writer reads and writes. Saying it again
    here is not direction, it is the subject line telling the writer their book is about a
    category.

    So: a brief is a story, a situation, a constraint somebody cares about — or nothing. It is
    not a shelf label.
    """
    ask = brief.strip() or "Anything you would most want to read."
    if person == "first":
        ask = f"{ask}\n{FIRST_PERSON_ASK}"
    prompt = f"What this book is to be about:\n{ask}"
    if concept:
        prompt = f"{prompt}\n\n{concept}"
    if blurbs:
        prompt = f"{blurbs}\n\n{prompt}"
    return CompletionRequest(
        prompt=prompt,
        system=_system(writer),
        max_output_tokens=MAX_OUTPUT_TOKENS,
        profile=OVERVIEW_PROFILE,
        call_class="generation",
        timeout_seconds=600.0,
    )


#: **What a title has to survive, and it is not what a listing has to survive.** Two to five
#: words, above the blurb, on a page of a hundred others, and read aloud when somebody
#: recommends the book. Written as what fails, which is the standing constraint in `house`:
#: five clauses, all prohibitions, and no list of good title shapes for a model to work
#: through.
_TITLE_TASK = (
    "You are titling the serial whose listing is below. The title is the first thing on a page "
    "of a hundred others and the only part of a book anybody has to say out loud.\n"
    "Two to five words. No subtitle, no colon, no tagline, no series number, and no quotation "
    "marks around it.\n"
    "A title that could sit on any book in this genre has failed, and so has one that needs the "
    "listing beside it to make sense.\n"
    "Answer with the title and nothing else."
)


def title_system(writer: Writer | None) -> str:
    """The title job's assembled system message, so `litharness prompts` can count it.

    It had no ceiling until 2026-08-25 because it had no name: `tests/test_prompt_budget.py`
    reads `_roles()`, and a role that is never assembled anywhere outside its own call is a
    role nobody can see the size of. That is the exact failure the budget file exists for.
    """
    return f"{writer.render()}\n\n{_TITLE_TASK}" if writer is not None else _TITLE_TASK


def render_title_request(
    overview: str,
    writer: Writer | None = None,
    taken: tuple[str, ...] = (),
    machinery: tuple[str, ...] = (),
) -> CompletionRequest:
    """One title, from the listing the same writer just wrote.

    The listing goes in the prompt and the job in the system message. Material belongs beside
    the thing it is about; a standing system instruction would give this one listing authority
    over every title the writer produces.

    **`taken` is what a lookup found already in use, and it is a prohibition.** It names
    instances, which `house`'s standing constraint is usually against — but that constraint is
    about enumerating what *succeeds*, and §138 measured the two halves separately: the
    prohibition half of all three clauses tested did its work and none of it was ever recited.
    A title that already belongs to somebody is a fact about the world, so it goes in the
    prompt beside the listing rather than into the job, where it would become a standing rule
    about titles for every book this system ever writes.

    **`machinery` is §178's and is the same shape for the same reasons.** Serial Pilot 16's
    title was *Reading The Ladder Wrong*, and `ladder` is this repository's own word for §113's
    chain — the operator's *"biggest unecessary leak of internal architechture to date"*. It
    is a prohibition, it names only the word this draw actually reached for rather than the
    whole of `house.MACHINERY_WORDS`, and it costs nothing when it is empty, which is why the
    title role's ceiling in `tests/test_prompt_budget.py` does not move: like `taken`, it is
    measured on the form with neither block present.

    Naming the word back at the writer is deliberate. The alternative — redrawing silently —
    invites the same coinage again, and §138's finding is that a prohibition does its work and
    is not recited, which is the half of that measurement `taken` has been standing on since it
    shipped.
    """
    material = f"The listing:\n\n{overview.strip()}"
    if taken:
        material += (
            "\n\nAlready the title of a published book, so it cannot be this one:\n"
            + "\n".join(f"- {name}" for name in taken)
        )
    if machinery:
        material += (
            "\n\nNot in the title, in any form: "
            + ", ".join(sorted(machinery))
            + ". That is the tooling's word for a part of the machinery, not this book's."
        )
    return CompletionRequest(
        prompt=material,
        system=title_system(writer),
        max_output_tokens=200,
        profile=TITLE_PROFILE,
        call_class="generation",
        timeout_seconds=300.0,
    )


def clean_title(text: str) -> str:
    """The title as it reaches a shelf: one line, no wrapper the model added.

    A model asked for a title alone still sometimes returns it quoted, or under a heading, or
    with a full stop. `library.slugify` would carry every one of those into a folder name and a
    chapter filename, which is where a stray quotation mark stops being cosmetic.
    """
    line = next((part.strip() for part in text.strip().splitlines() if part.strip()), "")
    line = line.lstrip("#").strip()
    for wrapper in ('"', "'", "\u201c", "\u2018", "*", "_"):
        line = line.strip(wrapper).strip()
    return line.rstrip(".").strip()


__all__ = [
    "MAX_OUTPUT_TOKENS",
    "OVERVIEW_PROFILE",
    "TITLE_PROFILE",
    "clean_title",
    "render_overview_request",
    "render_title_request",
    "title_system",
]
