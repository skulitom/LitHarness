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

from litharness.domain import house
from litharness.domain.generation import CompletionRequest
from litharness.domain.writers import Writer

#: Frozen profiles, one per stage, so a draft and a revision are separable on the decision rows.
OVERVIEW_PROFILE = "writer.overview.v0"
REVISION_PROFILE = "writer.overview.revise.v0"

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
#: So this call does not go through `writers.system_for`: the house floor governs the book's
#: prose, and a listing is not the book's prose.
_TASK = (
    "You are writing the listing for a new serial: the few lines a reader meets on the front "
    "page of a serial-fiction site, and the only thing that decides whether they open chapter "
    "one.\n"
    "A reader meeting this has not started the book. Open where the trouble already is: not on "
    "an account of the world, and not on an introduction to whoever it happens to.\n"
    "A reader scanning a list has to see what kind of book this is and what the person is "
    "after: name the magic, the system, the monsters, the dungeon in plain words rather than "
    "implying them, and say what the person is trying to get.\n"
    "An exact number is worth its space only where the world itself counts it: exactness "
    "spent on props, distances and durations is space the hook needed.\n"
    "No title, no headings, no tags, no word about the author, and no dashes: this market's "
    "listings punctuate with full stops and commas. About a hundred words."
)


def _system(writer: Writer | None) -> str:
    """Who is writing, then the job. No scene floor: see `_TASK`.

    `house.ACCUMULATION` is referenced rather than restated. It is the one clause of the
    floor a listing genuinely needs — a mechanic that spends its own capability is the
    thing this genre's reader is least here for — and one object with two callers is what
    keeps it from becoming two rules that drift.
    """
    body = f"{_TASK}\n{house.ACCUMULATION}"
    return f"{writer.render()}\n\n{body}" if writer is not None else body


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


def render_appetite(hoping_for: tuple[str, ...], dreading: tuple[str, ...]) -> str:
    """What the steering pool said, as the writer reads it. Empty when nobody wanted anything.

    Reported as what readers said, never as an instruction — `readers.Anticipation.render`'s
    rule, and the same reason: the writer decides what to do about it.
    """
    if not hoping_for and not dreading:
        return ""
    blocks = ["READERS WHO SAW THIS LISTING, ASKED WHAT THEY HOPED THE BOOK WOULD BE."]
    if hoping_for:
        blocks.append("Hoping for:\n" + "\n".join(f"- {item}" for item in hoping_for))
    if dreading:
        blocks.append(
            "Would drop it by chapter three for:\n"
            + "\n".join(f"- {item}" for item in dreading)
        )
    return "\n\n".join(blocks)


__all__ = [
    "MAX_OUTPUT_TOKENS",
    "OVERVIEW_PROFILE",
    "REVISION_PROFILE",
    "render_appetite",
    "render_overview_request",
    "render_revision_request",
]
