"""Call-free admission of manuscript evidence into causal-salience experiments.

The ledger can name a relation without proving where the prose establishes it. This module is
the refusal boundary between those useful-but-unlocated records and an ecological battery whose
answer key must be owned by code. It validates current-revision hashes and exact spans, reports
every family separately, and can build the first narrow state-continuity siblings without a
model deciding what its own corruption changed.
"""

from __future__ import annotations

import enum
import re
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from hashlib import sha256
from itertools import combinations
from typing import Any

import litharness_contracts as lc

from litharness.domain.events import payload_digest
from litharness.domain.promises import Promise
from litharness.domain.revision import Revision, node_version_id
from litharness.domain.serials import SerialShape
from litharness.domain.state import CANON, order_key_of
from litharness.domain.text import content_hash


class InterventionFamily(enum.StrEnum):
    STATE_CONTINUITY = "state_continuity"
    EVENT_CONSEQUENCE = "event_consequence"
    PROGRESSION_COST = "progression_cost"
    CHARACTER_CAUSE = "character_cause"
    PROMISE_PAYOFF = "promise_payoff"


class ContextRung(enum.StrEnum):
    ADJACENT = "adjacent_scene_or_chapter"
    LOCAL_ARC = "local_arc"
    HALF_VOLUME = "half_volume"
    FULL_VOLUME = "full_volume"
    CROSS_VOLUME = "cross_volume"
    GROWING_SERIAL = "growing_serial_prefix"


# Narrow, reviewable oppositions only. Free-text antonyms never enter admission.
OPPOSITES: dict[str, str] = {
    "alive": "dead",
    "dead": "alive",
    "locked": "unlocked",
    "unlocked": "locked",
    "lit": "dark",
    "dark": "lit",
    "sealed": "unsealed",
    "unsealed": "sealed",
    "raised": "lowered",
    "lowered": "raised",
    "present": "absent",
    "absent": "present",
    "open": "closed",
    "closed": "open",
}


@dataclass(frozen=True, slots=True)
class LocatedEvidence:
    record_id: str
    logical_id: str
    start: int
    end: int
    content_hash: str
    quote: str
    order_key: str | None


@dataclass(frozen=True, slots=True)
class EvidenceCandidate:
    candidate_id: str
    family: InterventionFamily
    relation_id: str
    record_ids: tuple[str, ...]
    evidence: tuple[LocatedEvidence, ...]
    context_rung: ContextRung


@dataclass(frozen=True, slots=True)
class EvidenceCensus:
    book_id: str
    branch_id: str
    revision_id: str
    candidates: tuple[EvidenceCandidate, ...]
    rejected: Mapping[str, int]

    def to_payload(self) -> dict[str, Any]:
        """Aggregate, prose-free census safe to keep beside public packets."""
        families = Counter(candidate.family.value for candidate in self.candidates)
        rungs = Counter(candidate.context_rung.value for candidate in self.candidates)
        return {
            "book_id": self.book_id,
            "branch_id": self.branch_id,
            "revision_id": self.revision_id,
            "candidate_counts": {
                family.value: families.get(family.value, 0) for family in InterventionFamily
            },
            "long_context_rungs": {rung.value: rungs.get(rung.value, 0) for rung in ContextRung},
            "rejected": dict(sorted(self.rejected.items())),
            "candidate_count": len(self.candidates),
        }

    def private_payload(self) -> dict[str, Any]:
        """Complete located answer-key material; never include this in a reader request."""
        return {
            **self.to_payload(),
            "candidates": [
                {
                    **asdict(candidate),
                    "family": candidate.family.value,
                    "context_rung": candidate.context_rung.value,
                    "evidence": [asdict(span) for span in candidate.evidence],
                }
                for candidate in self.candidates
            ],
        }

    @property
    def digest(self) -> str:
        return payload_digest(self.private_payload())


@dataclass(frozen=True, slots=True)
class EditFingerprint:
    token_delta: int
    sentence_delta: int
    punctuation_delta: int
    whitespace_delta: int
    position_decile: int
    anchor_distance_scenes: int


@dataclass(frozen=True, slots=True)
class EcologicalItem:
    item_id: str
    source_group: str
    source_revision_id: str
    source_logical_id: str
    source_content_hash: str
    family: InterventionFamily
    implementation: str
    anchor_record_id: str
    target_record_id: str
    expected_value: str
    observed_value: str
    clean_text: str
    damaged_text: str
    sham_text: str
    target_start: int
    target_end: int
    damage_fingerprint: EditFingerprint
    sham_fingerprint: EditFingerprint

    def __post_init__(self) -> None:
        if self.clean_text in {self.damaged_text, self.sham_text}:
            raise ValueError("ecological siblings must differ from their clean source")
        if self.damage_fingerprint != self.sham_fingerprint:
            raise ValueError("damage and sham expose different shallow edit fingerprints")

    def manifest_entry(self) -> dict[str, Any]:
        variants = _variants_for(self)
        return {
            "item_id": self.item_id,
            "source_group_digest": content_hash(self.source_group),
            "source_revision_digest": content_hash(self.source_revision_id),
            "source_content_hash": self.source_content_hash,
            "variant_ids": [variant_id for variant_id, _label, _text in variants],
            "variant_digests": [content_hash(text) for _variant_id, _label, text in variants],
            "fingerprint": asdict(self.damage_fingerprint),
        }


