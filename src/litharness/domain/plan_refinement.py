"""Versioned plan proposals: the transaction seam for the Narrative Planner.

The planner contains a model call, and a model call is a long gap between reading the book
and proposing what should change. This module splits that work in two: produce a
proposal against one frozen plan revision, then apply it only if that revision is still the
head. A director or another tick may have changed the plan while the model was thinking;
silently applying the stale reading would overwrite the newer direction.

Three LitHarness rules make this stricter than a generic editable-memory store:

* **Application is atomic.** A directive cannot become half interpreted because edit three
  of four conflicted. Every edit validates first, then one new snapshot is constructed.
* **Locked plan items stay locked.** Ordinary proposals cannot update or delete them.
  Forward rollback is the narrow exception: it restores a previously accepted snapshot.
* **Rollback goes forward.** Restoring an old plan creates a child of the current plan;
  neither the mistake nor its correction disappears from history.

The types are provider-independent. A bounded Narrative Planner now produces proposals for
one interpretive directive at a time; deterministic producers and future full-book planners
use the same validation, storage, conflict, and rollback boundary.
"""

from __future__ import annotations

import enum
import json
from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any, cast

import litharness_contracts as lc


def _digest(payload: object) -> str:
    rendered = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return sha256(rendered.encode("utf-8")).hexdigest()


def _item_payload(item: lc.PlanItem) -> dict[str, Any]:
    payload = lc.to_jsonable(item)
    if not isinstance(payload, dict):  # pragma: no cover - contract serializer guarantee
        raise TypeError("PlanItem did not serialize to an object")
    return payload


def _clone_item(item: lc.PlanItem) -> lc.PlanItem:
    return cast(lc.PlanItem, lc.from_jsonable(lc.PlanItem, _item_payload(item)))


class PlanProposalError(ValueError):
    """A proposal is internally invalid and cannot produce a plan revision."""


class PlanConflict(PlanProposalError):
    """The plan head moved after proposal planning began."""


class PlanProposalStatus(enum.StrEnum):
    """Durable outcome of presenting a proposal to the plan head."""

    APPLIED = "applied"
    CONFLICTED = "conflicted"


@dataclass(frozen=True, slots=True)
class PlanRevision:
    """A content-addressed full plan snapshot with single-parent lineage."""

    book_id: str
    branch_id: str
    items: tuple[lc.PlanItem, ...]
    parent_plan_revision_id: str | None = None
    source_snapshot_id: str | None = field(default=None, compare=False)
    plan_revision_id: str = field(default="", compare=False)

    def __post_init__(self) -> None:
        # Contract dataclasses are mutable. Snapshot the values at the boundary so a caller
        # retaining its imported PlanItem cannot change this revision behind its hash.
        cloned = tuple(_clone_item(item) for item in self.items)
        object.__setattr__(self, "items", cloned)
        _validate_items(cloned)
        computed = self._compute_id()
        if self.plan_revision_id and self.plan_revision_id != computed:
            raise ValueError(
                "restored plan revision id does not match its content: "
                f"{self.plan_revision_id[:12]} != {computed[:12]}"
            )
        object.__setattr__(self, "plan_revision_id", computed)

    def _compute_id(self) -> str:
        return _digest(
            {
                "book_id": self.book_id,
                "branch_id": self.branch_id,
                "parent_plan_revision_id": self.parent_plan_revision_id,
                "items": sorted(
                    (_item_payload(item) for item in self.items),
                    key=lambda item: str(item["logical_id"]),
                ),
            }
        )

    def item(self, logical_id: str) -> lc.PlanItem:
        for item in self.items:
            if item.logical_id == logical_id:
                return _clone_item(item)
        raise KeyError(f"no plan item {logical_id} in {self.plan_revision_id[:12]}")

    def reverting_to(self, target: PlanRevision) -> PlanRevision:
        """Create a forward revision whose content restores ``target``."""
        if (self.book_id, self.branch_id) != (target.book_id, target.branch_id):
            raise ValueError("cannot restore a plan from another book or branch")
        return PlanRevision(
            book_id=self.book_id,
            branch_id=self.branch_id,
            items=target.items,
            parent_plan_revision_id=self.plan_revision_id,
            source_snapshot_id=target.source_snapshot_id,
        )


