"""Stage-0 §183: the house genre reaches the call that invents the premise, and it goes as a floor.

**The gap.** The house genre is mandatory and `domain/genre.py` refuses a book that cannot speak
system voice — but that floor sits at the *seed*, which runs after a premise exists, and the
listing is the promise a reader buys. Nothing in `application/overview._TASK` said which kind of
book was being sold, so a writer whose dossier is not system-shaped sold its shelf flavour: light
fantasy (pilot 13), sci-fi horror with no interface in it (pilot 18), an institution's paperwork
twice (pilot 17, refused on its own ground and sharing this surface). Three refusals in one day
at one call.

**Why this file rather than `tests/test_genre_floor.py`.** That file is the seed floor: canon,
records, and a run that stops. This one is the promise, and its assertions are about prompt text.
The two are one constraint at two altitudes and neither restates the other's sentence, which is
what `test_the_seed_s_refusal_sentence_is_not_restated_in_the_listing` holds.

**The hazard this file mostly exists for.** §136 measured two words of genre-as-brief outweighing
every rule in this prompt. The floor is not that: it names no shelf label, nothing is put in the
brief field, and an empty brief is still empty. Each of those is asserted below, because a clause
that comes back wearing any of them is §136 again wearing this entry's clothes.

No model reads, ranks or judges anything here, and no bar is declared anywhere in it.
"""

from __future__ import annotations

import pytest

from litharness.application import overview, readers, recruiter
from litharness.domain import genre, house
from litharness.domain import writers as writers_domain

#: The demand §183 added, held by its two operative halves rather than by the whole sentence, so
#: a later rewording of its terminator does not have to edit an assertion about the constraint.
_OPENS_AND_READS = "opens something and reads their own capabilities in it"
_NAMES_A_GAIN = "names one of them they did not have before"

#: The clause the floor stands in front of, and the reason the floor was needed at all: it asks a
#: listing to be plain about whatever furniture it has, which any kind of book satisfies.
_NAME_IT_PLAINLY = "name the magic, the system, the monsters, the dungeon in plain words"

#: The prohibition that governs the gain, three clauses above it. Dropping it would turn *one of
#: them they did not have before* into a licence for the countable fittings §136 measured.
_NO_EXACTNESS = "Exactness spent on floors, ranks, counts and lengths of time"

#: The operator's own words on this constraint, which live in `plan/house-genre-constraint.md`
#: and may not travel (§97.1). Fragments rather than whole quotes, because a fragment is what a
#: paraphrase would carry.
_OPERATOR_WORDS = (
    "we shouldn't be writing any books",
    "feel progress and potential",
    "as soon as possible",
    "constant and regular",
    "dopamine",
)


def _writing_roles() -> dict[str, str]:
    """Prompt text that decides what gets written.

    `overview._TASK` is not assembled through `house.with_house_rules`, which is the fact this
    whole entry turns on, so it is listed by hand rather than derived from the floor. The
    Recruiter is here despite being a tool essay because it made this same refusal at its own
    address on 2026-08-29, and what it writes rides in every scene call its writer ever makes.

    **The two reader pools are deliberately not here, and the boundary is §136's own.** That
    measurement is about a shelf label arriving where a book's subject matter is decided; a
    persona saying what its owner reads is a fact about who is answering, not an instruction
    about what to write, and both pools have named this genre since they were written. A rail
    that refused them would be refusing a reader for being a reader of it.
    """
    return {
        "house floor": house.HOUSE_RULES,
        "listing task": overview._TASK,
        "title task": overview._TITLE_TASK,
        "recruiter": (
            recruiter.render_recruit_request("cozy-fantasy", shape="single-image").system or ""
        ),
    }


def _every_prompt() -> dict[str, str]:
    """Every surface §97.1 reaches: what writes a book and what reads one back."""
    return {
        **_writing_roles(),
        "measurement reader": readers.pool(readers.MEASUREMENT)[0].system(),
        "steering reader": readers.pool(readers.STEERING)[0].system(),
    }


def _clause() -> str:
    (found,) = [
        item for item in house.demands(overview._TASK) if _OPENS_AND_READS in item
    ]
    return found


def test_the_house_genre_is_one_demand_of_the_listing_task() -> None:
    """One sentence, one demand, and the ceiling that paid for it knows about it.

    `house.demands` splits on sentences and line breaks, so a clause written as two lands as two
    and a ceiling raised for one would be short by one. `tests/test_prompt_budget.py` is where
    the raise from 17 to 18 is argued; this is what says the raise bought what it was argued for.
    """
    assert _clause()


def test_the_clause_carries_both_halves_of_the_floor() -> None:
    """The furniture exists in the promise, and a gain on it is on the page rather than deferred.

    `plan/house-genre-constraint.md` names both and this project has one sentence for them,
    because a listing failing either is refused at the same gate for the same reason. A later
    edit keeping one half and dropping the other would leave a clause that reads whole and
    refuses half of what it was written for.
    """
    clause = _clause()
    assert _OPENS_AND_READS in clause
    assert _NAMES_A_GAIN in clause


