"""How many people the opening puts on the page.

The operator, read 10, on the draw the coordinator's gate had passed:

    "There are too many people, too many conversation about mundane things which don't
    progress the story."

**That quote lives here and may not travel** (§97.1, and the `debug-book` rule): it is
direction where direction enters, and no word of it is rendered into any call. What is
rendered is composed below, in code.

**What the packet does, measured before anything was written.** The scene the operator read
was drafted against a packet of 179 items and 4,953 tokens against a 200,000-token budget —
2.5% of the ceiling, so nothing was competing for room. Its cast section carried **nine**
sheets, which is every person that book's canon declares, and the chapter put five of them on
stage and named the other four offstage. The writer used every person it was handed.

`context.assemble` packs cast by budget alone: it walks `characters.cast(visible)` and keeps
whatever fits. At a budget that does not bind, that is a pass-through — the cast section is
the one part of the packet with no scene scoping of any kind, while facts are cut by story
time and by point-of-view visibility, hidden claims by disclosure, and prose nearest-scene
first. Nothing between the world and the page bounded the opening's cast, so this module is
the thing to bound it with.

**Why the bound is here and not in the packet's selection, which was tried first.** Cutting
the cast section needs an order to cut by, and two candidate orders were checked against the
book that produced the complaint. *Adjacency to the protagonist* selects one person — that
world declares no person-to-person edge from its protagonist at all — which would hand the
opening a town it may not mention. *Glossing only the people the packet's other sections
name* selects nine of nine, a measured no-op: every declared person is named somewhere in the
facts. The remaining order the code already has is protagonist-first-then-by-id, and cutting
alphabetically would withhold whichever person the scene actually needed. **A selection rule
with no honest order is worse than no selection rule**, so the packet is left carrying the
whole town — a writer that cannot see a person cannot use a fact about them (`context.py`'s
own argument for packing cast above facts, and §112's four-of-five cast members who never
reached either chapter). The town stays available; what is bounded is how much of it reaches
one page.

**And not in the scene plan the outline writes, because the pilot shape never takes one.**
`planner.make_plan_selector` outlines a book only when `len(set(functions)) < len(functions)`
— when the beat sheet cannot tell its own scenes apart. At six scenes every dramatic function
is distinct, so the standard pilot length is outlined never, and the book read at read 10 has
one plan item (its premise) and no per-scene statement at all. A participant list written by
an outline would not have reached it. This rides the same fold `genre.with_beat` uses for
exactly that reason, at both of that schedule's call sites.

**The sentence is a bound and not an adjective.** §154: a demand whose object is a reader's
state names nothing a writer can emit, and lands with its sign multiplied by zero. A count of
names is the opposite — the writer's only output is words on a page, and names on a page are
countable by whoever put them there. §138: a rule is signed, and what it forbids stops. This
is a ceiling, so the thing it names is the thing that does not happen. It carries no quality
word, no `house.MACHINERY_WORDS`, and no pronoun, on `genre.BEAT`'s reasons.

**It does not forbid a large world cast, and the distinction is the operator's own.** A town
of nine is not the defect; nine names in nineteen hundred words is. Unnamed people are not
bounded at all — a scene may be as full of bakers and carters as it likes, and the second
clause says so, because a bare ceiling invites a generator to empty the room instead of
leaving it unnamed (the packet's hidden section carries the same two-clause shape for the
same failure).

**Deliberately not here.** No count of anything in drafted prose, no census, no gate, no
threshold a scene is measured against afterwards, and no opinion about which people matter.
This module answers one question about position — is this scene one of the book's opening
scenes — and composes one sentence when the answer is yes.
"""

from __future__ import annotations

