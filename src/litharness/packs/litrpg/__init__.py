"""The first domain pack: LitRPG and progression fantasy, as this house has read it.

Everything here was moved out of `application/readers.py` and `domain/rivals.py` on
2026-09-03 (stage-0 §221) with its bytes unchanged: the readers' framing sentence, the eight
readers, the no-taste roster, and the genre set a rival may be filed under. The comments travel
with the constants because the constants are only worth what their reasons are.

The essays the pack carries as tier 3 (§129) are `house.READER` and `house.ACCUMULATION`, and
they stay in `domain/house.py`: `HOUSE_RULES` reaches every writer prompt byte for byte, and
moving the text would change every stored policy digest for nothing. The pack points at them.
"""

from __future__ import annotations

from litharness.domain import audience, house
from litharness.domain.audience import MEASUREMENT, STEERING, AudienceSpec, Reader, StopRule
from litharness.packs import Pack

PACK_ID = "litrpg"

#: How a reader of this pack is introduced to itself. This was the literal inside the old
#: `Reader.system`, and every LitRPG reader still renders it first.
FRAMING = (
    "You read a lot of LitRPG and progression fantasy — several serials at once, and "
    "you drop most of what you start."
)

#: The genres this project's readership reads, which is the same ground `writers.CAST` covers.
#: Membership is checked rather than inferred, and a refusal names the set so an operator can see
#: what to widen. Deliberately not a taxonomy: it is a list of the labels this market uses for
#: the books these readers read, and it has no meaning outside that.
GENRES: frozenset[str] = frozenset(
    {
        "litrpg",
        "progression fantasy",
        "portal fantasy",
        "isekai",
        "cultivation",
        "system apocalypse",
        "reincarnation",
        "dungeon core",
    }
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
        "power_s",
        STEERING,
        framing=FRAMING,
        reads_for="watching somebody go from nothing to genuinely dangerous, and getting to feel "
        "every jump on the way",
        drops_on="a main character who is already the strongest thing in the room on page one",
    ),
    Reader(
        "elsewhere_s",
        STEERING,
        framing=FRAMING,
        reads_for="getting dropped somewhere impossible and working out how it runs at the same "
        "time the character does",
        drops_on="names and titles thrown around like I am supposed to already know them",
    ),
    Reader(
        "magic_s",
        STEERING,
        framing=FRAMING,
        reads_for="the magic itself — what it actually does, how strange it gets, and somebody "
        "working out a use for it that nobody else had",
        drops_on="a world where the magic turns out to be a job with forms to fill in",
    ),
    Reader(
        "binge_s",
        STEERING,
        framing=FRAMING,
        reads_for="somewhere I want to keep coming back to, people I like being around, and the "
        "next good thing always close enough to reach",
        drops_on="misery with nothing to look forward to, or a book that skips the part it told "
        "me to care about",
    ),
    Reader(
        "power_m",
        MEASUREMENT,
        framing=FRAMING,
        reads_for="watching somebody go from nothing to genuinely dangerous, and getting to feel "
        "every jump on the way",
        drops_on="a main character who is already the strongest thing in the room on page one",
    ),
    Reader(
        "elsewhere_m",
        MEASUREMENT,
        framing=FRAMING,
        reads_for="getting dropped somewhere impossible and working out how it runs at the same "
        "time the character does",
        drops_on="names and titles thrown around like I am supposed to already know them",
    ),
    Reader(
        "magic_m",
        MEASUREMENT,
        framing=FRAMING,
        reads_for="the magic itself — what it actually does, how strange it gets, and somebody "
        "working out a use for it that nobody else had",
        drops_on="a world where the magic turns out to be a job with forms to fill in",
    ),
    Reader(
        "binge_m",
        MEASUREMENT,
        framing=FRAMING,
        reads_for="somewhere I want to keep coming back to, people I like being around, and the "
        "next good thing always close enough to reach",
        drops_on="misery with nothing to look forward to, or a book that skips the part it told "
        "me to care about",
    ),
)


#: **A measurement roster with no declared taste, and it exists because the declared one was
#: answering with our own prompt's rules.** Measured 2026-08-26: across 15 pairs in which the
#: readership chose our listing over a published serial, the stated reason was the same two
#: things every time — *"starts him at zero"*, *"a real cost"*, *"the climb has teeth"*, against
#: *"hands her lightning in the veins before the story starts"*. That is `power_m`'s own
#: `drops_on` clause read back verbatim (*"a main character who is already the strongest thing
#: in the room on page one"*), and it is also what `house.READER` and `house.ACCUMULATION`
#: instruct the writer to produce. The pool was running a two-item checklist that our prompt
#: guarantees passing.
#:
#: **§120 is the first instance and this is the second.** There, reader personas built to catch
#: a machinery leak were themselves written to read for *"what the next rung costs"*, so they
#: scored the jargon as a virtue. The shape is a persona whose stated taste is the thing under
#: test.
#:
#: **So the fix is a subtraction rather than a different taste**, which is what this repository
#: keeps finding works (§135, §138). Any preference written here is a checklist somebody chose;
#: what is left when they go is a person with limited time deciding what to spend it on, which
#: is §97.4's behavioural frame applied to the persona itself rather than only to its answer.
#:
#: **It is an arm and `READERS` is its control.** Nothing is settled by having it: a roster with
#: no taste could equally turn out to separate nothing at all, and the check that says which is
#: `research/quality-measurement/blurb_gradient.py` — a roster that stops preferring our
#: listings but also stops telling 12,000 followers from 0 has not been fixed, it has been
#: blinded.
BLIND: tuple[Reader, ...] = tuple(
    Reader(f"plain_{index}", MEASUREMENT, framing=FRAMING) for index in range(1, 5)
)


def pool(name: str) -> tuple[Reader, ...]:
    """The LitRPG readers of one pool, in roster order — `readers.pool`'s old contract."""
    return audience.pool(READERS, name)


LITRPG = Pack(
    pack_id=PACK_ID,
    genres=GENRES,
    framing=FRAMING,
    rosters=(("declared", pool(MEASUREMENT)), ("blind", BLIND)),
    steering=pool(STEERING),
    stop_rule=StopRule(),
    default_audience=AudienceSpec(PACK_ID, population=len(pool(MEASUREMENT)), roster="declared"),
    rule_essays=(house.READER, house.ACCUMULATION),
)

__all__ = ["BLIND", "FRAMING", "GENRES", "LITRPG", "PACK_ID", "READERS", "pool"]
