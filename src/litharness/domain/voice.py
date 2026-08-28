"""Voice as a channel: what a text *carries*, as distinct from what it *says*.

**The measured fact this module is built on.** A model writes in the register it is handed, and
this repository has caught it three times: the round-one listings carried em dashes at a rate the
market's carried none at, and our instruction prose is em-dash-heavy
(`plan/handoff-listing-loop.md` owns that table); §120 caught a machinery word crossing from
persona text into a chapter; §138 caught a rule's affirmative half returning as a verbal formula,
and §146.8 caught the same thing again the same day. `plan/dossier-voice-direction.md` is where the
operator's question and the three receipts live, and it names the design this module makes
mechanical: a dossier **written as the writer writes** names nothing and demonstrates instead, so
exhibition becomes a third channel beside instruction and subtraction.

**And the caution that comes with it, which is the whole of why this file exists.**
`directors.prose_axes_named` catches a text that *names* a registered prose axis. It cannot catch
a text that simply *is* heavy in one — an em-dash-laden exhibited voice asserts by example the
thing the em-dash loop exists to test, and asserting by example is not weaker than asserting by
sentence. So exhibited text needs a mechanical census against the registered axes before it is
legal, and a vibe check is not one.

**Nothing here judges a text and nothing here ranks two.** Every function below is arithmetic or
membership over one text's own characters. R3 says a writer never judges; a census that returned a
verdict about quality would be a judge in a hat, and the two dossier counters
`application/roster.py` already carries (`appetite_markers`, `machinery_words`) are the shape being
copied rather than extended.

**Imports nothing but `domain/text`, deliberately.** `directors` imports this module and not the
reverse, so the naming vocabulary and the carrying vocabulary can sit on opposite sides of one
import without a cycle, and `writers` composes both.
"""

from __future__ import annotations

import enum
import re
import statistics
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from dataclasses import fields as dataclass_fields
from hashlib import sha256

from litharness.domain.text import canonicalize, content_hash

#: Prefix for an exemplar's content address. Its own prefix rather than a bare hex string for
#: `wtr-`'s reason: `writer_id_for` takes this value as opaque addressed material, and a
#: prefixed digest says what a stored column holds without a join.
EXEMPLAR_DIGEST_PREFIX = "exm-"

#: Prefix for a style descriptor's content address. **The address is over the descriptor's own
#: numbers and over nothing else** — see `descriptor_id_for`, where the reason is RS1 rather than
#: tidiness.
DESCRIPTOR_ID_PREFIX = "sty-"


# ---------------------------------------------------------------------------
# The registered-axis census: an axis carried rather than named
# ---------------------------------------------------------------------------

#: A registered prose axis whose *mark* is a thing a text can be seen to carry, and the mark.
#:
#: **One entry, and the entry was already being enforced somewhere else, which is the finding.**
#: `directors._CRAFT_INSTRUCTION["em_dash"]` has the literal character as one of its
#: alternatives, so a dossier that merely contains an em dash is refused today by a function
#: whose name and docstring both say it catches text that *instructs about* an axis. The roster
#: vocabulary already explains that refusal in exhibition's own terms — *"a dossier rides in the
#: system message of every scene call, so a dossier written with the mark demonstrates the mark
#: on every draft"* — so the rule was right and its home was wrong. This is the home.
#:
#: **What the table is for is the axis that has not been registered yet.** Today it holds one
#: mark and the census it powers is nearly vacuous. `test_every_registered_axis_is_placed`
#: is the mechanism: an axis added to the naming vocabulary and to neither this mapping nor
#: `UNMARKED_AXES` fails the suite, so nobody can register an axis without saying whether
#: demonstrating it is detectable. That is the part that survives this file's own thinness.
EXHIBITION_MARKERS: Mapping[str, str] = {
    "em_dash": "—",
}

