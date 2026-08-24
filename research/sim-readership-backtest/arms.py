"""Session construction for the sim-readership backtest: describe-then-behave, both orders.

PREREG.md §5 is the contract here. Each session is one elicitation cell — pair x persona x
order x arm — and carries exactly two turns: stage 1 asks the persona to name the concrete
differences it noticed between two blinded excerpts (free text, never scored, operator-side
diagnostic only), and stage 2 emits one schema-constrained behavioural action plus at most
one reason code from a closed set. No quality vocabulary appears anywhere in either turn or
in the schema, and no persona ever outputs a verdict: behavioural vocabulary is the only
output this module lets a persona produce.

This module builds the exact requests a transport will send and parses what comes back; it
never constructs an `Elicitor`, performs no call, touches no network, and reads no corpus.
The blinding callable arrives as a parameter (`blinding.blind`'s seam), so every behaviour
here is checkable on synthetic fictions without any I/O.

The sample index folds (pair_id, persona_id, order) into one stable integer the way
`feed_session.py` folds replicate into step: the replay cache keys on a digest of the request
plus this index, and ollama uses it as the sampler seed, so two distinct sessions must never
share one.
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import blinding  # noqa: E402  # sibling research module, imported by path
import corpus  # noqa: E402  # sibling research module, imported by path

#: Byte-frozen turns; a reworded prompt is a different instrument with no evidence behind it.
#: Stage 1 presents the two excerpts through exactly the {a} and {b} slots and asks for
#: concrete differences only — no preference is requested and no verdict vocabulary appears.
STAGE1_TURN: str = (
    "Below are the openings of two serialised web fictions.\n\n"
    "Book A:\n\n{a}\n\n"
    "Book B:\n\n{b}\n\n"
    "In 2-3 sentences, name the concrete differences you noticed between these two openings: "
    "what happens, who is on the page, how the reading time is spent."
)

#: Stage 2's single question: with your own limited reading time, which would you continue -
#: or would you abandon both? Answer as JSON, one reason code from the closed list at most.
STAGE2_TURN: str = (
    "You have limited reading time and can keep going with only one of these openings - or "
    "with neither. Which would you continue reading: Book A, Book B, or neither?\n\n"
    'Answer as a single JSON object: {"continue": "A" | "B" | "neither", "reason": "<code>"} '
    "where <code> is one of slow-start, no-advancement, prose-friction, seen-it-before, "
    'confusing, wrong-genre-for-me, hooked-by-other, or "".'
)

#: One reason code per abandonment driver the population's taste axes cover (PREREG §6), in
#: fixed order, plus "" for a decision that moved on nothing the axes name. Codes say why a
#: reader moved — never how good a text is.
REASON_CODES: tuple[str, ...] = (
    "slow-start",
    "no-advancement",
    "prose-friction",
    "seen-it-before",
    "confusing",
    "wrong-genre-for-me",
    "hooked-by-other",
    "",
)

#: Stage 2's closed schema. Both fields are required because an absent field defaulting
#: benign is a known defect shape (the §69 lesson); additionalProperties is false because an
#: open schema lets a verdict in through a side door.
STAGE2_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "continue": {"enum": ["A", "B", "neither"]},
        "reason": {"enum": list(REASON_CODES)},
    },
    "required": ["continue", "reason"],
    "additionalProperties": False,
}

#: C-arm excerpt cap in words (PREREG §2): each side capped here, truncation only at a
#: paragraph boundary, truncation recorded by the caller via the excerpt digests.
EXCERPT_CAP_WORDS = 6000

#: P-arm opening length in words (PREREG §2): first ~500 words of chapter 1, extended to the
#: paragraph boundary past word 500 by `blinding.first_words`.
PREMISE_WORDS = 500

#: The sham windows differ by dropping this many leading paragraphs before re-applying the
#: cap (§120.2: a byte-identical sham cannot move, so it is no control).
SHAM_OFFSET_PARAGRAPHS = 2

_STAGE1_MAX_TOKENS = 300
_STAGE2_MAX_TOKENS = 60


class Blinds(Protocol):
    """Anything exposing `blinding.blind`'s seam; callers pass the real function."""

    def __call__(self, text: str, *, title: str, author: str) -> blinding.Blinded: ...


@dataclass(frozen=True, slots=True)
class SessionSpec:
    """One elicitation cell: which pair, which persona, which order, which arm."""

    pair_id: str
    arm: str  # "C" | "P" | control arm names ("sham", "damage", ...)
    persona_id: str
    order: int  # 0 = (high outcome as A); 1 = swapped
    excerpt_a_digest: str
    excerpt_b_digest: str


