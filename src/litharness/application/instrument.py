"""The evaluator as a port: a passage in, a content-addressed behavioural record out, and no
verdict anywhere in it.

**Why this is a module beside `ports.py` and not a protocol inside it (stage-0 §221).**
`ports.py` names what the application layer needs from outside — stores, a generator. The
instrument is what the application layer *offers* to a caller: the simulated readership as a
service another pipeline can call with its own passage and its own audience. An inbound
protocol beside the outbound ones would blur the one thing `ports.py` is for.

**What the port is, in the ledger's own terms.** Every reader is stopped part-way
(`domain/text.stop_point`, §124); the readers are one measurement roster of one domain pack
(`packs/`), never a steering reader (§97.1); the elicitation is behaviour under a currency
(`readers.render_choice_request`, §134's lesson) with the reader's own one-sentence account —
the E6 frame, a description and never a preference (§89.4); and the answer vocabulary is the
BCR's three words, *continue, abandon, return* (§97.4). The record carries the distribution,
per reader and in total, and the validity block beside it. (§87 to §89 are the entries the E6
frame survived.)

**The record is the distribution artifact** (the operator's addendum, 2026-09-03). It is
self-describing — schema, pack id and pack digest, transport and model, the stop rule, the
audience and currency specs, the passage and stopped-passage hashes, every reader's act,
every rail's status, every transport failure — and content-addressed over all of it, so a
downstream pipeline can verify a report against the record and the record against the text
without this repository. `report` renders the Markdown a consumer pastes into a README or a
model card, from the record alone.

**No verdict slot exists here and none can be added quietly.** `Readout.__post_init__` walks
every field of the record and every key of every nested mapping and refuses a name from
`VERDICT_SLOTS`; `tests/test_instrument.py` adds one and watches it refuse. A consumer wanting
a number gets the continue/abandon/return distribution and its validity flags, not a 1-10.

**The validity block names every rail the backtest registered and says what each did.** For
a single-passage read: `under_run` is measured (planned against answered, the failures
listed); `positional` is not applicable (one text, no slot to lean toward); `recognition` is
`unprobed` — a passage nobody probed is not `clean`, and the record says which; the sham floor
and the label shuffle did not run. The rails' arithmetic stays where the backtest's
registration names it (`research/sim-readership-backtest/analysis.py`, PREREG §10, K1a); the
port carries their vocabulary and will reach them through an adapter, not a copy.

**Transport failures are recorded, never raised** (§95: read `transport_failures` before any
number). A reader whose call failed, or who answered outside the schema, is a failure row and
an under-run, not a vote and not an exception.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, fields, is_dataclass
from hashlib import sha256
from typing import Any, Protocol

from litharness.application import readers
from litharness.application.ports import TextGenerator
from litharness.domain.audience import AudienceSpec, CurrencySpec, StopRule
from litharness.domain.failures import OperationalFailure
from litharness.domain.text import canonicalize, content_hash
from litharness.packs import DomainPack, select

#: The record's schema name. A consumer reads this first and knows what the rest means.
SCHEMA = "litharness.readout.v0"

#: The BCR's vocabulary (§97.4), and nothing else is a behaviour.
BEHAVIOURS: tuple[str, ...] = ("continue", "abandon", "return")

#: How a reader's act, in the schema's own words, reads as behaviour. `go_and_look` is leaving
#: for the named alternative: the reader abandoned this text today, and the record keeps the
#: act so nobody has to reconstruct that from the count.
ACTS: dict[str, str] = {
    "carry_on": "continue",
    "put_it_down": "abandon",
    "come_back_later": "return",
    "go_and_look": "abandon",
}

#: Field and key names a record may not carry, at any depth. The verdict channel is dead as
#: measured (§89.4, 4,676 to 1) and §97.4 says no verdict slot exists anywhere in a sim; this
#: is that sentence as a check rather than a comment.
VERDICT_SLOTS: frozenset[str] = frozenset(
    {
        "verdict",
        "score",
        "scores",
        "rating",
        "ratings",
        "grade",
        "grades",
        "rank",
        "ranking",
        "quality",
        "preference",
        "preferred",
        "stars",
        "winner",
        "better",
        "worse",
    }
)

#: The rails, by the backtest's registered names (PREREG §7, `analysis.verdicts`), in the
#: order the report prints them.
RAILS: tuple[str, ...] = (
    "positional",
    "recognition",
    "sham_floor",
    "shuffle_clear_share",
    "under_run",
)

#: What a rail may say about itself. `measured` carries a value; the rest say why there is
#: none. `unprobed`, `clean` and `recognised` are the recognition screen's three classes
#: (FINDINGS.md, the pilot's fix: an unanswered probe classifies `unprobed`, never `clean`).
RAIL_STATUSES: tuple[str, ...] = (
    "measured",
    "not_run",
    "not_applicable",
    "unprobed",
    "clean",
    "recognised",
)


class VerdictSlot(TypeError):
    """A record tried to carry a field or key that names a verdict."""


def refuse_verdict_slots(value: Any, path: str = "record") -> None:
    """Walk a record and refuse any field or mapping key named in `VERDICT_SLOTS`.

    Recursive over dataclasses, mappings and sequences, so a slot cannot ride in under a
    rail's `detail` any more than as a top-level field.
    """
    if is_dataclass(value) and not isinstance(value, type):
        for item in fields(value):
            if item.name.casefold() in VERDICT_SLOTS:
                raise VerdictSlot(f"{path}.{item.name} names a verdict slot")
            refuse_verdict_slots(getattr(value, item.name), f"{path}.{item.name}")
    elif isinstance(value, Mapping):
        for key, inner in value.items():
            if str(key).casefold() in VERDICT_SLOTS:
                raise VerdictSlot(f"{path}[{key!r}] names a verdict slot")
            refuse_verdict_slots(inner, f"{path}[{key!r}]")
    elif isinstance(value, (list, tuple)):
        for index, inner in enumerate(value):
            refuse_verdict_slots(inner, f"{path}[{index}]")


@dataclass(frozen=True, slots=True)
class Rail:
    """One validity rail: its status, its value where it measured one, and its reasons."""

    name: str
    status: str
    value: float | None = None
    detail: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # A rail refuses its own detail's keys, so a verdict cannot ride in through a rail
        # built on its own before it ever reaches a record.
        refuse_verdict_slots(self.detail, f"rail.{self.name}.detail")
        if self.name not in RAILS:
            raise ValueError(f"{self.name!r} is not one of the rails {RAILS}")
        if self.status not in RAIL_STATUSES:
            raise ValueError(f"{self.status!r} is not one of {RAIL_STATUSES}")
        if self.status == "measured" and self.value is None:
            raise ValueError(f"rail {self.name} says it measured and carries no value")
        if self.status != "measured" and self.value is not None:
            raise ValueError(f"rail {self.name} carries a value it says it did not measure")

    def to_jsonable(self) -> dict[str, Any]:
        return {"status": self.status, "value": self.value, "detail": dict(self.detail)}


@dataclass(frozen=True, slots=True)
class Validity:
    """Every rail, named. A rail absent from the block would read as passed; none is absent."""

    positional: Rail
    recognition: Rail
    sham_floor: Rail
    shuffle_clear_share: Rail
    under_run: Rail

    def __post_init__(self) -> None:
        for name in RAILS:
            rail = getattr(self, name)
            if rail.name != name:
                raise ValueError(f"the {name} slot holds the {rail.name} rail")

    @property
    def rails(self) -> tuple[Rail, ...]:
        return tuple(getattr(self, name) for name in RAILS)

    def to_jsonable(self) -> dict[str, Any]:
        return {rail.name: rail.to_jsonable() for rail in self.rails}


@dataclass(frozen=True, slots=True)
class ReaderReadout:
    """What one reader did, in the schema's word and in the BCR's, and what they said."""

    reader_id: str
    act: str
    behaviour: str
    said: str
    provider: str
    model: str

    def __post_init__(self) -> None:
        if self.act not in ACTS:
            raise ValueError(f"{self.act!r} is not an act a reader can name")
        if self.behaviour != ACTS[self.act]:
            raise ValueError(f"{self.act!r} reads as {ACTS[self.act]!r}, not {self.behaviour!r}")

    @property
    def left_for_other(self) -> bool:
        return self.act == "go_and_look"

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "reader_id": self.reader_id,
            "act": self.act,
            "behaviour": self.behaviour,
            "left_for_other": self.left_for_other,
            "said": self.said,
            "provider": self.provider,
            "model": self.model,
        }


@dataclass(frozen=True, slots=True)
class TransportFailure:
    """A reader who produced no vote: the transport failed, or the answer was not one."""

    reader_id: str
    kind: str
    message: str

    def to_jsonable(self) -> dict[str, Any]:
        return {"reader_id": self.reader_id, "kind": self.kind, "message": self.message}


@dataclass(frozen=True, slots=True)
class Readout:
    """The record. Content-addressed over everything below; refuses a verdict slot."""

    pack_id: str
    pack_digest: str
    #: The provider that served the calls (`fake`, `claude_code`), or empty when none could.
    transport: str
    model: str
    stop_rule: StopRule
    audience: AudienceSpec
    currency: CurrencySpec
    passage_sha256: str
    stopped_sha256: str
    passage_words: int
    stopped_words: int
    readers: tuple[ReaderReadout, ...]
    validity: Validity
    transport_failures: tuple[TransportFailure, ...] = ()
    schema: str = SCHEMA

    def __post_init__(self) -> None:
        refuse_verdict_slots(self)
        if self.schema != SCHEMA:
            raise ValueError(f"a readout is {SCHEMA}, not {self.schema!r}")
        answered = [item.reader_id for item in self.readers]
        failed = [item.reader_id for item in self.transport_failures]
        if len(set(answered + failed)) != len(answered) + len(failed):
            raise ValueError("a reader appears twice in one record")
        if len(answered) + len(failed) != self.audience.population:
            raise ValueError(
                f"{self.audience.population} reader(s) were asked and the record accounts for "
                f"{len(answered) + len(failed)}"
            )
        if self.stopped_words >= self.passage_words:
            raise ValueError("a reader is never shown the end (§124)")

    @property
    def counts(self) -> dict[str, int]:
        tally = dict.fromkeys(BEHAVIOURS, 0)
        for item in self.readers:
            tally[item.behaviour] += 1
        return tally

    @property
    def answered(self) -> int:
        return len(self.readers)

    @property
    def left_for_other(self) -> int:
        return sum(1 for item in self.readers if item.left_for_other)

    @property
    def shares(self) -> dict[str, float | None]:
        """The distribution. `None` where nobody answered, never a manufactured zero."""
        answered = self.answered
        return {
            behaviour: (count / answered if answered else None)
            for behaviour, count in self.counts.items()
        }

    def _body(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "pack_id": self.pack_id,
            "pack_digest": self.pack_digest,
            "transport": self.transport,
            "model": self.model,
            "stop_rule": self.stop_rule.to_jsonable(),
            "audience": self.audience.to_jsonable(),
            "currency": self.currency.to_jsonable(),
            "passage_sha256": self.passage_sha256,
            "stopped_sha256": self.stopped_sha256,
            "passage_words": self.passage_words,
            "stopped_words": self.stopped_words,
            "readers": [item.to_jsonable() for item in self.readers],
            "counts": self.counts,
            "shares": self.shares,
            "left_for_other": self.left_for_other,
            "validity": self.validity.to_jsonable(),
            "transport_failures": [item.to_jsonable() for item in self.transport_failures],
        }

    @property
    def record_id(self) -> str:
        """`rd-` and the sha256 of the canonical JSON of everything else in the record."""
        material = json.dumps(
            self._body(), sort_keys=True, ensure_ascii=False, separators=(",", ":")
        )
        return f"rd-{sha256(material.encode('utf-8')).hexdigest()[:24]}"

    def to_jsonable(self) -> dict[str, Any]:
        return {"record_id": self.record_id, **self._body()}


class Instrument(Protocol):
    """The port. A caller hands in a passage and an audience and gets a `Readout` back."""

    def read(
        self,
        passage: str,
        *,
        audience: AudienceSpec,
        currency: CurrencySpec | None = None,
        stop: StopRule | None = None,
    ) -> Readout: ...


def _unprobed_validity(
    *, planned: int, answered: int, failures: Sequence[TransportFailure]
) -> Validity:
    """The block a single-passage read can honestly write."""
    return Validity(
        positional=Rail(
            "positional",
            "not_applicable",
            detail={"reason": "one passage in one slot; there is no position to lean toward"},
        ),
        recognition=Rail(
            "recognition",
            "unprobed",
            detail={
                "reason": "no recognition probe ran; an unprobed passage is not clean "
                "(sim-readership-backtest FINDINGS, the pilot's fix)"
            },
        ),
        sham_floor=Rail(
            "sham_floor",
            "not_run",
            detail={"reason": "no same-text sham pair was read beside this passage"},
        ),
        shuffle_clear_share=Rail(
            "shuffle_clear_share",
            "not_run",
            detail={"reason": "a single passage carries no label to shuffle"},
        ),
        under_run=Rail(
            "under_run",
            "measured",
            value=float(planned - answered),
            detail={
                "planned": planned,
                "answered": answered,
                "failed": [item.reader_id for item in failures],
            },
        ),
    )


class SimulatedReadership:
    """The port over a generator and the packs a caller installed.

    A domain pack is looked up by the audience's `pack_id` and nothing here knows which packs
    exist; the composition root and the tests install them. A steering reader can never be
    asked, because a pack's rosters hold measurement readers only (`packs.Pack`).
    """

    def __init__(
        self,
        generator: TextGenerator,
        packs: Mapping[str, DomainPack] | Sequence[DomainPack],
    ) -> None:
        self._generator = generator
        self._packs: dict[str, DomainPack] = (
            dict(packs) if isinstance(packs, Mapping) else {pack.pack_id: pack for pack in packs}
        )

    def read(
        self,
        passage: str,
        *,
        audience: AudienceSpec,
        currency: CurrencySpec | None = None,
        stop: StopRule | None = None,
    ) -> Readout:
        pack = select(self._packs, audience.pack_id)
        roster = pack.roster(audience.roster)
        if audience.population > len(roster):
            raise ValueError(
                f"{audience.population} readers were asked for and roster "
                f"{audience.roster!r} of pack {pack.pack_id!r} holds {len(roster)}; a "
                "population padded by repeating a reader is one judge replicated (§89.1)"
            )
        seated = roster[: audience.population]
        stop_rule = stop or pack.stop_rule
        spend = currency or CurrencySpec()
        whole = canonicalize(passage)
        stopped = stop_rule.apply(whole)

        readouts: list[ReaderReadout] = []
        failures: list[TransportFailure] = []
        transport = ""
        try:
            transport = self._generator.resolve(readers.CALL_CLASS)[0].name
        except OperationalFailure as error:
            failures.extend(
                TransportFailure(reader.reader_id, error.classification, str(error))
                for reader in seated
            )
            seated = ()

        for reader in seated:
            request = readers.render_choice_request(
                reader,
                stopped,
                spend.rival_title,
                budget_chapters=spend.budget_chapters,
            )
            try:
                result, _resolution = self._generator.complete(request)
            except OperationalFailure as error:
                failures.append(
                    TransportFailure(reader.reader_id, error.classification, str(error))
                )
                continue
            parsed = result.parsed if isinstance(result.parsed, Mapping) else None
            act = str(parsed.get("next") or "") if parsed else ""
            if act not in ACTS:
                failures.append(
                    TransportFailure(
                        reader.reader_id,
                        "out_of_schema",
                        f"answered {act!r}, which is not an act the schema offers",
                    )
                )
                continue
            readouts.append(
                ReaderReadout(
                    reader_id=reader.reader_id,
                    act=act,
                    behaviour=ACTS[act],
                    said=str(parsed.get("because") or "").strip() if parsed else "",
                    provider=result.provider,
                    model=result.model,
                )
            )

        return Readout(
            pack_id=pack.pack_id,
            pack_digest=pack.digest(),
            transport=transport,
            model=readouts[0].model if readouts else "",
            stop_rule=stop_rule,
            audience=audience,
            currency=spend,
            passage_sha256=content_hash(whole),
            stopped_sha256=content_hash(stopped),
            passage_words=len(whole.split()),
            stopped_words=len(stopped.split()),
            readers=tuple(readouts),
            validity=_unprobed_validity(
                planned=audience.population, answered=len(readouts), failures=failures
            ),
            transport_failures=tuple(failures),
        )


def report(record: Readout) -> str:
    """A short Markdown validity report, from the record alone.

    Every backticked token is a value the record holds and every number is one of its
    numbers; `tests/test_instrument.py` reads the report back against the record's JSON to
    hold that. There is no summary line and no adjective: what the readers did and what each
    rail measured, and a consumer wanting one number has the distribution.
    """
    lines = [
        f"# Validity report `{record.record_id}`",
        "",
        f"Schema `{record.schema}`. Pack `{record.pack_id}`, digest `{record.pack_digest}`.",
    ]
    # Every backticked token is a record value, so an empty value is written as a sentence
    # rather than as an empty pair of backticks a reader would pair with the next one.
    if record.transport and record.model:
        lines.append(f"Transport `{record.transport}`, model `{record.model}`.")
    elif record.transport:
        lines.append(f"Transport `{record.transport}`; no model answered.")
    else:
        lines.append("No transport served a call.")
    lines += [
        "",
        f"Passage `{record.passage_sha256}`, stopped under `{record.stop_rule.rule_id}` at "
        f"fraction `{record.stop_rule.fraction}` to `{record.stopped_sha256}`: "
        f"`{record.stopped_words}` of `{record.passage_words}` words were shown.",
        f"Audience: `{record.audience.population}` reader(s) from roster "
        f"`{record.audience.roster}`. Currency: `{record.currency.budget_chapters}` "
        "chapter(s) left"
        + (
            f"; the named alternative was `{record.currency.rival_title}`."
            if record.currency.rival_title
            else "; no named alternative (the control arm)."
        ),
        "",
        "| behaviour | readers |",
        "| --- | ---: |",
    ]
    lines += [f"| `{behaviour}` | `{count}` |" for behaviour, count in record.counts.items()]
    if record.left_for_other:
        lines.append(f"| of which left for the alternative | `{record.left_for_other}` |")
    lines += ["", "| rail | status | value |", "| --- | --- | ---: |"]
    for rail in record.validity.rails:
        value = f"`{rail.value}`" if rail.value is not None else "not measured"
        lines.append(f"| `{rail.name}` | `{rail.status}` | {value} |")
    lines.append("")
    if record.transport_failures:
        lines.append(
            f"Transport failures `{len(record.transport_failures)}`: "
            + ", ".join(
                f"`{item.reader_id}` (`{item.kind}`)" for item in record.transport_failures
            )
            + "."
        )
    else:
        lines.append("Transport failures: none.")
    lines += [
        "",
        "What the readers did, and what each rail measured or did not. A consumer wanting one "
        "number has the distribution above and the rails beside it.",
    ]
    return "\n".join(lines) + "\n"


__all__ = [
    "ACTS",
    "BEHAVIOURS",
    "RAILS",
    "RAIL_STATUSES",
    "SCHEMA",
    "VERDICT_SLOTS",
    "Instrument",
    "Rail",
    "ReaderReadout",
    "Readout",
    "SimulatedReadership",
    "TransportFailure",
    "Validity",
    "VerdictSlot",
    "refuse_verdict_slots",
    "report",
]