#: Registered axes a text can demonstrate and no mechanical marker can see, with the reason each
#: one resists. **Stated rather than gated**, which is §146.4's own move for the day-job detector:
#: three candidate detectors were named there with the entry that killed each, and the gap was
#: written down instead of half-closed.
#:
#: The candidate that looked closest for `stat_flatten` was the bracketed system-tag form a LitRPG
#: page uses — `[STATUS]`, `[Level Up]` — and it is refused for the reason a word list is always
#: refused here: it would fire on a legitimate dossier. `writers.CAST["ferreira"]` loves *"the
#: first message nobody asked for"*, which is one bracket away from a tag, and a shelf called
#: LitRPG Comedy is staffed by somebody who would write it with the bracket. A counter that
#: refuses a shipped fixture is measuring the wrong thing (`roster.machinery_words` records the
#: same trade over `writers.BUILTIN["volcanology"]`).
#:
#: `interiority` has no candidate at all. A dossier saying what still bothers this person is
#: ordinary English and is the form all ten of `writers.BUILTIN` close on.
UNMARKED_AXES: Mapping[str, str] = {
    "interiority": (
        "no mark: a character's inside reaching the page is a construction rather than a "
        "character, and every narrow pattern for it fires on ordinary English"
    ),
    "stat_flatten": (
        "no mark: the closest candidate is the bracketed system tag, which would refuse a "
        "legitimate dossier for a shelf whose reader came for that tag"
    ),
}


def axes_exhibited(text: str) -> tuple[str, ...]:
    """Registered prose axes this text *carries the mark of*, in `EXHIBITION_MARKERS` order.

    The companion to `directors.prose_axes_named` and deliberately not a replacement: naming an
    axis and demonstrating one are two different acts with two different detectors, and a text
    can do either, both, or neither. What they share is the consequence — a dossier rides in the
    system message of every scene call, so either act answers a question the loop has open, in
    every prompt, with nothing to answer back.

    Substring rather than regex, because a mark is a character. Nothing is case-folded: a mark
    has no case, and folding would be a decision waiting to be wrong for the first marker that
    is a word.
    """
    return tuple(axis for axis, mark in EXHIBITION_MARKERS.items() if mark in text)


def exhibition_census(text: str) -> dict[str, int]:
    """How many times this text carries each registered mark. **A count, never a complaint.**

    Separate from `axes_exhibited` because the two are used at different distances: the tuple is
    what a gate asks, the counts are what an operator reads beside a dossier before deciding
    anything. `roster.check`'s census is where this lands, next to `appetite_markers` and
    `machinery_words`, and it is not a gate there for the same reason neither of those is.
    """
    return {axis: text.count(mark) for axis, mark in EXHIBITION_MARKERS.items()}


# ---------------------------------------------------------------------------
# The exemplar: a passage a writer drew as itself
# ---------------------------------------------------------------------------


def exemplar_digest_for(text: str) -> str:
    """The content address of an exemplar passage, canonical form first.

    **Full digest rather than the 24 hex characters `writer_id_for` truncates to.** A writer id
    is typed at a shell and read in a listing; an exemplar digest is compared — by a dedupe, by a
    leak audit, by a reader asking whether two writers were minted from one passage — and
    truncating a value whose only job is comparison is the wrong trade in the one place it costs
    something.

    `canonicalize` first, through `text.content_hash`, so a passage that crossed a Windows
    checkout addresses the same as the one that did not. `core.autocrlf` is global on this box.
    """
    if not text.strip():
        raise ValueError("an empty exemplar is not an exemplar; it is the unaimed draw")
    return f"{EXEMPLAR_DIGEST_PREFIX}{content_hash(text)}"


# ---------------------------------------------------------------------------
# The derived style descriptor: what may cross from the measurement side
# ---------------------------------------------------------------------------


class Person(enum.StrEnum):
    """Grammatical person, as a closed label. Lowercase for the reason `RosterStatus` is."""

    FIRST = "first"
    THIRD = "third"
    MIXED = "mixed"


class Tense(enum.StrEnum):
    """Narrative tense, as a closed label."""

    PAST = "past"
    PRESENT = "present"
    MIXED = "mixed"


class MalformedDescriptor(Exception):
    """A style descriptor that could not have been distilled from anything."""