class PlanEditAction(enum.StrEnum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"


@dataclass(frozen=True, slots=True)
class PlanEdit:
    action: PlanEditAction
    logical_id: str
    item: lc.PlanItem | None = None
    reason: str = ""

    def __post_init__(self) -> None:
        if not self.logical_id:
            raise PlanProposalError("plan edit requires logical_id")
        if self.action is PlanEditAction.DELETE and self.item is not None:
            raise PlanProposalError("delete edit must not carry an item")
        if self.action is not PlanEditAction.DELETE:
            if self.item is None:
                raise PlanProposalError(f"{self.action.value} edit requires an item")
            if self.item.logical_id != self.logical_id:
                raise PlanProposalError(
                    f"edit target {self.logical_id!r} does not match item "
                    f"{self.item.logical_id!r}"
                )
            object.__setattr__(self, "item", _clone_item(self.item))


@dataclass(frozen=True, slots=True)
class DirectiveReading:
    """What the planner decided one immutable director directive means."""

    directive_id: str
    interpretation: str
    produced_constraint_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.directive_id or not self.interpretation.strip():
            raise PlanProposalError("directive reading requires an id and interpretation")


@dataclass(frozen=True, slots=True)
class PlanProposal:
    base_plan_revision_id: str
    summary: str
    rationale: str
    expected_outcome: str
    edits: tuple[PlanEdit, ...]
    readings: tuple[DirectiveReading, ...] = ()
    provider: str | None = None
    model: str | None = None
    profile: str | None = None
    rollback_of: str | None = None
    proposal_id: str = field(default="", compare=False)

    def __post_init__(self) -> None:
        if not self.base_plan_revision_id:
            raise PlanProposalError("proposal requires a base plan revision")
        if not self.summary.strip():
            raise PlanProposalError("proposal requires a summary")
        if not self.rationale.strip() or not self.expected_outcome.strip():
            raise PlanProposalError("proposal requires rationale and expected outcome")
        if not self.edits:
            raise PlanProposalError("proposal must change at least one plan item")
        edited = [edit.logical_id for edit in self.edits]
        duplicates = sorted({logical_id for logical_id in edited if edited.count(logical_id) > 1})
        if duplicates:
            raise PlanProposalError(f"proposal edits a plan item more than once: {duplicates}")
        read = [reading.directive_id for reading in self.readings]
        duplicate_readings = sorted(
            {directive_id for directive_id in read if read.count(directive_id) > 1}
        )
        if duplicate_readings:
            raise PlanProposalError(
                f"proposal interprets a directive more than once: {duplicate_readings}"
            )
        computed = f"planprop-{_digest(proposal_to_dict(self, include_id=False))[:24]}"
        if self.proposal_id and self.proposal_id != computed:
            raise ValueError(
                f"restored proposal id does not match its content: "
                f"{self.proposal_id} != {computed}"
            )
        object.__setattr__(self, "proposal_id", computed)


@dataclass(frozen=True, slots=True)
class AppliedPlanEdit:
    action: PlanEditAction
    logical_id: str
    before: lc.PlanItem | None = None
    after: lc.PlanItem | None = None


@dataclass(frozen=True, slots=True)
class PlanApplication:
    proposal: PlanProposal
    before: PlanRevision
    after: PlanRevision
    applied_edits: tuple[AppliedPlanEdit, ...]


@dataclass(frozen=True, slots=True)
class StoredPlanProposal:
    """A proposal plus the outcome recorded by the atomic commit seam."""

    proposal: PlanProposal
    status: PlanProposalStatus
    resulting_plan_revision_id: str | None
    error: str | None
    created_at: str
    applied_at: str | None


def _validate_items(items: tuple[lc.PlanItem, ...]) -> None:
    ids = [item.logical_id for item in items]
    duplicates = sorted({logical_id for logical_id in ids if ids.count(logical_id) > 1})
    if duplicates:
        raise PlanProposalError(f"plan contains duplicate logical ids: {duplicates}")
    if any(not item.logical_id or not item.text.strip() for item in items):
        raise PlanProposalError("plan items require a logical id and non-empty text")
    premises = [item for item in items if item.kind is lc.PlanKind.PREMISE]
    if len(premises) != 1:
        raise PlanProposalError(f"plan must contain exactly one premise, found {len(premises)}")


def apply_plan_proposal(base: PlanRevision, proposal: PlanProposal) -> PlanApplication:
    """Validate every edit and return one child snapshot, without persistence."""
    if proposal.base_plan_revision_id != base.plan_revision_id:
        raise PlanConflict(
            f"proposal planned against {proposal.base_plan_revision_id[:12]}, but plan head "
            f"is {base.plan_revision_id[:12]}"
        )

    records = {item.logical_id: _clone_item(item) for item in base.items}
    applied: list[AppliedPlanEdit] = []
    rollback = proposal.rollback_of is not None
    for edit in proposal.edits:
        before = records.get(edit.logical_id)
        if edit.action is PlanEditAction.CREATE:
            if before is not None:
                raise PlanProposalError(f"plan item {edit.logical_id!r} already exists")
            assert edit.item is not None
            after = _clone_item(edit.item)
            records[edit.logical_id] = after
        elif edit.action is PlanEditAction.UPDATE:
            if before is None:
                raise PlanProposalError(f"plan item {edit.logical_id!r} does not exist")
            if before.locked and not rollback:
                raise PlanProposalError(f"locked plan item {edit.logical_id!r} cannot be updated")
            assert edit.item is not None
            after = _clone_item(edit.item)
            records[edit.logical_id] = after
        else:
            if before is None:
                raise PlanProposalError(f"plan item {edit.logical_id!r} does not exist")
            if before.locked and not rollback:
                raise PlanProposalError(f"locked plan item {edit.logical_id!r} cannot be deleted")
            after = None
            del records[edit.logical_id]
        applied.append(
            AppliedPlanEdit(
                action=edit.action,
                logical_id=edit.logical_id,
                before=_clone_item(before) if before else None,
                after=_clone_item(after) if after else None,
            )
        )

    final_items = tuple(records[logical_id] for logical_id in sorted(records))
    _validate_items(final_items)
    final_ids = set(records)
    for reading in proposal.readings:
        missing = sorted(set(reading.produced_constraint_ids) - final_ids)
        if missing:
            raise PlanProposalError(
                f"directive {reading.directive_id} cites missing produced constraints: {missing}"
            )
        invalid = sorted(
            logical_id
            for logical_id in reading.produced_constraint_ids
            if records[logical_id].kind is not lc.PlanKind.CONSTRAINT
            or not records[logical_id].locked
        )
        if invalid:
            raise PlanProposalError(
                f"directive {reading.directive_id} must produce locked constraints: {invalid}"
            )

    after_revision = PlanRevision(
        book_id=base.book_id,
        branch_id=base.branch_id,
        items=final_items,
        parent_plan_revision_id=base.plan_revision_id,
    )
    return PlanApplication(proposal, base, after_revision, tuple(applied))


def rollback_proposal(
    current: PlanRevision,
    target: PlanRevision,
    *,
    rollback_of: str,
    provider: str | None = None,
    model: str | None = None,
    profile: str | None = None,
) -> PlanProposal:
    """Describe restoring ``target`` as ordinary auditable edits against ``current``."""
    if (current.book_id, current.branch_id) != (target.book_id, target.branch_id):
        raise ValueError("cannot restore a plan from another book or branch")
    current_items = {item.logical_id: item for item in current.items}
    target_items = {item.logical_id: item for item in target.items}
    edits: list[PlanEdit] = []
    for logical_id in sorted(set(current_items) | set(target_items)):
        before = current_items.get(logical_id)
        after = target_items.get(logical_id)
        if before is None and after is not None:
            edits.append(PlanEdit(PlanEditAction.CREATE, logical_id, after, "restore"))
        elif before is not None and after is None:
            edits.append(PlanEdit(PlanEditAction.DELETE, logical_id, reason="restore"))
        elif (
            before is not None
            and after is not None
            and _item_payload(before) != _item_payload(after)
        ):
            edits.append(PlanEdit(PlanEditAction.UPDATE, logical_id, after, "restore"))
    if not edits:
        raise PlanProposalError("target plan already matches the current plan")
    return PlanProposal(
        base_plan_revision_id=current.plan_revision_id,
        summary=f"Restore plan revision {target.plan_revision_id[:12]}",
        rationale=f"Forward rollback of proposal {rollback_of}",
        expected_outcome="The accepted plan matches the selected earlier snapshot.",
        edits=tuple(edits),
        provider=provider,
        model=model,
        profile=profile,
        rollback_of=rollback_of,
    )


def proposal_to_dict(proposal: PlanProposal, *, include_id: bool = True) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "base_plan_revision_id": proposal.base_plan_revision_id,
        "summary": proposal.summary,
        "rationale": proposal.rationale,
        "expected_outcome": proposal.expected_outcome,
        "edits": [
            {
                "action": edit.action.value,
                "logical_id": edit.logical_id,
                "item": _item_payload(edit.item) if edit.item else None,
                "reason": edit.reason,
            }
            for edit in proposal.edits
        ],
        "readings": [
            {
                "directive_id": reading.directive_id,
                "interpretation": reading.interpretation,
                "produced_constraint_ids": list(reading.produced_constraint_ids),
            }
            for reading in proposal.readings
        ],
        "provider": proposal.provider,
        "model": proposal.model,
        "profile": proposal.profile,
        "rollback_of": proposal.rollback_of,
    }
    if include_id:
        payload["proposal_id"] = proposal.proposal_id
    return payload