def _valid_span(
    revision: Revision, record: lc.StateRecord, span: lc.EvidenceSpan
) -> LocatedEvidence | None:
    source = span.source
    if (source.book_id, source.branch_id) != (revision.book_id, revision.branch_id):
        return None
    try:
        node = revision.node(source.logical_id)
    except KeyError:
        return None
    text = node.content or ""
    actual = node.content_sha256 or content_hash(text)
    if not (0 <= span.start < span.end <= len(text)):
        return None
    if source.version_id and source.version_id != node_version_id(node):
        return None
    quote = text[span.start : span.end]
    if not quote.strip() or content_hash(quote) != span.content_sha256 or text.count(quote) != 1:
        return None
    return LocatedEvidence(
        record_id=record.record_id,
        logical_id=source.logical_id,
        start=span.start,
        end=span.end,
        content_hash=actual,
        quote=quote,
        order_key=order_key_of(record),
    )


def locate_record(revision: Revision, record: lc.StateRecord) -> LocatedEvidence | None:
    """The record's one current, digest-valid, uniquely located evidence span."""
    located = [
        evidence
        for span in record.evidence
        if (evidence := _valid_span(revision, record, span)) is not None
    ]
    return located[0] if len(located) == 1 else None


def _promise_span(revision: Revision, promise: Promise, *, payment: bool) -> LocatedEvidence | None:
    logical_id = promise.paid_logical_id if payment else promise.opened_logical_id
    start = promise.paid_start if payment else promise.opened_start
    end = promise.paid_end if payment else promise.opened_end
    expected_hash = promise.paid_content_hash if payment else promise.opened_content_hash
    if logical_id is None or start is None or end is None or expected_hash is None:
        return None
    try:
        node = revision.node(logical_id)
    except KeyError:
        return None
    text = node.content or ""
    actual = node.content_sha256 or content_hash(text)
    if actual != expected_hash or not (0 <= start < end <= len(text)):
        return None
    quote = text[start:end]
    if not quote.strip() or text.count(quote) != 1:
        return None
    key = promise.paid_at_key if payment else promise.opened_at_key
    return LocatedEvidence(
        record_id=promise.promise_id,
        logical_id=logical_id,
        start=start,
        end=end,
        content_hash=actual,
        quote=quote,
        order_key=key,
    )


def _scene_ordinals(revision: Revision) -> dict[str, int]:
    scenes = [node for node in revision.in_reading_order() if node.kind.value == "scene"]
    return {node.logical_id: index for index, node in enumerate(scenes, start=1)}


def context_rung_for(
    evidence: Sequence[LocatedEvidence], revision: Revision, shape: SerialShape
) -> ContextRung:
    ordinals = _scene_ordinals(revision)
    positions = [ordinals[item.logical_id] for item in evidence if item.logical_id in ordinals]
    distance = max(positions) - min(positions) if positions else 0
    chapter_distance = distance // shape.scenes_per_chapter
    if chapter_distance <= 1:
        return ContextRung.ADJACENT
    if chapter_distance <= shape.chapters_per_arc:
        return ContextRung.LOCAL_ARC
    if chapter_distance <= 25:
        return ContextRung.HALF_VOLUME
    if chapter_distance <= 50:
        return ContextRung.FULL_VOLUME
    if chapter_distance <= 100:
        return ContextRung.CROSS_VOLUME
    return ContextRung.GROWING_SERIAL


def _candidate(
    family: InterventionFamily,
    relation_id: str,
    records: Sequence[lc.StateRecord],
    evidence: Sequence[LocatedEvidence],
    revision: Revision,
    shape: SerialShape,
) -> EvidenceCandidate:
    record_ids = tuple(record.record_id for record in records)
    material = payload_digest(
        {
            "family": family.value,
            "relation_id": relation_id,
            "record_ids": record_ids,
            "revision_id": revision.revision_id,
        }
    )
    return EvidenceCandidate(
        candidate_id=f"ecand-{sha256(material.encode()).hexdigest()[:24]}",
        family=family,
        relation_id=relation_id,
        record_ids=record_ids,
        evidence=tuple(evidence),
        context_rung=context_rung_for(evidence, revision, shape),
    )