#: Statistics a descriptor may **not** carry, by the axis each one would be a measurement of.
#: This is the rail that keeps the crossing legal, and it is narrower and more load-bearing than
#: it looks.
#:
#: A descriptor is a prose-craft statement by construction — sentence length and connective
#: density are exactly what `directors._PROSE_STYLE` refuses in a brief. What makes
#: the crossing legal is not that those numbers are innocent; it is **where they are allowed to
#: land**. They aim one draw, they never enter a dossier or a brief, and the gates on the
#: rewritten dossier (`legal_dossier` plus `axes_exhibited`) are what stop them arriving in the
#: text that repeats. A descriptor carrying a *registered measured axis*' own statistic would
#: break that: the number would aim the draw, the draw would demonstrate the axis, and the
#: rewritten dossier would carry it into every scene call — which is the em-dash loop being
#: answered by its own instrument's output.
#:
#: So: no punctuation rates of any kind, no interiority rate, no stat-block rate. Structural
#: rather than checked at runtime, because `StyleDescriptor`'s fields are fixed and a new one
#: costs an edit here; `test_a_descriptor_carries_no_registered_axis_statistic` is the mechanism.
REFUSED_DESCRIPTOR_STATISTICS: Mapping[str, str] = {
    "em_dash": "a punctuation rate aims the draw at the mark the em-dash loop is measuring",
    "interiority": "an interiority rate aims the draw at the axis the interiority work measures",
    "stat_flatten": "a stat-block rate aims the draw at the axis the flattening work measures",
}


@dataclass(frozen=True, slots=True)
class StyleDescriptor:
    """A voice reduced to numbers and closed labels, and to nothing else.

    **The corpus aims; the pretrained prior executes.** `plan/dossier-voice-direction.md` settles
    where voice Y's example text may come from, and its answer is that market prose may not enter
    a generation prompt — not for copyright, which was that note's own corrected overclaim, but
    for measurement independence. The market is this project's yardstick, and an artifact that is
    a partial function of the measurement corpus makes every ours-versus-market number partly a
    measurement of the market against itself. The permitted middle is a *derived descriptor*:
    numbers and labels, never prose.

    **This class is that boundary made structural.** Every field is a float or a member of a
    closed enum. There is no free-text field, so there is nowhere for a phrase to ride; there is
    no corpus identifier — no shard, no story id, no cohort name — so RS1's *no corpus digest
    crosses* holds by the shape of the record rather than by the care of whoever fills it in. The
    map from a descriptor to what it was distilled from lives on the measurement side, which is
    the side allowed to know.

    **What it costs, stated with it rather than discovered later.** The statistics a descriptor
    carries stop being independent measurements against the market for anything drafted under it.
    If writers are aimed at the market's sentence-length distribution, then comparing our
    sentence-length distribution to the market's measures our aim. `plan/dossier-voice-direction.md`
    §1 asks for exactly this accounting — *naming which instruments lose their independence* —
    before any raw crossing; the same accounting is owed for a derived one, at smaller scale, and
    the fields below are the list.
    """

    #: Words per sentence: centre, spread, and the two tails, because a mean alone cannot tell a
    #: uniformly mid-length voice from one that alternates short and long.
    sentence_words_mean: float
    sentence_words_sd: float
    sentence_words_p10: float
    sentence_words_p50: float
    sentence_words_p90: float
    #: Sentences per paragraph. The one structural number, and the cheapest thing a rewrite can
    #: get wrong while every word-level number is right.
    paragraph_sentences_mean: float
    #: Coordinating and subordinating connectives per hundred words: how much of the prose is
    #: clauses joined rather than sentences stopped.
    connective_density: float
    person: Person
    tense: Tense

    #: **A fragment rate was here and its own test deleted it, which is recorded rather than
    #: quietly tidied.** The detector approximated a finite verb by the closed auxiliary classes
    #: plus `\\w+ed` and `\\w+s`, and on the three-sentence fixture in `tests/test_voice.py` it
    #: called *"The floor gave way beneath him"* a fragment: an irregular past tense is neither.
    #: The available fix was a verb list, which is §127's shape — word lists in this repository
    #: are deleted with their causes and never converted — and a field named `fragment_rate`
    #: that is not a fragment rate is the lying-column defect `migrations/036`'s header names.
    #: `sentence_words_p10` already carries what the rate was wanted for.

    def __post_init__(self) -> None:
        for field_ in dataclass_fields(self):
            value = getattr(self, field_.name)
            if isinstance(value, (Person, Tense)):
                continue
            if not isinstance(value, float) or value != value or value < 0:
                raise MalformedDescriptor(
                    f"{field_.name} is {value!r}; every descriptor statistic is a "
                    "non-negative real, and a NaN here is a distillation that found nothing "
                    "reporting itself as a voice"
                )
        if not (
            self.sentence_words_p10 <= self.sentence_words_p50 <= self.sentence_words_p90
        ):
            raise MalformedDescriptor(
                f"the sentence-length quantiles are not ordered "
                f"({self.sentence_words_p10}, {self.sentence_words_p50}, "
                f"{self.sentence_words_p90}); p10 <= p50 <= p90 or the distillation read its "
                "own output backwards"
            )

    @property
    def descriptor_id(self) -> str:
        return descriptor_id_for(self)

    def as_labels(self) -> dict[str, str]:
        """The descriptor as the flat mapping a prompt and a decision row both render from.

        One renderer rather than two, for `house`'s reason: a number formatted one way in a
        prompt and another way on the record is a number nobody can join back.

        **Two decimals, and the address is taken over this form rather than over the floats.**
        Two distillations that render identically to a model *are* the same descriptor for every
        purpose this project has — they aim the same draw — and addressing the raw floats would
        mint a second id for a difference in the seventh decimal that no prompt can express.
        """
        return {
            field_.name: (
                str(getattr(self, field_.name))
                if isinstance(getattr(self, field_.name), (Person, Tense))
                else f"{getattr(self, field_.name):.2f}"
            )
            for field_ in dataclass_fields(self)
        }


