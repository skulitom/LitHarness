"""The audience as a value: who is reading, how they are introduced to themselves, and what a
read costs them.

**Why this left `application/readers.py` (stage-0 §221).** A domain pack may import only the
domain, and a pack has to be able to declare its own readers. The reader type therefore
lives here, and the one thing that was a literal inside it — the framing sentence, *"You read
a lot of LitRPG and progression fantasy ..."* — is now a field every reader carries. The LitRPG
readers carry that sentence byte for byte (`packs/litrpg`), so every system prompt they render
is the one the pipeline has rendered since 2026-08-25 and every stored persona digest still
resolves. A reader of another pack carries another sentence.

**What stays general, and it is the E6 frame.** The closing sentence — answer as yourself, in
your own words, briefly — is the one elicitation frame that survived §87 to §89: a reader names
what is there and is never asked to prefer. It is the same for every pack because it is not
about a genre; it is about what a reader is for.

**The three specs the port takes are here for the same reason.** A stop rule, an audience spec
and a currency spec are named by the pack (its defaults) and by the caller (its overrides),
and both sides may import the domain and nothing above it.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import KW_ONLY, dataclass
from hashlib import sha256
from typing import Any

from litharness.domain.text import STOP_FRACTION, stop_point

#: The two pools, and nobody is in both. A claim about prose shaped by the readers who then
#: judge it is circular (§97.1); a reader's pool is decided when it is written down.
STEERING = "steering"
MEASUREMENT = "measurement"
POOLS: tuple[str, ...] = (STEERING, MEASUREMENT)

#: The closing sentence of every reader's system prompt. E6 (§89.4): a reader describes and
#: never prefers, and the answer is theirs rather than a critic's.
ANSWER_FRAME = "You answer as yourself, in your own words, briefly."

#: What a reader is told they have left. Small on purpose: an unbounded reader continues out of
#: politeness, which is the failure §94 measured. Moved here from `application/readers.py`
#: with its value unchanged so the currency spec below can name it.
BUDGET_CHAPTERS = 2


@dataclass(frozen=True, slots=True)
class Reader:
    """One reader. `pool` is fixed here and may not be chosen at call time.

    `framing` is who this person is as a reader — the sentence a pack writes about its
    audience — and it is required: a reader with no framing is a persona with a blank where its
    situation goes, and a model asked to fill blanks fills them. `reads_for` and `drops_on` are
    the declared taste and both are optional; a reader with neither is the no-taste arm
    (`packs/litrpg`'s `BLIND`, and the reason it exists is recorded there).
    """

    reader_id: str
    pool: str
    _: KW_ONLY
    framing: str
    reads_for: str = ""
    drops_on: str = ""

    def __post_init__(self) -> None:
        if self.pool not in POOLS:
            raise ValueError(f"{self.reader_id!r} is in pool {self.pool!r}, not one of {POOLS}")
        if not self.framing.strip():
            raise ValueError(f"{self.reader_id!r} has no framing: a reader has to be somebody")

    def system(self) -> str:
        """Who is reading. The preference sentences appear only where there is a preference.

        A declared taste renders as two sentences; an undeclared one renders as nothing at all,
        rather than as "You read for . You stop reading on ." — which would be a persona with a
        blank where its opinions go, and a model asked to fill blanks fills them.
        """
        said = self.framing.strip()
        if self.reads_for:
            said += f" You read for {self.reads_for}."
        if self.drops_on:
            said += f" You stop reading on {self.drops_on}."
        return f"{said} {ANSWER_FRAME}"

    def to_jsonable(self) -> dict[str, Any]:
        return {"reader_id": self.reader_id, "pool": self.pool, "system": self.system()}


def pool(roster: Sequence[Reader], name: str) -> tuple[Reader, ...]:
    """The readers of one pool, in roster order."""
    if name not in POOLS:
        raise ValueError(f"{name!r} is not one of {POOLS}")
    return tuple(reader for reader in roster if reader.pool == name)


def roster_digest(roster: Sequence[Reader]) -> str:
    """Content address of a roster: the ids, pools and rendered system prompts, in order.

    The system prompt rather than the fields, because the prompt is what a model reads; two
    rosters that render the same bytes are the same audience whatever their fields were called.
    """
    material = json.dumps([reader.to_jsonable() for reader in roster], sort_keys=True)
    return sha256(material.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class StopRule:
    """Where a reader is stopped: the paragraph boundary nearest `fraction` of the words.

    `rule_id` names the implementation so a record can say which cut it was read under;
    `text.stop_point.v0` is the name `application/editorial.py` already writes into the
    anticipation mechanism's spec digest, and the fraction is §124's registered value. A pack
    may override the fraction; a caller may override the pack. The rule itself is one
    function, `domain/text.stop_point`, and stays one.
    """

    fraction: float = STOP_FRACTION
    rule_id: str = "text.stop_point.v0"

    def __post_init__(self) -> None:
        if not 0.0 < self.fraction < 1.0:
            raise ValueError(f"a stop fraction lies strictly inside (0, 1), got {self.fraction!r}")

    def apply(self, passage: str) -> str:
        """The passage-so-far. Raises for a passage with no future in it (`stop_point`)."""
        return stop_point(passage, self.fraction)

    def to_jsonable(self) -> dict[str, Any]:
        return {"rule_id": self.rule_id, "fraction": self.fraction}


@dataclass(frozen=True, slots=True)
class AudienceSpec:
    """Who is asked: which pack, how many of its readers, and from which measurement roster.

    `roster` names one of the pack's measurement rosters — `declared` (readers with a stated
    taste) or `blind` (the same situation with no taste), which is the arm and its control
    recorded at `packs/litrpg`. `population` is how many of that roster are asked, in roster
    order; it may not exceed the roster, because a population padded by cloning a reader is
    one judge replicated (§89.1's replication defect) and the port refuses it by name.
    """

    pack_id: str
    population: int
    roster: str = "declared"

    def __post_init__(self) -> None:
        if not self.pack_id.strip():
            raise ValueError("an audience names its pack")
        if self.population < 1:
            raise ValueError("an audience holds at least one reader")
        if not self.roster.strip():
            raise ValueError("an audience names the roster it is drawn from")

    def to_jsonable(self) -> dict[str, Any]:
        return {"pack_id": self.pack_id, "population": self.population, "roster": self.roster}


@dataclass(frozen=True, slots=True)
class CurrencySpec:
    """What continuing costs the reader. §134's lesson: an unspent hour is not scarce.

    `budget_chapters` is what the reader is told they have left across everything they are
    part-way through. `rival_title` names a book they could spend the hour on instead — the
    named-and-not-shown competitor of `readers.render_choice_request` — and empty is the
    no-competitor control arm, which every reading before 2026-08-26 measured. `rival_id` is
    the admitted rival's content address, carried so a record can say which competitor it was
    measured against without the record holding somebody else's listing.
    """

    budget_chapters: int = BUDGET_CHAPTERS
    rival_title: str = ""
    rival_id: str = ""

    def __post_init__(self) -> None:
        if self.budget_chapters < 1:
            raise ValueError("a reader with no chapters left has nothing to decide")
        if bool(self.rival_title.strip()) != bool(self.rival_id.strip()):
            raise ValueError("a named rival carries its id, and an id names its rival")

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "budget_chapters": self.budget_chapters,
            "rival_title": self.rival_title,
            "rival_id": self.rival_id,
        }


__all__ = [
    "ANSWER_FRAME",
    "BUDGET_CHAPTERS",
    "MEASUREMENT",
    "POOLS",
    "STEERING",
    "AudienceSpec",
    "CurrencySpec",
    "Reader",
    "StopRule",
    "pool",
    "roster_digest",
]
