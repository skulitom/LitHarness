"""Bounded patch application and the mechanical veto list.

A `BoundedPatch` is the only sanctioned shape for a prose change: it names one node
version, cites exact spans, and carries the hash of the text it expects to find. This
module applies one and refuses it for structural reasons — no model, no critic, no
judgement. Every refusal is a named veto with a reason, because §4.2's ladder needs a
structured gate result to feed back into a bounded retry.

The load-bearing guarantee is **preservation**: text outside the cited spans is
byte-identical after application. That is what makes "unchanged text is structurally
ineligible for revision" (§12) mechanically true. It is checked rather than assumed —
`_verify_preservation` recomputes the untouched segments from the result and their
expected offsets, which catches the offset-arithmetic slips that are the realistic
failure mode here.

Span hashes are the anti-staleness mechanism. Each op cites `content_sha256` for the
exact text it intends to replace, so a patch built against a stale read is refused at
the span level rather than silently applied to different text that happens to sit at
the same offsets.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from itertools import pairwise

import litharness_contracts as lc

from litharness.domain.nodes import Node
from litharness.domain.revision import Revision, node_version_id
from litharness.domain.text import canonicalize, content_hash


class Veto(enum.StrEnum):
    """One vocabulary for every mechanical refusal, shared with `domain.draft`.

    Kept as a single enum rather than one per gate so a policy decision record cites the
    same name whichever gate produced it, and so §4.2's retry ladder has one table of
    reasons to act on.
    """

    EMPTY_PATCH = "empty_patch"
    UNKNOWN_TARGET = "unknown_target"
    STALE_BASE_VERSION = "stale_base_version"
    STALE_BASE_CONTENT = "stale_base_content"
    TARGET_HAS_NO_CONTENT = "target_has_no_content"
    SPAN_OUT_OF_RANGE = "span_out_of_range"
    SPAN_HASH_MISMATCH = "span_hash_mismatch"
    OVERLAPPING_SPANS = "overlapping_spans"
    CONTENT_LOCKED = "content_locked"
    UNLICENSED_DELETION = "unlicensed_deletion"
    LENGTH_MOVEMENT = "length_movement"
    PRESERVATION_BREACH = "preservation_breach"
    UNSUPPORTED_OP = "unsupported_op"
    #: Raised by `domain.draft` only.
    EMPTY_DRAFT = "empty_draft"
    SHAPE_NOT_CONFORMING = "shape_not_conforming"
    #: Raised by `domain.integrity` only: a blocking finding stands against the candidate.
    #: One veto for every finding category, because §4.2's ladder acts on the veto and the
    #: action is the same for all of them — see `findings.vetoes_for`.
    CONTINUITY_BREACH = "continuity_breach"
    #: Raised by `domain.calibration.promoted_gate` only: a craft metric carrying measured
    #: held-out precision measured this candidate on the failing side of its threshold. One
    #: veto for every metric, for `CONTINUITY_BREACH`'s reason — the ladder acts on the veto,
    #: and the action is the same whichever proxy fired.
    CRAFT_BELOW_BAR = "craft_below_bar"


@dataclass(frozen=True, slots=True)
class VetoRecord:
    veto: Veto
    detail: str

    def __str__(self) -> str:  # pragma: no cover - diagnostics only
        return f"{self.veto.value}: {self.detail}"


@dataclass(frozen=True, slots=True)
class PatchPolicy:
    """Deterministic limits. Named so a policy decision record can cite the values used."""

    #: Reject a patch whose result is shorter than this fraction of the original, or
    #: longer than its reciprocal. RevisionBench's mechanical veto against silent
    #: truncation and runaway expansion.
    min_length_ratio: float = 0.5
    max_length_ratio: float = 2.0
    #: Deletion (a replace with empty text, or an explicit delete op) requires a located
    #: complaint. Without this, "improve this" degenerates into "remove this".
    require_license_for_deletion: bool = True
    max_ops: int = 32


@dataclass(frozen=True, slots=True)
class PatchOutcome:
    accepted: bool
    vetoes: tuple[VetoRecord, ...] = ()
    revision: Revision | None = None
    node_before: Node | None = None
    node_after: Node | None = None
    applied_ops: int = 0
    length_delta: int = 0
    #: Offsets of the spans the patch was licensed to touch, for the provenance record.
    touched_spans: tuple[tuple[int, int], ...] = field(default_factory=tuple)

    @property
    def veto_kinds(self) -> tuple[Veto, ...]:
        return tuple(record.veto for record in self.vetoes)


def _op_span(op: lc.PatchOp) -> tuple[int, int]:
    return int(op.target_span.start), int(op.target_span.end)


def _is_deletion(op: lc.PatchOp) -> bool:
    if op.kind is lc.PatchOpKind.DELETE_SPAN:
        return True
    start, end = _op_span(op)
    return end > start and not (op.new_text or "")


def apply_patch(
    revision: Revision,
    patch: lc.BoundedPatch,
    policy: PatchPolicy | None = None,
) -> PatchOutcome:
    """Apply ``patch`` to ``revision``, or refuse it with named vetoes."""
    policy = policy or PatchPolicy()
    vetoes: list[VetoRecord] = []

    if not patch.ops:
        return PatchOutcome(False, (VetoRecord(Veto.EMPTY_PATCH, "patch carries no ops"),))
    if len(patch.ops) > policy.max_ops:
        vetoes.append(
            VetoRecord(
                Veto.UNSUPPORTED_OP,
                f"{len(patch.ops)} ops exceeds the policy limit of {policy.max_ops}",
            )
        )

    logical_id = patch.target.logical_id
    try:
        node = revision.node(logical_id)
    except KeyError:
        return PatchOutcome(
            False, (VetoRecord(Veto.UNKNOWN_TARGET, f"no node {logical_id} in revision"),)
        )

    if node.content is None:
        return PatchOutcome(
            False,
            (VetoRecord(Veto.TARGET_HAS_NO_CONTENT, f"node {logical_id} carries no text"),),
        )

    actual_version = node_version_id(node)
    if patch.base_version_id != actual_version:
        vetoes.append(
            VetoRecord(
                Veto.STALE_BASE_VERSION,
                f"patch targets {patch.base_version_id[:12]} but node is {actual_version[:12]}",
            )
        )
    if patch.base_content_sha256 != node.content_sha256:
        vetoes.append(
            VetoRecord(
                Veto.STALE_BASE_CONTENT,
                "patch base content hash does not match the node's current text",
            )
        )
    if node.lock.freezes_content:
        vetoes.append(
            VetoRecord(
                Veto.CONTENT_LOCKED,
                f"node {logical_id} is {node.lock.value}-locked and its content is frozen",
            )
        )

    text = node.content
    spans: list[tuple[int, int, str]] = []
    for index, op in enumerate(patch.ops):
        if op.kind is lc.PatchOpKind.UNKNOWN:
            vetoes.append(VetoRecord(Veto.UNSUPPORTED_OP, f"op {index} has an unknown kind"))
            continue
        start, end = _op_span(op)
        if not 0 <= start <= end <= len(text):
            vetoes.append(
                VetoRecord(
                    Veto.SPAN_OUT_OF_RANGE,
                    f"op {index} cites {start}..{end} outside text of length {len(text)}",
                )
            )
            continue
        expected = op.target_span.content_sha256
        if expected and expected != content_hash(text[start:end]):
            vetoes.append(
                VetoRecord(
                    Veto.SPAN_HASH_MISMATCH,
                    f"op {index} cites text at {start}..{end} that is no longer there",
                )
            )
            continue
        if (
            _is_deletion(op)
            and policy.require_license_for_deletion
            and not patch.licensed_by_finding_id
        ):
            vetoes.append(
                VetoRecord(
                    Veto.UNLICENSED_DELETION,
                    f"op {index} deletes {end - start} characters with no licensing finding",
                )
            )
            continue
        replacement = (
            "" if op.kind is lc.PatchOpKind.DELETE_SPAN else canonicalize(op.new_text or "")
        )
        spans.append((start, end, replacement))

    spans.sort(key=lambda item: (item[0], item[1]))
    for (a_start, a_end, _), (b_start, _b_end, _b) in pairwise(spans):
        if b_start < a_end:
            vetoes.append(
                VetoRecord(
                    Veto.OVERLAPPING_SPANS,
                    f"spans {a_start}..{a_end} and {b_start}.. overlap; each op must be disjoint",
                )
            )
            break

    if vetoes:
        return PatchOutcome(False, tuple(vetoes), node_before=node)

    result, untouched = _splice(text, spans)

    ratio = len(result) / len(text) if text else 1.0
    if not policy.min_length_ratio <= ratio <= policy.max_length_ratio:
        return PatchOutcome(
            False,
            (
                VetoRecord(
                    Veto.LENGTH_MOVEMENT,
                    f"result is {ratio:.2f}x the original, outside "
                    f"[{policy.min_length_ratio}, {policy.max_length_ratio}]",
                ),
            ),
            node_before=node,
        )

    breach = _verify_preservation(text, result, spans, untouched)
    if breach is not None:
        return PatchOutcome(
            False, (VetoRecord(Veto.PRESERVATION_BREACH, breach),), node_before=node
        )

    updated = node.with_content(result)
    return PatchOutcome(
        accepted=True,
        revision=revision.replacing([updated]),
        node_before=node,
        node_after=updated,
        applied_ops=len(spans),
        length_delta=len(result) - len(text),
        touched_spans=tuple((start, end) for start, end, _ in spans),
    )


def _splice(text: str, spans: list[tuple[int, int, str]]) -> tuple[str, list[str]]:
    """Rebuild ``text`` with ``spans`` replaced, returning the untouched segments too."""
    pieces: list[str] = []
    untouched: list[str] = []
    cursor = 0
    for start, end, replacement in spans:
        segment = text[cursor:start]
        untouched.append(segment)
        pieces.append(segment)
        pieces.append(replacement)
        cursor = end
    tail = text[cursor:]
    untouched.append(tail)
    pieces.append(tail)
    return "".join(pieces), untouched


def _verify_preservation(
    original: str, result: str, spans: list[tuple[int, int, str]], untouched: list[str]
) -> str | None:
    """Confirm every untouched segment survives byte-identically at its new offset.

    Walks the *result* independently of how it was built: it recomputes where each
    untouched segment must now start given the cumulative length change from the
    replacements before it, then compares. An off-by-one in the splice arithmetic shows
    up here as a mismatch rather than as quietly corrupted prose.
    """
    expected_length = len(original) - sum(end - start for start, end, _ in spans) + sum(
        len(replacement) for _, _, replacement in spans
    )
    if len(result) != expected_length:
        return f"result length {len(result)} does not match the expected {expected_length}"

    cursor = 0
    for index, segment in enumerate(untouched):
        if result[cursor : cursor + len(segment)] != segment:
            return (
                f"untouched segment {index} was altered: expected {segment[:40]!r} at "
                f"offset {cursor}, found {result[cursor : cursor + len(segment)][:40]!r}"
            )
        cursor += len(segment)
        if index < len(spans):
            cursor += len(spans[index][2])
    return None
