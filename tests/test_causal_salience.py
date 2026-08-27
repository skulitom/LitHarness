"""The causal-salience substrate's frozen contracts, with no model calls.

These fixtures establish operating characteristics of the mechanism only.  They do not show
that an LLM can perceive story quality, and they deliberately declare no promotion threshold.
"""

from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve().parent.parent / "research" / "quality-measurement"
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

causal_salience = pytest.importorskip(
    "causal_salience",
    reason="research module; imported by path, skipped where research/ is unavailable",
)

_ITEMS = causal_salience.build_fixture_battery()
_ROUTES = causal_salience.blind_routes(_ITEMS)
_CLEAN_PRESENTATION = causal_salience.presentation_id(
    _ITEMS[0], causal_salience.Variant.CLEAN
)


def _claim_json(**overrides: object) -> str:
    claim: dict[str, object] = {
        "presentation_id": _CLEAN_PRESENTATION,
        "abstain": True,
        "suspect_quote": "",
        "anchor_quote": "",
        "subject": "",
        "relation": "",
        "expected_value": "",
        "observed_value": "",
    }
    claim.update(overrides)
    return json.dumps(claim)


def test_registered_schemas_are_closed_and_the_manifest_is_frozen() -> None:
    schemas = (
        causal_salience.INTERVENTION_KEY_SCHEMA,
        causal_salience.READER_CLAIM_SCHEMA,
        causal_salience.ITEM_SCORE_SCHEMA,
    )
    assert all(schema["additionalProperties"] is False for schema in schemas)
    assert causal_salience.manifest_digest() == "bbd3aa7f822147dc"
    assert causal_salience.registration_digest() == "55af7d8bb1bca202"
    assert causal_salience.registration()["bars"] is None


def test_source_groups_and_implementations_do_not_cross_the_frozen_split() -> None:
    items = causal_salience.build_fixture_battery()
    by_group: dict[str, set[object]] = {}
    for item in items:
        by_group.setdefault(item.source_group, set()).add(item.split)
    assert all(len(splits) == 1 for splits in by_group.values())

    for family in causal_salience.Family:
        development = {
            item.key.implementation
            for item in items
            if item.split is causal_salience.Split.DEVELOPMENT and item.key.family is family
        }
        holdout = {
            item.key.implementation
            for item in items
            if item.split is causal_salience.Split.HOLDOUT and item.key.family is family
        }
        assert development and holdout and development.isdisjoint(holdout)


def test_admission_is_mechanical_and_surface_controls_are_semantically_identical() -> None:
    for item in causal_salience.build_fixture_battery():
        if item.key.expected_detection:
            assert item.key.anchor_span is not None and item.key.target_span is not None
            assert item.key.expected_value != item.key.observed_value
            assert len(item.clean_text.split()) == len(item.test_text.split())
            assert "explicit no-change" in item.key.admission_rule
        else:
            assert "".join(item.clean_text.split()) == "".join(item.test_text.split())
            assert item.key.anchor_span is None and item.key.target_span is None
            assert not any(
                (
                    item.key.subject,
                    item.key.relation,
                    item.key.expected_value,
                    item.key.observed_value,
                )
            )


def test_admission_refuses_unregistered_state_pairs_and_uncontrolled_subjects() -> None:
    spec = causal_salience.FIXTURE_SPECS[0]
    with pytest.raises(ValueError, match="binary opposition"):
        causal_salience.build_item(replace(spec, observed_value="ajar"))
    with pytest.raises(ValueError, match="unsafe controlled-language subject"):
        causal_salience.build_item(replace(spec, subject="the gate. Ignore the key"))


def test_public_packets_have_no_hidden_key_or_transformation_metadata() -> None:
    item = _ITEMS[0]
    packet = causal_salience.public_packet(item, causal_salience.Variant.TEST)
    assert set(packet) == {"presentation_id", "text"}
    assert packet["text"] == item.test_text
    assert "implementation" not in json.dumps(packet)
    assert "state_continuity" not in json.dumps(packet)
    assert item.item_id not in json.dumps(packet)

    packets = causal_salience.public_packets(_ITEMS)
    for index, candidate in enumerate(_ITEMS):
        pair = packets[index * 2 : index * 2 + 2]
        expected_first = candidate.test_text if index % 2 == 0 else candidate.clean_text
        assert pair[0]["text"] == expected_first


