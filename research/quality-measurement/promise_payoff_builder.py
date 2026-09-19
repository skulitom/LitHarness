"""Construct promise/payment evidence-withdrawal controls, without calling a model.

This is a construction diagnostic, not an ecological damage oracle. Removing the ledger's
registered payment span proves that those bytes were withheld, not that no other passage
fulfils the promise. See promise-payoff-builder-20260919/RUNBOOK.md.
"""

from __future__ import annotations

import argparse
import inspect
import json
import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import asdict, dataclass, replace
from hashlib import file_digest
from pathlib import Path
from typing import Any

import litharness_contracts as lc

from litharness.adapters.sqlite_store import SqliteStore
from litharness.application.export import resolve_branch
from litharness.domain.events import payload_digest
from litharness.domain.nodes import NodeKind
from litharness.domain.promises import PROMISE_PAID, Promise
from litharness.domain.revision import Revision
from litharness.domain.salience import (
    EditFingerprint,
    LocatedEvidence,
    _fingerprint,
    _promise_span,
    _valid_span,
    context_rung_for,
)
from litharness.domain.serials import SerialShape
from litharness.domain.text import content_hash

VERSION = "promise-payment-evidence-withdrawal.v1"
DEFAULT_MAX_CHARS = 400_000
DEFAULT_SHAPE = SerialShape(1, 6)
BOUNDARY = re.compile(r"\r?\n[ \t]*\r?\n")


@dataclass(frozen=True)
class Span:
    start: int
    end: int

    def overlaps(self, other: Span) -> bool:
        return self.start < other.end and other.start < self.end

    def contains(self, other: Span) -> bool:
        return self.start <= other.start < other.end <= self.end


def paragraphs(text: str) -> tuple[Span, ...]:
    """Complete nonblank paragraphs with exact source offsets, including CRLF input."""
    spans = []
    start = 0
    for end, next_start in [
        *((match.start(), match.end()) for match in BOUNDARY.finditer(text)),
        (len(text), len(text)),
    ]:
        while start < end and text[start].isspace():
            start += 1
        while end > start and text[end - 1].isspace():
            end -= 1
        if start < end:
            spans.append(Span(start, end))
        start = next_start
    return tuple(spans)


def remove(text: str, span: Span) -> str:
    return text[:span.start] + text[span.end:]