def evidence_census(
    revision: Revision,
    records: Sequence[lc.StateRecord],
    promises: Sequence[Promise],
    *,
    shape: SerialShape,
) -> EvidenceCensus:
    """Count only relations whose complete answer key survives current-revision validation."""
    canon = [record for record in records if record.authority in CANON]
    located = {record.record_id: locate_record(revision, record) for record in canon}
    rejected: Counter[str] = Counter()
    candidates: list[EvidenceCandidate] = []

    slots: dict[tuple[str, str, str], list[lc.StateRecord]] = defaultdict(list)
    for record in canon:
        value = str(record.value or "").strip().casefold()
        if value in OPPOSITES:
            slots[(record.subject, record.predicate, value)].append(record)
    for (subject, predicate, value), members in slots.items():
        for first, second in combinations(
            sorted(members, key=lambda row: (order_key_of(row) or "", row.record_id)), 2
        ):
            first_evidence = located[first.record_id]
            second_evidence = located[second.record_id]
            if first_evidence is None or second_evidence is None:
                rejected["state_continuity:missing_unique_evidence"] += 1
                continue
            candidates.append(
                _candidate(
                    InterventionFamily.STATE_CONTINUITY,
                    f"{subject}:{predicate}:{value}",
                    (first, second),
                    (first_evidence, second_evidence),
                    revision,
                    shape,
                )
            )

    changes: dict[str, list[lc.StateRecord]] = defaultdict(list)
    for record in canon:
        if record.predicate in {
            "actor",
            "participant",
            "precondition",
            "caused_by",
            "performed_by",
            "effect",
            "consumes",
            "produces",
        }:
            changes[record.subject].append(record)

    def admit_change(
        change_id: str,
        members: Sequence[lc.StateRecord],
        family: InterventionFamily,
        required: Sequence[set[str]],
    ) -> None:
        selected: list[lc.StateRecord] = []
        for alternatives in required:
            row = next((item for item in members if item.predicate in alternatives), None)
            if row is None:
                rejected[f"{family.value}:missing_role"] += 1
                return
            selected.append(row)
        spans = [located[row.record_id] for row in selected]
        if any(span is None for span in spans):
            rejected[f"{family.value}:missing_unique_evidence"] += 1
            return
        candidates.append(
            _candidate(
                family,
                change_id,
                selected,
                [span for span in spans if span is not None],
                revision,
                shape,
            )
        )

    for change_id, members in changes.items():
        admit_change(
            change_id,
            members,
            InterventionFamily.EVENT_CONSEQUENCE,
            ({"effect"}, {"precondition", "caused_by"}),
        )
        admit_change(
            change_id,
            members,
            InterventionFamily.PROGRESSION_COST,
            ({"consumes"}, {"produces"}),
        )
        admit_change(
            change_id,
            members,
            InterventionFamily.CHARACTER_CAUSE,
            ({"actor", "performed_by"}, {"caused_by"}, {"effect"}),
        )

    for promise in promises:
        opening = _promise_span(revision, promise, payment=False)
        payment = _promise_span(revision, promise, payment=True)
        if opening is None or payment is None:
            rejected["promise_payoff:missing_unique_evidence"] += 1
            continue
        candidates.append(
            EvidenceCandidate(
                candidate_id=(
                    "ecand-"
                    + sha256((promise.promise_id + revision.revision_id).encode()).hexdigest()[:24]
                ),
                family=InterventionFamily.PROMISE_PAYOFF,
                relation_id=promise.promise_id,
                record_ids=(promise.promise_id,),
                evidence=(opening, payment),
                context_rung=context_rung_for((opening, payment), revision, shape),
            )
        )

    return EvidenceCensus(
        revision.book_id,
        revision.branch_id,
        revision.revision_id,
        tuple(sorted(candidates, key=lambda item: (item.family.value, item.candidate_id))),
        dict(rejected),
    )


_TOKEN = re.compile(r"[^\W_]+(?:[-'][^\W_]+)*", re.UNICODE)
_PUNCTUATION = re.compile(r"[^\w\s]", re.UNICODE)


