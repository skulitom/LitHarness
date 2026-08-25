"""The simulated readership: where a passage left it, what it expects, and what it stays for.

Two calls, two disjoint sets of readers, and the split is the whole safety argument.

**Every reader is stopped part-way through.** The operator, 2026-08-25: *"The readers should be
fed text only up until a point and then the rest left out. The readers have to predict what
happens next."* `domain/text.stop_point` is where the cut falls — §124's registered rule, a
paragraph boundary near 60% of the words, never mid-thought and never the whole thing. A reader
given the end has no future to predict and nothing left to want, so what it produces instead is
an assessment.

**Measurement readers** spend a currency. Behaviour rather than a verdict, because §89 measured
the verdict channel running 4,676x position over text and §97.4 states that no verdict slot
exists anywhere in a sim. The currency is not decoration: §94's continuation saturated at 195 of
196 because continuing was free, and §134 recorded five more rounds between 13/16 and 16/16 with
a scarcity clause that named no competitor. Now there is one — a real published book that
cleared `domain/rivals.admit` — and the two lanes use it differently, because a reader uses it
differently. Browsing a front page you see several blurbs at once, so `render_pick_request`
shows two, unlabelled and order-swapped. Part-way into a chapter you have not opened the other
book, so `render_choice_request` names it and does not show it: *"if they read a new overview,
they miss out on reading our book"*.

**Steering readers** say where the passage left them, what they think happens next, and what
they want to happen. Not what they think of it — the operator, 2026-08-25: *"The readers
shouldn't critique what is already written that's for the writers to do."* That prohibition has
a measured cause and it is the most expensive thing in this module's history: on *Patch Notes
For Earth* four steering readers asked for *"a real changelog with version numbers, nerfs"* and
*"repro steps, edge cases"*, and the revision put six of the operator's seven quoted defects
into a hundred-word listing, every one of them absent from the draft those readers had seen.
The channel handed the writer vocabulary and the writer transcribed it.

It is still E6 — naming what is there — which is the one elicitation frame that survived
§87-§89, and it still needs no counter and no axis, which is why it can carry what the deleted
prose-axis loop could not: the operator's *"understand anticipation of the simulated readers to
predict and provide what the reader secretly or not so secretly desires"*.

**Nobody is in both sets.** A claim about prose shaped by the readers who then judge it is
circular, which is what §97.1 always guarded and what `pools.py` enforced in 189 lines. Here it
is two frozen rosters and one assertion, because a reader's pool is decided when it is written
down rather than drawn. It now carries a second load: a rival is published prose, so the same
refusal keeps RS1's corpus firewall between somebody else's book and a writing prompt.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from litharness.domain.generation import CompletionRequest

#: Frozen profiles, one per lane, so the two spends are separable on the decision rows.
CONTINUE_PROFILE = "reader.continue.v0"
ANTICIPATE_PROFILE = "reader.anticipate.v0"
#: The blurb stage's two, kept separate from the chapter stage's so the spends are
#: separable on the decision rows and so a mixed run cannot be read as one number.
START_PROFILE = "reader.start.v0"
APPETITE_PROFILE = "reader.appetite.v0"

CALL_CLASS = "generation"

#: What a reader is told they have left. Small on purpose: an unbounded reader continues out of
#: politeness, which is the failure §94 measured.
BUDGET_CHAPTERS = 2

STEERING = "steering"
MEASUREMENT = "measurement"


@dataclass(frozen=True, slots=True)
class Reader:
    """One avid genre reader. `pool` is fixed here and may not be chosen at call time."""

    reader_id: str
    pool: str
    reads_for: str
    drops_on: str

    def system(self) -> str:
        return (
            f"You read a lot of LitRPG and progression fantasy — several serials at once, and "
            f"you drop most of what you start. You read for {self.reads_for}. You stop reading "
            f"on {self.drops_on}. You answer as yourself, in your own words, briefly."
        )


#: Eight readers, four a side, and the two halves are the same four people so that a
#: difference between the lanes is never a difference in who was asked.
#:
#: **Written in a reader's words and not in this repository's.** The first roster read for
#: "a climb with rules — what the next rung costs", which is `domain/worlds.py` vocabulary
#: put in a reader's mouth; it then reported back the same words as praise, and every number
#: measured with it leaned toward books that talked like the schema. Nothing below is a term
#: this system uses for its own machinery.
READERS: tuple[Reader, ...] = (
    Reader(
        "power_s", STEERING,
        "watching somebody go from nothing to genuinely dangerous, and getting to feel every "
        "jump on the way",
        "a main character who is already the strongest thing in the room on page one",
    ),
    Reader(
        "elsewhere_s", STEERING,
        "getting dropped somewhere impossible and working out how it runs at the same time the "
        "character does",
        "names and titles thrown around like I am supposed to already know them",
    ),
    Reader(
        "magic_s", STEERING,
        "the magic itself — what it actually does, how strange it gets, and somebody working "
        "out a use for it that nobody else had",
        "a world where the magic turns out to be a job with forms to fill in",
    ),
    Reader(
        "binge_s", STEERING,
        "somewhere I want to keep coming back to, people I like being around, and the next good "
        "thing always close enough to reach",
        "misery with nothing to look forward to, or a book that skips the part it told me to "
        "care about",
    ),
    Reader(
        "power_m", MEASUREMENT,
        "watching somebody go from nothing to genuinely dangerous, and getting to feel every "
        "jump on the way",
        "a main character who is already the strongest thing in the room on page one",
    ),
    Reader(
        "elsewhere_m", MEASUREMENT,
        "getting dropped somewhere impossible and working out how it runs at the same time the "
        "character does",
        "names and titles thrown around like I am supposed to already know them",
    ),
    Reader(
        "magic_m", MEASUREMENT,
        "the magic itself — what it actually does, how strange it gets, and somebody working "
        "out a use for it that nobody else had",
        "a world where the magic turns out to be a job with forms to fill in",
    ),
    Reader(
        "binge_m", MEASUREMENT,
        "somewhere I want to keep coming back to, people I like being around, and the next good "
        "thing always close enough to reach",
        "misery with nothing to look forward to, or a book that skips the part it told me to "
        "care about",
    ),
)


def pool(name: str) -> tuple[Reader, ...]:
    return tuple(reader for reader in READERS if reader.pool == name)


#: Behaviour, not a verdict. The three words are the BCR's (§97.4) and nothing else is offered.
CHOICE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["next", "because"],
    "properties": {
        "next": {
            "type": "string",
            "enum": ["carry_on", "put_it_down", "come_back_later"],
            "description": "What you actually do with your remaining reading time.",
        },
        "because": {
            "type": "string",
            "description": "One sentence, in your own words. Not a review.",
        },
    },
}

#: **What a reader is for, rewritten 2026-08-25 on the operator's direction.** *"From the
#: readers we want to read their emotions about what they read, and find out what they predict
#: and want to happen next"*, and the half that is a prohibition: *"The readers shouldn't
#: critique what is already written — that's for the writers to do."*
#:
#: **The field that went is `dreading`, and it is why this rewrite happened.** Measured on
#: *Patch Notes For Earth*: four steering readers asked for *"a real changelog with version
#: numbers, nerfs"*, *"not 'he's good at games' but repro steps, edge cases"* and *"an
#: interaction between two stated rules"*, and the revision put **six of the operator's seven
#: quoted defects** into a hundred-word listing — every one of them absent from the draft the
#: readers had seen. The channel handed the writer vocabulary and the writer transcribed it.
#: That is §138's finding at one level up: reader material rendered as *"it outranks every
#: craft rule you have been given"* is a maximal permission, and a permission is recited.
#:
#: A want and a prediction are about the story. A critique is about the artifact, and it is the
#: form that carries nouns. So the schema below can hold the first two and cannot hold the
#: third: there is no field for what should have been done differently, and no field a reader
#: can put a craft instruction in without lying about what the field is for.
ANTICIPATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["felt", "expect_next", "want_next"],
    "properties": {
        "felt": {
            "type": "string",
            "description": "What reading this did to you, in your own words. How it left you "
                           "feeling, not what you think of it and not how it could be better.",
        },
        "expect_next": {
            "type": "string",
            "description": "What you think actually happens next. Say it as a prediction.",
        },
        "want_next": {
            "type": "array",
            "items": {"type": "string"},
            "description": "What you find yourself wanting to happen next. Things that could "
                           "happen in the story, never things the writing should do.",
        },
    },
}

#: **The currency, and it is one slot rather than a vague sufficiency.** The operator, 2026-08-25:
#: *"the readers have a specific amount of currency they can spend either reading our text or a
#: tantalizing alternative"*. §94 measured continuation at 195 of 196 because carrying on was
#: free, and the four rounds after it ran 13/16 to 16/16 with a scarcity clause that named no
#: competitor. An unspent hour is not scarce; an hour that has somewhere else to go is.
_CURRENCY = (
    "You have one reading hour left today and two things you could spend it on. Spending it "
    "on one is not spending it on the other."
)


def _two_up(ours: str, rival: str, ours_first: bool) -> str:
    """Two listings on one page, in the order the draw put them, neither labelled as ours.

    **Unlabelled and swapped, because otherwise this measures position.** §89 clocked a verdict
    channel running 4,676x position over text, and a reader told which book is the house's own
    is not choosing between books. `rivals.ours_first` derives the order from the same content
    key the rival was drawn with, so it varies, replays identically, and is recorded on the
    decision as a covariate rather than assumed away.

    **Side by side is right here and wrong for the continuation**, and the difference is what a
    reader actually has in front of them. Somebody browsing a front page sees several blurbs at
    once; somebody part-way into a chapter has not opened the other book. See
    `render_choice_request`.
    """
    first, second = (ours, rival) if ours_first else (rival, ours)
    return "\n\n".join(("ONE:", first, "---", "THE OTHER:", second))


#: **The continuation's vocabulary once there is somewhere else to go.** Three acts, and the
#: middle one costs the reader this chapter — which is the whole instrument. `CHOICE_SCHEMA`'s
#: `come_back_later` is gone from this arm on purpose: coming back later is what a reader says
#: when nothing is at stake, and it is the answer that made §94's continuation unfalsifiable.
LEAVE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["next", "because"],
    "properties": {
        "next": {
            "type": "string",
            "enum": ["carry_on", "go_and_look", "put_it_down"],
            "description": "What you actually spend the hour on.",
        },
        "because": {
            "type": "string",
            "description": "One sentence, in your own words. Not a review.",
        },
    },
}


def render_choice_request(
    reader: Reader, chapter: str, rival_title: str = ""
) -> CompletionRequest:
    """A measurement reader, stopped part-way, deciding whether to stay.

    **The chapter is cut off**, on `text.stop_point`'s rule and for the operator's reason: a
    reader shown a whole chapter has already spent the hour, so asking what they do with it is
    asking about the past. Stopped part-way, the question is real and the answer is behaviour.

    **The other book is named and not shown, which is the operator's correction of 2026-08-26**:
    *"the readers shouldn't be able to read both, they should only be able to spend currency to
    read something, and if they read a new overview, they miss out on reading our book."* A
    rival whose blurb is on the page has already been read for free, which is §94's defect —
    continuing was free — moved one object across. So the reader knows a book is there and has
    not opened it, and going to look costs them this chapter. What our prose is being measured
    against is the pull of something new, which is the thing a serial actually loses readers to.

    `rival_title` empty renders what every round before 2026-08-26 rendered, which keeps the
    no-competitor arm reachable as the control this is read against.
    """
    if reader.pool != MEASUREMENT:
        raise ValueError(f"{reader.reader_id} is a {reader.pool} reader and may not measure")
    if not rival_title.strip():
        return CompletionRequest(
            prompt=(
                f"{chapter}\n\n---\n\n"
                f"You have time for about {BUDGET_CHAPTERS} more chapters today, across "
                "everything you are part-way through. This is one of them. What do you do?"
            ),
            system=reader.system(),
            schema=CHOICE_SCHEMA,
            max_output_tokens=600,
            profile=CONTINUE_PROFILE,
            call_class=CALL_CLASS,
        )
    return CompletionRequest(
        prompt=(
            f"You are part-way into this and it stops here:\n\n{chapter}\n\n---\n\n"
            f"{_CURRENCY} You can spend it finishing this chapter. Or you can spend it on a "
            f"serial you have not opened called {rival_title.strip()}, which somebody put in "
            "front of you today: read what it is about, and start it if it takes you. You "
            "cannot do both today, and if you go and look you do not finish this. What do "
            "you do?"
        ),
        system=reader.system(),
        schema=LEAVE_SCHEMA,
        max_output_tokens=600,
        profile=CONTINUE_PROFILE,
        call_class=CALL_CLASS,
    )


def render_anticipation_request(reader: Reader, chapter: str) -> CompletionRequest:
    """A steering reader, stopped part-way, saying what it felt and what it thinks comes next.

    **No budget, no competitor and no choice**, for the reason the two lanes were split at all:
    this reader is not deciding anything. Putting a decision beside a wish lets one colour the
    other, and the wish is the half that reaches the writer.

    **The passage is cut off and that is the whole change.** A reader given the end has nothing
    to predict and nothing left to want, so what it produces instead is an assessment — the one
    thing `plan/reader-judge-loop.md` guards and the thing that put six defects into a listing
    on 2026-08-25.
    """
    if reader.pool != STEERING:
        raise ValueError(f"{reader.reader_id} is a {reader.pool} reader and may not steer")
    return CompletionRequest(
        prompt=(
            f"{chapter}\n\n---\n\nThat is as far as you have got. How did that leave you, "
            "what do you think happens next, and what do you find yourself wanting to happen?"
        ),
        system=reader.system(),
        schema=ANTICIPATION_SCHEMA,
        max_output_tokens=800,
        profile=ANTICIPATE_PROFILE,
        call_class=CALL_CLASS,
    )


#: **The browsing behaviours, and they are not the reading ones.** §97.4 gives a sim a
#: behavioural vocabulary and no verdict slot; `CHOICE_SCHEMA`'s three words are what somebody
#: part-way through a book does. Somebody looking at an overview has not started, so
#: "carry on" is not available to them and offering it would be asking about an act they
#: cannot perform. These three are the platform's own: open it now, scroll past, or shelve it.
START_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["next", "because"],
    "properties": {
        "next": {
            "type": "string",
            "enum": ["start_reading", "pass_on_it", "save_for_later"],
            "description": "What you actually do with this listing.",
        },
        "because": {
            "type": "string",
            "description": "One sentence, in your own words. Not a review.",
        },
    },
}

#: **A browsing reader is a reader who has read a prefix**, which is what a listing is, so this
#: is `ANTICIPATION_SCHEMA` and no longer a schema of its own. It used to ask *"what are you
#: hoping this book turns out to be"* and *"what would make you drop it by chapter three"* —
#: two questions about the artifact, and the pair that produced *"a real changelog with version
#: numbers, nerfs"* and *"repro steps"* on 2026-08-25.
#:
#: A listing is not truncated the way a chapter is, and that is not an oversight: a chapter
#: resolves and has to be cut off to leave a future, and a listing resolves nothing. It is
#: already the prefix.
APPETITE_SCHEMA: dict[str, Any] = ANTICIPATION_SCHEMA

#: **The browsing cost, and it is the one §94 said was missing.** Continuation saturated at
#: 195 of 196 because continuing was free; a blurb has the same problem worse, since nodding at
#: a listing costs nothing at all. What is scarce on this platform is not attention in the
#: abstract but the slot: a reader following several serials starts very few new ones, and the
#: competition is the rest of the page rather than nothing.
_SLOT = (
    "You are scrolling a list of new serials. You are already following several and you have "
    "room for maybe one more this month, so most of what you look at you scroll past. The "
    "rest of the page is full of other people's books."
)


#: **The paired screen's vocabulary, and it is deliberately not the solo one's.** A reader with
#: two blurbs and one slot is not deciding whether to start a book; they are deciding which. The
#: two options name a **position** and never a side, because a schema whose values were `ours`
#: and `theirs` would tell the reader the answer in the act of asking.
#:
#: `neither` is kept and is load-bearing. A forced binary manufactures a 50% floor, and a floor
#: nobody can fall through is not a measurement — §97.4's behavioural vocabulary keeps to acts a
#: reader can actually perform, and scrolling past both is one of them.
PICK_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["next", "because"],
    "properties": {
        "next": {
            "type": "string",
            "enum": ["the_first", "the_second", "neither"],
            "description": "Which one you spend the slot on.",
        },
        "because": {
            "type": "string",
            "description": "One sentence, in your own words. Not a review.",
        },
    },
}


def render_pick_request(
    reader: Reader, ours: str, rival: str, ours_first: bool
) -> CompletionRequest:
    """A measurement reader, two listings, one slot, and no way to tell which is ours.

    **This is the first pairing in this project that carries a label, and the label is not
    ours.** The rival cleared `rivals.admit` — a real book, rated above four stars by more than
    a handful of people, in a genre this reader reads — so the answer comes from what a market
    did rather than from anybody's opinion. §87-§89 spent three entries without one.

    What it is for is a **screen and not a score** (`plan/reader-calibration.md`): a readership
    that cannot pick the published book out of this pair has no resolution, and every number it
    has produced is empty. Nothing here is a quality claim about either book.
    """
    if reader.pool != MEASUREMENT:
        raise ValueError(f"{reader.reader_id} is a {reader.pool} reader and may not measure")
    return CompletionRequest(
        prompt=(
            f"{_SLOT}\n\nTwo of them:\n\n{_two_up(ours, rival, ours_first)}\n\n---\n\n"
            "You have room for one. Which do you start, and why?"
        ),
        system=reader.system(),
        schema=PICK_SCHEMA,
        max_output_tokens=600,
        profile=START_PROFILE,
        call_class=CALL_CLASS,
    )


def render_start_request(
    reader: Reader, overview: str, title: str = ""
) -> CompletionRequest:
    """A measurement reader, one overview, one behavioural choice against the rest of the page.

    **`title` is an arm and the empty string is its control.** A listing on this market never
    appears without one — the title is the line above the blurb and the only part of a book
    anybody says out loud — and the browsing pool, written off as saturated after three rounds
    at 15/16, 16/16 and 16/16 (§134's ceiling), discriminated when eight listings were read
    with titles: 1/4, 2/4, 3/4, 3/4, 4/4, 4/4, 4/4, 3/4. Two things changed at once there, the
    artifact gaining a title and the listings getting better, so which unstuck it is unknown.

    It is a parameter rather than a caller's f-string for exactly that reason: the two arms
    have to be the same code path, or the comparison is between two scripts. Empty renders
    byte-identical to every round measured before a title existed, which is what the
    with-title reading is read against.
    """
    if reader.pool != MEASUREMENT:
        raise ValueError(f"{reader.reader_id} is a {reader.pool} reader and may not measure")
    page = f"{title.strip()}\n\n{overview}" if title.strip() else overview
    return CompletionRequest(
        prompt=f"{page}\n\n---\n\n{_SLOT} What do you do?",
        system=reader.system(),
        schema=START_SCHEMA,
        max_output_tokens=600,
        profile=START_PROFILE,
        call_class=CALL_CLASS,
    )


def render_appetite_request(reader: Reader, overview: str) -> CompletionRequest:
    """A steering reader, one listing, and the same three questions a chapter gets.

    No slot clause and no choice, for `render_anticipation_request`'s reason: a reader deciding
    something and a reader wanting something are two calls, because put together each colours
    the other.

    **The question changed on 2026-08-25 and the old one is the defect.** It asked *"what are
    you hoping it turns out to be, and what would make you drop it by chapter three"*, and both
    halves invite a specification of the artifact — which is what came back, and what the
    writer then transcribed. Asking instead where the blurb left them and what they think
    happens keeps the reader inside the story, which is the only place a reader's words are
    safe to hand to a writer.
    """
    if reader.pool != STEERING:
        raise ValueError(f"{reader.reader_id} is a {reader.pool} reader and may not steer")
    return CompletionRequest(
        prompt=(
            f"{overview}\n\n---\n\nThat is all there is so far: the listing for a serial "
            "nobody has read yet. How did that leave you, what do you think happens in it, "
            "and what do you find yourself wanting to happen?"
        ),
        system=reader.system(),
        schema=APPETITE_SCHEMA,
        max_output_tokens=800,
        profile=APPETITE_PROFILE,
        call_class=CALL_CLASS,
    )


def _strings(value: Any) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, str | bytes):
        return ()
    return tuple(text for item in value if isinstance(item, str) and (text := item.strip()))


@dataclass(frozen=True, slots=True)
class Reading:
    """What the measurement pool did with one chapter."""

    carried_on: int
    put_down: int
    come_back: int
    asked: int
    #: (reader_id, choice, because)
    said: tuple[tuple[str, str, str], ...]
    #: Readers who spent the hour going to look at a book they had not opened. Zero in the
    #: no-rival arm, where the act is not offered — see `LEAVE_SCHEMA`.
    left_for_other: int = 0

    @property
    def answered(self) -> int:
        return self.carried_on + self.put_down + self.come_back + self.left_for_other

    @property
    def continuation(self) -> float | None:
        """Share who carried straight on. `None` when nobody answered."""
        return self.carried_on / self.answered if self.answered else None

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "asked": self.asked,
            "answered": self.answered,
            "carried_on": self.carried_on,
            "put_down": self.put_down,
            "come_back_later": self.come_back,
            "left_for_other": self.left_for_other,
            "continuation": self.continuation,
            "said": [
                {"reader": r, "next": c, "because": b} for r, c, b in self.said
            ],
        }

    @classmethod
    def of(cls, answers: Mapping[str, Mapping[str, Any] | None]) -> Reading:
        counts = {"carry_on": 0, "put_it_down": 0, "come_back_later": 0, "go_and_look": 0}
        said: list[tuple[str, str, str]] = []
        for reader in pool(MEASUREMENT):
            answer = answers.get(reader.reader_id)
            if not isinstance(answer, Mapping):
                continue
            choice = str(answer.get("next") or "")
            if choice not in counts:
                continue
            counts[choice] += 1
            said.append((reader.reader_id, choice, str(answer.get("because") or "").strip()))
        return cls(
            carried_on=counts["carry_on"],
            put_down=counts["put_it_down"],
            come_back=counts["come_back_later"],
            left_for_other=counts["go_and_look"],
            asked=len(pool(MEASUREMENT)),
            said=tuple(said),
        )


@dataclass(frozen=True, slots=True)
class Anticipation:
    """Where the steering pool got to: how it felt, what it expects, what it wants. The direction.

    **`hoping_for` and `dreading` are gone and `felt`, `expect_next` and `want_next` replace
    them**, on the operator's direction of 2026-08-25 and for a measured reason (see
    `ANTICIPATION_SCHEMA`). `of` still reads a pre-032 row so a book part-drafted across the
    change keeps its direction: an old `hoping_for` is a want by another name, and an old
    `dreading` has no successor and is dropped, which is the point rather than a loss.
    """

    felt: tuple[str, ...]
    expect_next: tuple[str, ...]
    want_next: tuple[str, ...]
    answered: int

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "answered": self.answered,
            "felt": list(self.felt),
            "expect_next": list(self.expect_next),
            "want_next": list(self.want_next),
        }

    @classmethod
    def of(cls, answers: Mapping[str, Mapping[str, Any] | None]) -> Anticipation:
        felt: list[str] = []
        expect: list[str] = []
        want: list[str] = []
        answered = 0
        for reader in pool(STEERING):
            answer = answers.get(reader.reader_id)
            if not isinstance(answer, Mapping):
                continue
            answered += 1
            felt.extend(_strings([answer.get("felt")]))
            expect.extend(_strings([answer.get("expect_next")]))
            want.extend(_strings(answer.get("want_next")))
            # Migration 031's column, read so a book part-drafted across 032 keeps its direction.
            want.extend(_strings(answer.get("hoping_for")))
        return cls(
            felt=tuple(dict.fromkeys(felt)),
            expect_next=tuple(dict.fromkeys(expect)),
            want_next=tuple(dict.fromkeys(want)),
            answered=answered,
        )

    def render(self) -> str:
        """The direction, as the writer reads it. Empty when nobody read anything.

        **What changed on 2026-08-25 is the framing, and the framing is what broke.** This used
        to open *"This is what your readers are actually hoping for. It outranks every craft
        rule you have been given"* — a maximal permission over a list of up to fifty items, and
        §138 measured permission-only text being recited maximally. It was: the revision of one
        listing put four of the readers' own nouns on the page verbatim, including *repro
        steps*.
        §129's ordering is unchanged and is not what is being edited here — reader direction
        still outranks every craft rule this project wrote. What is edited is the claim that
        the *words* outrank them. So the block below reports three things a reader said and
        says what they are: a state somebody was left in, a guess, and a wish. None of those is
        a specification, and the sentence that used to say they were is gone.
        """
        if not (self.felt or self.expect_next or self.want_next):
            return ""
        blocks = [
            "READERS WHO STOPPED PART-WAY THROUGH THIS, ASKED WHERE IT LEFT THEM.",
            "They have not seen the rest and are not describing what you should write. What "
            "they expect is what is already obvious; what they want is what they would stay "
            "for.",
        ]
        if self.felt:
            blocks.append(
                "It left them:\n" + "\n".join(f"- {item}" for item in self.felt)
            )
        if self.expect_next:
            blocks.append(
                "They expect next:\n" + "\n".join(f"- {item}" for item in self.expect_next)
            )
        if self.want_next:
            blocks.append(
                "They want to happen:\n" + "\n".join(f"- {item}" for item in self.want_next)
            )
        return "\n\n".join(blocks)



@dataclass(frozen=True, slots=True)
class Browsing:
    """What the measurement pool did with one overview. `Reading`'s shape, browsing's verbs."""

    started: int
    passed: int
    saved: int
    asked: int
    #: (reader_id, choice, because)
    said: tuple[tuple[str, str, str], ...]

    @property
    def answered(self) -> int:
        return self.started + self.passed + self.saved

    @property
    def start_rate(self) -> float | None:
        """Share who would open chapter one. `None` when nobody answered."""
        return self.started / self.answered if self.answered else None

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "asked": self.asked,
            "answered": self.answered,
            "started": self.started,
            "passed": self.passed,
            "saved_for_later": self.saved,
            "start_rate": self.start_rate,
            "said": [{"reader": r, "next": c, "because": b} for r, c, b in self.said],
        }

    @classmethod
    def of(cls, answers: Mapping[str, Mapping[str, Any] | None]) -> Browsing:
        counts = {"start_reading": 0, "pass_on_it": 0, "save_for_later": 0}
        said: list[tuple[str, str, str]] = []
        for reader in pool(MEASUREMENT):
            answer = answers.get(reader.reader_id)
            if not isinstance(answer, Mapping):
                continue
            choice = str(answer.get("next") or "")
            if choice not in counts:
                continue
            counts[choice] += 1
            said.append((reader.reader_id, choice, str(answer.get("because") or "").strip()))
        return cls(
            started=counts["start_reading"],
            passed=counts["pass_on_it"],
            saved=counts["save_for_later"],
            asked=len(pool(MEASUREMENT)),
            said=tuple(said),
        )



def side_of(choice: str, ours_first: bool) -> str:
    """Which book a positional answer actually names: `ours`, `theirs`, or `neither`.

    The reader answers in positions because it may not be told which side is the house's own,
    so the un-blinding happens here, once, against the order that was recorded. Anything the
    schema did not offer reads as `neither` rather than as a side, because a malformed answer
    is not a vote.
    """
    if choice == "neither":
        return "neither"
    if choice == "the_first":
        return "ours" if ours_first else "theirs"
    if choice == "the_second":
        return "theirs" if ours_first else "ours"
    return "neither"


@dataclass(frozen=True, slots=True)
class Pairing:
    """What the measurement pool did with one listing beside published books.

    **A screen, never a score.** `plan/reader-calibration.md` states what a reading of this is
    allowed to be: the pool picking the published book is the instrument showing resolution, and
    the pool failing to is a fact about the instrument. Neither is a claim about either book,
    and there is no bar here — §61's attainability checks have not been done for any quantity on
    this class, so nothing below may be compared to a threshold.
    """

    ours: int
    theirs: int
    neither: int
    #: (reader_id, side, rival title, ours_first, because)
    said: tuple[tuple[str, str, str, bool, str], ...] = ()

    @property
    def answered(self) -> int:
        return self.ours + self.theirs + self.neither

    @property
    def ours_first_share(self) -> float | None:
        """Share of pairs that put ours first. The covariate, reported beside the result.

        A pairing whose order never varied is one whose result is a position effect, and this
        is the number that says so. `None` when nobody answered.
        """
        if not self.said:
            return None
        return sum(1 for item in self.said if item[3]) / len(self.said)

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "answered": self.answered,
            "ours": self.ours,
            "theirs": self.theirs,
            "neither": self.neither,
            "ours_first_share": self.ours_first_share,
            "said": [
                {
                    "reader": reader,
                    "chose": side,
                    "rival": rival,
                    "ours_first": first,
                    "because": because,
                }
                for reader, side, rival, first, because in self.said
            ],
        }

    @classmethod
    def of(cls, picks: Sequence[Mapping[str, Any]]) -> Pairing:
        counts = {"ours": 0, "theirs": 0, "neither": 0}
        said: list[tuple[str, str, str, bool, str]] = []
        for pick in picks:
            side = str(pick.get("chose") or "neither")
            if side not in counts:
                continue
            counts[side] += 1
            rival = pick.get("rival")
            said.append(
                (
                    str(pick.get("reader") or ""),
                    side,
                    str(rival.get("title") or "") if isinstance(rival, Mapping) else "",
                    bool(pick.get("ours_first")),
                    str(pick.get("because") or ""),
                )
            )
        return cls(
            ours=counts["ours"],
            theirs=counts["theirs"],
            neither=counts["neither"],
            said=tuple(said),
        )

__all__ = [
    "ANTICIPATE_PROFILE",
    "ANTICIPATION_SCHEMA",
    "APPETITE_PROFILE",
    "APPETITE_SCHEMA",
    "BUDGET_CHAPTERS",
    "CALL_CLASS",
    "CHOICE_SCHEMA",
    "CONTINUE_PROFILE",
    "LEAVE_SCHEMA",
    "MEASUREMENT",
    "PICK_SCHEMA",
    "READERS",
    "START_PROFILE",
    "START_SCHEMA",
    "STEERING",
    "Anticipation",
    "Browsing",
    "Pairing",
    "Reader",
    "Reading",
    "pool",
    "render_anticipation_request",
    "render_appetite_request",
    "render_choice_request",
    "render_pick_request",
    "render_start_request",
    "side_of",
]