#: How many scenes at the head of a book carry the bound. **A placed number, and recorded as
#: one**: `SUMMARY_SHARE` and `DEFAULT_TOKEN_BUDGET` are the house precedent for saying so
#: rather than implying a measurement. No census stands behind it — `BRIEF.md` governs what may
#: become evidence and nothing here is offered as any, and the one census this project owns
#: (progression cadence) measures a different quantity entirely.
#:
#: Two, because the complaint was about a chapter and the pilots draft chapters of two scenes,
#: so the opening the operator read and the span this covers are the same span at the shape the
#: house actually runs. It is counted in scenes rather than in chapters because the chapter
#: shape is optional — `positions` is empty at `--chapter-scenes 1` — and a bound that silently
#: stopped firing on a default run would be a slot with no filler.
OPENING = 2

#: How many people the opening may name on one page. Placed, on the same terms as `OPENING`,
#: against one counterexample rather than a distribution: the chapter that produced read 10's
#: item named nine in 1,903 words. Three leaves a scene the person it follows and two others,
#: which is a room; it is not a claim that four would be wrong.
NAMED = 3

#: Spelled rather than printed, because the sentence is read as prose by its addressee and a
#: digit in an instruction has been read as a quantity to put on the page before. Rendered from
#: `NAMED` rather than written into the sentence, so the constant and the text cannot drift.
_NUMBER_WORDS = ("no", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine")

#: The bound as the writer reads it. Two clauses, and both are load-bearing: the first is the
#: ceiling and the second is what to do instead of it, because a prohibition handed over with no
#: alternative is answered by writing around the hole rather than by filling it differently.
BOUND = (
    "No more than {count} people are named on the page in this scene; "
    "everyone else in it goes unnamed."
)


def bounds_opening(
    ordinal: int, *, arc_index: int | None = None, opening: int = OPENING
) -> bool:
    """Whether this scene is one of the book's opening scenes.

    A pure function of position, so the answer is the same on every replay and a book can be
    asked which scenes are bounded without rendering anything — `genre.beat_ordinals`' shape,
    and for its reason.

    **`arc_index` is what keeps an open-ended serial's fifth arc from opening the book again.**
    Beats are arc-scoped on a serial, so `ordinal` counts from one inside every arc and a bound
    keyed to the ordinal alone would treat every arc's first scenes as the book's. `None` is a
    book that has no arcs, and arc 1 is the one that opens.
    """
    if opening < 0:
        raise ValueError(f"opening must not be negative, not {opening}")
    if arc_index is not None and arc_index > 1:
        return False
    return 1 <= ordinal <= opening


def bound_text(*, named: int = NAMED) -> str:
    """The sentence a bounded scene carries."""
    if not 0 <= named < len(_NUMBER_WORDS):
        raise ValueError(f"named must be between 0 and {len(_NUMBER_WORDS) - 1}, not {named}")
    return BOUND.format(count=_NUMBER_WORDS[named])


def with_bound(
    statement: str,
    ordinal: int,
    *,
    arc_index: int | None = None,
    opening: int = OPENING,
    named: int = NAMED,
) -> str:
    """One scene's plan text, with the opening's cast bound appended where it applies.

    Appended last, after the scene's own statement and after any scheduled progression beat:
    those two say what the scene contains, and this says what it may not also contain. A
    constraint read before the material would make every opening scene read as an exercise in
    restraint first and its own story second, which is `genre.with_beat`'s argument for its own
    placement one clause along.

    **An empty statement is a contract, not an edge case**, exactly as it is for the beat: a
    bounded scene with nothing to say still carries the bound, an unbounded one stays empty and
    renders nothing. That pair is what lets the drafting selector pass the bare fold for a book
    that never takes an outline, which is every six-scene book and therefore every pilot.
    """
    if not bounds_opening(ordinal, arc_index=arc_index, opening=opening):
        return statement
    bound = bound_text(named=named)
    stripped = statement.strip()
    if not stripped:
        return bound
    joiner = " " if stripped.endswith((".", "!", "?")) else ". "
    return f"{stripped}{joiner}{bound}"


__all__ = [
    "BOUND",
    "NAMED",
    "OPENING",
    "bound_text",
    "bounds_opening",
    "with_bound",
]