def _cap_paragraph(text: str, limit: int = EXCERPT_CAP_WORDS) -> str:
    """Whole paragraphs up to `limit` words; never cut inside one.

    Paragraphs are taken while the running total stays within the limit, so a multi-paragraph
    text always lands at or under the cap with the cut exactly between paragraphs. A single
    paragraph longer than the limit is shown whole — cutting mid-paragraph is the one thing
    the cap must not do — and empty input returns empty.
    """
    kept: list[str] = []
    seen = 0
    for paragraph in text.split("\n\n"):
        words = len(paragraph.split())
        if kept and seen + words > limit:
            break
        kept.append(paragraph)
        seen += words
    return "\n\n".join(kept)


def _joined_opening(fiction: corpus.Fiction) -> tuple[corpus.Chapter, ...]:
    """Chapters 1-3 or a ValueError naming the fiction; eligibility should have filtered."""
    chapters = corpus.chapters_1_to_3(fiction)
    if chapters is None:
        raise ValueError(
            f"arms: chapters 1-3 unidentifiable for fiction {fiction.fiction_id!r}"
        )
    return chapters


# ---------------------------------------------------------------------------------- stimuli


def c_arm_texts(
    pair: corpus.Pair, fictions: Mapping[str, corpus.Fiction], blind: Blinds
) -> tuple[str, str]:
    """The two C-arm stimuli: capped chapters 1-3, blinded, high-outcome member first.

    For each member the identified opening chapters are joined with blank lines, capped at
    `EXCERPT_CAP_WORDS` at a paragraph boundary, then run through `blind`. Returns
    (high_text, low_text) BEFORE ordering — applying the session order is `ordered`'s job,
    and it is the only place that happens. Raises KeyError for a pair member absent from
    `fictions`: a missing stimulus is a caller bug, not an empty excerpt.
    """
    return (
        _c_arm_text(fictions[pair.high], blind),
        _c_arm_text(fictions[pair.low], blind),
    )


def _c_arm_text(fiction: corpus.Fiction, blind: Blinds) -> str:
    chapters = _joined_opening(fiction)
    joined = "\n\n".join(chapter.text for chapter in chapters)
    capped = _cap_paragraph(joined)
    return blind(capped, title=fiction.title, author=fiction.author).text


def p_arm_texts(
    pair: corpus.Pair, fictions: Mapping[str, corpus.Fiction], blind: Blinds
) -> tuple[str, str]:
    """The two P-arm stimuli: blinded blurb plus the first ~500 words of chapter 1.

    Per member: the description joined to chapter 1's opening extended past word 500 to the
    next paragraph boundary (`blinding.first_words`), blinded once so the excerpt carries one
    content address. Returns (high_text, low_text) BEFORE ordering. Raises KeyError for an
    absent pair member and ValueError when a member's opening chapters are unidentifiable —
    a premise session without its chapter text would be a different instrument wearing the
    same tag, so it refuses rather than degrades silently.
    """
    return (
        _p_arm_text(fictions[pair.high], blind),
        _p_arm_text(fictions[pair.low], blind),
    )


def _p_arm_text(fiction: corpus.Fiction, blind: Blinds) -> str:
    chapters = _joined_opening(fiction)
    opening = blinding.first_words(chapters[0].text, PREMISE_WORDS)
    parts = [part for part in (fiction.description.strip(), opening.strip()) if part]
    return blind("\n\n".join(parts), title=fiction.title, author=fiction.author).text


def ordered(high_text: str, low_text: str, order: int) -> tuple[str, str]:
    """Apply the session order: 0 keeps (high, low) as (A, B); 1 swaps them.

    This is the ONLY place order is applied anywhere in the pipeline, so a positional
    artifact is attributable to exactly these lines. Any other order value raises: a silent
    identity mapping for an unregistered order would fold two cells into one.
    """
    if order == 0:
        return high_text, low_text
    if order == 1:
        return low_text, high_text
    raise ValueError(f"order must be 0 or 1, got {order!r}")



# --------------------------------------------------------------------------- the full request


