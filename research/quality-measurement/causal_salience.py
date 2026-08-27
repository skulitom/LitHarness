"""A model-agnostic substrate for testing causal-salience readers.

This is infrastructure, not evidence that any reader works.  It makes no model calls and
contains no production integration.  Its small synthetic battery exists to prove that the
hidden-key contract, scorer, controls, and split discipline behave as registered before scarce
model access is spent on them.

The first admitted semantic intervention is deliberately narrow: a controlled-language binary
state is contradicted after an explicit statement that it did not change.  Code owns both state
values and both evidence spans.  A whitespace-only sibling is the matched surface control.  More
natural interventions can be admitted later only when LitHarness already holds the relation that
certifies what the edit changed; generated criticism may never certify its own answer key.

Run the free diagnostic with::

    uv run python research/quality-measurement/causal_salience.py --selftest
"""

from __future__ import annotations

import argparse
import json
import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from enum import StrEnum
from hashlib import sha256
from typing import Any

VERSION = "0.1"
MAX_QUOTE_TOKENS = 18
BLINDING_NAMESPACE = "causal-salience-blind-v1"


class Split(StrEnum):
    DEVELOPMENT = "development"
    HOLDOUT = "holdout"


class Family(StrEnum):
    CAUSAL_CONTRADICTION = "causal_contradiction"
    SURFACE_CONTROL = "surface_control"


class Variant(StrEnum):
    CLEAN = "clean"
    TEST = "test"


@dataclass(frozen=True, slots=True)
class TokenSpan:
    start: int
    end: int

    def __post_init__(self) -> None:
        if self.start < 0 or self.end <= self.start:
            raise ValueError("a token span must be non-empty and ordered")


@dataclass(frozen=True, slots=True)
class InterventionKey:
    family: Family
    implementation: str
    admission_rule: str
    expected_detection: bool
    subject: str = ""
    relation: str = ""
    expected_value: str = ""
    observed_value: str = ""
    anchor_span: TokenSpan | None = None
    target_span: TokenSpan | None = None

    def __post_init__(self) -> None:
        causal_fields = (
            self.subject,
            self.relation,
            self.expected_value,
            self.observed_value,
        )
        if self.expected_detection:
            if self.family is not Family.CAUSAL_CONTRADICTION:
                raise ValueError("only an admitted semantic intervention expects detection")
            if not all(causal_fields) or self.anchor_span is None or self.target_span is None:
                raise ValueError("a causal key needs its relation and both evidence spans")
            if self.expected_value == self.observed_value:
                raise ValueError("a contradiction needs distinct expected and observed values")
        elif any(causal_fields) or self.anchor_span is not None or self.target_span is not None:
            raise ValueError("a surface control cannot carry a semantic answer key")


@dataclass(frozen=True, slots=True)
class BatteryItem:
    item_id: str
    source_group: str
    split: Split
    clean_text: str
    test_text: str
    key: InterventionKey

    def __post_init__(self) -> None:
        if not self.item_id or not self.source_group:
            raise ValueError("item and source-group identities are required")
        if not self.clean_text.strip() or not self.test_text.strip():
            raise ValueError("both sibling texts are required")
        if self.clean_text == self.test_text:
            raise ValueError("the test sibling must contain an intervention")


@dataclass(frozen=True, slots=True)
class ReaderClaim:
    """One top-one claim for one blinded sibling; empty fields are the abstention."""

    item_id: str
    variant: Variant
    abstain: bool
    suspect_quote: str = ""
    anchor_quote: str = ""
    subject: str = ""
    relation: str = ""
    expected_value: str = ""
    observed_value: str = ""

    def __post_init__(self) -> None:
        if not self.item_id:
            raise ValueError("a reader claim needs an item id")
        fields = (
            self.suspect_quote,
            self.anchor_quote,
            self.subject,
            self.relation,
            self.expected_value,
            self.observed_value,
        )
        if self.abstain:
            if any(fields):
                raise ValueError("an abstention must leave every claim field empty")
            return
        if not all(fields):
            raise ValueError("a non-abstaining claim needs two quotes and one complete relation")
        if len(_tokens(self.suspect_quote)) > MAX_QUOTE_TOKENS:
            raise ValueError("the suspect quote exceeds the top-one span budget")
        if len(_tokens(self.anchor_quote)) > MAX_QUOTE_TOKENS:
            raise ValueError("the anchor quote exceeds the evidence span budget")


