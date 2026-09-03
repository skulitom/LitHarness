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

**The rosters left this module on 2026-09-03 (stage-0 §221), and what stays is general.** The
reader type is `domain/audience.Reader` (re-exported here) with its framing sentence as a field;
the eight LitRPG readers, the no-taste roster and the genre set live in `packs/litrpg`. What
remains here is the machinery any pack's readers are put through: the schemas, the request
renderers, the bounded reading context, and the aggregates — which now take the roster they
count over, because the roster is the pack's and this module no longer knows which pack is
reading. Every prompt a LitRPG reader renders is byte-identical to the one it rendered before.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from litharness.domain import serials as serials_mod
from litharness.domain.audience import BUDGET_CHAPTERS, MEASUREMENT, STEERING, Reader
from litharness.domain.generation import CompletionRequest
from litharness.domain.nodes import NodeKind
from litharness.domain.revision import Revision

# A reader gets the current chapter exactly as read, the two preceding chapters in full, and
# compact scene memories for the rest of the current arc.  Both bounds are structural: the
# request does not grow with a ten-volume serial, while it is no longer a cold read of one scene.
RECENT_FULL_CHAPTERS = 2
RECALLED_SUMMARY_CHAPTERS = 4

#: Frozen profiles, one per lane, so the two spends are separable on the decision rows.
CONTINUE_PROFILE = "reader.continue.v0"
ANTICIPATE_PROFILE = "reader.anticipate.v0"
#: The blurb stage's two, kept separate from the chapter stage's so the spends are
#: separable on the decision rows and so a mixed run cannot be read as one number.
START_PROFILE = "reader.start.v0"
APPETITE_PROFILE = "reader.appetite.v0"

CALL_CLASS = "generation"

#: `BUDGET_CHAPTERS`, `STEERING`, `MEASUREMENT` and `Reader` are `domain/audience.py`'s now and
#: are re-exported above; the LitRPG rosters (`READERS`, `BLIND`) and their `pool` are
#: `packs/litrpg`'s. A caller that needs the house's readers names the pack.


def _measurement_only(roster: Sequence[Reader]) -> tuple[Reader, ...]:
    """The roster, if every reader on it may measure. A steering reader counted here would put
    a reader that shapes the prose among those that judge it (§97.1)."""
    wrong = [reader.reader_id for reader in roster if reader.pool != MEASUREMENT]
    if wrong:
        raise ValueError(f"{wrong} are not measurement readers and may not be counted as such")
    return tuple(roster)


def _steering_only(roster: Sequence[Reader]) -> tuple[Reader, ...]:
    wrong = [reader.reader_id for reader in roster if reader.pool != STEERING]
    if wrong:
        raise ValueError(f"{wrong} are not steering readers and may not be counted as such")
    return tuple(roster)


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

