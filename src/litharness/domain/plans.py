"""Plan statements: premise, promises, locked constraints.

The fixtures' `plans.json` carries exactly what a planner needs and `cli import` was
throwing away — five items for mystery, four for litrpg, all of them book-wide
statements rather than per-scene instructions. Not one is a `scene_plan`; not one carries a
`scope`. So this module stores *statements*, and `beats.py` derives the *work*.

**Re-anchor, do not deserialize** — the same decision `import_manuscript` records. A
contracts `PlanSnapshot` pins `revision_id` to the upstream UUID5 (mystery
`1462725a…`, litrpg `cfb8482a…`), which by construction is never the sha256 content
address LitHarness mints on import. Matching a plan to its manuscript by that field would
therefore never succeed. The rows are keyed on the local book and branch, and the upstream
id is kept as provenance.

**The premise is required, and its absence blocks rather than defaults.** A prompt cannot
be rendered without it, and a planner that substituted a placeholder would draft a book
against a premise nobody wrote — the failure would be six scenes of plausible prose about
nothing, which no gate in this system can detect.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import litharness_contracts as lc


@dataclass(frozen=True, slots=True)
class ImportedPlan:
    book_id: str
    branch_id: str
    items: tuple[lc.PlanItem, ...]
    #: The upstream PlanSnapshot's revision_id, kept as provenance. See the module docstring.
    source_revision_id: str | None = None


def import_plan(
    source: lc.PlanSnapshot, *, book_id: str, branch_id: str
) -> ImportedPlan:
    """Adopt a foreign plan snapshot against a local book and branch."""
    return ImportedPlan(
        book_id=book_id,
        branch_id=branch_id,
        items=tuple(source.items),
        source_revision_id=source.revision_id,
    )


def premise_of(items: Sequence[lc.PlanItem]) -> str | None:
    """The single premise statement, or None if there is not exactly one.

    Zero and many are both None on purpose. Zero means the book was never given a premise;
    many means nobody can say which one governs. Both are conditions a human resolves, and
    picking one would hide the question.
    """
    premises = [item for item in items if item.kind is lc.PlanKind.PREMISE]
    return premises[0].text if len(premises) == 1 else None


def constraints_of(items: Sequence[lc.PlanItem]) -> tuple[lc.PlanItem, ...]:
    """Locked constraints and promises — the raw material for context assembly.

    Read by nothing in this slice, which is why they are returned rather than rendered:
    the next slice's prompt builder is their consumer and will decide how they appear.
    """
    return tuple(
        item
        for item in items
        if item.kind in {lc.PlanKind.CONSTRAINT, lc.PlanKind.PROMISE} and item.locked
    )


def scene_plan_id_for(logical_id: str) -> str:
    """The plan item id carrying what one scene is for.

    Derived from the scene rather than minted, so an outline re-proposed for the same book
    edits the same items instead of accumulating a second set beside the first — and so
    `scene_plan_for` can find a statement without scanning `scope` on every item.
    """
    return f"{logical_id}-plan"


def scene_plan_line(statement: str) -> str:
    """The prompt fragment that hands one scene its statement — rendered LAST, always.

    One function, two callers, no drift: `render_prompt` appends it when the plan already
    holds the statement, and the plan-search handler (§61 Add 3) appends one *alternative*
    per candidate draft. The empirical bet §61 names — alternatives differ exactly where
    the generator is most sensitive, the final line of the prompt — is only a controlled
    comparison while both callers render the line byte-identically, which is why this is a
    function rather than two f-strings that agree today.
    """
    stripped = statement.strip()
    return f" This scene: {stripped}" if stripped else ""


def scene_plan_for(
    items: Sequence[lc.PlanItem], logical_id: str
) -> lc.PlanItem | None:
    """The statement of what *this* scene is for, or None if the book has no outline.

    **Scoped, so it reaches one scene and not the book.** `constraints_of` selects locked
    constraints and promises and therefore cannot pick these up, which is what keeps thirty
    scene statements out of every scene's constraint block — a packet carrying the whole
    outline would hand every scene every other scene's errand, which is a more expensive way
    to cause the failure the outline exists to fix.

    Matched on `scope` first and on the derived id second. The id is how they are written and
    the scope is what they *mean*, so an item scoped to this scene under some other id is
    still this scene's plan; an outline imported from elsewhere is the case that makes the
    difference.
    """
    scoped = [
        item
        for item in items
        if item.kind is lc.PlanKind.SCENE_PLAN
        and item.scope is not None
        and item.scope.logical_id == logical_id
    ]
    if scoped:
        return scoped[0]
    derived = scene_plan_id_for(logical_id)
    return next(
        (
            item
            for item in items
            if item.kind is lc.PlanKind.SCENE_PLAN and item.logical_id == derived
        ),
        None,
    )


__all__ = [
    "ImportedPlan",
    "constraints_of",
    "import_plan",
    "premise_of",
    "scene_plan_for",
    "scene_plan_id_for",
    "scene_plan_line",
]