def proposal_from_dict(payload: dict[str, Any]) -> PlanProposal:
    return PlanProposal(
        base_plan_revision_id=str(payload["base_plan_revision_id"]),
        summary=str(payload["summary"]),
        rationale=str(payload.get("rationale", "")),
        expected_outcome=str(payload.get("expected_outcome", "")),
        edits=tuple(
            PlanEdit(
                action=PlanEditAction(edit["action"]),
                logical_id=str(edit["logical_id"]),
                item=(
                    lc.from_jsonable(lc.PlanItem, edit["item"])
                    if isinstance(edit.get("item"), dict)
                    else None
                ),
                reason=str(edit.get("reason", "")),
            )
            for edit in payload.get("edits", ())
        ),
        readings=tuple(
            DirectiveReading(
                directive_id=str(reading["directive_id"]),
                interpretation=str(reading["interpretation"]),
                produced_constraint_ids=tuple(reading.get("produced_constraint_ids", ())),
            )
            for reading in payload.get("readings", ())
        ),
        provider=payload.get("provider"),
        model=payload.get("model"),
        profile=payload.get("profile"),
        rollback_of=payload.get("rollback_of"),
        proposal_id=str(payload.get("proposal_id", "")),
    )


__all__ = [
    "AppliedPlanEdit",
    "DirectiveReading",
    "PlanApplication",
    "PlanConflict",
    "PlanEdit",
    "PlanEditAction",
    "PlanProposal",
    "PlanProposalError",
    "PlanProposalStatus",
    "PlanRevision",
    "StoredPlanProposal",
    "apply_plan_proposal",
    "proposal_from_dict",
    "proposal_to_dict",
    "rollback_proposal",
]