@dataclass(frozen=True, slots=True)
class ItemScore:
    item_id: str
    source_group: str
    split: Split
    family: Family
    implementation: str
    detection_expected: bool
    clean_false_positive: bool
    test_false_positive: bool
    suspect_located: bool
    anchor_located: bool
    target_localized: bool
    anchor_localized: bool
    relation_matched: bool
    detected: bool


def _closed_schema(properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": list(properties),
        "properties": properties,
    }


_SPAN_SCHEMA = {
    "oneOf": [
        {"type": "null"},
        _closed_schema(
            {
                "start": {"type": "integer", "minimum": 0},
                "end": {"type": "integer", "minimum": 1},
            }
        ),
    ]
}

INTERVENTION_KEY_SCHEMA = _closed_schema(
    {
        "family": {"enum": [family.value for family in Family]},
        "implementation": {"type": "string"},
        "admission_rule": {"type": "string"},
        "expected_detection": {"type": "boolean"},
        "subject": {"type": "string"},
        "relation": {"type": "string"},
        "expected_value": {"type": "string"},
        "observed_value": {"type": "string"},
        "anchor_span": _SPAN_SCHEMA,
        "target_span": _SPAN_SCHEMA,
    }
)

READER_CLAIM_SCHEMA = _closed_schema(
    {
        "presentation_id": {"type": "string"},
        "abstain": {"type": "boolean"},
        "suspect_quote": {"type": "string"},
        "anchor_quote": {"type": "string"},
        "subject": {"type": "string"},
        "relation": {"type": "string"},
        "expected_value": {"type": "string"},
        "observed_value": {"type": "string"},
    }
)

_BOOL_SCORE_FIELDS = (
    "detection_expected",
    "clean_false_positive",
    "test_false_positive",
    "suspect_located",
    "anchor_located",
    "target_localized",
    "anchor_localized",
    "relation_matched",
    "detected",
)
ITEM_SCORE_SCHEMA = _closed_schema(
    {
        "item_id": {"type": "string"},
        "source_group": {"type": "string"},
        "split": {"enum": [split.value for split in Split]},
        "family": {"enum": [family.value for family in Family]},
        "implementation": {"type": "string"},
        **{field: {"type": "boolean"} for field in _BOOL_SCORE_FIELDS},
    }
)


@dataclass(frozen=True, slots=True)
class FixtureSpec:
    item_id: str
    source_group: str
    split: Split
    family: Family
    render_implementation: str
    intervention_implementation: str
    subject: str
    expected_value: str
    observed_value: str


_STATE_PAIRS = {
    frozenset(("locked", "unlocked")),
    frozenset(("lit", "dark")),
    frozenset(("sealed", "unsealed")),
    frozenset(("raised", "lowered")),
}

def _fixture_pair(
    first_id: int,
    group_id: int,
    split: Split,
    render: str,
    contradiction: str,
    surface: str,
    subject: str,
    expected: str,
    observed: str,
) -> tuple[FixtureSpec, FixtureSpec]:
    def _one(offset: int, family: Family, implementation: str) -> FixtureSpec:
        return FixtureSpec(
            f"cs-{first_id + offset:03}",
            f"sg-{group_id:02}",
            split,
            family,
            render,
            implementation,
            subject,
            expected,
            observed,
        )

    return (
        _one(0, Family.CAUSAL_CONTRADICTION, contradiction),
        _one(1, Family.SURFACE_CONTROL, surface),
    )


