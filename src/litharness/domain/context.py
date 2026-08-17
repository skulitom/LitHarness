"""§12 step 2: assemble the context packet a scene is drafted against.

Before this module, the prompt for the final scene of a locked-room mystery was its title,
its ordinal, the word "resolution", and the premise. Four locked constraints sat in the same
database unread — one of them naming scene 6 by number, another a promise the book owed a
payoff — and `plans.constraints_of` was a parsed function with no caller. Scene six was
written knowing nothing of scene five.

**What this is, and what it deliberately is not.** §12 words step 2 as "simple baseline until
LongRangeContext promotes", and that sibling owns discovery, scoring and packing; the
contract's own `context.py` says so in its first sentence. So this packs by a fixed priority
order, not by relevance scoring. Under a budget too small to hold the book it will drop things
a scorer would have kept, and it has no way to know that. What it therefore owes — the whole
of what a baseline can honestly promise — is that **every omission is recorded**, in
`rejected_candidates`, with the reason. A packet that silently dropped the constraint naming
this scene would be worse than the empty prompt it replaces, because the prompt was at least
obviously empty.

**Priority order, and why prose is last.** Constraints and promises are the director's word
and are tiny; open threads are what the book still owes; established facts ground the scene;
prose is the largest and the most redundant with the facts extracted from it. So the order is
premise → constraints → threads → facts → prior prose, and under pressure prose is what goes.
LongRangeContext measured a recent-window baseline for exactly this shape, which is why prose
is *selected* nearest-scene-first — scene five matters more to scene six than scene one does —
while being *rendered* in reading order, because a generator handed the story out of sequence
will write it that way.

**Selection order is not render order**, and conflating them is the bug this docstring exists
to prevent: dropping the oldest scene under a tight budget is right, and showing the
generator scene 5 before scene 1 is not.

**What the evicted scenes leave behind.** Dropping the oldest prose is right and it is not
free: at 900-word scenes the 6,000-token budget binds at about scene five, so from scene six
onward the generator was being handed a premise, some facts, and the three scenes immediately
behind it — and *nothing at all* about the rest of the book it had written. Every omission was
recorded, which is what a baseline honestly can promise, and a recorded omission is still an
omission. `SUMMARIES` is the slot the eviction leaves: a scene the budget could not carry
whole arrives as what it contained instead of as an entry in `rejected_candidates`.

**The summaries are supplied, never computed here.** `assemble` is pure — no store, no clock,
no provider — which is what lets the golden suite grade it directly, and calling a model from
inside it would end that. `application/planner.py::packet_for` loads them, and a scene with no
summary yet is simply an eviction with nothing to leave behind, exactly as before.

**The premise is not droppable.** `plans.py` records why: a book drafted without one produces
"six scenes of plausible prose about nothing, which no gate in this system can detect". A
budget that cannot hold the premise is a misconfiguration, not a tight packet, so it raises
rather than producing a packet whose failure is invisible.

**Token counts are an approximation, and named as one.** `regex-v1` is the same
`\\w+|[^\\w\\s]` counter LongRangeContext uses for its budget matching. Matching the method
rather than importing it is deliberate — §13 keeps siblings depending on contracts and never
on each other — but matching it matters, because a packet whose budget accounting differs
from the benchmark that grades packets would produce numbers nobody could compare.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType

import litharness_contracts as lc

from litharness.domain import promises as promises_mod
from litharness.domain import state as state_mod
from litharness.domain.nodes import NodeKind
from litharness.domain.plans import constraints_of, premise_of
from litharness.domain.revision import Revision

#: The counter's identity, recorded on the packet so a report says which one produced the
#: numbers rather than implying model-token accuracy.
COUNTER_ID = "regex-v1"

_TOKEN_PATTERN = re.compile(r"\w+|[^\w\s]", re.UNICODE)

#: Section names, in packing priority order. Order is load-bearing — see the module docstring.
PREMISE = "premise"
CONSTRAINTS = "constraints"
THREADS = "threads"
FACTS = "facts"
#: What the scenes the budget could not hold actually contained. Above `PRIOR_PROSE` in the
#: order for the same reason `FACTS` is: a summary is a compressed form of prose, so under
#: pressure the compressed form is what survives and the raw text is what goes.
SUMMARIES = "summaries"
PRIOR_PROSE = "prior_prose"
SECTION_ORDER = (PREMISE, CONSTRAINTS, THREADS, FACTS, SUMMARIES, PRIOR_PROSE)

#: The largest share of the packet summaries may claim, so that they can be placed at all.
#:
#: **Without a reserve this section is unreachable and would be a slot with no filler**, which
#: is the defect shape §19.1 catalogues — a documented promise whose only caller is a test.
#: Prose packs greedily nearest-first, so by the time the oldest scenes are known to have been
#: evicted the budget that would carry their summaries is already spent on the newest scenes'
#: full text. A quarter is a placed number, not a measured one: it is enough to carry a
#: one-paragraph summary of every scene in a long book at the budgets this system runs, and
#: small enough that the three or four most recent scenes still arrive whole.
SUMMARY_SHARE = 0.25

#: Matches the golden suite's `draft_scene` case. Not a measured figure: nothing in this
#: project has yet measured what a scene needs, and §15's cost model is explicitly a
#: hypothesis awaiting Book Zero.
DEFAULT_TOKEN_BUDGET = 6000

#: Held back from the packet for the generation itself. A budget spent entirely on input
#: leaves no room for the scene, and discovering that at the provider is discovering it after
#: paying for it.
DEFAULT_RESERVED_OUTPUT = 1500


class ContextBudgetTooSmall(Exception):
    """The budget cannot hold what a packet may not omit. See the module docstring."""


def count_tokens(text: str) -> int:
    """Deterministic, provider-independent approximation. See `COUNTER_ID`."""
    return len(_TOKEN_PATTERN.findall(text))


@dataclass(frozen=True, slots=True)
class PackedItem:
    """One thing the generator is told, and where it came from."""

    item_id: str
    kind: lc.ContextItemKind
    #: The logical id of what this came from — a scene, a plan item, a state record. This is
    #: what a golden `ref` target matches on, so it is the record's own id and never a
    #: rendered-text identifier.
    source_logical_id: str
    source_kind: lc.ResourceKind
    text: str
    tokens: int
    authority: lc.StateAuthority = lc.StateAuthority.DERIVED
    #: Character range of `text` within the source's content, for items quoted from prose.
    #: Absent for items that are not quotations — a plan statement is not a span of the book.
    span: tuple[int, int] | None = None
    pov_visibility: tuple[str, ...] = ()

    def source_ref(self, project_id: str, book_id: str, branch_id: str) -> lc.ResourceRef:
        return lc.ResourceRef(
            project_id=project_id,
            book_id=book_id,
            branch_id=branch_id,
            logical_id=self.source_logical_id,
            kind=self.source_kind,
        )

    def covers(self, start: int, end: int) -> bool:
        """Whether this item quotes the source range [start, end).

        A golden `span` target is satisfied by any packed item from the same source whose
        own range contains it: handing the generator the whole of scene 4 supplies the motive
        span inside it. Containment rather than equality, because a packet that had to quote
        exactly the ranges a grader chose would be scoring the grader's line breaks.
        """
        if self.span is None:
            return False
        return self.span[0] <= start and end <= self.span[1]


@dataclass(frozen=True, slots=True)
class Omission:
    """Something that belonged in the packet and did not fit. Never silent."""

    source_logical_id: str
    item_id: str
    reason: str


@dataclass(frozen=True, slots=True)
class ContextPacket:
    """A frozen answer to "what does this scene get to know", with its own accounting."""

    query_id: str
    target_logical_id: str
    book_id: str
    branch_id: str
    base_revision_id: str
    sections: dict[str, tuple[PackedItem, ...]] = field(default_factory=dict)
    omitted: tuple[Omission, ...] = ()
    token_budget: int = DEFAULT_TOKEN_BUDGET
    reserved_output: int = DEFAULT_RESERVED_OUTPUT
    pov_character_id: str | None = None

    @property
    def items(self) -> tuple[PackedItem, ...]:
        return tuple(
            item for name in SECTION_ORDER for item in self.sections.get(name, ())
        )

    @property
    def used_tokens(self) -> int:
        return sum(item.tokens for item in self.items)

    def contains_ref(self, logical_id: str, kind: lc.ResourceKind | None = None) -> bool:
        """Whether anything in the packet came from ``logical_id``.

        ``kind`` is checked when given, because a golden `ref` target names one and getting
        it wrong is not cosmetic: `StateRecordKind.EVENT` is referenced as
        `ResourceKind.STATE_EVENT`, and a packet that labelled it `UNKNOWN` would match no
        target while looking, from the item list, entirely correct.
        """
        return any(
            item.source_logical_id == logical_id and (kind is None or item.source_kind is kind)
            for item in self.items
        )

    def contains_span(self, logical_id: str, start: int, end: int) -> bool:
        return any(
            item.source_logical_id == logical_id and item.covers(start, end)
            for item in self.items
        )

    def to_contract(
        self, meta: lc.ArtifactMeta, *, project_id: str, packet_id: str
    ) -> lc.ContextPacket:
        def ref(logical_id: str, kind: lc.ResourceKind) -> lc.ResourceRef:
            return lc.ResourceRef(
                project_id=project_id,
                book_id=self.book_id,
                branch_id=self.branch_id,
                logical_id=logical_id,
                kind=kind,
            )

        return lc.ContextPacket(
            meta=meta,
            packet_id=packet_id,
            query_id=self.query_id,
            source_snapshot=ref("book", lc.ResourceKind.MANUSCRIPT_BOOK),
            sections=[
                lc.PacketSection(
                    name=name,
                    items=[
                        lc.ContextItem(
                            item_id=item.item_id,
                            kind=item.kind,
                            source=item.source_ref(project_id, self.book_id, self.branch_id),
                            text=item.text,
                            token_count=item.tokens,
                            authority=item.authority,
                            pov_visibility=list(item.pov_visibility),
                        )
                        for item in self.sections[name]
                    ],
                )
                for name in SECTION_ORDER
                if self.sections.get(name)
            ],
            budget=lc.TokenBudget(
                limit=self.token_budget,
                used=self.used_tokens,
                reserved_output=self.reserved_output,
            ),
            consumed_sources=[
                ref(item.source_logical_id, item.source_kind) for item in self.items
            ],
            rejected_candidates=[
                lc.RejectedCandidate(
                    reason=omission.reason,
                    item_id=omission.item_id,
                    source=ref(omission.source_logical_id, lc.ResourceKind.UNKNOWN),
                )
                for omission in self.omitted
            ],
        )

    def render(self) -> str:
        """The packet as the text a generator is handed.

        Sections are labelled and separated, because an undifferentiated wall gives the model
        no way to tell a locked constraint it must obey from prose it may echo.
        """
        blocks: list[str] = []
        for premise in self.sections.get(PREMISE, ()):
            blocks.append(f"Premise: {premise.text}")
        constraints = self.sections.get(CONSTRAINTS, ())
        if constraints:
            lines = "\n".join(f"- {item.text}" for item in constraints)
            blocks.append(
                "Locked constraints and promises — these are the director's and may not "
                f"be contradicted:\n{lines}"
            )
        threads = self.sections.get(THREADS, ())
        if threads:
            lines = "\n".join(f"- {item.text}" for item in threads)
            blocks.append(f"Open threads the book still owes:\n{lines}")
        facts = self.sections.get(FACTS, ())
        if facts:
            lines = "\n".join(f"- {item.text}" for item in facts)
            pov = f" known to {self.pov_character_id}" if self.pov_character_id else ""
            blocks.append(f"Established facts{pov}:\n{lines}")
        summaries = self.sections.get(SUMMARIES, ())
        if summaries:
            lines = "\n".join(
                f"- {item.item_id.split(':', 1)[-1]}: {item.text}" for item in summaries
            )
            # Labelled as summary *and* as a register not to copy. This is the one section
            # that hands the generator prose written in a voice the book must not use:
            # §1a.3 item 6 names "summarising instead of dramatising" as an AI tell, and a
            # block of summary immediately above "now write the scene" is an invitation to
            # write more of it. Naming the trap is free; measuring whether it works is what
            # `craft` instrumentation on the scenes drafted after an eviction is for.
            blocks.append(
                "Earlier scenes, in summary — these happened and are established; write the "
                f"new scene in full dramatised prose, never in this register:\n{lines}"
            )
        prose = self.sections.get(PRIOR_PROSE, ())
        if prose:
            scenes = "\n\n".join(f"[{item.item_id}]\n{item.text}" for item in prose)
            blocks.append(f"The story so far, in full:\n\n{scenes}")
        return "\n\n".join(blocks)


def _prose_label(revision: Revision, logical_id: str) -> str:
    node = revision.node(logical_id)
    return node.title or logical_id


def assemble(
    revision: Revision,
    target_logical_id: str,
    *,
    plan_items: Sequence[lc.PlanItem] = (),
    state_records: Sequence[lc.StateRecord] = (),
    query_id: str = "",
    pov_character_id: str | None = None,
    token_budget: int = DEFAULT_TOKEN_BUDGET,
    reserved_output: int = DEFAULT_RESERVED_OUTPUT,
    story_time_cutoff: str | None = None,
    summaries: Mapping[str, str] = MappingProxyType({}),
    promises: Sequence[promises_mod.Promise] = (),
) -> ContextPacket:
    """Build the packet for drafting ``target_logical_id``.

    Pure: no store, no clock, no provider. Everything it reads is passed in, which is what
    lets the golden `GoldContextSuite` grade it directly rather than through a database.

    Raises `ContextBudgetTooSmall` when the budget cannot hold the premise — see the module
    docstring for why that is a refusal rather than an omission.
    """
    available = token_budget - reserved_output
    sections: dict[str, tuple[PackedItem, ...]] = {}
    omitted: list[Omission] = []
    used = 0

    def fits(item: PackedItem) -> bool:
        return used + item.tokens <= available

    # 1. Premise. Not droppable, and checked before anything else can consume the budget.
    premise_text = premise_of(plan_items)
    if premise_text is not None:
        premise_item = PackedItem(
            item_id="premise",
            kind=lc.ContextItemKind.PLAN,
            source_logical_id="premise",
            source_kind=lc.ResourceKind.PLAN,
            text=premise_text,
            tokens=count_tokens(premise_text),
            authority=lc.StateAuthority.AUTHOR_LOCKED,
        )
        if not fits(premise_item):
            raise ContextBudgetTooSmall(
                f"budget of {token_budget} tokens ({available} after reserving "
                f"{reserved_output} for output) cannot hold the premise alone "
                f"({premise_item.tokens} tokens); a packet without a premise drafts a book "
                "about nothing and no gate here can detect that"
            )
        sections[PREMISE] = (premise_item,)
        used += premise_item.tokens

    # 2. Locked constraints and promises. The director's word, and until this slice they were
    #    parsed by `constraints_of` and read by nothing.
    constraints: list[PackedItem] = []
    for plan_item in constraints_of(plan_items):
        item = PackedItem(
            item_id=plan_item.logical_id,
            kind=lc.ContextItemKind.AUTHOR_RULE,
            source_logical_id=plan_item.logical_id,
            source_kind=lc.ResourceKind.PLAN,
            text=plan_item.text,
            tokens=count_tokens(plan_item.text),
            authority=lc.StateAuthority.AUTHOR_LOCKED,
        )
        if fits(item):
            constraints.append(item)
            used += item.tokens
        else:
            omitted.append(
                Omission(item.source_logical_id, item.item_id, "budget exhausted: constraint")
            )
    sections[CONSTRAINTS] = tuple(constraints)

    # 3. State. Canon only, POV-filtered, sliced at the story-time cutoff if one was given.
    #    The order of these three filters does not matter to the result and does to the
    #    reason: a record dropped for POV is a different fact about the system than one
    #    dropped for being a proposal, and both are recorded as such.
    visible: list[lc.StateRecord] = []
    for record in state_mod.records_before(state_records, story_time_cutoff):
        if not state_mod.is_canon(record):
            continue  # A proposal is not an omission; it was never a candidate.
        if not state_mod.visible_to(record, pov_character_id):
            omitted.append(
                Omission(
                    record.record_id,
                    record.record_id,
                    f"not visible to POV {pov_character_id or '(none named)'}",
                )
            )
            continue
        visible.append(record)

    threads: list[PackedItem] = []
    for record in state_mod.open_threads(visible):
        item = _state_item(record)
        if fits(item):
            threads.append(item)
            used += item.tokens
        else:
            omitted.append(Omission(record.record_id, record.record_id, "budget: thread"))

    # Open promises from the ledger (§61 Add 2), rendered as owed lines beside the canon
    # threads — the same "what the book still owes" question answered from the model-sourced
    # side. `DERIVED`, never canon: the analogous exclusion already keeps PROPOSED
    # milestones out of this packet (`is_canon` above), and a promise reaching FACTS as an
    # established record would launder a model's claim into canon by section label. The
    # caller supplies open rows only; a paid promise is not owed.
    for promise in promises:
        text = promises_mod.describe_owed(promise)
        item = PackedItem(
            item_id=promise.promise_id,
            kind=lc.ContextItemKind.THREAD,
            source_logical_id=promise.promise_id,
            source_kind=lc.ResourceKind.THREAD,
            text=text,
            tokens=count_tokens(text),
            authority=lc.StateAuthority.DERIVED,
        )
        if fits(item):
            threads.append(item)
            used += item.tokens
        else:
            omitted.append(
                Omission(promise.promise_id, promise.promise_id, "budget: promise")
            )
    sections[THREADS] = tuple(threads)

    thread_ids = {item.item_id for item in threads}
    in_order = [
        record for record in state_mod.in_story_order(visible)
        if record.record_id not in thread_ids
    ]
    # Nearest story-time first: under pressure the packet keeps what was established most
    # recently, which is the recent-window baseline LongRangeContext measured.
    selected: set[str] = set()
    for record in reversed(in_order):
        item = _state_item(record)
        if fits(item):
            selected.add(record.record_id)
            used += item.tokens
        else:
            omitted.append(Omission(record.record_id, record.record_id, "budget: fact"))
    # Selected nearest-first, rendered in story order — see the module docstring. Rebuilt
    # from `in_order` rather than sorted afterwards, because the packed items carry no story
    # position and sorting them by id would order the mystery's facts alphabetically.
    sections[FACTS] = tuple(
        _state_item(record) for record in in_order if record.record_id in selected
    )

    # 4. Prior prose. Everything before the target in reading order that actually has text.
    scenes = [
        node
        for node in revision.in_reading_order()
        if node.kind is NodeKind.SCENE and node.content is not None
    ]
    ordinals = {node.logical_id: index for index, node in enumerate(scenes)}
    target_ordinal = ordinals.get(target_logical_id, len(scenes))
    prior = [node for node in scenes if ordinals[node.logical_id] < target_ordinal]

    # **Prose packs against a reduced ceiling whenever summaries are waiting.** Held back
    # rather than spent last, because prose is packed greedily nearest-first: by the time the
    # oldest scene is known to have been evicted, an unreserved budget is already inside the
    # newest scenes' full text, and the section that exists to carry what was evicted could
    # never be filled. The reserve is only as large as the summaries actually on hand, so a
    # book with none packs exactly as it did before this existed.
    supplied = {
        logical_id: text
        for logical_id, text in dict(summaries).items()
        if logical_id in ordinals and ordinals[logical_id] < target_ordinal
    }
    reserve = min(
        sum(count_tokens(text) for text in supplied.values()),
        int((available - used) * SUMMARY_SHARE),
    )
    prose_ceiling = available - reserve

    kept: dict[str, PackedItem] = {}
    for node in reversed(prior):  # nearest scene first
        assert node.content is not None
        item = PackedItem(
            item_id=_prose_label(revision, node.logical_id),
            kind=lc.ContextItemKind.EXACT_PROSE,
            source_logical_id=node.logical_id,
            source_kind=lc.ResourceKind.MANUSCRIPT_SCENE,
            text=node.content,
            tokens=count_tokens(node.content),
            authority=lc.StateAuthority.ACCEPTED_CANON,
            span=(0, len(node.content)),
        )
        if used + item.tokens <= prose_ceiling:
            kept[node.logical_id] = item
            used += item.tokens
        elif node.logical_id in supplied:
            # Not an omission: the scene is still in the packet, in compressed form. Recording
            # it as dropped would make `rejected_candidates` say the generator was told nothing
            # about a scene it was told the substance of.
            pass
        else:
            omitted.append(
                Omission(
                    node.logical_id,
                    item.item_id,
                    f"budget exhausted: {item.tokens} tokens would exceed {available}",
                )
            )
    sections[PRIOR_PROSE] = tuple(
        kept[node.logical_id] for node in prior if node.logical_id in kept
    )

    # 5. Summaries, for the evicted scenes only. A summary beside the full text of the same
    #    scene is the same information twice at the generator's expense.
    packed_summaries: list[PackedItem] = []
    for node in prior:  # reading order: a summary of scene 1 comes before one of scene 4
        if node.logical_id in kept or node.logical_id not in supplied:
            continue
        text = supplied[node.logical_id]
        item = PackedItem(
            item_id=f"summary:{_prose_label(revision, node.logical_id)}",
            kind=lc.ContextItemKind.SUMMARY,
            source_logical_id=node.logical_id,
            source_kind=lc.ResourceKind.MANUSCRIPT_SCENE,
            text=text,
            tokens=count_tokens(text),
            # **Derived, not canon.** A model wrote it from prose that is itself canon, and
            # the distinction is what stops a summary's paraphrase being cited back as an
            # established fact. `state` records remain the only accepted-canon route.
            authority=lc.StateAuthority.DERIVED,
        )
        if fits(item):
            packed_summaries.append(item)
            used += item.tokens
        else:
            omitted.append(
                Omission(node.logical_id, item.item_id, "budget exhausted: summary")
            )
    sections[SUMMARIES] = tuple(packed_summaries)

    return ContextPacket(
        query_id=query_id,
        target_logical_id=target_logical_id,
        book_id=revision.book_id,
        branch_id=revision.branch_id,
        base_revision_id=revision.revision_id,
        sections=sections,
        omitted=tuple(omitted),
        token_budget=token_budget,
        reserved_output=reserved_output,
        pov_character_id=pov_character_id,
    )


def _state_item(record: lc.StateRecord) -> PackedItem:
    text = state_mod.describe(record)
    kind = (
        lc.ContextItemKind.THREAD
        if record.kind is lc.StateRecordKind.THREAD
        else lc.ContextItemKind.EVENT
        if record.kind is lc.StateRecordKind.EVENT
        else lc.ContextItemKind.FACT
    )
    return PackedItem(
        item_id=record.record_id,
        kind=kind,
        source_logical_id=record.record_id,
        source_kind=state_mod.resource_kind(record),
        text=text,
        tokens=count_tokens(text),
        authority=record.authority,
        pov_visibility=tuple(record.pov_visibility),
    )


__all__ = [
    "CONSTRAINTS",
    "COUNTER_ID",
    "DEFAULT_RESERVED_OUTPUT",
    "DEFAULT_TOKEN_BUDGET",
    "FACTS",
    "PREMISE",
    "PRIOR_PROSE",
    "SECTION_ORDER",
    "SUMMARIES",
    "SUMMARY_SHARE",
    "THREADS",
    "ContextBudgetTooSmall",
    "ContextPacket",
    "Omission",
    "PackedItem",
    "assemble",
    "count_tokens",
]
