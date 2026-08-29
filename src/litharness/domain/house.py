"""The two things every role that writes for a reader is told, recorded once.

**Why this module exists, and it is an architecture finding rather than a style preference.**
On 2026-08-23 six worlds from the now-retired Forge were refused by the operator and five rule
changes went into that subsystem's private prompt — a premise must be a pitch, its nouns must be
explained where they appear, its ladder must be abilities somebody keeps, its world may not be an
administration.
Measured on premises, they worked: unexplained terms fell from twenty to two and the old prompt's
administrative vocabulary fell 25x.

Then the first book written on that world opened on 1,067 words of a call-centre shift rendered
step by step, and the operator's reading of chapter one was that *"it's like the clarity learnings
haven't been applied at all"*. They had not been. **Every one of those changes edited the
Architect, and the Writer, the outline and the planner never saw any of them** — the writer's
whole system prompt was three sentences about not writing headings. The lesson is the operator's:
*"we should definitely have the clarity feature in all subagents of our application, as it would
help put everything in the correct perspective, as well as our goal for fulfilling the readers."*

**Written once and referenced, never restated.** Nine modules in this package call a model. Text
copied into nine prompts is text that drifts in eight of them, and the repository's standing rule
about counts — one canonical home, pointers everywhere else — is the same rule for instructions.

**What this is NOT, and the boundary is `planner`'s own.** `point_of_view`'s docstring refuses to
carry an adjective because *how* to handle a protagonist is the director's to say, and "a default
here would be this system's own taste arriving in every prompt it ever renders" (§95's scope
axiom, §97.1). That boundary holds and this does not cross it: **neither rule below is a
judgment about a story.** They do not say what to write, who to like, how a scene should end, or
that anybody should win. One says a reader must be able to follow the words; the other says the
words should be spent on what the book is selling. Both are the operator's standing direction,
recorded here with their provenance so that a later reader can see they were *given* rather than
assumed — which is exactly what §95 leaves open.

**A standing constraint on every rule in this module, learned three times on 2026-08-25.**
*A rule here may say what fails. It may not enumerate what succeeds.* Each of the three was
written as an affirmative list and each came back as a verbal formula in the prose:
`READER`'s "Ranks, tallies a record would hold ... those are counted" produced nine bands,
six cords, four collar grades and nineteen licensed halls; `CLARITY`'s "a name the reader
has not met is welcome, and is how a world gets big" produced inserted undefined words; and
`ACCUMULATION`'s "a price is paid in a body, in time, in risk" produced "pays in blood, in
sleep, in years" in five listings of eight. The prohibition half of all three did its work
and none of it was ever recited.

**A fourth instance, found 2026-08-29, and it was inside this module the whole time.** The awe
clause added to `READER` later on 2026-08-25 — hours after the constraint above was written —
was itself two enumerations of what succeeds, and nobody checked the new clause against the
rule the same file had just adopted. Read 6 §4.6 is what it cost. A constraint that governs
edits is worth nothing if the next edit is not read against it, so: **before a clause ships
from here, split it with `demands` and name the sign of each half.**

**And signedness is not the whole test — a demand also has to be addressable.** The awe clause
failed in a way §138 could not predict: its permissions named a *reader state* rather than
anything on a page, so instead of overproducing they did nothing at all, and an earlier
correctly-signed prohibition took the slot. A rule here addresses a writer, and the only thing
a writer can do is put words on a page. A clause whose object is what the reader feels has no
addressee.
"""

from __future__ import annotations