#: **What a reader is for, rewritten 2026-08-25 and corrected 2026-08-26.** The operator:
#: *"From the readers we want to read their emotions about what they read, and find out what
#: they predict and want to happen next"*, then the prohibition — *"The readers shouldn't
#: critique what is already written, that's for the writers to do"* — and then, once the first
#: rewrite had dropped them, *"We still want these: hoping_for and dreading."*
#:
#: **Both directions are satisfied at once, because the defect was never the fields.** It was
#: the *question*. `render_appetite_request` used to ask what a reader hoped the book would
#: *turn out to be* and what would make them *drop it by chapter three*, and both are questions
#: about the artifact. Measured on *Patch Notes For Earth*: four steering readers answered with
#: *"a real changelog with version numbers, nerfs"*, *"not 'he's good at games' but repro
#: steps, edge cases"* and *"an interaction between two stated rules"*, and the revision put
#: **six of the operator's seven quoted defects** on the page — every one absent from the draft
#: those readers had seen. The channel handed the writer vocabulary and the writer transcribed
#: it. That is §138 one level up: reader material framed as *"it outranks every craft rule you
#: have been given"* is a maximal permission, and a permission is recited.
#:
#: So hope and dread are back and both are pinned to **what happens next in the story**. A want
#: and a fear about events are things only the story can answer; a want about the prose is a
#: specification, and there is still no field that can hold one.
#:
#: Migration 032 added a `want_next` column for the single-field version this replaces. Nothing
#: ever wrote to it — hope and dread came back first — and it is left in place rather than
#: edited out, because an applied migration is never edited (CONTRIBUTING) and a column that
#: was superseded before its first write is cheaper to explain than a schema nobody can
#: reconstruct.
ANTICIPATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["felt", "expect_next", "hoping_for", "dreading"],
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
        "hoping_for": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Things you find yourself WANTING to happen next. Things that could "
            "happen in the story, never things the writing should do.",
        },
        "dreading": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Things you are afraid happen next. Again things that could happen "
            "in the story, never things the writing should do.",
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
    reader: Reader,
    chapter: str,
    rival_title: str = "",
    *,
    prior_memory: str = "",
    budget_chapters: int = BUDGET_CHAPTERS,
) -> CompletionRequest:
    """A measurement reader, stopped part-way, deciding whether to stay.

    `budget_chapters` is the currency a caller may set (`domain/audience.CurrencySpec`); the
    default is the constant every reading before the port existed rendered, so a call that
    passes nothing is byte-identical to one made before the parameter existed.

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
    memory = (
        f"YOUR MEMORY FROM THE PREVIOUS READING STOP:\n{prior_memory.strip()}\n\n"
        if prior_memory.strip()
        else ""
    )
    if not rival_title.strip():
        return CompletionRequest(
            prompt=(
                f"{memory}{chapter}\n\n---\n\n"
                f"You have time for about {budget_chapters} more chapters today, across "
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
            f"{memory}You are part-way into this and it stops here:\n\n"
            f"{chapter}\n\n---\n\n"
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


def render_anticipation_request(
    reader: Reader, chapter: str, *, prior_memory: str = ""
) -> CompletionRequest:
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
    memory = (
        f"YOUR MEMORY FROM THE PREVIOUS READING STOP:\n{prior_memory.strip()}\n\n"
        if prior_memory.strip()
        else ""
    )
    return CompletionRequest(
        prompt=(
            f"{memory}{chapter}\n\n---\n\nThat is as far as you have got. How did that leave you, "
            "what do you think happens next, and what are you hoping for and dreading?"
        ),
        system=reader.system(),
        schema=ANTICIPATION_SCHEMA,
        max_output_tokens=800,
        profile=ANTICIPATE_PROFILE,
        call_class=CALL_CLASS,
    )


def accumulated_passage(
    revision: Revision,
    target_logical_id: str,
    stopped_passage: str,
    *,
    summaries: Mapping[str, str] | None = None,
    shape: serials_mod.SerialShape | None = None,
) -> str:
    """What a continuing reader has read up to one exact stop, with bounded recall.

    The current chapter contains full earlier scenes and only the stopped prefix of the target
    scene.  Recent chapters remain verbatim.  Older chapters in the recall window use summaries
    whose content hashes the caller has already checked; a missing summary is named rather than
    silently replaced with stale text.  Nothing after the target can enter the request.
    """
    summaries = summaries or {}
    shape = shape or serials_mod.SerialShape()
    scenes = [
        node
        for node in revision.in_reading_order()
        if node.kind is NodeKind.SCENE and not node.tombstoned
    ]
    ids = [node.logical_id for node in scenes]
    if target_logical_id not in ids:
        raise ValueError(f"{target_logical_id} is not a live scene")
    target_position = ids.index(target_logical_id)
    scene_by_id = {node.logical_id: node for node in scenes}
    chapters = serials_mod.chapters_of(revision, shape)
    target_chapter_at = next(
        index for index, chapter in enumerate(chapters) if target_logical_id in chapter.scene_ids
    )
    full_from = max(0, target_chapter_at - RECENT_FULL_CHAPTERS)
    recall_from = max(0, full_from - RECALLED_SUMMARY_CHAPTERS)
    blocks: list[str] = []

    if recall_from:
        blocks.append(
            f"[EARLIER READING]\n{recall_from} earlier chapter(s) were read before the "
            "bounded recall shown here."
        )
    recalled: list[str] = []
    for chapter in chapters[recall_from:full_from]:
        for logical_id in chapter.scene_ids:
            if ids.index(logical_id) >= target_position:
                break
            summary = summaries.get(logical_id)
            recalled.append(
                f"- {logical_id}: {summary}"
                if summary
                else f"- {logical_id}: [current summary unavailable]"
            )
    if recalled:
        blocks.append("[RECALLED EVENTS — COMPACT]\n" + "\n".join(recalled))

    for chapter in chapters[full_from:target_chapter_at]:
        prose = [
            scene_by_id[logical_id].content or ""
            for logical_id in chapter.scene_ids
            if ids.index(logical_id) < target_position
        ]
        if prose:
            blocks.append(f"[RECENT CHAPTER {chapter.index} — READ IN FULL]\n" + "\n\n".join(prose))

    current = chapters[target_chapter_at]
    current_parts: list[str] = []
    for logical_id in current.scene_ids:
        position = ids.index(logical_id)
        if position > target_position:
            break
        if logical_id == target_logical_id:
            current_parts.append(stopped_passage)
            break
        current_parts.append(scene_by_id[logical_id].content or "")
    blocks.append(
        f"[CURRENT CHAPTER {current.index} — STOPS MID-SCENE]\n" + "\n\n".join(current_parts)
    )
    return "\n\n".join(blocks)


def prior_reading_memory(
    rows: Sequence[Mapping[str, Any]],
    reader_id: str,
    *,
    earlier_logical_ids: Sequence[str],
) -> str:
    """The newest earlier answer from this same simulated reader, never another reader's."""
    earlier = frozenset(earlier_logical_ids)
    row = next(
        (
            item
            for item in rows
            if item.get("reader_id") == reader_id and item.get("logical_id") in earlier
        ),
        None,
    )
    if row is None:
        return ""
    parts: list[str] = []
    for key, label in (
        ("felt", "You felt"),
        ("expect_next", "You expected"),
        ("because", "Your last decision was because"),
    ):
        if row.get(key):
            parts.append(f"{label}: {row[key]}")
    for key, label in (("hoping_for", "You hoped for"), ("dreading", "You dreaded")):
        values = row.get(key)
        if isinstance(values, list) and values:
            parts.append(f"{label}: " + "; ".join(str(value) for value in values))
    return "\n".join(parts)


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
    did rather than from anybody's opinion. §87.2 ran §79's conversion-labelled pairs, a label
    a reader produced; what is new here is a market-admitted rival against our own text.

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


