"""The Director role: a named personality that says what a book is, and never whether it is good.

**Why a third role is not a fourth attempt at the frame that died.** Every frame this project has
buried was *evaluative and downstream* — handed prose that existed and asked how good it is. T0's
panel died there, §89's E1/E2 died there, the persona reader's absolute verdict died there. A
Director is *generative and upstream*: it says what the book should be, before any of it exists.
That is not a measurement, so it cannot be an invalid one. It can be a bad idea, and only a
reader can settle that — which is where the question already goes.

So a Director needs no validity licence. What it needs is containment, because a role that
measures nothing is exactly the role through which unmeasured taste walks in wearing something
else's authority. Two rails, both bought by failures already on the record.

**Rail one: a brief may name what the book is about; it may not name what good prose is.**
`plan/reader-judge-loop.md` §2.1 makes axis admission a four-step path — a human read names a
defect, a counter is built, E6 clears the family, readers establish a direction — and a brief goes
straight into the drafting context. So a brief saying "cut the em dashes" would inject a prose
axis into every prompt with no counter, no validation and no reader behind it, bypassing the whole
path. It is not hypothetical: `em_dash`'s own pre-registered hypothesis is currently VOID with the
estimate leaning *toward* the mark (§78.3), so a director instructing against em dashes would be
asserting as premise the thing the loop exists to test. `legal_brief` enforces it. The first
version of that guard reused the Judge's frozen `AXIS_MATCHERS` and had to be withdrawn — see
`_CRAFT_INSTRUCTION`, where the withdrawal is the interesting part.

**Rail two: a personality has to be earned.** §89.1 measured `qwen3:14b` returning **one distinct
answer vector across all four personas, byte-identical**; §83 found the register invariant to
simulated phenomenology; §77 measured persona-to-passage sum-of-squares ratios of 0.0028, 0.0071
and 0.0342 while one word of question change moved a rate ten points. Personas in this project are
usually decorative. So "experiment with different directors" is a claim to be checked before it is
made — `distinctness` is that check, and a comparison between directors that has not passed it is
one director in hats, reporting the seed.
"""

from __future__ import annotations

import enum
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256

from litharness.domain.directives import INTERPRETIVE_KINDS, DirectiveKind
from litharness.domain.text import canonicalize

#: The kinds a machine Director may emit, and it is exactly `INTERPRETIVE_KINDS`. `CONSTRAINT`
#: and `VETO` are `VERBATIM_KINDS` — preserve the words, lock them — and a veto is a *refusal*,
#: which is authority rather than direction. `CONTROL` is pause/resume/kill, which is operator
#: state and not narrative at all. So a Director says what the book is about; it may not refuse
#: anything and it may not stop the machine.
DIRECTOR_KINDS: frozenset[DirectiveKind] = frozenset(INTERPRETIVE_KINDS)

#: Prefix reserved for an author that is a machine. Restated rather than shared with
#: `preference.MACHINE_READER_PREFIX` for the reason that constant gives for not being shared:
#: the two mark different things in different tables, and unifying the constant invites unifying
#: the semantics.
DIRECTOR_AUTHOR_PREFIX = "director:"

#: How many draws each side of the distinctness comparison needs before it says anything. Three,
#: because two draws give one within-director distance and a comparison against a single number
#: is not a comparison. Below it the reading is UNREADABLE rather than passing.
DISTINCTNESS_FLOOR = 3


class IllegalBrief(Exception):
    """A brief or a directive that a Director is not licensed to write."""


def machine_author(director_id: str) -> str:
    """The author string a machine-written directive is stamped with. Always prefixed."""
    return f"{DIRECTOR_AUTHOR_PREFIX}{director_id}"


def is_machine_author(author: str | None) -> bool:
    """Whether this directive was written by a Director rather than by a person.

    `None` and the empty string are both false: a directive with no recorded author predates
    the column, and "unrecorded" is not "machine".
    """
    return (author or "").startswith(DIRECTOR_AUTHOR_PREFIX)