def descriptor_id_for(descriptor: StyleDescriptor) -> str:
    """Content address over the descriptor's own numbers, and over nothing else.

    **The exclusion is the point.** Addressing a descriptor by what it was distilled from would
    put a corpus identifier in a value the generation side stores, prints and passes to a model,
    which is the crossing RS1 forbids stated as an id instead of as a passage. Addressing it by
    its numbers means two distillations that agree converge on one id — which is also the right
    answer for a replay — and that the measurement side keeps the only map back to a source.
    """
    material = "\x00".join(
        f"{name}={value}" for name, value in sorted(descriptor.as_labels().items())
    ).encode()
    return f"{DESCRIPTOR_ID_PREFIX}{sha256(material).hexdigest()[:24]}"


# ---------------------------------------------------------------------------
# Distillation: the arithmetic, so both sides compute one voice the same way
# ---------------------------------------------------------------------------

#: The connectives counted by `connective_density`. **A closed list and an admitted crudity.**
#: Word lists have been deleted from this repository with their causes recorded (§127), and the
#: reason this one survives is that it is not a rule and produces no cause: it defines a
#: statistic, the same statistic is computed over the market and over our own text by the same
#: function, and a word missing from it is missing from both sides of every comparison. A list
#: that biases a measurement equally in both arms shifts the number and not the contrast.
CONNECTIVES: frozenset[str] = frozenset(
    {
        "and",
        "but",
        "or",
        "nor",
        "yet",
        "so",
        "because",
        "although",
        "though",
        "while",
        "whereas",
        "since",
        "unless",
        "until",
        "when",
        "whenever",
        "where",
        "if",
        "as",
        "than",
        "that",
        "which",
        "who",
        "whom",
        "whose",
        "after",
        "before",
    }
)

#: A sentence boundary. Crude on purpose, `house.demands`' own justification: what this is for is
#: a number computed identically on both sides of a comparison, not a parser.
_SENTENCE = re.compile(r"[.!?…]+[\"')\]]*\s+|[.!?…]+[\"')\]]*$")

#: A word. The curly apostrophe is escaped rather than written, because a literal one in a
#: pattern is the ambiguous-character class `ruff` flags and this file is read more than most.
_WORD = re.compile("[A-Za-z\u2019']+")


