"""The two things every role that writes for a reader is told, recorded once.

**Why this module exists, and it is an architecture finding rather than a style preference.**
On 2026-08-23 six forged worlds were refused by the operator and five rule changes went into
`application/architect._RULES` — a premise must be a pitch, its nouns must be explained where
they appear, its ladder must be abilities somebody keeps, its world may not be an administration.
Measured on premises, they worked: unexplained terms fell from twenty to two and the forge's
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
#: progression fantasy is you don't know where the top is"*. That is written here as a
#: reader effect rather than as a ban on ceilings, because a ban is the shape this project
#: keeps measuring as a pink elephant.
#:
#: **What the reader came for.** The measured failure this answers is one scene of eight spent
#: rendering a support call step by step — technically an opening in which somebody wants
#: something, and 1,067 words that bought the reader nothing. The simulated reader panel passed
#: that chapter with zero comprehension faults, which is why this is a second rule and not a
#: clause of the first.
READER = (
    "Spend the words on what the reader opened this book for. Detail that only establishes "
    "who somebody is — the steps of a job, the numbers on a card, the order of a routine — is "
    "worth a line rather than a scene, and if the events would be equally true with those "
    "specifics removed, remove them. Every scene moves the thing the book is about closer or "
    "further away.\n"
    "The opening shows what this book is offering: something a person could come to be able to "
    "do, and somewhere the reader has not been. A reader who reaches the end of the opening "
    "scene without seeing either has been given no reason to start another.\n"
    "The reader is measuring themselves against the offer, and that is the whole of why they "
    "are here. They should finish wanting to try it: wondering what they would be given, "
    "what they would pick, and what they would build out of it. A power with one use invites "
    "nobody in. What a reader plays with is a thing that combines with other things, that "
    "could be pushed further than anyone in the story has pushed it, and whose ceiling nobody "
    "in the world has seen.\n"
    "If the person this happens to came from somewhere like our own world, the life they came "
    "from is one a reader in their twenties has lived: a degree they are not using, a job "
    "that covers the rent, a thing they know far too much about for no professional reason.\n"
    "An exact number belongs to what this world counts and to nothing else. A puzzle box "
    "does not have thirty-one moves, a habit does "
    "not have eleven repetitions, and a wait is not four days: exactness spent on props and "
    "durations teaches a reader that the numbers here mean nothing, which costs the numbers "
    "that do."
)

#: The block as it reaches a prompt. One blank line between the two, so a role can append it to
#: its own instructions without reflowing them.
HOUSE_RULES = f"{CLARITY}\n\n{READER}"


def with_house_rules(system: str) -> str:
    """`system` with the house rules appended, or the rules alone for an empty system.

    A function rather than a constant at each call site, because every role that grew its own
    concatenation grew its own spacing, and a prompt that differs by whitespace between two roles
    is two prompts for the digest-keyed replay cache and one prompt for a reader.
    """
    body = system.strip()
    return f"{body}\n\n{HOUSE_RULES}" if body else HOUSE_RULES