#: **Corrected 2026-08-25, and the correction is the operator's.** This rule used to say
#: that every unmet word is explained where it is used *or it is not used*, and that
#: nothing is left for the reader to work out later. Read against six listings from the
#: market this project writes for, not one would survive it: `an unfeeling System... or
#: God`, `the Mark of the Crijik, a magical gift from a divine being`, `I've been reborn as
#: a WHAT?!`. The operator's reading of those was *"extremely clear and clever, I have zero
#: clarity complaints"*, which is correct and is the refutation: they are followable and
#: they explain nothing.
#:
#: What was measured was four readers quoting terms they could not cash. What got written
#: down was a ban on unexplained names, which is a larger rule and a wrong one, and it made
#: every listing an account of a rank system because an account is what the rule asked for.
#: The measured half is kept below and the generalisation is gone.
#:
#: **Corrected again the same day, in the same direction and for the same reason.** The
#: rewrite replaced a ban with an invitation, "a name the reader has not met is welcome, and
#: is how a world gets big", and the operator's next reading was *"we shouldn't be inserting
#: undefined words for no reason"*. That is the affirmative-half failure this module had
#: already been corrected for once the same day, in `READER`'s numbers clause: a rule that
#: names what a thing is *for* reads as an instruction to go and do it. What a rule here may
#: say is what fails.
#:
#: **Clarity, as measured rather than as an adjective.** `comprehension_battery` asked four
#: readers of the target genres to quote anything in a premise they could not follow, and the
#: terms they quoted were always the same shape: a word used as if the reader already knew it —
#: `frost rooms`, `keeper`, `the lists`, `nine deep`. The fix that worked on premises is the
#: sentence below, and it is what the prose never got.
CLARITY = (
    "Clarity is the floor, and it is about following rather than about explaining. Every "
    "sentence can be followed the first time it is read.\n"
    "A term the reader has not met needs a reason to be there before it needs anything "
    "else, and then a consequence rather than a definition: the sentence carrying it says "
    "what it does to somebody. What fails is a name invented because the world wanted one "
    "and handed over to be carried while it buys the reader nothing, and the test is "
    "whether they could say what it changes for the person it happens to.\n"
    "A sentence a reader can take two ways has failed, and the writer is the last person who "
    "can see it: `a sheet of directions in his brother's small hand` is handwriting to whoever "
    "wrote it and a hand inside the box to whoever reads it. Prefer the reading nobody can "
    "trip on.\n"
    "Objects do not act, speak, want, refuse or know. A box does not tell anybody anything; "
    "somebody works it out, or does not.\n"
    "A paragraph holds together or it is not a paragraph. Inside one, a pronoun points at one "
    "person only — where two are in play, use their names, however plain that reads. A reader "
    "who has to reread a paragraph to find out whose brother died has been thrown out of the "
    "book, and the sentences were all fine.\n"
    "A thing the reader cannot follow is a thing that did not happen."
)

#: **The second read, 2026-08-24, and every clause below is one line the operator quoted back.**
#: The redraft opened on a puzzle box rather than a call centre, which was the fix working, and
#: the paragraph under it failed in four ways at once: *"why is his brother inside the small
#: puzzle box?? what is going on here"* (an idiom that misparses), *"boxes don't communicate"*,
#: *"'dropped flush' isn't a phrase I heard anyone ever say"*, and *"these feel like sloppy code
#: magic numbers that are not tied to anything"*.
#:
#: **And the diagnosis that ties them together is the operator's too**: *"it's not just prose, I
#: feel like we are really lacking paragraph wide coherence."* Read against the passage that is
#: exact. `Vidor from the floor below had handed it over ... His brother had made it. His brother
#: was dead.` Every sentence is plain, C7 passes each one, and the paragraph does not say whose
#: brother died. Sentence-level craft rules cannot see that, which is why the clause below is
#: about the paragraph.
#:
#: **The clause was cut back on 2026-08-25, and the half that went was the half that
#: named what numbers are *for*.** It used to read "Ranks, tallies a record would hold,
#: quantities the world's own system keeps — those are counted, and a reader learns to
#: watch them", which is a true thing about a drafted scene and an instruction to
#: enumerate when what is being written is a listing. Four writers given the same brief
#: returned nine bands, six cords, four collar grades and nineteen licensed halls, and the
#: operator's reading was *"why the extra specific numbers"*. The prohibition below does
#: the work this clause was added for; the affirmative list was doing other work nobody
#: asked for.
#:
#: **The numbers clause is a correction of what this project meant by "numbers go up".**
#: §113 built a countable ladder and §114 an inventory; neither said where precision may
#: be spent, so the prose spent it on a box and a fortnight. The operator's words: *"I mean
#: numbers and stats that are relevant to the world system, like character sheets. We don't
#: need random objects and events to always have some unusually specific numbers tied."*