def _fingerprint(
    clean: str,
    edited: str,
    *,
    position: int,
    anchor_distance: int,
) -> EditFingerprint:
    return EditFingerprint(
        token_delta=len(_TOKEN.findall(edited)) - len(_TOKEN.findall(clean)),
        sentence_delta=len(re.findall(r"[.!?]+", edited)) - len(re.findall(r"[.!?]+", clean)),
        punctuation_delta=len(_PUNCTUATION.findall(edited)) - len(_PUNCTUATION.findall(clean)),
        whitespace_delta=sum(char.isspace() for char in edited)
        - sum(char.isspace() for char in clean),
        position_decile=min(9, (position * 10) // max(1, len(clean))),
        anchor_distance_scenes=anchor_distance,
    )


def build_state_continuity_items(
    census: EvidenceCensus, revision: Revision
) -> tuple[EcologicalItem, ...]:
    """Build clean/damaged/sham siblings for the census's admitted continuity pairs."""
    ordinals = _scene_ordinals(revision)
    items: list[EcologicalItem] = []
    for candidate in census.candidates:
        if candidate.family is not InterventionFamily.STATE_CONTINUITY:
            continue
        anchor, target = sorted(
            candidate.evidence,
            key=lambda span: (span.order_key or "", span.logical_id, span.start),
        )
        expected = candidate.relation_id.rsplit(":", 1)[-1]
        observed = OPPOSITES[expected]
        node = revision.node(target.logical_id)
        clean = node.content or ""
        window = clean[target.start : target.end]
        matches = list(re.finditer(re.escape(expected), window, flags=re.IGNORECASE))
        if len(matches) != 1:
            continue
        match = matches[0]
        start = target.start + match.start()
        end = target.start + match.end()
        original = clean[start:end]
        damaged = clean[:start] + observed + clean[end:]
        sham_value = original.swapcase()
        if sham_value == original:
            continue
        sham = clean[:start] + sham_value + clean[end:]
        distance = abs(ordinals.get(target.logical_id, 0) - ordinals.get(anchor.logical_id, 0))
        damage_fingerprint = _fingerprint(clean, damaged, position=start, anchor_distance=distance)
        sham_fingerprint = _fingerprint(clean, sham, position=start, anchor_distance=distance)
        material = payload_digest(
            {
                "candidate_id": candidate.candidate_id,
                "implementation": "binary-substitution.case-sham.v1",
            }
        )
        try:
            item = EcologicalItem(
                item_id=f"eitem-{sha256(material.encode()).hexdigest()[:24]}",
                source_group=f"{revision.book_id}:{revision.branch_id}",
                source_revision_id=revision.revision_id,
                source_logical_id=target.logical_id,
                source_content_hash=target.content_hash,
                family=candidate.family,
                implementation="binary-substitution.case-sham.v1",
                anchor_record_id=anchor.record_id,
                target_record_id=target.record_id,
                expected_value=expected,
                observed_value=observed,
                clean_text=clean,
                damaged_text=damaged,
                sham_text=sham,
                target_start=start,
                target_end=start + len(observed),
                damage_fingerprint=damage_fingerprint,
                sham_fingerprint=sham_fingerprint,
            )
        except ValueError:
            continue
        items.append(item)
    return tuple(items)


def ecological_manifest(census: EvidenceCensus, items: Sequence[EcologicalItem]) -> dict[str, Any]:
    return {
        "version": "ecological-causal-salience.v1",
        "census_digest": census.digest,
        "source_group_split": "whole book/world",
        "heldout_transformation_requirement": True,
        "items": [item.manifest_entry() for item in items],
        "eligible_for_model_run": bool(items),
        "promotion_bar": None,
    }


def _variants_for(item: EcologicalItem) -> tuple[tuple[str, str, str], ...]:
    variants = []
    for label, prose in (
        ("clean", item.clean_text),
        ("damaged", item.damaged_text),
        ("sham", item.sham_text),
    ):
        material = payload_digest({"item_id": item.item_id, "content_hash": content_hash(prose)})
        variants.append((f"variant-{sha256(material.encode()).hexdigest()[:24]}", label, prose))
    return tuple(sorted(variants))


def public_battery(items: Sequence[EcologicalItem]) -> dict[str, Any]:
    """Unlabelled prose packets. Variant order and ids reveal no clean/damage role."""
    return {
        "version": "ecological-causal-salience.public.v1",
        "items": [
            {
                "item_id": item.item_id,
                "variants": [
                    {"variant_id": variant_id, "text": prose}
                    for variant_id, _label, prose in _variants_for(item)
                ],
            }
            for item in items
        ],
    }


def private_battery(census: EvidenceCensus, items: Sequence[EcologicalItem]) -> dict[str, Any]:
    """Answer keys and source evidence kept physically separate from public packets."""
    private_items = []
    for item in items:
        payload = asdict(item)
        payload["family"] = item.family.value
        payload["variant_keys"] = {
            variant_id: label for variant_id, label, _prose in _variants_for(item)
        }
        private_items.append(payload)
    return {
        "version": "ecological-causal-salience.private.v1",
        "census": census.private_payload(),
        "items": private_items,
        "warning": "hidden keys and sibling labels; never pass this file to a reader",
    }


__all__ = [
    "OPPOSITES",
    "ContextRung",
    "EcologicalItem",
    "EditFingerprint",
    "EvidenceCandidate",
    "EvidenceCensus",
    "InterventionFamily",
    "LocatedEvidence",
    "build_state_continuity_items",
    "context_rung_for",
    "ecological_manifest",
    "evidence_census",
    "locate_record",
    "private_battery",
    "public_battery",
]