#: Prose-craft instruction vocabulary, per registered axis. **Purpose-built rather than reused,
#: and the first attempt reused `AXIS_MATCHERS` and had to be withdrawn — which is the finding.**
#:
#: Those matchers are tuned for *recall* on a description task: `elicitation_study` says in as
#: many words that they are "deliberately generous about vocabulary and strict about topic",
#: because what E6 tests is whether an axis reached the output at all. `stat_flatten`'s list
#: therefore contains `level`, `tier`, `stat`, `value`, `count` — ordinary LitRPG *story* words.
#: Run as a refusal gate they rejected this module's own first example brief, on the sentence
#: "every level gained should have cost something".
#:
#: The lists are the same shape and the error economics are inverted. In E6 a generous list
#: costs a false *positive* that reads as a miss; here it costs a refusal of legitimate
#: direction. So this vocabulary is tuned the other way — high precision, low recall — and the
#: trade is stated rather than hidden: a director who means "avoid em dashes" in other words
#: gets through. What the guard buys is that the axes the loop is **actively measuring** cannot
#: be pre-empted by an instruction that says so plainly.
_CRAFT_INSTRUCTION: Mapping[str, str] = {
    "em_dash": r"\bem[- ]?dash|\bemdash|\bpunctuat|—",
    "interiority": (
        r"\binterior(?:ity)?\b|\bshow,? don'?t tell\b|\binner monologue\b"
        r"|\bfree indirect\b"
    ),
    "stat_flatten": (
        r"\bstat[- ]?block|\bstatus[- ]?block|\bstatus[- ]?line|\bstat[- ]?line"
    ),
}

#: Prose-style instruction that names no single registered axis but is craft doctrine all the
#: same. Kept separate because it refuses for a different reason: not "you are pre-empting a
#: measurement in flight" but "prose instruction is not what a brief is for".
_PROSE_STYLE = (
    r"\bsentence length\b|\b(?:short|long|punchy|terse|flowery|purple) (?:sentence|prose)"
    r"|\bpurple prose\b|\bword choice\b|\badverb|\bprose style\b|\bwriting style\b"
)


def prose_axes_named(text: str) -> tuple[str, ...]:
    """Registered prose axes this text *instructs about*, by the narrow vocabulary above.

    Not `named_axes`, and the difference is deliberate — see `_CRAFT_INSTRUCTION`. A director
    naming an axis this plainly is pre-empting a measurement in flight; a director using the
    genre's ordinary nouns is writing a brief.
    """
    import re

    found = [
        axis_id
        for axis_id, pattern in _CRAFT_INSTRUCTION.items()
        if re.search(pattern, text, flags=re.IGNORECASE)
    ]
    if re.search(_PROSE_STYLE, text, flags=re.IGNORECASE):
        found.append("prose_style")
    return tuple(found)


def legal_brief(text: str) -> None:
    """Raise unless `text` is direction about a story rather than doctrine about prose.

    Narrow, and honest about it. It catches "avoid em dashes" and "keep the stat blocks vague";
    it does not catch a paraphrase, and no regex would. What it buys is that the axes the loop is
    **actively measuring** cannot be pre-empted by direction — which is the only part of the
    space where a wrong instruction would corrupt a measurement rather than merely produce a
    book somebody dislikes.
    """
    if not text.strip():
        raise IllegalBrief("a director with no brief is not a personality")
    named = prose_axes_named(text)
    if named:
        raise IllegalBrief(
            f"this names the registered prose axis/axes {', '.join(named)}. A brief says what "
            "the book is about; what good prose is comes from readers through the axis "
            "admission path (plan/reader-judge-loop.md §2.1), never from direction — "
            f"{named[0]}'s own hypothesis is still under test"
        )


def director_id_for(*, name: str, brief: str) -> str:
    """Content address over the personality itself.

    So a brief cannot drift under the books it directed: editing one word mints a different
    director, and "which director wrote this book" stays answerable after somebody rewrites a
    brief they were not happy with.
    """
    material = "\x00".join((name, canonicalize(brief))).encode()
    return f"dtor-{sha256(material).hexdigest()[:24]}"


