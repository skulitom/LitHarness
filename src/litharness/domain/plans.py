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


__all__ = ["ImportedPlan", "constraints_of", "import_plan", "premise_of"]