def sentences(text: str) -> tuple[str, ...]:
    """Sentence-like units, by `_SENTENCE`. Empty units are dropped, never counted as short."""
    return tuple(part.strip() for part in _SENTENCE.split(text) if part and part.strip())


def paragraphs(text: str) -> tuple[str, ...]:
    """Paragraph-like units: a blank line, or a lone line break where there are no blank ones."""
    canonical = canonicalize(text)
    blocks = [block.strip() for block in canonical.split("\n\n") if block.strip()]
    if len(blocks) > 1:
        return tuple(blocks)
    return tuple(line.strip() for line in canonical.split("\n") if line.strip())


def distill(
    passages: Sequence[str], *, person: Person, tense: Tense
) -> StyleDescriptor:
    """A descriptor from text, computed identically wherever it is computed.

    **In the domain rather than in the research package, and that is not a layering slip.** The
    measurement side distils the market and the generation side has to be able to compute the
    same numbers over our own prose, or the descriptor is a target nothing can be read against.
    Two implementations of one statistic is the defect this repository keeps finding under the
    name *a second home*, so there is one function and both sides call it.

    **It reads text it is handed and never reaches for a corpus.** RS1 is a rule about what
    `src/` may reference, not about what arithmetic may exist: `tests/test_corpus_leak_audit.py`
    checks that nothing here names a corpus, and nothing here does. The caller on the market side
    is `research/quality-measurement/`, which is allowed to open the shards and is not allowed to
    commit what it read.

    `person` and `tense` are arguments rather than derived, and the honesty is deliberate: no
    reliable mechanical detector for either exists in this repository, inventing one here would
    be a craft metric arriving through a helper function, and both are cheap for the measurement
    side to establish and record beside the numbers it did compute.
    """
    units = [unit for passage in passages for unit in sentences(passage)]
    if not units:
        raise MalformedDescriptor(
            "no sentence-like unit in any passage; a descriptor over nothing is a voice "
            "nobody has"
        )
    lengths = [float(len(_WORD.findall(unit))) for unit in units]
    words = sum(lengths)
    connectives = sum(
        1
        for passage in passages
        for word in _WORD.findall(passage.casefold())
        if word in CONNECTIVES
    )
    block_counts = [
        float(len(sentences(block))) for passage in passages for block in paragraphs(passage)
    ]
    ordered = sorted(lengths)
    return StyleDescriptor(
        sentence_words_mean=statistics.fmean(lengths),
        sentence_words_sd=statistics.pstdev(lengths) if len(lengths) > 1 else 0.0,
        sentence_words_p10=_quantile(ordered, 0.10),
        sentence_words_p50=_quantile(ordered, 0.50),
        sentence_words_p90=_quantile(ordered, 0.90),
        paragraph_sentences_mean=(
            statistics.fmean(block_counts) if block_counts else float(len(units))
        ),
        connective_density=(100.0 * connectives / words) if words else 0.0,
        person=person,
        tense=tense,
    )


#: How long a run of identical words may be, between a passage and a text rewritten to read like
#: it, before the rewrite is a copy rather than a register.
#:
#: **The one control the prior art says this design cannot go without.**
#: `research/quality-measurement/voice_binding.py` is the exemplar-dose experiment §85 ran, and
#: its whole design is a *borrowing* control: a model shown somebody's prose can move toward it
#: by picking up the deep features the register is made of, or by lifting their phrases, and a
#: distance measure cannot tell those apart. There the control is n-gram overlap against a shown
#: pool and a held-out pool; here, where one passage is shown to one rewrite, the cheap
#: equivalent is the longest run the two share.
#:
#: Six, chosen before any draw and stated with its direction of failure: two texts about
#: different things share a six-word run essentially never, so the refusal is high-precision, and
#: a rewrite that shares nothing passes without being asked to. It **can** fail — a rewrite that
#: lifts a clause trips it — which is the property `BRIEF.md` §2 Pass 5 records a control needing.
SHARED_RUN_LIMIT = 6