def render_start_request(reader: Reader, overview: str, title: str = "") -> CompletionRequest:
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
            "and what are you hoping for and dreading?"
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
            "said": [{"reader": r, "next": c, "because": b} for r, c, b in self.said],
        }

    @classmethod
    def of(
        cls, answers: Mapping[str, Mapping[str, Any] | None], *, roster: Sequence[Reader]
    ) -> Reading:
        """Counted over `roster`, the measurement readers who were asked; `asked` is its size."""
        asked = _measurement_only(roster)
        counts = {"carry_on": 0, "put_it_down": 0, "come_back_later": 0, "go_and_look": 0}
        said: list[tuple[str, str, str]] = []
        for reader in asked:
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
            asked=len(asked),
            said=tuple(said),
        )


@dataclass(frozen=True, slots=True)
class Anticipation:
    """Where the observation pool got to: how it felt, what it expects, what it wants.

    **Four fields, and hope and dread are two of them again** (2026-08-26). What changed is not
    which fields exist but what they are about: every one is pinned to what happens *next in the
    story*, so a reader can want an event and fear an event and cannot specify a sentence. See
    `ANTICIPATION_SCHEMA` for the measurement that forced it.
    """

    felt: tuple[str, ...]
    expect_next: tuple[str, ...]
    hoping_for: tuple[str, ...]
    dreading: tuple[str, ...]
    answered: int

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "answered": self.answered,
            "felt": list(self.felt),
            "expect_next": list(self.expect_next),
            "hoping_for": list(self.hoping_for),
            "dreading": list(self.dreading),
        }

    @classmethod
    def of(
        cls, answers: Mapping[str, Mapping[str, Any] | None], *, roster: Sequence[Reader]
    ) -> Anticipation:
        """Read over `roster`, the steering readers who were asked, in their order."""
        felt: list[str] = []
        expect: list[str] = []
        hoping: list[str] = []
        dreading: list[str] = []
        answered = 0
        for reader in _steering_only(roster):
            answer = answers.get(reader.reader_id)
            if not isinstance(answer, Mapping):
                continue
            answered += 1
            felt.extend(_strings([answer.get("felt")]))
            expect.extend(_strings([answer.get("expect_next")]))
            hoping.extend(_strings(answer.get("hoping_for")))
            hoping.extend(_strings(answer.get("want_next")))
            dreading.extend(_strings(answer.get("dreading")))
        return cls(
            felt=tuple(dict.fromkeys(felt)),
            expect_next=tuple(dict.fromkeys(expect)),
            hoping_for=tuple(dict.fromkeys(hoping)),
            dreading=tuple(dict.fromkeys(dreading)),
            answered=answered,
        )

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
    def of(
        cls, answers: Mapping[str, Mapping[str, Any] | None], *, roster: Sequence[Reader]
    ) -> Browsing:
        """Counted over `roster`, the measurement readers who were asked; `asked` is its size."""
        asked = _measurement_only(roster)
        counts = {"start_reading": 0, "pass_on_it": 0, "save_for_later": 0}
        said: list[tuple[str, str, str]] = []
        for reader in asked:
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
            asked=len(asked),
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
    "START_PROFILE",
    "START_SCHEMA",
    "STEERING",
    "Anticipation",
    "Browsing",
    "Pairing",
    "Reader",
    "Reading",
    "accumulated_passage",
    "prior_reading_memory",
    "render_anticipation_request",
    "render_appetite_request",
    "render_choice_request",
    "render_pick_request",
    "render_start_request",
    "side_of",
]