#: **The second clause below is the operator's product direction, 2026-08-25, and it had no
#: home before this.** *"we also need to create a sense of awe and limitless
#: potential/combination. the reader must be thinking omg this magic would be so cool to try
#: i wonder what I would get and pick, how will I develop it"*. The rule already said the
#: opening shows something a person could come to be able to do; it never said the reader is
#: sizing themselves against it, which is the difference between a world that is described
#: and one somebody wants to be let into.
#:
#: **It also carries the answer to a defect four listings kept**: every one of them named
#: where the top was, which the operator's first complaint was that *"part of the appeal of
#: progression fantasy is you don't know where the top is"*. ~~That is written here as a
#: reader effect rather than as a ban on ceilings, because a ban is the shape this project
#: keeps measuring as a pink elephant.~~ **The pink-elephant reasoning was refuted by §138
#: three days later** — the prohibition-only form of the clause it tested came back at 7.0
#: number tokens per thousand against the market's 7.2 and **0 of 8** listings naming a floor,
#: while the permission form ran to 47.2. A ban is the form that works; the ceiling is now
#: written as one below.
#:
#: **Corrected 2026-08-29 after read 6 §4.6, and the clause was this module's own standing
#: constraint left unapplied.** Pilot 12's chapter skimped the class menu — *"i didn't get a
#: vivid enough image of what i'm interested in, what the class options were"* — with the awe
#: clause live, the first ENFORCEMENT defect since read 4. It did not fail to be enforced; it
#: was never addressable. Of its four demands, three were permissions and two of those named
#: a **reader state** — *"they should finish wanting to try it: wondering what they would be
#: given, what they would pick, and what they would build out of it"* and *"a thing that
#: combines with other things ... whose ceiling nobody has seen"*. A reader state is not a
#: token a writer can emit, so the permission had no page surface to overproduce onto and
#: went inert instead. **That is the second axis §138 did not have**: signedness says which
#: direction a clause pushes, addressability says whether it pushes on anything at all. Both
#: of those sentences were also the enumerate-what-succeeds shape the paragraph above this
#: constant forbids, written the same day the constraint was, and never checked against it.
#:
#: **What actually occupied the slot was the compression clause, four demands earlier.** Its
#: examples named *"the numbers on a card, the order of a routine"*, which is the surface form
#: of a class menu, and it is a prohibition — correctly signed and page-addressable, against an
#: unaddressable permission. §138 predicts that outcome exactly. The instance list is gone from
#: it for the same reason (and was redundant with the numbers clause below); the offer's page
#: presence is now carried by the prohibition here, which is what a writer can act on.
#:
#: Shipped unmeasured: the effect on a drafted chapter is pilot 14's to find.
#:
#: **What the reader came for.** The measured failure this answers is one scene of eight spent
#: rendering a support call step by step — technically an opening in which somebody wants
#: something, and 1,067 words that bought the reader nothing. The simulated reader panel passed
#: that chapter with zero comprehension faults, which is why this is a second rule and not a
#: clause of the first.
#:
#: **The compression clause was teaching the defect it was blamed for, audited 2026-08-29 on
#: read 6 §4.2's named check, and the check was right.** The operator: *"I feel like i am being
#: narrated events instead of feeling present in the events."* The clause read *"is worth a line
#: rather than a scene, and if the events would be equally true with those specifics removed,
#: remove them"*, and both halves teach summary. **"A line rather than a scene" was the only
#: place in the whole assembled scene prompt that named a scene-to-summary conversion as a
#: target** — and it contradicted the drafting call's own length note two paragraphs later,
#: *"room to play out in real time ... instead of being told in summary"*, with the house floor
#: carrying the authority framing. **And the removal test was keyed to truth**: dramatisation is
#: by definition the specifics that leave the events equally true — what is said, what is
#: noticed — so a filter that deletes whatever does not change what is true deletes presence by
#: construction. This is §116's shape at a third address: the bias was in our own rule text.
#:
#: The remedy is gone and the target is kept. What sorts detail now is the movement criterion
#: the next demand already owned — *"every scene moves the thing the book is about"* — rather
#: than a truth test, and no clause anywhere now tells a writer to render a scene as a line.
#: Read 7 §4.5's *"useless information again"* is the same axis from the other side and the
#: movement criterion is the one that answers both. Shipped unmeasured.
#:
#: **The numbers clause was re-scoped 2026-08-29 as §161, and the licence it narrows is the one
#: read 8 §4.2 measured being spent on a bureaucracy.** It read *"an exact number belongs to
#: what this world counts and to nothing else"*, and the trouble is in the middle three words:
#: a guild's glasses, a ledger's entries and a tax roll are all things a world counts, so the
#: clause licensed exactness on exactly the surfaces the operator has now objected to four
#: books running. §157's scheduled beats fired twice in pilot 14 and both landed as promotions
#: inside a guild, which is what a licence this wide buys. The scope is now **what this world's
#: own system counts** — the thing the sheet renders and the status line prints — which is a
#: strictly smaller set than what the world counts, so this is a narrowing and not a new
#: permission. §138's direction holds: nothing here was made affirmative.
#:
#: **The instance list was re-aimed at the classes that actually leaked, and it did not grow.**
#: Its three instances were a prop's moves, a habit's repetitions and a wait's days, summarised
#: as *"props and durations"*. Read 8's chapter leaked days (covered), an hour (covered), a jar
#: count (**not** covered) and an age (not covered), so one instance moved from the habit —
#: which no read has ever named — to a tally, and the summary widened to match. The instances
#: are invented rather than lifted: §97.1 forbids an operator's read from becoming prompt text,
#: and a number harvested from the book under read is that laundering with the numeral left in.
#:
#: **What this clause could not address before, and now can.** §154's second axis is that a
#: demand naming something the writer cannot put on a page lands with its sign multiplied by
#: zero. *"What this world counts"* named no artifact the drafting call had ever shown a
#: writer — the referent was empty, so the exclusion had nothing to exclude *toward* and
#: precision went where precision always goes. §158 made the status line reach the writer
#: filled, and §161's furniture contract puts it on the page at the moment a number moves; the
#: licence half of this clause now points at something the writer is holding. That is the whole
#: of why a re-scope is worth more here than another prohibition would be. Shipped unmeasured,
#: and its effect is Track 3's mundane-precision census to find, not this module's to claim.
#:
#: **Narrowed once more the same day as §166, because §161's scope licensed the sentence the
#: operator then called wrong.** On pilot 15's chapter: *"numbers should only come up when
#: talking about skills and ability level reached. outside of that numbers shouldn't come up
#: more than any other book"*, extended minutes later to *"classes as well, litrpg elements"*.
#: The offending sentence spoke a town's count of its own repairs — and that quantity is a
#: column of the book's own printed line, so the world's own system does count it and §161's
#: scope permitted it. **The licence therefore splits by surface rather than by quantity**: the
#: printed line carries every quantity the sheet holds, aggregates included, and prose speaks a
#: number only where the system counts it in a person. One and the same figure is furniture and
#: is not prose, which no wording of *what the system counts* could have separated.
#:
#: **Why the object is "in a person" rather than a list of what may be spoken.** The included
#: side the operator named runs skills, levels, classes and the genre's own elements; writing
#: those four down would be the instance-list shape this module has been corrected for twice,
#: and an enumeration of what SUCCEEDS besides — the constraint adopted here on 2026-08-25,
#: which §154 caught the awe clause breaking hours after it was written. What the four share is
#: not their kind but their address: the system counts them **in a person**, where a world's
#: tally of itself is counted in the world. The clause reaches numerals only, so a class *name*
#: is not governed by it at all and nothing here stops one being spoken.
#:
#: **The furniture is named inline, which is §161.5's third surgery pattern at its second use.**
#: A scope narrowed to the person alone would forbid the very line `application/planner.py`
#: renders filled a few paragraphs later, and four books have failed for want of that line being
#: distinguishable from narration. An exemption written as its own sentence would be a
#: permission, and §138 measured a permission-only clause returning more than six times what a
#: prohibition-only one did, worse than silence. Hung off a semicolon inside the sentence it
#: delimits instead of permitting, and `house.demands` still reads one clause — so no ceiling
#: moved. For the roles that never see a status line the referent is empty and by §154 it lands
#: as a delimiter with nothing to delimit: inert, which is the right behaviour for a call that
#: prints no line.
#:
#: **The instance list did not grow, for §161.8's reason unchanged.** A town's tally of its own
#: repairs is a tally, which the summary already names, and the scope sentence is the half §138
#: says gets obeyed; a fourth instance stays refused. The two classes §161.8 left uncovered — an
#: age, an almanac ordinal — are uncovered still and still fall under the scope sentence. No
#: numeral or phrase from the chapter under read is in the clause (§97.1); the chapter is a test
#: fixture and nothing more. Shipped unmeasured: §162's non-genre distributions are what a later
#: census would read this against, and no number of theirs is in any prompt.
READER = (
    "Spend the words on what the reader opened this book for. Detail that only establishes "
    "who somebody is — the steps of a job, the order of a routine — is not why the reader "
    "came. Every scene moves the thing the book is about closer or further away.\n"
    "The opening shows what this book is offering: something a person could come to be able to "
    "do, and somewhere the reader has not been. A reader who reaches the end of the opening "
    "scene without seeing either has been given no reason to start another.\n"
    "The reader is measuring themselves against the offer, and that is the whole of why they "
    "are here. A power with one use invites nobody in, and neither does one the reader meets "
    "as a summary of what it could be rather than on the page. A story that names its own "
    "ceiling has told the reader where to stop.\n"
    "If the person this happens to came from somewhere like our own world, the life they came "
    "from is one a reader in their twenties has lived: a degree they are not using, a job "
    "that covers the rent, a thing they know far too much about for no professional reason.\n"
    "An exact number belongs to what this world's own system counts in a person and to "
    "nothing else; the line the book itself prints is not prose. A "
    "puzzle box does not have thirty-one moves, a crate does "
    "not hold forty-two bottles, and a wait is not four days: exactness spent on props, "
    "tallies and durations teaches a reader that the numbers here mean nothing, which costs "
    "the numbers that do."
)