FIXTURE_SPECS = (
    *_fixture_pair(
        1, 1, Split.DEVELOPMENT, "continuity.v1", "binary-state-continuity.v1",
        "paragraph-reflow.v1", "the west gate", "locked", "unlocked"
    ),
    *_fixture_pair(
        3, 2, Split.DEVELOPMENT, "continuity.v1", "binary-state-continuity.v1",
        "paragraph-reflow.v1", "the signal lantern", "lit", "dark"
    ),
    *_fixture_pair(
        5, 3, Split.HOLDOUT, "inspection.v1", "binary-state-inspection.v1",
        "sentence-spacing.v1", "the archive door", "sealed", "unsealed"
    ),
    *_fixture_pair(
        7, 4, Split.HOLDOUT, "inspection.v1", "binary-state-inspection.v1",
        "sentence-spacing.v1", "the river barrier", "raised", "lowered"
    ),
)

_TOKEN = re.compile(r"[^\W_]+(?:[-'][^\W_]+)*", re.UNICODE)
_SAFE_SUBJECT = re.compile(r"[a-z][a-z -]{1,48}")


def _tokens(text: str) -> list[str]:
    return [match.group(0).casefold() for match in _TOKEN.finditer(text)]


def locate_unique_tokens(quote: str, text: str) -> TokenSpan | None:
    """Locate a normalized quote only when it has exactly one token-sequence match."""
    wanted = _tokens(quote)
    if not wanted:
        return None
    tokens = _tokens(text)
    size = len(wanted)
    starts = [
        start
        for start in range(len(tokens) - size + 1)
        if tokens[start : start + size] == wanted
    ]
    return TokenSpan(starts[0], starts[0] + size) if len(starts) == 1 else None


def _render_clean(spec: FixtureSpec) -> tuple[str, str, str]:
    subject = spec.subject
    expected = spec.expected_value
    if spec.render_implementation == "continuity.v1":
        anchor = f"{subject.capitalize()} was {expected}."
        bridge = f"The record states that {subject} did not change during the interval."
        target = f"Later, {subject} was still {expected}."
    elif spec.render_implementation == "inspection.v1":
        anchor = f"At the first inspection, {subject} was {expected}."
        bridge = f"The log states that {subject} did not change before the second inspection."
        target = f"At the second inspection, {subject} was {expected}."
    else:
        raise ValueError(f"unknown render implementation: {spec.render_implementation}")
    return " ".join((anchor, bridge, target)), anchor, target


def _render_damaged_target(spec: FixtureSpec) -> str:
    if spec.render_implementation == "continuity.v1":
        # "now" keeps the controlled sentence's token count matched to clean's "still".
        return f"Later, {spec.subject} was now {spec.observed_value}."
    if spec.render_implementation == "inspection.v1":
        return f"At the second inspection, {spec.subject} was {spec.observed_value}."
    raise ValueError(f"unknown render implementation: {spec.render_implementation}")


def _validate_spec(spec: FixtureSpec) -> None:
    if _SAFE_SUBJECT.fullmatch(spec.subject) is None:
        raise ValueError(f"unsafe controlled-language subject: {spec.subject!r}")
    if frozenset((spec.expected_value, spec.observed_value)) not in _STATE_PAIRS:
        raise ValueError("state values are not an admitted binary opposition")
    if spec.expected_value == spec.observed_value:
        raise ValueError("the two binary state values must differ")


def build_item(spec: FixtureSpec) -> BatteryItem:
    """Admit and build one controlled item, refusing uncertified states or transforms."""
    _validate_spec(spec)
    clean, anchor_quote, clean_target = _render_clean(spec)
    if spec.family is Family.CAUSAL_CONTRADICTION:
        damaged_target = _render_damaged_target(spec)
        test = clean.replace(clean_target, damaged_target)
        if test == clean or clean.count(clean_target) != 1:
            raise AssertionError("the controlled target must be replaced exactly once")
        anchor_span = locate_unique_tokens(anchor_quote, test)
        target_span = locate_unique_tokens(damaged_target, test)
        if anchor_span is None or target_span is None:
            raise AssertionError("controlled evidence spans must be uniquely locatable")
        key = InterventionKey(
            family=spec.family,
            implementation=spec.intervention_implementation,
            admission_rule="allowlisted binary opposition after explicit no-change statement",
            expected_detection=True,
            subject=spec.subject,
            relation="state_continuity",
            expected_value=spec.expected_value,
            observed_value=spec.observed_value,
            anchor_span=anchor_span,
            target_span=target_span,
        )
    else:
        if spec.intervention_implementation == "paragraph-reflow.v1":
            test = clean.replace(". ", ".\n\n")
        elif spec.intervention_implementation == "sentence-spacing.v1":
            test = clean.replace(". ", ".  ")
        else:
            raise ValueError(
                f"unknown surface implementation: {spec.intervention_implementation}"
            )
        if "".join(clean.split()) != "".join(test.split()):
            raise AssertionError("a surface control may change whitespace only")
        key = InterventionKey(
            family=spec.family,
            implementation=spec.intervention_implementation,
            admission_rule="non-whitespace codepoint sequence is identical",
            expected_detection=False,
        )
    return BatteryItem(spec.item_id, spec.source_group, spec.split, clean, test, key)