@dataclass(frozen=True, slots=True)
class Director:
    """One named personality: what it cares about, and nothing about what good prose is."""

    director_id: str
    name: str
    #: The standing instruction that shapes what this director asks for. Story, subject, arc,
    #: stakes, world, mood. Checked by `legal_brief` at construction, so an illegal brief is
    #: unrepresentable rather than merely discouraged.
    brief: str
    note: str = ""

    def __post_init__(self) -> None:
        legal_brief(self.brief)
        if not self.name.strip():
            raise IllegalBrief("a director needs a name; provenance is the whole point")
        expected = director_id_for(name=self.name, brief=self.brief)
        if self.director_id != expected:
            raise IllegalBrief(
                f"director_id {self.director_id} does not address this personality"
            )

    @property
    def author(self) -> str:
        return machine_author(self.director_id)


def build(name: str, brief: str, *, note: str = "") -> Director:
    """A director from its own words, with the id derived rather than supplied."""
    return Director(
        director_id=director_id_for(name=name, brief=brief),
        name=name,
        brief=brief,
        note=note,
    )


#: Three example personalities, and they are **examples rather than recommendations**. They exist
#: to exercise the distinctness control with briefs that differ on subject rather than on style —
#: which is also the only dimension a brief is allowed to differ on. Nothing here claims any of
#: them is a good director; which briefs are worth running is an operator act, the way admitting a
#: fixture family is (§84).
BUILTIN: Mapping[str, Director] = {
    director.name: director
    for director in (
        build(
            "delver",
            "You care about what is under the ground. Push the book toward descent, mapped "
            "space, and the slow accumulation of things that were bought at a price. Every "
            "level gained should have cost something the reader watched being spent. You "
            "distrust prophecy and destiny; what happens should happen because somebody chose "
            "it or somebody paid for it.",
            note="example: dungeon-first, cost-first",
        ),
        build(
            "chandler",
            "You care about obligation between people. Push the book toward debts, favours, "
            "contracts and the awkwardness of owing someone. The System is a creditor before "
            "it is a game. Keep the cast small and let the same faces come back changed by "
            "what passed between them.",
            note="example: social-first, obligation-first",
        ),
        build(
            "cartwright",
            "You care about consequence at scale. Push the book toward the effect one person's "
            "choices have on a town, a road, a season. Let time pass. What was fixed in one "
            "chapter should be visibly unfixed later by something that followed from it.",
            note="example: consequence-first, long-horizon",
        ),
    )
}


class Distinctness(enum.StrEnum):
    """Whether two directors are two directors. A named refusal, never a silent pass.

    §89.1 is the whole reason this enum exists: four personas, one byte-identical answer vector,
    and a panel that read as four judges was one judge replicated. The same failure is available
    here and it would make every director comparison a report about the sampler seed.
    """

    IDENTICAL = "identical"
    INDISTINCT = "indistinct"
    DISTINCT = "distinct"
    #: The sets differ and the within-director noise floor was **zero**, so the gap was not
    #: tested against anything. A weaker claim wearing the same word, and it earns its own
    #: member because conflating the two is how a control that cannot fail gets quoted as one
    #: that did: with no wobble to clear, "between exceeds within" is satisfied by a single
    #: differing character. It happens whenever the generator is deterministic — which the
    #: padded fake always is, and a temperature-0 model always is.
    DISTINCT_NO_FLOOR = "distinct_no_floor"
    UNREADABLE = "unreadable"


@dataclass(frozen=True, slots=True)
class DistinctnessReading:
    reading: Distinctness
    within: float | None
    between: float | None
    draws: int

    @property
    def comparable(self) -> bool:
        """Whether a comparison between these directors may be reported at all.

        `DISTINCT_NO_FLOOR` counts, and the reason is that it establishes the thing the rail
        exists to establish — these briefs are not inert — even though it does not establish the
        stronger one. What it may not do is be *reported* as `DISTINCT`, which is why it is a
        separate member rather than a flag somebody renders as a footnote.
        """
        return self.reading in {Distinctness.DISTINCT, Distinctness.DISTINCT_NO_FLOOR}


