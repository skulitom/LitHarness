"""The evaluator port: a passage in, a content-addressed behavioural record out, no verdict.

**What this file proves and what it does not.** It proves the port's shape on the fake
provider: a passage that is not fiction, read by a pack with no genre, produces a record whose
fields are the ones stage-0 §221 names, whose validity block says what each rail did and did
not do, whose hash moves with its content, and which refuses a verdict slot at construction. It
proves that the Markdown report is made of the record and nothing else. It proves nothing about
any reader's perception of any text: the fake answers the first enum value and a scripted one,
and no number here is evidence (EPISTEMIC_GOVERNANCE).

**The passage is written here, for this test.** Not from any corpus (RS1): a description of
how a tide gauge is read, in six paragraphs, so the stop rule has a future to leave.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

import pytest

from litharness.application import instrument, readers
from litharness.domain import rivals
from litharness.domain.audience import (
    MEASUREMENT,
    STEERING,
    AudienceSpec,
    CurrencySpec,
    Reader,
    StopRule,
)
from litharness.packs import Pack, PackNotInstalled, litrpg, plain, select
from litharness.providers.fake import FakeProvider
from litharness.providers.registry import ProviderRegistry

PASSAGE = "\n\n".join(
    [
        "A tide gauge is a well with a float in it. The well is a pipe sunk into the harbour "
        "bed with a small hole near the bottom, so the water inside rises and falls with the "
        "sea but does not slap about with the waves.",
        "The float rides on that quieter water. A wire runs from the float over a wheel at the "
        "top of the pipe to a counterweight, and the wheel turns as the float moves.",
        "The wheel used to drive a pen across a drum of paper that a clock turned once a day. "
        "The pen drew the tide as a curve, and the curve was the record.",
        "Reading the record meant finding the highest and lowest points of each curve and "
        "writing their heights and times into a ledger, one line per tide, by hand.",
        "Two things go wrong with a gauge. The hole in the pipe silts up, and the float then "
        "answers the sea late and small. Or the clock drifts, and every time in the ledger "
        "is shifted by the same unknown minutes.",
        "So a gauge is checked against a staff, a graduated board bolted to the quay, by a "
        "person who reads the water against the board at a known minute and writes down "
        "what the gauge said at the same one.",
    ]
)


def _port(*packs: Pack, provider: FakeProvider | None = None) -> instrument.SimulatedReadership:
    return instrument.SimulatedReadership(
        ProviderRegistry(provider or FakeProvider()), list(packs) or [plain.PLAIN, litrpg.LITRPG]
    )


def _readout(provider: FakeProvider | None = None) -> instrument.Readout:
    return _port(provider=provider).read(
        PASSAGE, audience=AudienceSpec("plain", population=4, roster="blind")
    )


# --- generality: a non-fiction passage through a pack with no genre ---------------------


def test_a_non_fiction_passage_reads_through_the_plain_pack_on_the_fake_provider() -> None:
    record = _readout()

    assert record.schema == instrument.SCHEMA
    assert record.pack_id == "plain"
    assert record.pack_digest == plain.PLAIN.digest()
    assert record.transport == "fake"
    assert record.model == "fake-deterministic-v1"
    assert record.audience == AudienceSpec("plain", population=4, roster="blind")
    assert record.currency == CurrencySpec()
    assert record.stop_rule == StopRule()
    assert [item.reader_id for item in record.readers] == [
        reader.reader_id for reader in plain.READERS
    ]
    assert all(item.behaviour in instrument.BEHAVIOURS for item in record.readers)
    assert all(item.act in instrument.ACTS for item in record.readers)
    assert record.transport_failures == ()
    assert sum(record.counts.values()) == record.answered == 4


def test_the_reader_is_stopped_part_way_and_both_hashes_travel() -> None:
    record = _readout()
    assert record.stopped_words < record.passage_words
    assert record.stopped_sha256 != record.passage_sha256
    assert len(record.passage_sha256) == len(record.stopped_sha256) == 64


def test_the_validity_block_names_every_rail_and_says_what_it_did_not_do() -> None:
    """A rail that did not run is written as not having run — never as passed."""
    record = _readout()
    statuses = {rail.name: rail.status for rail in record.validity.rails}
    assert set(statuses) == set(instrument.RAILS)
    assert statuses["recognition"] == "unprobed"
    assert statuses["positional"] == "not_applicable"
    assert statuses["sham_floor"] == "not_run"
    assert statuses["shuffle_clear_share"] == "not_run"
    assert statuses["under_run"] == "measured"
    assert record.validity.under_run.value == 0.0
    assert record.validity.under_run.detail == {"planned": 4, "answered": 4, "failed": []}


def test_the_plain_pack_has_no_genre_no_rival_and_no_essay() -> None:
    assert plain.PLAIN.genres == frozenset()
    assert plain.PLAIN.rule_essays == ()
    assert plain.PLAIN.steering == ()
    with pytest.raises(rivals.IllegalRival, match="admits no rival"):
        plain.PLAIN.admit_rival({"title": "A", "listing": "B", "genre": "litrpg", "rating": 4.36})


def test_the_pack_is_named_by_the_audience_and_an_uninstalled_one_is_refused() -> None:
    port = _port(plain.PLAIN)
    with pytest.raises(PackNotInstalled, match="litrpg"):
        port.read(PASSAGE, audience=AudienceSpec("litrpg", population=1))
    with pytest.raises(PackNotInstalled):
        select({"plain": plain.PLAIN}, "litrpg")


def test_an_audience_larger_than_the_roster_is_refused_rather_than_padded() -> None:
    """A population padded by repeating a reader is one judge replicated (§89.1)."""
    with pytest.raises(ValueError, match="replicated"):
        _port().read(PASSAGE, audience=AudienceSpec("plain", population=5, roster="blind"))


def test_a_roster_the_pack_does_not_have_is_refused_naming_the_ones_it_has() -> None:
    with pytest.raises(ValueError, match="blind"):
        _port().read(PASSAGE, audience=AudienceSpec("plain", population=1, roster="declared"))


def test_a_passage_with_no_future_is_refused_not_read_whole() -> None:
    with pytest.raises(ValueError, match="two paragraphs"):
        _port().read("One paragraph.", audience=AudienceSpec("plain", population=1, roster="blind"))


# --- the record is content-addressed and carries no verdict ------------------------------


def test_the_record_is_content_addressed_over_everything_it_carries() -> None:
    first, second = _readout(), _readout()
    assert first.record_id == second.record_id
    assert first.record_id.startswith("rd-")
    other = _port().read(
        PASSAGE + "\n\nAn added paragraph moves the hash.",
        audience=AudienceSpec("plain", population=4, roster="blind"),
    )
    assert other.record_id != first.record_id
    payload = first.to_jsonable()
    assert payload["record_id"] == first.record_id
    json.dumps(payload)  # portable: nothing in it needs this repository to serialise


def test_the_record_carries_no_verdict_slot_at_any_depth() -> None:
    payload = _readout().to_jsonable()
    seen: set[str] = set()

    def walk(value: object) -> None:
        if isinstance(value, dict):
            for key, inner in value.items():
                seen.add(str(key).casefold())
                walk(inner)
        elif isinstance(value, list):
            for inner in value:
                walk(inner)

    walk(payload)
    assert not seen & instrument.VERDICT_SLOTS


def test_a_record_refuses_a_verdict_slot_added_later() -> None:
    """The refusal is at construction, so a field added by a later session cannot ride in."""

    @dataclass(frozen=True, slots=True)
    class Scored(instrument.Readout):
        score: float = 0.0

    record = _readout()
    with pytest.raises(instrument.VerdictSlot, match="score"):
        Scored(
            **{name: getattr(record, name) for name in instrument.Readout.__dataclass_fields__},
        )
    with pytest.raises(instrument.VerdictSlot, match="verdict"):
        instrument.Rail("under_run", "measured", value=0.0, detail={"verdict": "fine"})


def test_a_rail_says_measured_only_with_a_value_and_the_other_way_round() -> None:
    with pytest.raises(ValueError, match="no value"):
        instrument.Rail("positional", "measured")
    with pytest.raises(ValueError, match="did not measure"):
        instrument.Rail("positional", "not_run", value=0.1)
    with pytest.raises(ValueError, match="not one of the rails"):
        instrument.Rail("vibes", "not_run")


# --- transport failures are recorded, never raised --------------------------------------


def test_a_transport_failure_and_an_out_of_schema_answer_are_recorded_not_raised() -> None:
    from litharness.providers.base import ProviderError

    failure = ProviderError("the socket closed")
    provider = FakeProvider()
    provider.set_responses(
        [
            json.dumps({"next": "put_it_down", "because": "it stopped moving"}),
            failure,
            json.dumps({"next": "rate_it_five", "because": "not an act"}),
            json.dumps({"next": "come_back_later", "because": "another time"}),
        ]
    )
    record = _readout(provider)
    assert [item.behaviour for item in record.readers] == ["abandon", "return"]
    # The failure's kind is the provider's own classification of it, whatever that is; the
    # record copies it rather than translating it, so a reader of the record sees the
    # transport's word.
    assert [item.kind for item in record.transport_failures] == [
        failure.classification,
        "out_of_schema",
    ]
    assert [item.reader_id for item in record.transport_failures] == ["plain_2", "plain_3"]
    assert record.validity.under_run.value == 2.0
    assert record.validity.under_run.detail["failed"] == ["plain_2", "plain_3"]
    assert record.counts == {"continue": 0, "abandon": 1, "return": 1}
    assert record.shares["abandon"] == 0.5


def test_leaving_for_the_named_alternative_is_an_abandonment_that_keeps_its_act() -> None:
    provider = FakeProvider()
    provider.set_responses([json.dumps({"next": "go_and_look", "because": "the other one"})])
    record = _port(provider=provider).read(
        PASSAGE,
        audience=AudienceSpec("plain", population=1, roster="blind"),
        currency=CurrencySpec(rival_title="The Deep Ledger", rival_id="rv-0123456789abcdef"),
    )
    (reader,) = record.readers
    assert reader.act == "go_and_look"
    assert reader.behaviour == "abandon"
    assert reader.left_for_other
    assert record.left_for_other == 1


# --- the report: the record's hash and nothing the record does not carry ----------------


def test_the_report_carries_the_record_hash_and_nothing_the_record_does_not() -> None:
    record = _readout()
    text = instrument.report(record)
    dump = json.dumps(record.to_jsonable(), ensure_ascii=False)

    assert record.record_id in text
    for token in re.findall(r"`([^`]+)`", text):
        assert token in dump, f"the report says `{token}` and the record does not"
    for number in re.findall(r"(?<![\w.-])-?\d+(?:\.\d+)?(?![\w.])", text):
        assert number in dump, f"the report says {number} and the record does not"
    lowered = text.casefold()
    for word in instrument.VERDICT_SLOTS:
        assert not re.search(rf"\b{word}\b", lowered), word
    for rail in instrument.RAILS:
        assert f"`{rail}`" in text


def test_the_report_names_the_failures_and_the_alternative_when_there_are_any() -> None:
    from litharness.providers.base import ProviderError

    failure = ProviderError("no answer came back")
    provider = FakeProvider()
    provider.set_responses([failure])
    record = _port(provider=provider).read(
        PASSAGE,
        audience=AudienceSpec("plain", population=1, roster="blind"),
        currency=CurrencySpec(rival_title="The Deep Ledger", rival_id="rv-0123456789abcdef"),
    )
    text = instrument.report(record)
    assert "`The Deep Ledger`" in text
    assert f"`plain_1` (`{failure.classification}`)" in text
    dump = json.dumps(record.to_jsonable(), ensure_ascii=False)
    for token in re.findall(r"`([^`]+)`", text):
        assert token in dump


# --- the LitRPG pack renders the readers the pipeline always had --------------------------


def test_the_litrpg_readers_render_the_system_text_the_pipeline_has_always_rendered() -> None:
    """The move (stage-0 §221) changed no byte a LitRPG reader is sent. Reconstructed here from
    the sentence the old `Reader.system` carried as a literal."""
    power = litrpg.pool(MEASUREMENT)[0]
    assert power.reader_id == "power_m"
    assert power.system() == (
        "You read a lot of LitRPG and progression fantasy — several serials at once, and you "
        "drop most of what you start. You read for watching somebody go from nothing to "
        "genuinely dangerous, and getting to feel every jump on the way. You stop reading on a "
        "main character who is already the strongest thing in the room on page one. You answer "
        "as yourself, in your own words, briefly."
    )
    assert litrpg.BLIND[0].system() == (
        "You read a lot of LitRPG and progression fantasy — several serials at once, and you "
        "drop most of what you start. You answer as yourself, in your own words, briefly."
    )
    assert [reader.reader_id for reader in litrpg.READERS] == [
        "power_s", "elsewhere_s", "magic_s", "binge_s",
        "power_m", "elsewhere_m", "magic_m", "binge_m",
    ]
    assert litrpg.LITRPG.roster("declared") == litrpg.pool(MEASUREMENT)
    assert litrpg.LITRPG.roster("blind") == litrpg.BLIND
    assert litrpg.LITRPG.steering == litrpg.pool(STEERING)
    assert readers.Reader is Reader


def test_the_litrpg_pack_points_at_the_house_essays_and_the_genre_set() -> None:
    from litharness.domain import house

    assert litrpg.LITRPG.rule_essays == (house.READER, house.ACCUMULATION)
    assert "litrpg" in litrpg.GENRES and "progression fantasy" in litrpg.GENRES
    assert not hasattr(rivals, "GENRES")
    assert not hasattr(readers, "READERS") and not hasattr(readers, "pool")


def test_a_reader_needs_a_framing_and_a_pool_it_can_be_in() -> None:
    with pytest.raises(ValueError, match="somebody"):
        Reader("x", MEASUREMENT, framing="   ")
    with pytest.raises(ValueError, match="not one of"):
        Reader("x", "judging", framing="You read.")


def test_a_pack_refuses_a_reader_in_both_pools_and_a_steering_reader_in_a_roster() -> None:
    measuring = Reader("m", MEASUREMENT, framing="You read.")
    steering = Reader("m", STEERING, framing="You read.")
    with pytest.raises(ValueError, match="both pools"):
        Pack(
            pack_id="x",
            genres=frozenset(),
            framing="You read.",
            rosters=(("blind", (measuring,)),),
            steering=(steering,),
            stop_rule=StopRule(),
            default_audience=AudienceSpec("x", 1, "blind"),
        )
    with pytest.raises(ValueError, match="non-measurement"):
        Pack(
            pack_id="x",
            genres=frozenset(),
            framing="You read.",
            rosters=(("blind", (steering,)),),
            steering=(),
            stop_rule=StopRule(),
            default_audience=AudienceSpec("x", 1, "blind"),
        )


def test_the_pack_digest_moves_with_its_roster_and_its_essays() -> None:
    base = plain.PLAIN
    reworded = Pack(
        pack_id=base.pack_id,
        genres=base.genres,
        framing=base.framing,
        rosters=(("blind", base.roster("blind")[:3]),),
        steering=(),
        stop_rule=base.stop_rule,
        default_audience=AudienceSpec("plain", 1, "blind"),
    )
    assert reworded.digest() != base.digest()
    essayed = Pack(
        pack_id=base.pack_id,
        genres=base.genres,
        framing=base.framing,
        rosters=base.rosters,
        steering=(),
        stop_rule=base.stop_rule,
        default_audience=base.default_audience,
        rule_essays=("Every scene moves the thing the book is about.",),
    )
    assert essayed.digest() != base.digest()
    assert plain.PLAIN.digest() == base.digest()


def test_the_currency_reaches_the_prompt_and_the_default_is_what_it_always_was() -> None:
    reader = plain.READERS[0]
    default = readers.render_choice_request(reader, PASSAGE)
    same = readers.render_choice_request(reader, PASSAGE, budget_chapters=readers.BUDGET_CHAPTERS)
    assert default.prompt == same.prompt
    assert "about 2 more chapters" in default.prompt
    assert "about 5 more chapters" in readers.render_choice_request(
        reader, PASSAGE, budget_chapters=5
    ).prompt