def longest_shared_run(first: str, second: str) -> int:
    """The longest run of identical consecutive words the two texts share, case-folded.

    Whole words rather than content words: a stop-word list is a word list, and the strictness
    costs nothing here because six consecutive words including its stop words is still a lifted
    clause rather than a coincidence.
    """
    left = [word.casefold() for word in _WORD.findall(first)]
    right = [word.casefold() for word in _WORD.findall(second)]
    if not left or not right:
        return 0
    # Row-by-row dynamic programming: `previous[j]` is the run ending at `left[i-1]`/`right[j-1]`.
    previous = [0] * (len(right) + 1)
    best = 0
    for word in left:
        current = [0] * (len(right) + 1)
        for position, other in enumerate(right, start=1):
            if word == other:
                current[position] = previous[position - 1] + 1
                best = max(best, current[position])
        previous = current
    return best


#: The two closed pronoun classes `person_of` counts, and a closed class is the whole reason
#: this list is allowed to exist where a verb list is not: English stopped minting pronouns, so
#: the list cannot rot the way `_FINITE`'s did before its own test deleted it.
FIRST_PERSON: frozenset[str] = frozenset(
    {"i", "me", "my", "mine", "myself", "we", "us", "our", "ours", "ourselves"}
)
THIRD_PERSON: frozenset[str] = frozenset(
    {"he", "him", "his", "himself", "she", "her", "hers", "herself", "they", "them",
     "their", "theirs", "themselves"}
)

#: How far apart the two counts must be before a text is called one person rather than mixed.
#: **A label rule stated before use, not a bar**: it declares nothing about quality, it is
#: applied identically to the market side and to ours, and §61's attainability checks are about
#: declared thresholds on a measured quantity, which this is not.
PERSON_MARGIN = 2.0


def person_of(text: str) -> Person:
    """Grammatical person by pronoun share. **Mechanical, so both sides agree by construction.**

    `distill` takes `person` and `tense` as arguments rather than deriving them, because no
    reliable mechanical detector for either existed here — and person turned out to be the half
    that does. Narrative person is carried by a class English stopped adding to, so counting it
    is arithmetic rather than a craft judgment, and a measurement side that had to *decide* the
    person of a hundred and twenty-six chapters would be putting a hundred and twenty-six
    judgments into a number.

    **Tense stays an argument and the gap is stated.** Its closed auxiliaries are reliable in
    narration and unreliable in dialogue, where present-tense speech sits inside past-tense
    prose, and the fix is a dialogue parser rather than a longer list. §146.4's move: name what
    was refused, do not half-close it.
    """
    words = [word.casefold() for word in _WORD.findall(text)]
    first = sum(1 for word in words if word in FIRST_PERSON)
    third = sum(1 for word in words if word in THIRD_PERSON)
    if first > third * PERSON_MARGIN:
        return Person.FIRST
    if third > first * PERSON_MARGIN:
        return Person.THIRD
    return Person.MIXED


def _quantile(ordered: Sequence[float], share: float) -> float:
    """Nearest-rank quantile over an already-sorted sequence.

    Nearest-rank rather than interpolated because a descriptor is compared for equality by
    `descriptor_id_for`, and an interpolation scheme is a choice two implementations can make
    differently while both being defensible. This one cannot.
    """
    if not ordered:
        return 0.0
    index = min(len(ordered) - 1, max(0, round(share * (len(ordered) - 1))))
    return float(ordered[index])


__all__ = [
    "CONNECTIVES",
    "DESCRIPTOR_ID_PREFIX",
    "EXEMPLAR_DIGEST_PREFIX",
    "EXHIBITION_MARKERS",
    "FIRST_PERSON",
    "PERSON_MARGIN",
    "REFUSED_DESCRIPTOR_STATISTICS",
    "SHARED_RUN_LIMIT",
    "THIRD_PERSON",
    "UNMARKED_AXES",
    "MalformedDescriptor",
    "Person",
    "StyleDescriptor",
    "Tense",
    "axes_exhibited",
    "descriptor_id_for",
    "distill",
    "exemplar_digest_for",
    "exhibition_census",
    "longest_shared_run",
    "paragraphs",
    "person_of",
    "sentences",
]