def _distance(left: str, right: str) -> float:
    """Normalised compression distance, `domain/craft.py`'s measure, reused deliberately.

    Reused rather than invented because this repo has refuted enough hand-rolled text distances
    to be suspicious of a new one, and because what is being asked here is deliberately crude:
    *are these the same bytes or not*, with a graded answer for the near-identical case.
    """
    from litharness.domain.craft import _compressed

    if left == right:
        return 0.0
    a, b = _compressed(left), _compressed(right)
    both = _compressed(left + "\n" + right)
    return (both - min(a, b)) / max(max(a, b), 1)


def distance(left: str, right: str) -> float:
    """`_distance` under a name another module may call.

    Added when the Architect needed the same crude are-these-the-same-bytes question over K
    worlds. Exported rather than copied for the reason `_distance` gives for reusing
    `craft._compressed`: this repo has refuted enough hand-rolled text distances to be
    suspicious of a second one, and two measures called distinctness that disagreed would be
    worse than either.
    """
    return _distance(left, right)


def _mean_pairwise(texts: Sequence[str]) -> float | None:
    pairs = [
        _distance(texts[i], texts[j])
        for i in range(len(texts))
        for j in range(i + 1, len(texts))
    ]
    return sum(pairs) / len(pairs) if pairs else None


def distinctness(
    left: Sequence[str], right: Sequence[str], *, floor: int = DISTINCTNESS_FLOOR
) -> DistinctnessReading:
    """Do two directors differ more from each other than each differs from itself?

    `left` and `right` are the directive bodies each director produced on the same book state,
    varying only the sampler seed — so the within-director spread *is* the generator's noise, and
    a between-director gap has to clear it to mean anything.

    **Byte-identity is checked first because it is free and because it is what actually
    happened.** §89.1's `qwen3:14b` returned one answer vector across four personas; a graded
    distance would have reported that as a very small number rather than as the categorical
    failure it was.
    """
    draws = min(len(left), len(right))
    if draws < floor:
        return DistinctnessReading(Distinctness.UNREADABLE, None, None, draws)
    if set(left) == set(right):
        return DistinctnessReading(Distinctness.IDENTICAL, 0.0, 0.0, draws)
    within_left = _mean_pairwise(left)
    within_right = _mean_pairwise(right)
    if within_left is None or within_right is None:
        return DistinctnessReading(Distinctness.UNREADABLE, None, None, draws)
    within = (within_left + within_right) / 2.0
    crossed = [_distance(one, other) for one in left for other in right]
    between = sum(crossed) / len(crossed)
    if between <= within:
        reading = Distinctness.INDISTINCT
    elif within > 0.0:
        reading = Distinctness.DISTINCT
    else:
        # **No wobble to clear, so nothing was cleared.** Every draw from each director came
        # back byte-identical to its siblings, which is what a deterministic generator does —
        # the padded fake always, a temperature-0 model always. The sets still differ, so the
        # briefs are not inert; but "between exceeds within" was satisfied by arithmetic rather
        # than by a margin, and a run that reported this as DISTINCT would be quoting a control
        # that could not fail (§50: a control which cannot fail is not a control).
        reading = Distinctness.DISTINCT_NO_FLOOR
    return DistinctnessReading(reading, within, between, draws)


__all__ = [
    "BUILTIN",
    "DIRECTOR_AUTHOR_PREFIX",
    "DIRECTOR_KINDS",
    "DISTINCTNESS_FLOOR",
    "Director",
    "Distinctness",
    "DistinctnessReading",
    "IllegalBrief",
    "build",
    "director_id_for",
    "distance",
    "distinctness",
    "is_machine_author",
    "legal_brief",
    "machine_author",
    "prose_axes_named",
]
