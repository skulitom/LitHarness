"""The production comprehension screen: four readers restate a premise before a person sees it.

**What this is.** Every premise the forge writes is shown to four genre readers, and each one
answers the same five questions in their own words: what this person can do that nobody else
can, what is in the way, what kind of book this is and what happens next, every word used as
if they already knew it, and every question they expect the book itself to answer. A premise
passes at **zero undefined words across all four readers**, and nothing else about the answers
gates anything. The open questions are reported beside the result and never counted against it:
a pitch that leaves questions it plans to answer is working, which is what
`research/quality-measurement/comprehension_battery.py` learned when one counter tried to
measure a withheld hook and an unexplained word at the same time.

**Nothing here judges, ranks, or orders.** Four readers say what they could not follow; the
count is arithmetic; the forge refuses on the count. No model is asked which premise is better
and none is asked whether this one is any good — §61(5) and §105.1 are why, and
`plan/world-architect.md` §2's rail is unchanged: K candidates are generated, gated, and
stopped, and a person picks among what passed.

**Why the readers here carry no titles.** These four are derived from the research panel in
`research/quality-measurement/personas.py` (`GENRE_PANEL`), which carries `anchors` — named
published works, each with a verdict and a reason. Anchor text may enter measurement and may
**never** enter a drafting, revision or planning prompt (§97.3, enforced by provenance rather
than by pattern). This module runs inside `forge`, in the same process that writes the premise,
so it is on the generation side of that line: the readers below are **title-free derivations**
of the panel's four roles — the `reads_for` and the `drops_on`, and nothing else. The same
boundary `architect._BORROWED`'s docstring refuses to cross from the other direction.

**And the research battery is untouched, on purpose.**
`research/quality-measurement/comprehension_battery.py` keeps its own panel, its own model and
its own scorer. It is the measuring stick the clarity work's before and after are read off, and
a measuring stick that moves with the thing it measures measures nothing. This module is the
production screen. `ANSWER_SCHEMA` below is therefore a **copy** rather than an import — the
research tree sits outside `src/` and nothing in the package may import it — and the two are
allowed to drift: a change to one is not a change to the other, and the numbers they produce
are labelled as coming from different instruments wherever both are reported.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, TypeGuard

from litharness.domain.generation import CompletionRequest

#: Frozen generation profile for a reader call, recorded in provenance and carried on the
#: screen's own decision row so the screen's spend is separable from the forge's.
SCREEN_PROFILE = "architect.screen.v0"

#: The same call class the world and the premise use. A reader answering a schema is mechanical
#: work, and the pinned production provider is the point: the operator's requirement is that the
#: model producing the premises is also shown to understand them, which only holds if both calls
#: resolve to the same tier.
CALL_CLASS = "generation"

#: Five short answers about one paragraph. Measured on the research battery's own runs: 700 was
#: enough there, and this is the same question with the same schema against a larger model whose
#: thinking counts against the budget.
READER_MAX_OUTPUT_TOKENS = 1500


@dataclass(frozen=True, slots=True)
class Reader:
    """One genre reader, as the screen introduces them to themselves.

    Four fields and no anchors: see the module docstring. `reads_for` and `drops_on` are the
    research panel's own strings for these roles, which is what makes the two instruments
    comparable at all without either carrying what the other may not.
    """

    reader_id: str
    name: str
    reads_for: str
    drops_on: str

    def system(self) -> str:
        """The reader as a system message.

        Deliberately **not** `house.with_house_rules`: the house rules tell a role that is
        writing prose how to write it, and a reader is not writing prose. Appending them here
        would put a writing instruction inside the instrument that checks writing, which is the
        contamination the whole screen exists to be free of.
        """
        return (
            f"You are {self.name}. You read for {self.reads_for}. You stop reading on "
            f"{self.drops_on}. You answer questions about what you read in your own words, "
            "as yourself."
        )


#: The four, in the research panel's own order. Their ids are the panel's ids so a production
#: screen and a research battery run over the same premise can be read side by side — the same
#: reason `ANSWER_SCHEMA` is copied verbatim rather than paraphrased.
READERS: tuple[Reader, ...] = (
    Reader(
        reader_id="climber",
        name="the progression and cultivation reader",
        reads_for=(
            "a climb with rules — what the next rung costs, and what it lets somebody do that "
            "they could not do before"
        ),
        drops_on=(
            "figures that move without changing what anyone can do. I start a lot of serials "
            "and drop most of them inside three chapters"
        ),
    ),
    Reader(
        reader_id="stranger",
        name="the isekai and portal reader",
        reads_for=(
            "somebody dropped into a world whose rules they have to work out, using what they "
            "already knew how to do"
        ),
        drops_on=(
            "terms and ranks used as if I already knew them, or a newcomer who arrives fluent. "
            "Most portal stories lose me in the first chapter and I stop there"
        ),
    ),
    Reader(
        reader_id="regular",
        name="the cozy, academy and slow-burn reader",
        reads_for=(
            "a place worth coming back to, and people who get better at something slowly "
            "enough that I see it happen"
        ),
        drops_on=(
            "grimness for its own sake, or a story that skips the years it told me mattered. I "
            "abandon more books than I finish and I do it without guilt"
        ),
    ),
    Reader(
        reader_id="mechanism",
        name="the science-fiction and superhero reader",
        reads_for=(
            "powers with a mechanism under them, and consequences that follow from the "
            "mechanism rather than from what the scene needs"
        ),
        drops_on=(
            "hand-waving where the rule should be, or an ability that does whatever is "
            "convenient. I read the first chapter of most things and go no further"
        ),
    ),
)

#: **Copied verbatim from `research/quality-measurement/comprehension_battery.py`, and the copy
#: is the point.** The research module is the frozen measuring stick and this is the production
#: screen; the package may not import from the research tree (it sits outside `src/` and CI must
#: never need it), and even if it could, an import would make the two one instrument. A change
#: to one is **not** a change to the other. If they are ever edited together, that is a decision
#: for the ledger, not a refactor.
#:
#: The two-list split is the research module's measured correction and is carried here with it:
#: one counter could not separate a withheld hook from an unexplained word, so a human-written
#: reference pitch drew five "could not follow" items that were all questions a pitch exists to
#: raise. `undefined_words` is the gated half; `open_questions` is reported and never gated.
ANSWER_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["can_do", "in_the_way", "expect_next", "undefined_words", "open_questions"],
    "properties": {
        "can_do": {
            "type": "string",
            "description": "In your own words: what can this person do that nobody else can? "
                           "One or two plain sentences. Do not reuse the text's phrasing.",
        },
        "in_the_way": {
            "type": "string",
            "description": "In your own words: what is in the way, or what does it cost them?",
        },
        "expect_next": {
            "type": "string",
            "description": "What kind of book is this, and what do you expect to happen next?",
        },
        "undefined_words": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Words or phrases used as if you already knew them, where you were "
                           "never told what they mean. Quote each one. Empty list if none.",
        },
        "open_questions": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Things you expect the book itself to answer later — a hook, a "
                           "withheld fact, something you want to read on for. These are not "
                           "faults. Quote each one. Empty list if none.",
        },
    },
}

#: The research battery's own wording, kept verbatim for the same reason the schema is: the two
#: instruments answer the same question of the same paragraph, and a premise screened here and
#: measured there should differ by panel and model rather than by what was asked.
_ASK = (
    "That is the back-cover copy of a book you just picked up. Answer in your own words, as if "
    "telling a friend — do not quote the text back."
)


def render_reader_request(reader: Reader, premise: str) -> CompletionRequest:
    """One reader, one premise, five answers.

    The premise and nothing else — `plan/handoff-clarity-first.md` boundary 6: an elicitation
    carries exactly what a real reader would have at that point. Somebody reading a back cover
    has the back cover, so no world record, no title, no forge context and no sibling premise
    reaches this call.
    """
    return CompletionRequest(
        prompt=f"{premise.strip()}\n\n---\n\n{_ASK}",
        system=reader.system(),
        schema=ANSWER_SCHEMA,
        max_output_tokens=READER_MAX_OUTPUT_TOKENS,
        profile=SCREEN_PROFILE,
        call_class=CALL_CLASS,
    )


def _is_quote_list(value: Any) -> bool:
    """Whether one answer's list field is a list of quoted strings and nothing else.

    **Every item is checked, and the reason is that nothing upstream checks them.**
    `providers.base.parse_schema_payload` validates required keys and top-level types, so
    `undefined_words: [1, null]` arrives as a conforming answer. Coercing those with `str()`
    would invent the quoted words `1` and `None`, fail the premise on them, and store them as
    the evidence of what a reader could not follow. Refusing the answer instead fails the
    attempt, which is the direction this instrument always fails in.
    """
    if not isinstance(value, Sequence) or isinstance(value, str | bytes):
        return False
    return all(isinstance(item, str) for item in value)


def _quotes(value: Any) -> tuple[str, ...]:
    """The non-empty quoted strings of one answer's list field. Only called on a checked list.

    An empty string is not a quoted word and neither is whitespace, so neither is counted as a
    confusion.
    """
    if not _is_quote_list(value):
        return ()
    return tuple(text for item in value if (text := str(item).strip()))


def _conforms(answer: Any) -> TypeGuard[Mapping[str, Any]]:
    """Whether one reader's answer can be read as an answer at all.

    Strict on the two lists rather than on all five fields, and the direction is deliberate: a
    reader whose `undefined_words` cannot be read has **not** said there were none, and the
    screen may never read silence as a pass. The prose fields are reported and not gated, so a
    short one costs nothing.
    """
    if not isinstance(answer, Mapping):
        return False
    return all(
        _is_quote_list(answer.get(key)) for key in ("undefined_words", "open_questions")
    )


@dataclass(frozen=True, slots=True)
class ScreenResult:
    """What four readers made of one premise. A count and its evidence, never a verdict."""

    #: Each reader's answer exactly as it parsed, in `READERS` order — `None` only where no
    #: answer arrived at all. **An answer that is present and unreadable is kept**, because it
    #: is the evidence of what went wrong; which readers were readable is `undefined_by_reader`,
    #: whose keys are exactly the conforming set.
    answers: tuple[tuple[str, Mapping[str, Any] | None], ...]
    undefined_by_reader: tuple[tuple[str, tuple[str, ...]], ...]
    open_questions_by_reader: tuple[tuple[str, tuple[str, ...]], ...]
    #: How many readers quoted at least one word they were never given.
    readers_confused: int
    undefined_total: int
    #: Whether every reader answered in a shape the screen could read.
    conformed: bool

    @property
    def passed(self) -> bool:
        """Zero undefined words across all four, and all four readable.

        Both halves are required and the second is the one that is easy to drop: a screen that
        called a run clean because three readers answered and the fourth returned nothing would
        pass a premise on the strength of a provider error.
        """
        return self.conformed and self.undefined_total == 0

    @classmethod
    def of(cls, answers: Mapping[str, Mapping[str, Any] | None]) -> ScreenResult:
        """Build the result from what came back, in `READERS` order.

        A reader the caller never ran is absent from `answers` and counts as non-conforming —
        a screen that could not be completed did not pass, which is the same rail `_conforms`
        states one reader at a time.
        """
        ordered = [(reader.reader_id, answers.get(reader.reader_id)) for reader in READERS]
        readable = {
            reader_id: answer for reader_id, answer in ordered if _conforms(answer)
        }
        undefined = tuple(
            (reader_id, _quotes(readable[reader_id].get("undefined_words")))
            for reader_id, _ in ordered
            if reader_id in readable
        )
        questions = tuple(
            (reader_id, _quotes(readable[reader_id].get("open_questions")))
            for reader_id, _ in ordered
            if reader_id in readable
        )
        return cls(
            answers=tuple(ordered),
            undefined_by_reader=undefined,
            open_questions_by_reader=questions,
            readers_confused=sum(1 for _, quoted in undefined if quoted),
            undefined_total=sum(len(quoted) for _, quoted in undefined),
            conformed=len(readable) == len(READERS),
        )

    def to_jsonable(self) -> dict[str, Any]:
        """The block that lands in every forged bundle beside the premise it screened.

        The quoted words are carried and not only counted. A count says a premise failed; the
        words say what a reader could not follow, and the operator reading the forge output is
        the only consumer either of them has — **nothing here is fed back into a prompt**
        (§97.1, and `plan/handoff-clarity-first.md` boundary 5: a failed premise is re-forged,
        never rewritten from a reader's quotes).
        """
        return {
            "passed": self.passed,
            "conformed": self.conformed,
            "readers": [reader.reader_id for reader in READERS],
            "readers_confused": self.readers_confused,
            "undefined_total": self.undefined_total,
            "undefined_by_reader": {
                reader_id: list(quoted) for reader_id, quoted in self.undefined_by_reader
            },
            "open_questions_by_reader": {
                reader_id: list(quoted) for reader_id, quoted in self.open_questions_by_reader
            },
            "answers": {
                reader_id: (dict(answer) if isinstance(answer, Mapping) else None)
                for reader_id, answer in self.answers
            },
        }


__all__ = [
    "ANSWER_SCHEMA",
    "CALL_CLASS",
    "READERS",
    "READER_MAX_OUTPUT_TOKENS",
    "SCREEN_PROFILE",
    "Reader",
    "ScreenResult",
    "render_reader_request",
]