def deletion_fingerprint(text: str, span: Span, distance: int) -> EditFingerprint:
    """Whole-paragraph deletion cannot join tokens across its whitespace boundaries."""
    if (
        not 0 <= span.start < span.end <= len(text)
        or (span.start and not text[span.start - 1].isspace())
        or (span.end < len(text) and not text[span.end].isspace())
    ):
        raise ValueError("Deletion must be bounded by whitespace or text edges")
    local = _fingerprint(text[span.start:span.end], "", position=0, anchor_distance=distance)
    return replace(local, position_decile=min(9, (span.start * 10) // len(text)))


def file_hash(path: Path) -> str:
    with path.open("rb") as stream:
        return file_digest(stream, "sha256").hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8", newline="\n",
    )


def _protected_evidence(
    revision: Revision, records: Sequence[lc.StateRecord], promises: Sequence[Promise],
) -> list[LocatedEvidence]:
    # Protect single anchors too: a promise with no payment is still not a donor paragraph.
    protected = [
        located for record in records for span in record.evidence
        if (located := _valid_span(revision, record, span)) is not None
    ]
    for promise in promises:
        for payment in (False, True):
            if span := _promise_span(revision, promise, payment=payment):
                protected.append(span)
    return protected


def _construct(
    revision: Revision,
    promise: Promise,
    protected: Sequence[LocatedEvidence],
    *,
    source_group: str,
    shape: SerialShape,
    max_chars: int,
) -> tuple[dict[str, Any] | None, str]:
    if promise.status != PROMISE_PAID:
        return None, "not_paid"
    opening = _promise_span(revision, promise, payment=False)
    payment = _promise_span(revision, promise, payment=True)
    if opening is None or payment is None:
        return None, "missing_current_unique_evidence"
    scenes = [node for node in revision.in_reading_order() if node.kind is NodeKind.SCENE]
    positions = {node.logical_id: i for i, node in enumerate(scenes)}
    if opening.logical_id not in positions or payment.logical_id not in positions:
        return None, "evidence_not_in_live_scene"
    first, last = positions[opening.logical_id], positions[payment.logical_id]
    if (
        not promise.paid_at_key or promise.paid_at_key < promise.opened_at_key
        or first > last or (first == last and opening.end > payment.start)
    ):
        return None, "payment_not_after_opening"
    if (first == last) != (promise.opened_at_key == promise.paid_at_key):
        return None, "story_position_disagrees_with_scene"
    window = scenes[first:last + 1]
    if any(not (node.content or "").strip() for node in window):
        return None, "incomplete_context"
    context = "\n\n".join(node.content or "" for node in window)
    if len(context) > max_chars:
        return None, "context_exceeds_limit"
    if context.count(opening.quote) != 1 or context.count(payment.quote) != 1:
        return None, "ambiguous_context_evidence"
    target_text = window[-1].content or ""
    offset = len(context) - len(target_text)
    units = paragraphs(target_text)
    containing = [p for p in units if p.contains(Span(payment.start, payment.end))]
    if len(containing) != 1:
        return None, "payment_crosses_paragraphs"
    target = containing[0]
    blockers = [e for e in protected if e.logical_id == payment.logical_id and e != payment]
    if any(target.overlaps(Span(e.start, e.end)) for e in blockers):
        return None, "target_overlaps_other_evidence"
    # Both interventions remove one complete paragraph in the same payment scene. Match
    # all six existing shallow edit fields; do not call an unmatched deletion a placebo.
    target_global = Span(offset + target.start, offset + target.end)
    withheld = remove(context, target_global)
    fp = deletion_fingerprint(context, target_global, last - first)
    all_payment_scene_spans = [
        Span(e.start, e.end) for e in protected if e.logical_id == payment.logical_id
    ]
    donors = []
    for unit in units:
        if any(unit.overlaps(span) for span in all_payment_scene_spans):
            continue
        global_span = Span(offset + unit.start, offset + unit.end)
        control_fp = deletion_fingerprint(context, global_span, last - first)
        if control_fp == fp:
            donors.append((unit, global_span))
    if not donors:
        return None, "no_matched_unprotected_paragraph"
    donor, donor_global = min(
        donors, key=lambda row: (abs(row[0].start - target.start), row[0].start),
    )
    control = remove(context, donor_global)
    whitespace = BOUNDARY.sub("\n \n", context)
    if whitespace == context:
        return None, "no_whitespace_control"
    texts = {
        "clean": context,
        "payment_evidence_withheld": withheld,
        "other_paragraph_withheld": control,
        "whitespace_only": whitespace,
    }
    # The only certified labels concern the registered quote's presence. No text is
    # labelled "unpaid", "bad prose" or "semantically intact" by this constructor.
    if (
        len(set(texts.values())) != len(texts)
        or any(text.count(opening.quote) != 1 for text in texts.values())
        or any(text.count(payment.quote) != int(role != "payment_evidence_withheld")
               for role, text in texts.items())
        or context.split() != whitespace.split()
    ):
        return None, "reference_visibility_control_failed"
    item_id = "pp-" + payload_digest({
        "version": VERSION, "revision": revision.revision_id, "promise": asdict(promise),
        "source_group": source_group, "target": asdict(target), "donor": asdict(donor),
    })[:24]
    variants = []
    for role, text in texts.items():
        packet = {
            "presentation_id": "packet-" + payload_digest({
                "item_id": item_id, "opening": opening.quote, "text": text,
            })[:24],
            "promise_opening": opening.quote,
            "passage": text,
        }
        variants.append({
            "role": role, "registered_payment_visible": role != "payment_evidence_withheld",
            "packet": packet, "packet_sha256": payload_digest(packet),
        })
    return {
        "item_id": item_id, "promise_id": promise.promise_id,
        "source_group": source_group, "revision_id": revision.revision_id,
        "implementation": VERSION, "context_rung": context_rung_for(
            (opening, payment), revision, shape,
        ).value,
        "context_chars": len(context), "scene_count": len(window),
        "context_sources": [
            {"logical_id": node.logical_id, "content_sha256": content_hash(node.content or "")}
            for node in window
        ],
        "opening": asdict(opening), "payment": asdict(payment),
        "target_paragraph": asdict(target), "control_paragraph": asdict(donor),
        "target_context_span": asdict(target_global), "control_context_span": asdict(donor_global),
        "matched_fingerprint": asdict(fp),
        "character_deltas": {
            "payment_evidence_withheld": len(withheld) - len(context),
            "other_paragraph_withheld": len(control) - len(context),
        },
        "variants": variants,
    }, "constructed"


def build_battery(
    revision: Revision, records: Sequence[lc.StateRecord], promises: Sequence[Promise], *,
    source_group: str, shape: SerialShape, max_chars: int = DEFAULT_MAX_CHARS,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Return prose-free report, unlabelled packets, and physically separate private keys."""
    if not source_group.strip() or max_chars < 1:
        raise ValueError("A whole book/world source group and positive context limit are required")
    if len({p.promise_id for p in promises}) != len(promises):
        raise ValueError("Duplicate promise identities")
    protected = _protected_evidence(revision, records, promises)
    items, dispositions = [], []
    for promise in sorted(promises, key=lambda p: p.promise_id):
        item, reason = _construct(
            revision, promise, protected,
            source_group=source_group, shape=shape, max_chars=max_chars,
        )
        dispositions.append({"promise_id": promise.promise_id, "reason": reason})
        if item is not None:
            items.append(item)
    packets = sorted(
        (variant["packet"] for item in items for variant in item["variants"]),
        key=lambda packet: packet["presentation_id"],
    )
    public = {"version": VERSION + ".public", "packets": packets}
    private = {
        "version": VERSION + ".private", "items": items,
        "warning": "Construction keys and references; never send this file to a model.",
    }
    report = {
        "version": VERSION, "book_id": revision.book_id, "branch_id": revision.branch_id,
        "revision_id": revision.revision_id, "source_group_digest": content_hash(source_group),
        "input_digest": payload_digest({
            "revision": revision.revision_id,
            "promises": [asdict(p) for p in sorted(promises, key=lambda p: p.promise_id)],
            "protected": sorted((asdict(e) for e in protected), key=payload_digest),
        }),
        "max_context_chars": max_chars,
        "promises_seen": len(promises), "constructed_items": len(items), "packets": len(packets),
        "dispositions": dispositions, "reason_counts": dict(sorted(Counter(
            row["reason"] for row in dispositions
        ).items())),
        "context_rungs": dict(sorted(Counter(item["context_rung"] for item in items).items())),
        "items": [{
            "item_id": item["item_id"], "promise_id": item["promise_id"],
            "context_rung": item["context_rung"], "scene_count": item["scene_count"],
            "context_chars": item["context_chars"],
            "matched_fingerprint": item["matched_fingerprint"],
            "character_deltas": item["character_deltas"],
            "packet_ids": [v["packet"]["presentation_id"] for v in item["variants"]],
        } for item in items],
        "public_digest": payload_digest(public), "private_digest": payload_digest(private),
        "model_calls": 0, "construction_ready": bool(items),
        "eligible_for_model_run": False, "production_authority": False,
        "certified_scope": "presence or withdrawal of the ledger's registered payment quotation",
        "unresolved_controls": [
            "independent semantic validity of the ledger relation",
            "alternative payoff evidence and semantic effects of both paragraph deletions",
            "lexical and character-length shortcuts beyond the six matched edit fields",
            "held-out whole books/worlds and transformation implementations",
            "registered task, scoring rule and model-context token budgets",
        ],
    }
    return report, public, private


def build_from_database(
    database: Path, out: Path, *, source_group: str,
    book_id: str | None = None, branch_id: str | None = None,
    shape: SerialShape = DEFAULT_SHAPE, max_chars: int = DEFAULT_MAX_CHARS,
) -> dict[str, Any]:
    """Back up a read-only source and construct from that fixed snapshot, without migrations."""
    if out.exists():
        raise FileExistsError(f"Preserve the existing construction run: {out}")
    with SqliteStore.open_read_only(database) as source:
        book_id, branch_id = resolve_branch(source, book_id, branch_id)
        out.mkdir(parents=True)
        source.backup_to(out / "source.db")
    with SqliteStore.open_read_only(out / "source.db") as snapshot:
        head = snapshot.head(book_id, branch_id)
        if head is None:
            raise ValueError("This branch has no manuscript revision")
        report, public, private = build_battery(
            head, snapshot.state_records(book_id, branch_id), snapshot.promises(book_id, branch_id),
            source_group=source_group, shape=shape, max_chars=max_chars,
        )
    report["provenance"] = {
        "snapshot_sha256": file_hash(out / "source.db"),
        "builder_sha256": file_hash(Path(__file__)),
        "salience_sha256": file_hash(Path(inspect.getfile(_promise_span))),
        "source_access": "SQLite mode=ro; consistent backup; no migration",
    }
    write_json(out / "packets.public.json", public)
    write_json(out / "keys.private.json", private)
    report["artifact_sha256"] = {
        name: file_hash(out / name) for name in ("packets.public.json", "keys.private.json")
    }
    write_json(out / "report.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--source-group", required=True, help="Whole book/world identity for splits",
    )
    parser.add_argument("--book")
    parser.add_argument("--branch")
    parser.add_argument("--chapter-scenes", type=int, default=1)
    parser.add_argument("--arc-chapters", type=int, default=6)
    parser.add_argument("--max-context-chars", type=int, default=DEFAULT_MAX_CHARS)
    args = parser.parse_args()
    report = build_from_database(
        args.database, args.out, source_group=args.source_group,
        book_id=args.book, branch_id=args.branch,
        shape=SerialShape(args.chapter_scenes, args.arc_chapters), max_chars=args.max_context_chars,
    )
    print(json.dumps({key: report[key] for key in (
        "promises_seen", "constructed_items", "packets", "reason_counts", "context_rungs",
        "eligible_for_model_run", "model_calls",
    )}, indent=2))


if __name__ == "__main__":
    main()