def build_fixture_battery() -> tuple[BatteryItem, ...]:
    """Build the frozen dry-run battery; it is a mechanism test, not a research sample."""
    items = tuple(build_item(spec) for spec in FIXTURE_SPECS)
    ids = [item.item_id for item in items]
    if len(ids) != len(set(ids)):
        raise AssertionError("fixture item ids must be unique")
    groups: dict[str, set[Split]] = {}
    for item in items:
        groups.setdefault(item.source_group, set()).add(item.split)
    if any(len(splits) != 1 for splits in groups.values()):
        raise AssertionError("a source group may not cross the frozen split")
    for family in Family:
        development = {
            item.key.implementation
            for item in items
            if item.split is Split.DEVELOPMENT and item.key.family is family
        }
        holdout = {
            item.key.implementation
            for item in items
            if item.split is Split.HOLDOUT and item.key.family is family
        }
        if development & holdout:
            raise AssertionError("holdout transformation implementations must be unseen")
    return items


def _digest(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


def fixture_manifest() -> dict[str, Any]:
    """A prose-free manifest whose split and implementation choices are reviewable."""
    return {
        "version": VERSION,
        "items": [
            {
                "item_id": item.item_id,
                "source_group": item.source_group,
                "split": item.split.value,
                "family": item.key.family.value,
                "render_implementation": spec.render_implementation,
                "intervention_implementation": item.key.implementation,
                "clean_digest": _digest(item.clean_text),
                "test_digest": _digest(item.test_text),
                "clean_tokens": len(_tokens(item.clean_text)),
                "test_tokens": len(_tokens(item.test_text)),
            }
            for item, spec in zip(build_fixture_battery(), FIXTURE_SPECS, strict=True)
        ],
    }


def _json_digest(value: object) -> str:
    material = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(material.encode("utf-8")).hexdigest()[:16]


def manifest_digest() -> str:
    return _json_digest(fixture_manifest())


def registration() -> dict[str, Any]:
    return {
        "version": VERSION,
        "max_quote_tokens": MAX_QUOTE_TOKENS,
        "intervention_key_schema": INTERVENTION_KEY_SCHEMA,
        "reader_claim_schema": READER_CLAIM_SCHEMA,
        "item_score_schema": ITEM_SCORE_SCHEMA,
        "state_pairs": sorted(sorted(pair) for pair in _STATE_PAIRS),
        "manifest": fixture_manifest(),
        "blinding": {
            "presentation_id_namespace": BLINDING_NAMESPACE,
            "public_packet_fields": ["presentation_id", "text"],
            "position_balance": "test first on even fixture index; clean first on odd index",
            "routing": "item id and sibling role are attached only after response parsing",
        },
        "scoring": (
            "one uniquely located bounded suspect quote overlapping the hidden target; one "
            "uniquely located anchor quote overlapping the hidden anchor; exact normalized "
            "subject/relation/expected/observed tuple; every clean or surface-control report "
            "is a false positive"
        ),
        "bars": None,
    }


def registration_digest() -> str:
    return _json_digest(registration())


def presentation_id(item: BatteryItem, variant: Variant) -> str:
    """Opaque stable routing id; it contains neither item identity nor sibling role."""
    return _digest(f"{BLINDING_NAMESPACE}:{item.item_id}:{variant.value}")[:16]


def blind_routes(items: Sequence[BatteryItem]) -> dict[str, tuple[str, Variant]]:
    routes = {
        presentation_id(item, variant): (item.item_id, variant)
        for item in items
        for variant in Variant
    }
    if len(routes) != len(items) * len(Variant):
        raise AssertionError("opaque presentation ids collided")
    return routes


def public_packet(item: BatteryItem, variant: Variant) -> dict[str, str]:
    """The complete blinded reader input.  Hidden labels have no route into this shape."""
    return {
        "presentation_id": presentation_id(item, variant),
        "text": item.clean_text if variant is Variant.CLEAN else item.test_text,
    }


def public_packets(items: Sequence[BatteryItem]) -> tuple[dict[str, str], ...]:
    """Blinded siblings in deterministic position-balanced order."""
    packets: list[dict[str, str]] = []
    for index, item in enumerate(items):
        order = (
            (Variant.TEST, Variant.CLEAN)
            if index % 2 == 0
            else (Variant.CLEAN, Variant.TEST)
        )
        packets.extend(public_packet(item, variant) for variant in order)
    return tuple(packets)


def parse_reader_claim(
    text: str, routes: Mapping[str, tuple[str, Variant]]
) -> ReaderClaim | None:
    """Parse a blinded response, then attach hidden routing labels outside the reader."""
    try:
        raw = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None
    required = set(READER_CLAIM_SCHEMA["required"])
    if not isinstance(raw, dict) or set(raw) != required:
        return None
    string_fields = required - {"abstain"}
    if any(not isinstance(raw[field], str) for field in string_fields):
        return None
    if not isinstance(raw["abstain"], bool):
        return None
    route = routes.get(raw["presentation_id"])
    if route is None:
        return None
    item_id, variant = route
    try:
        return ReaderClaim(
            item_id=item_id,
            variant=variant,
            abstain=raw["abstain"],
            suspect_quote=" ".join(raw["suspect_quote"].split()),
            anchor_quote=" ".join(raw["anchor_quote"].split()),
            subject=" ".join(raw["subject"].split()),
            relation=" ".join(raw["relation"].split()),
            expected_value=" ".join(raw["expected_value"].split()),
            observed_value=" ".join(raw["observed_value"].split()),
        )
    except (ValueError, TypeError):
        return None


def _overlaps(left: TokenSpan | None, right: TokenSpan | None) -> bool:
    return (
        left is not None
        and right is not None
        and left.start < right.end
        and right.start < left.end
    )


def _same_relation(claim: ReaderClaim, key: InterventionKey) -> bool:
    observed = (
        claim.subject,
        claim.relation,
        claim.expected_value,
        claim.observed_value,
    )
    expected = (key.subject, key.relation, key.expected_value, key.observed_value)
    return tuple(value.casefold() for value in observed) == tuple(
        value.casefold() for value in expected
    )


def score_item(
    item: BatteryItem, clean_claim: ReaderClaim, test_claim: ReaderClaim
) -> ItemScore:
    if clean_claim.item_id != item.item_id or test_claim.item_id != item.item_id:
        raise ValueError("claim and battery item ids differ")
    if clean_claim.variant is not Variant.CLEAN or test_claim.variant is not Variant.TEST:
        raise ValueError("each item needs its clean and test claim in the named positions")

    suspect = (
        None
        if test_claim.abstain
        else locate_unique_tokens(test_claim.suspect_quote, item.test_text)
    )
    anchor = (
        None
        if test_claim.abstain
        else locate_unique_tokens(test_claim.anchor_quote, item.test_text)
    )
    target_localized = _overlaps(suspect, item.key.target_span)
    anchor_localized = _overlaps(anchor, item.key.anchor_span)
    relation_matched = not test_claim.abstain and _same_relation(test_claim, item.key)
    detected = (
        item.key.expected_detection
        and target_localized
        and anchor_localized
        and relation_matched
    )
    return ItemScore(
        item_id=item.item_id,
        source_group=item.source_group,
        split=item.split,
        family=item.key.family,
        implementation=item.key.implementation,
        detection_expected=item.key.expected_detection,
        clean_false_positive=not clean_claim.abstain,
        test_false_positive=not item.key.expected_detection and not test_claim.abstain,
        suspect_located=suspect is not None,
        anchor_located=anchor is not None,
        target_localized=target_localized,
        anchor_localized=anchor_localized,
        relation_matched=relation_matched,
        detected=detected,
    )


def score_battery(
    items: Sequence[BatteryItem], claims: Iterable[ReaderClaim]
) -> tuple[ItemScore, ...]:
    indexed: dict[tuple[str, Variant], ReaderClaim] = {}
    for claim in claims:
        key = (claim.item_id, claim.variant)
        if key in indexed:
            raise ValueError(f"duplicate reader claim: {claim.item_id}/{claim.variant.value}")
        indexed[key] = claim
    wanted = {(item.item_id, variant) for item in items for variant in Variant}
    if set(indexed) != wanted:
        raise ValueError("claims must contain exactly one clean and one test response per item")
    return tuple(
        score_item(
            item,
            indexed[(item.item_id, Variant.CLEAN)],
            indexed[(item.item_id, Variant.TEST)],
        )
        for item in items
    )


def _rate(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def summarize(scores: Sequence[ItemScore]) -> dict[str, Any]:
    """Counts and distributions only.  No promotion bar or model verdict is inferred."""

    def _slice(rows: Sequence[ItemScore]) -> dict[str, Any]:
        damage = [row for row in rows if row.detection_expected]
        controls = [row for row in rows if not row.detection_expected]
        detected = sum(row.detected for row in damage)
        clean_fp = sum(row.clean_false_positive for row in rows)
        control_fp = sum(row.test_false_positive for row in controls)
        return {
            "items": len(rows),
            "damage_items": len(damage),
            "damage_detected": detected,
            "damage_detection_rate": _rate(detected, len(damage)),
            "clean_false_positives": clean_fp,
            "clean_false_positive_rate": _rate(clean_fp, len(rows)),
            "control_items": len(controls),
            "control_false_positives": control_fp,
            "control_false_positive_rate": _rate(control_fp, len(controls)),
        }

    return {
        "registration_digest": registration_digest(),
        "manifest_digest": manifest_digest(),
        "overall": _slice(scores),
        "by_split": {
            split.value: _slice([row for row in scores if row.split is split]) for split in Split
        },
        "by_family": {
            family.value: _slice([row for row in scores if row.family is family])
            for family in Family
        },
        "item_scores": [
            {
                **asdict(row),
                "split": row.split.value,
                "family": row.family.value,
            }
            for row in scores
        ],
        "promotion_bar": None,
    }


def _abstain(item: BatteryItem, variant: Variant) -> ReaderClaim:
    return ReaderClaim(item.item_id, variant, True)


def _keyed_claim(item: BatteryItem) -> ReaderClaim:
    key = item.key
    if key.anchor_span is None or key.target_span is None:
        raise ValueError("a keyed claim requires a semantic answer key")
    tokens = item.test_text.split()
    # Generated punctuation and whitespace make these slices exact enough for the fixture;
    # scorer credit still comes from normalized token offsets, not this convenience path.
    suspect = " ".join(tokens[key.target_span.start : key.target_span.end])
    anchor = " ".join(tokens[key.anchor_span.start : key.anchor_span.end])
    return ReaderClaim(
        item.item_id,
        Variant.TEST,
        False,
        suspect,
        anchor,
        key.subject,
        key.relation,
        key.expected_value,
        key.observed_value,
    )


def perfect_reader(items: Sequence[BatteryItem]) -> tuple[ReaderClaim, ...]:
    claims: list[ReaderClaim] = []
    for item in items:
        claims.append(_abstain(item, Variant.CLEAN))
        test_claim = (
            _keyed_claim(item)
            if item.key.expected_detection
            else _abstain(item, Variant.TEST)
        )
        claims.append(test_claim)
    return tuple(claims)


def criticism_flood_reader(items: Sequence[BatteryItem]) -> tuple[ReaderClaim, ...]:
    claims: list[ReaderClaim] = []
    for item in items:
        quote = " ".join(item.clean_text.split()[:4])
        for variant in Variant:
            claims.append(
                ReaderClaim(
                    item.item_id,
                    variant,
                    False,
                    quote,
                    quote,
                    "the passage",
                    "quality",
                    "sound",
                    "flawed",
                )
            )
    return tuple(claims)


def style_only_reader(items: Sequence[BatteryItem]) -> tuple[ReaderClaim, ...]:
    claims: list[ReaderClaim] = []
    for item in items:
        claims.append(_abstain(item, Variant.CLEAN))
        if item.key.family is Family.SURFACE_CONTROL:
            quote = " ".join(item.test_text.split()[:4])
            claims.append(
                ReaderClaim(
                    item.item_id,
                    Variant.TEST,
                    False,
                    quote,
                    quote,
                    "the layout",
                    "surface_change",
                    "plain",
                    "altered",
                )
            )
        else:
            claims.append(_abstain(item, Variant.TEST))
    return tuple(claims)


def random_reader(
    items: Sequence[BatteryItem], *, seed: str = "frozen-random-v1"
) -> tuple[ReaderClaim, ...]:
    """A stable pseudo-random baseline; SHA-256 avoids runtime PRNG/version drift."""
    claims: list[ReaderClaim] = []
    for item in items:
        for variant in Variant:
            choice = int(_digest(f"{seed}:{item.item_id}:{variant.value}")[:8], 16)
            if choice % 2 == 0:
                claims.append(_abstain(item, variant))
                continue
            text = item.clean_text if variant is Variant.CLEAN else item.test_text
            words = text.split()
            start = choice % max(1, len(words) - 3)
            suspect = " ".join(words[start : start + 3])
            anchor = " ".join(words[max(0, start - 3) : max(0, start - 3) + 3])
            claims.append(
                ReaderClaim(
                    item.item_id,
                    variant,
                    False,
                    suspect,
                    anchor,
                    "the passage",
                    "random_relation",
                    "expected",
                    "observed",
                )
            )
    return tuple(claims)


FakeReader = Callable[[Sequence[BatteryItem]], tuple[ReaderClaim, ...]]


def operating_characteristics() -> dict[str, Any]:
    items = build_fixture_battery()
    readers: dict[str, FakeReader] = {
        "perfect": perfect_reader,
        "criticism_flood": criticism_flood_reader,
        "style_only": style_only_reader,
        "random": random_reader,
    }
    return {
        name: summarize(score_battery(items, reader(items))) for name, reader in readers.items()
    }


def selftest() -> int:
    """Prove the mechanism can distinguish its four hand-stated operating signatures."""
    reports = operating_characteristics()
    perfect = reports["perfect"]["overall"]
    flood = reports["criticism_flood"]["overall"]
    style = reports["style_only"]["overall"]
    random = reports["random"]["overall"]
    failures: list[str] = []
    if perfect["damage_detection_rate"] != 1.0:
        failures.append("perfect reader did not localize every admitted contradiction")
    if perfect["clean_false_positives"] or perfect["control_false_positives"]:
        failures.append("perfect reader accused a clean or surface-only sibling")
    if flood["clean_false_positive_rate"] != 1.0:
        failures.append("criticism flood was not exposed by clean siblings")
    if style["damage_detected"] or style["control_false_positive_rate"] != 1.0:
        failures.append("style-only reader did not show the registered shortcut signature")
    if random == perfect:
        failures.append("stable random baseline unexpectedly matched the perfect signature")
    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        return 1
    print(
        "causal-salience selftest passed "
        f"(registration={registration_digest()}, manifest={manifest_digest()})"
    )
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--selftest", action="store_true", help="run fake-reader diagnostics")
    action.add_argument("--print-manifest", action="store_true", help="print the frozen manifest")
    action.add_argument(
        "--print-operating-characteristics",
        action="store_true",
        help="print fake-reader score distributions",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.selftest:
        return selftest()
    output = (
        operating_characteristics()
        if args.print_operating_characteristics
        else fixture_manifest()
    )
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
