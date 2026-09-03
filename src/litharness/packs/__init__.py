"""The domain-pack seam: what a domain supplies to the evaluator, and nothing about which one.

**Why a seam exists (stage-0 §221).** The reusable asset this repository holds is the simulated
readership — stopped part-way, two disjoint rosters, behaviour and never a verdict, the
validity rails — and every pipeline that generates text for an audience has the problem §89
measured. Made domain-agnostic, that evaluator is what another system can call. LitRPG serial
fiction is its first domain pack and its flagship demonstration, not the definition of the tool.

**What a pack supplies, and each item is one the inventory found bound to the genre:**

- `genres`: the labels this audience reads under, which is also the set a rival may be filed
  under (`domain/rivals.admit` takes it as an argument now; it used to hold the LitRPG set).
- `framing`: how a reader of this pack is introduced to itself — the sentence that was a
  literal inside the old reader type.
- the rosters: measurement readers by name (`declared` with a stated taste, `blind` without —
  the arm and its control), and the steering roster, which may be empty for a pack that
  steers no writer.
- `stop_rule`: the pack's default cut; the caller may override it per read.
- `default_audience`: how many readers, from which roster, when the caller has no opinion.
- `rule_essays`: the pack's role-specific craft essays, tier 3 of §129 — provisional, and
  below `house.CLARITY` and below any qualified reader mechanism. The port never renders them
  into a reader's prompt; they are carried so a consumer of the record can see what the pack
  believes and so a writer-side caller can find them in one place.

**The arrows.** A pack imports the domain and nothing above it. The application layer imports
this module — the protocol and the value type — and never a concrete pack; the composition
root (`cli.py`) and the tests are the only places a pack is named. `tests/test_architecture.py`
enforces both directions, so an import that reaches for `packs.litrpg` from inside
`application` is refused by name rather than discovered as a cycle.

**No pack registry lives here.** A default pack in this module would make every application
import carry the LitRPG pack transitively, which is the coupling the seam exists to remove. The
caller hands the port a mapping of the packs it installed, and `select` looks one up.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Protocol

from litharness.domain import rivals
from litharness.domain.audience import (
    AudienceSpec,
    Reader,
    StopRule,
    roster_digest,
)


class PackNotInstalled(KeyError):
    """The audience named a pack the caller did not install."""


class DomainPack(Protocol):
    """What the port needs from a domain. Structural, so a pack owes this module no import."""

    pack_id: str
    genres: frozenset[str]
    framing: str
    steering: tuple[Reader, ...]
    stop_rule: StopRule
    default_audience: AudienceSpec
    rule_essays: tuple[str, ...]

    def roster(self, name: str) -> tuple[Reader, ...]:
        """The measurement roster called `name`; raises naming the rosters it has."""
        ...

    def roster_names(self) -> tuple[str, ...]: ...

    def admit_rival(self, row: Mapping[str, Any]) -> rivals.Rival:
        """The domain's admission rule bound to this pack's genre set."""
        ...

    def digest(self) -> str:
        """Content address of everything above, so a record can say which pack read it."""
        ...


@dataclass(frozen=True, slots=True)
class Pack:
    """A pack as a value. Both shipped packs are instances; a third may be too, or may satisfy
    `DomainPack` on its own."""

    pack_id: str
    genres: frozenset[str]
    framing: str
    #: Measurement rosters by name, in declaration order. A tuple of pairs rather than a
    #: mapping so the value stays frozen and hashable.
    rosters: tuple[tuple[str, tuple[Reader, ...]], ...]
    steering: tuple[Reader, ...]
    stop_rule: StopRule
    default_audience: AudienceSpec
    rule_essays: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.pack_id.strip():
            raise ValueError("a pack names itself")
        names = [name for name, _ in self.rosters]
        if len(set(names)) != len(names):
            raise ValueError(f"pack {self.pack_id!r} names a roster twice: {names}")
        if not names:
            raise ValueError(f"pack {self.pack_id!r} has no measurement roster to ask")
        for name, roster in self.rosters:
            wrong = [reader.reader_id for reader in roster if reader.pool != "measurement"]
            if wrong:
                raise ValueError(
                    f"pack {self.pack_id!r} roster {name!r} holds non-measurement readers: {wrong}"
                )
        steering_ids = {reader.reader_id for reader in self.steering}
        for _name, roster in self.rosters:
            shared = steering_ids & {reader.reader_id for reader in roster}
            if shared:
                raise ValueError(
                    f"pack {self.pack_id!r}: {sorted(shared)} would be in both pools (§97.1)"
                )
        if self.default_audience.pack_id != self.pack_id:
            raise ValueError(f"pack {self.pack_id!r}'s default audience names another pack")
        if self.default_audience.roster not in names:
            raise ValueError(
                f"pack {self.pack_id!r}'s default audience names roster "
                f"{self.default_audience.roster!r}, not one of {names}"
            )

    def roster_names(self) -> tuple[str, ...]:
        return tuple(name for name, _ in self.rosters)

    def roster(self, name: str) -> tuple[Reader, ...]:
        for roster_name, roster in self.rosters:
            if roster_name == name:
                return roster
        raise ValueError(
            f"pack {self.pack_id!r} has no roster {name!r}; it has {self.roster_names()}"
        )

    def admit_rival(self, row: Mapping[str, Any]) -> rivals.Rival:
        return rivals.admit(row, genres=self.genres)

    def digest(self) -> str:
        material = json.dumps(
            {
                "pack_id": self.pack_id,
                "genres": sorted(self.genres),
                "framing": self.framing,
                "rosters": {name: roster_digest(roster) for name, roster in self.rosters},
                "steering": roster_digest(self.steering),
                "stop_rule": self.stop_rule.to_jsonable(),
                "default_audience": self.default_audience.to_jsonable(),
                # The essays by hash: a record should say which essays the pack carried
                # without carrying craft doctrine into a measurement artifact.
                "rule_essays": [
                    sha256(essay.encode("utf-8")).hexdigest() for essay in self.rule_essays
                ],
            },
            sort_keys=True,
            ensure_ascii=False,
        )
        return sha256(material.encode("utf-8")).hexdigest()


def select(packs: Mapping[str, DomainPack] | Sequence[DomainPack], pack_id: str) -> DomainPack:
    """The installed pack called `pack_id`, or `PackNotInstalled` naming what is installed."""
    installed: dict[str, DomainPack] = (
        dict(packs) if isinstance(packs, Mapping) else {pack.pack_id: pack for pack in packs}
    )
    try:
        return installed[pack_id]
    except KeyError as error:
        raise PackNotInstalled(
            f"no pack {pack_id!r} is installed; installed: {sorted(installed) or 'none'}"
        ) from error


__all__ = ["DomainPack", "Pack", "PackNotInstalled", "select"]