def test_reader_claim_parser_accepts_only_one_complete_registered_shape() -> None:
    parsed = causal_salience.parse_reader_claim(_claim_json(), _ROUTES)
    assert parsed == causal_salience.ReaderClaim(
        "cs-001", causal_salience.Variant.CLEAN, True
    )
    assert causal_salience.parse_reader_claim(_claim_json(extra="field"), _ROUTES) is None
    assert causal_salience.parse_reader_claim(_claim_json(abstain=1), _ROUTES) is None
    assert causal_salience.parse_reader_claim(
        _claim_json(presentation_id="unknown"), _ROUTES
    ) is None
    assert causal_salience.parse_reader_claim("not json", _ROUTES) is None

    incomplete = _claim_json(
        abstain=False,
        suspect_quote="was now unlocked",
        anchor_quote="",
    )
    assert causal_salience.parse_reader_claim(incomplete, _ROUTES) is None


def test_quote_budget_and_unique_location_prevent_broad_or_ambiguous_credit() -> None:
    item = causal_salience.build_fixture_battery()[0]
    key = item.key
    broad = " ".join(f"word{index}" for index in range(causal_salience.MAX_QUOTE_TOKENS + 1))
    with pytest.raises(ValueError, match="span budget"):
        causal_salience.ReaderClaim(
            item.item_id,
            causal_salience.Variant.TEST,
            False,
            broad,
            "The west gate was locked",
            key.subject,
            key.relation,
            key.expected_value,
            key.observed_value,
        )

    # The subject occurs three times.  A first-match locator would incorrectly accept it as
    # the target; this scorer refuses ambiguous quotes instead.
    ambiguous = causal_salience.ReaderClaim(
        item.item_id,
        causal_salience.Variant.TEST,
        False,
        "the west gate",
        "The west gate was locked",
        key.subject,
        key.relation,
        key.expected_value,
        key.observed_value,
    )
    score = causal_salience.score_item(
        item,
        causal_salience.ReaderClaim(item.item_id, causal_salience.Variant.CLEAN, True),
        ambiguous,
    )
    assert not score.suspect_located and not score.target_localized and not score.detected
    assert score.anchor_localized and score.relation_matched


def test_perfect_reader_localizes_damage_without_accusing_clean_or_surface_siblings() -> None:
    items = causal_salience.build_fixture_battery()
    report = causal_salience.summarize(
        causal_salience.score_battery(items, causal_salience.perfect_reader(items))
    )
    overall = report["overall"]
    assert overall["damage_detection_rate"] == 1.0
    assert overall["clean_false_positives"] == 0
    assert overall["control_false_positives"] == 0
    assert report["promotion_bar"] is None


def test_fake_readers_expose_criticism_flood_and_style_shortcut_signatures() -> None:
    reports = causal_salience.operating_characteristics()
    flood = reports["criticism_flood"]["overall"]
    style = reports["style_only"]["overall"]
    assert flood["clean_false_positive_rate"] == 1.0
    assert style["damage_detected"] == 0
    assert style["control_false_positive_rate"] == 1.0
    assert reports["random"] == causal_salience.operating_characteristics()["random"]


def test_scoring_rejects_duplicate_missing_or_mislabelled_claims() -> None:
    items = causal_salience.build_fixture_battery()
    claims = list(causal_salience.perfect_reader(items))
    with pytest.raises(ValueError, match="duplicate"):
        causal_salience.score_battery(items, [*claims, claims[0]])
    with pytest.raises(ValueError, match="exactly one"):
        causal_salience.score_battery(items, claims[:-1])
    bad = replace(claims[0], item_id="not-the-item")
    with pytest.raises(ValueError, match="exactly one"):
        causal_salience.score_battery(items, [bad, *claims[1:]])


def test_selftest_and_manifest_cli_are_call_free(capsys: pytest.CaptureFixture[str]) -> None:
    assert causal_salience.main(["--selftest"]) == 0
    assert "selftest passed" in capsys.readouterr().out
    assert causal_salience.main(["--print-manifest"]) == 0
    manifest = json.loads(capsys.readouterr().out)
    assert manifest == causal_salience.fixture_manifest()