def test_the_house_genre_reaches_a_prompt_as_its_floor_and_never_as_its_name() -> None:
    """§136's finding, applied to the entry that had the most reason to ignore it.

    Two words of shelf label under *"What this book is to be about"* outweighed every rule in
    this prompt: thirteen rank words across four listings and this system's own vocabulary coined
    in three of four. `application/recruiter.py` reached the same conclusion at its own address
    on 2026-08-29. What a prompt may carry is the mechanical property every book this house
    drafts has; the name of the shelf is a fact about the house and stays out.
    """
    named = sorted(
        role
        for role, text in _writing_roles().items()
        if genre.HOUSE_GENRE.lower() in text.lower()
    )
    assert not named, (
        f"{named} name the house genre by its label. §136 measured two such words outweighing "
        "every rule in the prompt they arrived in; what a prompt carries is the floor."
    )


def test_the_brief_field_is_untouched_and_an_empty_brief_is_still_empty() -> None:
    """The control §136 kept, and the half of it that survives this entry.

    The constraint is a standing property of the job, so it lives in the system message and
    applies identically in both arms. Nothing is put in the brief field: a briefed book and an
    unbriefed one still differ by exactly what somebody asked for, which is the comparison the
    control exists to make. What the floor does change is genre presence in both arms, and that
    is §183's business rather than this field's.
    """
    empty = overview.render_overview_request("")
    assert empty.prompt == (
        "What this book is to be about:\nAnything you would most want to read."
    )
    assert genre.HOUSE_GENRE.lower() not in empty.prompt.lower()
    briefed = overview.render_overview_request("a lighthouse that owes somebody a favour")
    assert briefed.system == empty.system


def test_the_clause_names_no_reader_and_no_state_a_reader_is_in() -> None:
    """§154's addressability check, run before the clause shipped rather than after a read.

    A rule in a prompt addresses a writer, and the only thing a writer can do is put words on a
    page. Both halves of this one name page facts — a thing that is opened and read, and a gain
    the promise states — so there is something to do about it. *The reader should feel progress*
    is the same direction with no addressee, and it is what this clause is deliberately not.
    """
    assert "reader" not in _clause().lower()


def test_the_clause_asks_for_no_quantity_and_the_prohibition_that_says_so_still_stands() -> None:
    """The gain is a capability and never a number, and the pair is what keeps it that way.

    §138 measured the numbers prohibition at 7.0 tokens per thousand words against a permission's
    47.2 and a market's 7.2, and §136's worst listing was furniture with numbers on it — bronze,
    iron, rank trial. A gain stated as a quantity is that failure with a new door, so the clause
    holds no digit and the prohibition three clauses above it is asserted here as its pair.
    """
    assert not any(character.isdigit() for character in _clause())
    assert _NO_EXACTNESS in overview._TASK


def test_the_clause_supplies_no_word_of_this_system_s_own_vocabulary() -> None:
    """§178's return-side check stays meaningful only if this prompt hands over no name.

    Pilot 16's listing coined *the Ladder* on its own, from a prompt containing none of these
    words, and the title, four world records and a printed column carried it. The clause says
    *something* and names no object, so what a book calls the thing it prints is the book's, and
    a name refused downstream is a name the model reached for rather than one we supplied.
    `tests/test_prompt_budget.py` runs the same rail over the whole assembled prompt; this is the
    clause-level statement of why this particular sentence has a hole in it where a noun would go.
    """
    lowered = _clause().lower()
    found = sorted(word for word in house.MACHINERY_WORDS if word in lowered)
    assert not found, f"the house-genre clause speaks this system's own vocabulary: {found}"


def test_the_floor_stands_before_the_clause_that_says_how_to_name_it() -> None:
    """Order is the argument: what the book has, then how to put it in plain words.

    The neighbouring clause is genre-agnostic by construction — any kind of book satisfies *what
    kind of book this is*, and its four nouns read as instances of what to say plainly rather
    than as things a book must contain. Pilot 18's listing named none of them and broke no rule.
    Placed after it, the floor would read as a fifth item on that menu, which is the shape §138
    measures getting recited; placed before it, the menu is the floor's *how*.
    """
    ordered = house.demands(overview._TASK)
    floor = next(index for index, item in enumerate(ordered) if _OPENS_AND_READS in item)
    plainly = next(index for index, item in enumerate(ordered) if _NAME_IT_PLAINLY in item)
    assert floor < plainly


def test_the_seed_s_refusal_sentence_is_not_restated_in_the_listing() -> None:
    """One constraint, two altitudes, and two sentences that do not try to be each other.

    `genre.NO_SHEET` is what a book is refused with when its canon cannot speak system voice, and
    it is already one string on two surfaces by that module's own design. A third copy here would
    be a second answer to what the listing must promise, drifting from the first the moment
    either is edited — the counts-have-one-home rule applied to instruction text.
    """
    assert genre.NO_SHEET not in overview._TASK
    assert genre.NO_SHEET not in overview._system(writers_domain.CAST["ferreira"])


@pytest.mark.parametrize("fragment", _OPERATOR_WORDS)
def test_no_word_of_the_operator_s_genre_direction_became_prompt_text(fragment: str) -> None:
    """§97.1: the operator's reads are direction where direction enters and never prompt text.

    The direction behind this entry is quoted in `plan/house-genre-constraint.md` and in the
    ledger, which is where an operator's words live. A prompt carries the structural consequence
    and nothing else — and the timing half in particular is a schedule in `domain/genre.py`
    rather than an instruction to make anything felt, which is the hazard that document named
    before anybody drafted a clause.
    """
    named = sorted(role for role, text in _every_prompt().items() if fragment in text.lower())
    assert not named, f"{named} carry the operator's own words ({fragment!r})"