def build_session(spec: SessionSpec, system: str, text_a: str, text_b: str) -> dict[str, Any]:
    """The full request the transport will send, stage-1 fields at top level.

    Shape: {"system", "turns", "schema" (None for stage 1), "plan", "tag", "sample"}.
    `plan` holds both stages in call order — stage 1 free text at 300 tokens, stage 2 under
    `STAGE2_SCHEMA` at 60 — and the top-level `turns`/`schema` mirror plan[0], the request
    the first `ask_raw` sends. `tag` carries every SessionSpec field so any cached record can
    be attributed back to its cell without consulting run state.

    `sample` is `_sample_index(spec)`: stable across runs and platforms, and distinct across
    cells for the collision-freedom argument documented there.
    """
    plan: list[dict[str, Any]] = [
        {
            "turns": [{"role": "user", "content": STAGE1_TURN.format(a=text_a, b=text_b)}],
            "schema": None,
            "max_tokens": _STAGE1_MAX_TOKENS,
        },
        {
            "turns": [{"role": "user", "content": STAGE2_TURN}],
            "schema": STAGE2_SCHEMA,
            "max_tokens": _STAGE2_MAX_TOKENS,
        },
    ]
    return {
        "system": system,
        "turns": plan[0]["turns"],
        "schema": None,
        "plan": plan,
        "tag": asdict(spec),
        "sample": _sample_index(spec),
    }


def _sample_index(spec: SessionSpec) -> int:
    """A stable integer folding (pair_id, persona_id, order); see the collision argument.

    sha256 over the NUL-joined fields, first 16 hex digits as an integer — 64 bits. Two
    sessions share an index only if they share all three folded fields, i.e. are the same
    cell. Truncated-hash collisions are theoretically possible, so the bound is stated: the
    registered capacity is ~989 pairs x 10 personas x 2 orders (~20k sessions), whose
    birthday probability at 64 bits is ~2e-11 — orders of magnitude under any other error
    source in the pipeline. And unlike `feed_session`'s arithmetic scheme, the request bytes
    themselves already differ per cell (different excerpts, different system), so the replay
    cache collides only if BOTH the request digest and this index collide.
    """
    payload = "\x00".join((spec.pair_id, spec.persona_id, str(spec.order)))
    return int(hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16], 16)


# ----------------------------------------------------------------------------------- parsing


_CHOICES = frozenset({"A", "B", "neither"})
_REASONS = frozenset(REASON_CODES)


def parse_stage2(text: str) -> tuple[str, str] | None:
    """("A"|"B"|"neither", reason) out of the raw stage-2 text, or None.

    Refused, empty, non-JSON, not an object, a key missing, an extra key, or a value outside
    its enum are all the same outcome: one None, no partial credit, mirroring
    `feed_session._parse_choice`. Folding a malformed answer into the record would put a
    format failure into a behavioural distribution; "neither" is a reader's decision and is
    parsed like any other. The key set is checked exactly — the schema forbids extras, so
    the parser does too (an accepted extra field is a verdict arriving through a side door).
    """
    if not text:
        return None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict) or set(parsed) != {"continue", "reason"}:
        return None
    choice = parsed["continue"]
    reason = parsed["reason"]
    if (
        isinstance(choice, str)
        and choice in _CHOICES
        and isinstance(reason, str)
        and reason in _REASONS
    ):
        return choice, reason
    return None


# ------------------------------------------------------------------------------------ shams


def sham_windows(fiction: corpus.Fiction, blind: Blinds) -> tuple[str, str] | None:
    """The C1 sham stimuli: two DIFFERENT capped windows of one book's chapters 1-3.

    Window one is the ordinary C-arm cap; window two drops `SHAM_OFFSET_PARAGRAPHS` leading
    paragraphs and re-applies the same cap. Different bytes, same outcome by construction —
    a byte-identical sham cannot move and is no control (§120.2), so equality after blinding
    returns None rather than a control that cannot fire. Also None when the book yields no
    identifiable opening (nothing to window) or too short a text (the offset leaves nothing).
    """
    chapters = corpus.chapters_1_to_3(fiction)
    if chapters is None:
        return None
    paragraphs = "\n\n".join(chapter.text for chapter in chapters).split("\n\n")
    if len(paragraphs) <= SHAM_OFFSET_PARAGRAPHS:
        return None
    first_raw = _cap_paragraph("\n\n".join(paragraphs))
    second_raw = _cap_paragraph("\n\n".join(paragraphs[SHAM_OFFSET_PARAGRAPHS:]))
    first = blind(first_raw, title=fiction.title, author=fiction.author).text
    second = blind(second_raw, title=fiction.title, author=fiction.author).text
    if not second or first == second:
        return None
    return first, second