#: **What the reader is accumulating, and it is the genre's own economics.** The operator,
#: 2026-08-25, on a listing whose magic was a word spoken once and used up: *"think of
#: progression fantasy/litrpg readers as dragons hoarding gold, instead of hoarding gold they
#: like to hoard perma abilities and passive effects. Losing words goes against this."*
#:
#: `READER` above asks for an offer that combines and whose ceiling nobody has seen. Neither
#: is *keeping*, and a power that is spent combines with nothing and reaches no ceiling. This
#: is written as what fails rather than as what to do, which is the correction this module
#: has already taken three times in one day, and as ONE sentence because it lands in every
#: role that stands on the floor: at three sentences it moved the scene writer from 27
#: demands to 30 and the Architect from 41 to 44 for a single idea.
#:
#: **Its second half was cut the day it shipped, for being recited.** It ended "and a price
#: is paid in a body, in time, in risk or in somebody now against them", and the next eight
#: listings contained "pays in sleep, in blood", "pays in blood, in sleep", "costs him
#: blood, sleep, and years", "pays, in blood weight and in sleep" and "will pay in blood,
#: in years" — five of eight, against zero of ten in the market's own listings.
ACCUMULATION = (
    "A power that is spent, used up or traded away costs the reader the thing they came "
    "for: what this genre's reader collects is what the person KEEPS."
)

