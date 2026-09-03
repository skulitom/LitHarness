"""The plain pack: no genre vocabulary, no rivals, the default stop point.

**What it is for.** The proof that the evaluator is not a fiction tool: a passage of any kind
read by readers who are introduced to themselves without a genre, stopped at the registered
fraction, and asked what they do with their remaining time. `tests/test_instrument.py` runs a
non-fiction passage through it on the fake provider and asserts the record's shape.

**What it deliberately lacks.** No genre set, so `admit_rival` refuses every row — a reader of
this pack is offered no named alternative, which is the no-competitor control arm of
`readers.render_choice_request`. No steering roster: nothing here steers a writer. No rule
essays: the pack believes nothing about craft. And no declared taste: its one roster is the
blind one, so an audience asking for `declared` is refused naming what the pack has.
"""

from __future__ import annotations

from litharness.domain.audience import MEASUREMENT, AudienceSpec, Reader, StopRule
from litharness.packs import Pack

PACK_ID = "plain"

#: A reader's situation with no genre in it: somebody with limited time, several things open,
#: and the habit of putting most of them down. That is the whole of what §97.4's behavioural
#: frame needs a reader to be.
FRAMING = (
    "You read for your own reasons — several things at a time — and you put most of what you "
    "start down part-way."
)

#: Four readers, no declared taste. The count matches the LitRPG measurement roster so an
#: audience spec written for one pack asks the same number of readers of the other.
READERS: tuple[Reader, ...] = tuple(
    Reader(f"plain_{index}", MEASUREMENT, framing=FRAMING) for index in range(1, 5)
)

PLAIN = Pack(
    pack_id=PACK_ID,
    genres=frozenset(),
    framing=FRAMING,
    rosters=(("blind", READERS),),
    steering=(),
    stop_rule=StopRule(),
    default_audience=AudienceSpec(PACK_ID, population=len(READERS), roster="blind"),
    rule_essays=(),
)

__all__ = ["FRAMING", "PACK_ID", "PLAIN", "READERS"]
