"""The book overview: what a reader sees before they open chapter one, and who writes it.

**This is the forge's job without the forge.** A world used to be assembled by an Architect with
its own identity and its own rule essay, K at a time, and an operator picked one — which is a
human production step, and §126's objective is fiction produced *without* a human production
loop. The operator, 2026-08-24: *"we just don't need a forge"*, and *"we need to pass to the
writer we are writing book overview and they are tasked in creating a compelling idea readers
will love (with a hook). But the core loop of feedback should be the same (simulated reader)."*

So: one writer from `writers.CAST`, one overview, and the same two-pool readership that reads
the chapters. Nothing here ranks anything and nothing chooses between candidates — there are no
candidates. The steering pool says what it hoped the book would be; the writer revises; the
measurement pool, which never steers, says whether it would open chapter one.

**The task text is deliberately short.** Three rules in `architect._RULES` were assertions about
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

from litharness.domain.generation import CompletionRequest
from litharness.domain.writers import Writer

#: Frozen profiles, one per stage, so a draft and a revision are separable on the decision rows.
OVERVIEW_PROFILE = "writer.overview.v0"
REVISION_PROFILE = "writer.overview.revise.v0"
TITLE_PROFILE = "writer.title.v0"

MAX_OUTPUT_TOKENS = 4000

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
_TASK = (
    "You are writing the listing for a new serial: the few lines a reader meets on the front "
    "page of a serial-fiction site, and the only thing that decides whether they open chapter "
    "one.\n"
    "A reader meeting this has not started the book. Open where the trouble already is: not on "
    "an account of the world, and not on an introduction to whoever it happens to.\n"
    "Exactness spent on floors, ranks, counts and lengths of time is space the hook needed.\n"
    "A sentence a reader can take two ways has failed, and so has one that asserts what nobody "
    "in the story could know yet.\n"
    "A reader scanning a list has to see what kind of book this is and what the person is "
    "after: name the magic, the system, the monsters, the dungeon in plain words rather than "
    "implying them, and say what the person is trying to get.\n"
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


def render_overview_request(brief: str, writer: Writer | None = None) -> CompletionRequest:
    """One overview, from a brief that may be empty.

    An empty brief is legitimate and is the control the old forge kept for the same reason: a
    book built from no direction at all is what a directed one is read against.

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
    return CompletionRequest(
        prompt=f"What this book is to be about:\n{ask}",
        system=_system(writer),
        max_output_tokens=MAX_OUTPUT_TOKENS,
        profile=OVERVIEW_PROFILE,
        call_class="generation",
        timeout_seconds=600.0,
    )


def render_revision_request(
    brief: str, overview: str, direction: str, writer: Writer | None = None
) -> CompletionRequest:
    """The same writer, the same job, having heard what readers hoped it would be.

    **The direction goes in the prompt rather than the system message**, and that is the one
    thing this does differently from `planner.render_prompt`. §133 measured a wish list rendered
    into a system prompt at 5,476 characters against 2,920 — two thirds of everything the writer
    was told — and the draft that came back serviced it. Here the reader material sits beside
    the thing it is about, where it reads as what people said rather than as the instructions.
    """
    ask = brief.strip() or "Anything you would most want to read."
    return CompletionRequest(
        prompt=(
            f"What this book is to be about:\n{ask}\n\n"
            f"The listing you wrote:\n{overview.strip()}\n\n"
            f"{direction}\n\n"
            "Write the listing again."
        ),
        system=_system(writer),
        max_output_tokens=MAX_OUTPUT_TOKENS,
        profile=REVISION_PROFILE,
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
    overview: str, writer: Writer | None = None, taken: tuple[str, ...] = ()
) -> CompletionRequest:
    """One title, from the listing the same writer just wrote.

    The listing goes in the prompt and the job in the system message, which is
    `render_revision_request`'s arrangement and for its reason: §133 measured reader material
    rendered into a system prompt at two thirds of everything the writer was told, and what
    came back serviced it. Material belongs beside the thing it is about.

    **`taken` is what a lookup found already in use, and it is a prohibition.** It names
    instances, which `house`'s standing constraint is usually against — but that constraint is
    about enumerating what *succeeds*, and §138 measured the two halves separately: the
    prohibition half of all three clauses tested did its work and none of it was ever recited.
    A title that already belongs to somebody is a fact about the world, so it goes in the
    prompt beside the listing rather than into the job, where it would become a standing rule
    about titles for every book this system ever writes.
    """
    material = f"The listing:\n\n{overview.strip()}"
    if taken:
        material += (
            "\n\nAlready the title of a published book, so it cannot be this one:\n"
            + "\n".join(f"- {name}" for name in taken)
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


def _bullets(items: tuple[str, ...]) -> str:
    """A list under a heading, one line each. One place, so two blocks cannot drift."""
    return "\n" + "\n".join(f"- {item}" for item in items)


def render_appetite(
    felt: tuple[str, ...], expect_next: tuple[str, ...], want_next: tuple[str, ...]
) -> str:
    """Where the listing left the steering pool, as the writer reads it. Empty when nobody read.

    `readers.Anticipation.render`'s block for the blurb stage, and the rewrite of 2026-08-25 is
    that entry's: the two questions this used to render — what a reader hoped the book would be
    and what would make them drop it — are specifications of an artifact, and a writer handed
    fifty of them writes them down. Measured on *Patch Notes For Earth*: four readers asked for
    version numbers, nerfs, a changelog and repro steps, and the revision put all four on the
    page.

    Reported as what readers said and never as an instruction, which was always this function's
    rule; what changed is that the material can no longer *be* an instruction.
    """
    if not (felt or expect_next or want_next):
        return ""
    blocks = ["READERS WHO SAW ONLY THIS LISTING, ASKED WHERE IT LEFT THEM."]
    if felt:
        blocks.append("It left them:" + _bullets(felt))
    if expect_next:
        blocks.append("They think this book is:" + _bullets(expect_next))
    if want_next:
        blocks.append("They want to happen:" + _bullets(want_next))
    return "\n\n".join(blocks)


__all__ = [
    "MAX_OUTPUT_TOKENS",
    "OVERVIEW_PROFILE",
    "REVISION_PROFILE",
    "TITLE_PROFILE",
    "clean_title",
    "render_appetite",
    "render_overview_request",
    "render_revision_request",
    "render_title_request",
    "title_system",
]
