"""The shape gate for a generated draft: §4.2 ladder step 1, deterministic and model-free.

`patch.py` gates a *change* to text that already exists. This gates the other case — a
node that has no prose yet receiving its first draft — and the two are deliberately not
the same function, because the interesting rule is the one that separates them.

**A draft may only fill emptiness. Rewriting existing prose must route through
`apply_patch`.** That is what `DraftPolicy.allow_overwrite = False` enforces, and it is
the structural expression of §1a.2 and §12: unchanged text is ineligible for revision
unless a located complaint licenses it, and `apply_patch` is where that license is
checked (`Veto.UNLICENSED_DELETION`). Without this rule the obvious next move once a
handler can generate and commit is "have it improve the scene it just wrote", which is
precisely the open-ended revision loop the plan forbids — with RevisionBench's ~80%
preference for human originals as the measured evidence against it. Relaxing the default
as a convenience would quietly delete that guarantee, so it is a policy field with a safe
default rather than a parameter callers pass casually.

The vetoes are named and structured rather than boolean because §4.2's ladder feeds a
failed gate back into a bounded retry, and "it failed" is not something a retry can act
on. `SHAPE_NOT_CONFORMING` is the one fed directly by the provider layer:
`CompletionResult.conforms` is false when a schema was requested and the answer did not
satisfy it, which is a retryable shape failure and never an exception.
"""

from __future__ import annotations

from dataclasses import dataclass

from litharness.domain.nodes import Node
from litharness.domain.patch import Veto, VetoRecord
from litharness.domain.revision import Revision
from litharness.domain.text import canonicalize


@dataclass(frozen=True, slots=True)
class DraftPolicy:
    """Deterministic limits. Named so a policy decision record can cite the values used."""

    #: A draft shorter than this is a stub, a refusal, or a truncated stream. The floor is
    #: low on purpose: this is a shape gate, not a quality gate, and §1a.1 warns against
    #: letting a mechanically checkable number stand in for whether the scene lands.
    min_chars: int = 200
    #: Guards against a runaway generation filling the store, not against verbosity.
    max_chars: int = 8000
    #: See the module docstring. Do not flip this to make a caller's life easier.
    allow_overwrite: bool = False


@dataclass(frozen=True, slots=True)
class DraftOutcome:
    accepted: bool
    vetoes: tuple[VetoRecord, ...] = ()
    revision: Revision | None = None
    node_before: Node | None = None
    node_after: Node | None = None
    chars: int = 0

    @property
    def veto_kinds(self) -> tuple[Veto, ...]:
        return tuple(record.veto for record in self.vetoes)


def gate_draft(
    revision: Revision,
    logical_id: str,
    text: str,
    *,
    conforms: bool = True,
    policy: DraftPolicy | None = None,
) -> DraftOutcome:
    """Gate ``text`` as the first draft of ``logical_id``, or refuse it with named vetoes.

    Returns the new revision on acceptance; it does not persist anything. Committing is
    the Conductor's job, because only the Conductor can put the revision, its events and
    the job's status change in one transaction.
    """
    policy = policy or DraftPolicy()

    try:
        node = revision.node(logical_id)
    except KeyError:
        return DraftOutcome(
            False, (VetoRecord(Veto.UNKNOWN_TARGET, f"no node {logical_id} in revision"),)
        )

    if not conforms:
        return DraftOutcome(
            False,
            (
                VetoRecord(
                    Veto.SHAPE_NOT_CONFORMING,
                    "provider answer did not satisfy the requested schema",
                ),
            ),
            node_before=node,
        )

    if node.lock.freezes_content:
        return DraftOutcome(
            False,
            (
                VetoRecord(
                    Veto.CONTENT_LOCKED,
                    f"node {logical_id} is {node.lock.value}-locked and its content is frozen",
                ),
            ),
            node_before=node,
        )

    if node.content is not None and not policy.allow_overwrite:
        return DraftOutcome(
            False,
            (
                VetoRecord(
                    Veto.TARGET_HAS_NO_CONTENT,
                    f"node {logical_id} already carries {len(node.content)} characters; "
                    "a rewrite needs a located complaint and must go through apply_patch",
                ),
            ),
            node_before=node,
        )

    canonical = canonicalize(text)
    if not canonical.strip():
        return DraftOutcome(
            False,
            (VetoRecord(Veto.EMPTY_DRAFT, "draft is empty or whitespace only"),),
            node_before=node,
        )

    vetoes: list[VetoRecord] = []
    if len(canonical) < policy.min_chars:
        vetoes.append(
            VetoRecord(
                Veto.LENGTH_MOVEMENT,
                f"draft is {len(canonical)} chars, below the floor of {policy.min_chars}",
            )
        )
    if len(canonical) > policy.max_chars:
        vetoes.append(
            VetoRecord(
                Veto.LENGTH_MOVEMENT,
                f"draft is {len(canonical)} chars, above the ceiling of {policy.max_chars}",
            )
        )
    if vetoes:
        return DraftOutcome(False, tuple(vetoes), node_before=node)

    updated = node.with_content(canonical)
    return DraftOutcome(
        accepted=True,
        revision=revision.replacing([updated]),
        node_before=node,
        node_after=updated,
        chars=len(canonical),
    )


__all__ = ["DraftOutcome", "DraftPolicy", "gate_draft"]