#: The block as it reaches a prompt. One blank line between the two, so a role can append it to
#: its own instructions without reflowing them.
HOUSE_RULES = f"{CLARITY}\n\n{READER}\n\n{ACCUMULATION}"


#: The vocabulary this system uses for its own machinery. **Text that shapes prose a reader
#: will read may not contain any of it**, and `tests/test_prompt_budget.py` is what enforces
#: that. Twice measured: `standing` reached a chapter as *"hotter than a girl at her standing
#: should be able to manage"* (§120), and the reader personas built to catch that were
#: themselves written to read for *"what the next rung costs"*, so they rewarded the register
#: they existed to detect.
#:
#: Schema-filling and tool-teaching prompts are exempt and have to be: a call that fills
#: `manifests_as` must name it, and a command list must name its commands. The boundary is
#: what the text shapes, not where it lives.
MACHINERY_WORDS: frozenset[str] = frozenset(
    {
        "rung",
        "rungs",
        "ladder",
        "standing",
        "criterion",
        "criteria",
        "manifests_as",
        "cardinality",
        "order_key",
        "logical_id",
        "predicate",
        "object_ref",
        "story_position",
        "reveal_scene",
        "entity_role",
        "graph_line",
        "packet",
        "canon",
    }
)


def demands(text: str) -> tuple[str, ...]:
    """Every separate thing a piece of instruction text asks for.

    A sentence, and a line break also ends one, because these rules are written as stacked
    clauses and a clause is a demand whether or not it was punctuated as a sentence.

    **Crude on purpose and it does not need to be otherwise.** What it is for is a ceiling
    nobody can raise by accident: measured 2026-08-25, the house floor alone is twenty-four
    demands, the scene writer is twenty-seven before anything conditional is appended, and
    the Architect is forty-one. None of those numbers existed before this function did, and
    the operator's standing instruction about not piling rules on rules had no way to be
    checked against anything.
    """
    import re

    return tuple(
        part.strip()
        for line in text.split("\n")
        for part in re.split(r"(?<=[.!?])\s+", line)
        if part.strip()
    )

def with_house_rules(system: str) -> str:
    """`system` with the house rules appended, or the rules alone for an empty system.

    A function rather than a constant at each call site, because every role that grew its own
    concatenation grew its own spacing, and a prompt that differs by whitespace between two roles
    is two prompts for the digest-keyed replay cache and one prompt for a reader.
    """
    body = system.strip()
    return f"{body}\n\n{HOUSE_RULES}" if body else HOUSE_RULES
