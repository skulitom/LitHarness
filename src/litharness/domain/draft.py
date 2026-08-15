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

from contextlib import suppress
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
    #: How long a scene the generator is **asked** for. A target, never a limit: nothing here
    #: checks it, and `gate_draft` keeps refusing only stubs and runaways.
    #:
    #: **It lives in the policy so the decision record cites it.** Measured on the first Book
    #: Zero run, a 3B model wrote a mean of 160 words per scene — 24 scenes came to under
    #: 4,000 words against §17 Stage 3's 50-80k — because nothing ever told it how long a
    #: scene is. An input that shapes every piece of prose in the book and appears in no
    #: policy record is exactly the invisible input `policy_config_digest` exists to catch.
    #:
    #: §1a.1 is the reason it is not a gate. "Beware the metric that is easy *because* it is
    #: shallow": a length floor raised to 900 words would make a scene that rambles for 900
    #: words pass and a taut one fail, which measures nothing about whether the scene lands.
    #: Asking is a generation instruction; refusing would be a quality claim this project has
    #: no evidence for.
    #:
    #: The default sits well under `max_chars`: at roughly six characters per word, 900 words
    #: is ~5,400 characters against a 8,000-character ceiling, so a model that overshoots by a
    #: third is still accepted rather than refused for obeying the instruction.
    target_words: int = 900


@dataclass(frozen=True, slots=True)
class DraftOutcome:
    accepted: bool
    vetoes: tuple[VetoRecord, ...] = ()
    revision: Revision | None = None
    node_before: Node | None = None
    node_after: Node | None = None
    chars: int = 0
    #: What arrived, beside what was asked for. `policy_config_digest` records
    #: `target_words`; without these the record cited the instruction and never the result,
    #: and the gap between them is the number that decides whether §17 Stage 3 is reachable.
    #: Measured across every stored run — 45 scenes over six books — the mean scene is 172
    #: words against a 900-word target, 19%, ranging 14% to 40%.
    words: int = 0
    target_words: int = 0

    @property
    def veto_kinds(self) -> tuple[Veto, ...]:
        return tuple(record.veto for record in self.vetoes)


def draft_block(
    revision: Revision,
    logical_id: str,
    *,
    policy: DraftPolicy | None = None,
) -> VetoRecord | None:
    """The *structural* veto that would refuse a first draft of this node, or None.

    Structural means: a property of the target, knowable before any text exists. Length and
    schema conformance are properties of the *candidate* and stay in `gate_draft`.

    **This function exists so a planner cannot disagree with the gate.** Selection has to
    ask "is this node draftable" and the gate has to ask "may this draft land", and if those
    are two implementations they will drift — and the drift is not benign. `CONTENT_LOCKED`
    and `TARGET_HAS_NO_CONTENT` are in neither `RETRYABLE` nor `REGENERABLE`, so `decide`
    escalates them on the first attempt and `_settle` parks the unit *and files an
    exception*. A selector that offered a node the gate would refuse would therefore fill
    the queue §4.3 reserves for the director with work nobody asked a human about. One
    function, two callers, no drift possible.
    """
    policy = policy or DraftPolicy()
    try:
        node = revision.node(logical_id)
    except KeyError:
        return VetoRecord(Veto.UNKNOWN_TARGET, f"no node {logical_id} in revision")

    if node.tombstoned:
        return VetoRecord(Veto.UNKNOWN_TARGET, f"node {logical_id} is tombstoned")

    if node.lock.freezes_content:
        return VetoRecord(
            Veto.CONTENT_LOCKED,
            f"node {logical_id} is {node.lock.value}-locked and its content is frozen",
        )

    if node.content is not None and not policy.allow_overwrite:
        return VetoRecord(
            Veto.TARGET_HAS_NO_CONTENT,
            f"node {logical_id} already carries {len(node.content)} characters; "
            "a rewrite needs a located complaint and must go through apply_patch",
        )
    return None


def is_draftable(
    revision: Revision, logical_id: str, *, policy: DraftPolicy | None = None
) -> bool:
    """Whether a first draft of this node could land. The planner's precondition."""
    return draft_block(revision, logical_id, policy=policy) is None


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

    # `conforms` is checked before the structural block only so a malformed answer reports
    # as a retryable shape failure rather than as a property of the target.
    if not conforms:
        node = None
        with suppress(KeyError):
            node = revision.node(logical_id)
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

    blocked = draft_block(revision, logical_id, policy=policy)
    if blocked is not None:
        node = None
        with suppress(KeyError):
            node = revision.node(logical_id)
        return DraftOutcome(False, (blocked,), node_before=node)

    node = revision.node(logical_id)
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
        words=len(canonical.split()),
        target_words=policy.target_words,
    )


__all__ = [
    "DraftOutcome",
    "DraftPolicy",
    "draft_block",
    "gate_draft",
    "is_draftable",
]
