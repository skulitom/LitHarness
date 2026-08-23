"""The promise/payoff ledger's vocabulary, and the overdue arithmetic over it.

§61 Add 2: the first metric aimed at PLAN §1a.3 item 3 — promises the book opens and does
not pay. `domain/state.py`'s `open_threads` was always "the exact seed" of this ledger, and
it is deliberately **not** the implementation: `open_threads` tests `record.value == "open"`
by exact equality, both golden fixtures author that value, and folding a payoff-due position
into the value would silently empty the packet's THREADS section, the summarizer's ground
truth, and the status thread counts in one edit. So a promise is its own row in its own
table (migration 023), written by the summary handler from the extended summary call, and
this module is the pure vocabulary both sides share.

**Everything here is arithmetic over model-sourced rows.** The rows come from a model's
`promises_opened`/`promises_paid` answer, so nothing built on them may block or park:
`promise.overdue.v0` (domain/integrity.py) mints MINOR findings only, and §10.4's promotion
rules are untouched. The refutation shaping this is scene_change_profile's: LEDGER delta is
not DRAMATIC delta — the confession scene carried zero records — so the promise question
takes a model leg, and a model leg stays advisory until calibrated.

**Story keys are `beats_for`'s, never minted here.** `overdue_promises` compares order keys
as strings, which is only correct because `beats_for` zero-pads them to the book's own width
(`s10 < s2` unpadded is the recorded bug). The summary handler derives every promise key by
indexing into the beats `beats_for` returned rather than formatting its own, so there is one
padding implementation in the project, not two that must agree. A template that is not
chronological mints no keys at all, and this ledger abstains there exactly as milestones do:
no promise rows, no overdue findings — no key rather than a guessed one.

**§94 adds two things to the vocabulary and no new authority.** A promise now carries a
`kind` (W1, migration 028) reported by the same summary call, which is what turns the
open-versus-paid tripwire into a per-kind one — five opened against five paid nets to zero
however mismatched the kinds are. And it can carry a planner-proposed **payoff window** (W2,
migration 029) validated by `window_fault`/`schedule_fault` here and rendered by
`describe_owed` as part of the debt line. Both are model-sourced and both stay PROPOSED-grade:
neither mints a finding, and `promise.overdue.v0` remains the whole evaluator side — a
model-scheduled window missed by a model-reported payoff is two model claims disagreeing, and
neither is entitled to raise a finding about the other.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from hashlib import sha256

#: A promise the book has opened and not yet paid. The vocabulary deliberately mirrors
#: `state.THREAD_OPEN`'s single-word values rather than inventing richer states: write-once
#: open, one transition to paid, nothing else to be in.
PROMISE_OPEN = "open"
PROMISE_PAID = "paid"

#: What sort of debt a promise is (W1, §94). **Derived rather than declared**: the set started
#: as a five-way guess — plot, character, progression, mystery, **tone** — and `tone` is gone
#: because two disjoint model families reported it **zero times across 120 promises** over the
#: only own-generated book in this repository. A category invented because it sounded like part
#: of a complete taxonomy is a category with no evidence behind it, which is the door twenty-one
#: refuted proxies came through (`research/quality-measurement/BRIEF.md` §2).
#:
#:     kind          qwen3:14b       gemma3:12b      per-model rule
#:     mystery       27/51  53%      31/69  45%      kept by both
#:     plot          20/51  39%      28/69  41%      kept by both
#:     character      1/51   2%       9/69  13%      kept by gemma, cut by qwen
#:     progression    3/51   6%       1/69   1%      kept by qwen, cut by gemma
#:     tone           0/51   0%       0/69   0%      CUT by both
#:
#: **Four survive rather than two, and the reason is the rule's own "per model, never pooled"
#: clause.** `character` and `progression` are each kept by one family and cut by the other, at
#: low rates, and two models disagreeing is not evidence for either — pooling them to break the
#: tie is exactly the move the clause forbids, because two models' taxonomies averaged together
#: are a taxonomy neither of them has. Only `tone` clears the rule's unambiguous branch on both.
#:
#: **What the cut rests on, stated so it can be undone honestly.** One book, ten scenes, two
#: local families. A book that genuinely owes a tonal register would not be represented here,
#: and re-admitting `tone` takes the nomination path — an operator act over a fresh
#: distribution — rather than an edit. The same path is open to `revelation`, which gemma's
#: open-vocabulary arm nominated at 13.2% and which is recorded, not admitted.
#:
#: **The order is the reporting order and nothing turns on it.** There is no ranking here and
#: none may be added: a kind carries no valence, exactly as `axes.Pole` carries none. Which
#: kinds of debt a reader minds going unpaid is a measurement nobody has made.
PROMISE_KINDS: tuple[str, ...] = (
    "plot",
    "character",
    "progression",
    "mystery",
)

#: The kind of a promise nobody typed. `None` rather than a `"unknown"` member, so the three
#: cases that produce it — a row written before migration 028, a model that answered nothing,
#: and a model that answered outside the frozen set — are one absence in the data rather than a
#: value that could be miscounted as a category with a population.
UNTYPED: None = None


@dataclass(frozen=True, slots=True)
class Promise:
    """One thing the book owes, with the story position it is owed by.

    A projection of a `promises` table row (migration 023), not a state record: keeping it
    off `lc.StateRecord` is what keeps `open_threads`, `detect_contradictions` and
    `has_story_vocabulary` blind to it — each of which the extraction-state map records as
    breaking if a promise were folded into their vocabulary.
    """

    promise_id: str
    subject: str
    description: str
    #: Story order key of the scene whose summary opened this, in `beats_for`'s padding.
    opened_at_key: str
    #: When the book owes payment, at the latest. `None` never occurs on rows the summary
    #: handler writes (absent hints default to the final scene key), and `overdue_promises`
    #: abstains on it rather than treating "no due date" as "always due".
    due_key: str | None
    opened_by_revision: str
    status: str = PROMISE_OPEN
    paid_at_key: str | None = None
    paid_by_revision: str | None = None
    #: The model whose summary call asserted this promise. Provenance, and the reason the
    #: overdue finding's confidence basis is `heuristic` rather than `deterministic`.
    model: str = ""
    #: What sort of debt this is (W1), or `None` for untyped. Fixed at insert and never
    #: updated: the content-derived `promise_id` exists so a re-report converges on one row,
    #: and a kind that could be updated would make "what does this book owe" depend on when the
    #: question was asked.
    kind: str | None = UNTYPED
    #: The scene range the planner intends payment inside, inclusive, in `beats_for`'s padding
    #: (W2). `None` on both when nothing has scheduled this promise — which is every promise
    #: until an outline call sees it, and stays that way for a book nobody replans.
    window_start_key: str | None = None
    window_end_key: str | None = None
    #: Which plan revision's outline answer proposed the window. Provenance for a PROPOSED-grade
    #: claim, and what makes "why is this promise due there" answerable after the plan moves.
    scheduled_by_plan_revision: str | None = None

    @property
    def scheduled(self) -> bool:
        """Whether a payoff window has been proposed for this promise.

        Both keys or neither: a half-scheduled window is not a range, and `schedule_window`
        refuses to mint one, so this reads one key and means both.
        """
        return self.window_start_key is not None and self.window_end_key is not None


def promise_id_for(book_id: str, subject: str) -> str:
    """Content-derived from the book and the normalised subject, and from nothing else.

    Deliberately value-insensitive, which is the opposite discipline from
    `extraction.record_id_for` because the failure modes are opposite: a contradiction
    detector needs two disagreeing readings to be two rows, while a promise ledger needs
    the same subject re-reported by a re-summarised scene to be **one** row — `INSERT OR
    IGNORE` on this id is what makes re-extraction converge instead of stacking a duplicate
    promise per replay. A changed description under the same subject is the same promise
    described differently, not a new debt.
    """
    return "prm-" + sha256((book_id + subject).encode("utf-8")).hexdigest()[:24]


def parse_due_hint(hint: object) -> int | None:
    """The scene number a model's ``due_hint`` names, or None when it names none.

    The model is asked for a story position by scene number and models answer in shapes:
    ``12``, ``"12"``, ``"scene 12"``, ``"by s12"``. The first integer in the answer is the
    reading; anything else — null, prose with no digits, a bool — is "unparseable", and the
    caller defaults the due key to the book's final scene rather than guessing, so a
    promise with an unreadable due date is at latest overdue when the book ends unpaid.
    """
    if isinstance(hint, bool):
        return None
    if isinstance(hint, int):
        return hint if hint > 0 else None
    if isinstance(hint, str):
        match = re.search(r"\d+", hint)
        if match is None:
            return None
        number = int(match.group())
        return number if number > 0 else None
    return None


def normalise_kind(value: object) -> str | None:
    """A model's ``kind`` answer as a frozen-set member, or None for untyped.

    Tolerant in exactly one direction — case and surrounding space — and closed in every
    other. A kind outside `PROMISE_KINDS` is **not** admitted under its own name and is not
    mapped to a near neighbour either: an unrecognised category is a *nomination*, and the
    place a nomination is weighed is an operator act over the derivation run's printed
    distribution, never a synonym table nobody registered. Same rail `domain/axes.py` puts in
    front of its registry, one layer over.

    Returns None for anything that is not a recognised kind, which is what every consumer
    reads as untyped. There is no failure mode here: a promise whose kind is unreadable is a
    usable promise with a missing annotation, exactly as a fumbled `delta` leaves a usable
    summary.
    """
    if not isinstance(value, str):
        return None
    folded = value.strip().lower()
    return folded if folded in PROMISE_KINDS else None


def kind_counts(promises: Sequence[Promise]) -> dict[str | None, tuple[int, int]]:
    """`{kind: (opened, paid)}` over one book's ledger, untyped rows under the `None` key.

    **The tripwire this column exists for** (§94): raw open-versus-paid density nets five
    opened against five paid to zero however mismatched the kinds are, so a book that opens
    cheap mystery hooks and pays only tone debts is invisible to it. Per kind it is not.

    `opened` counts every row — a paid promise was opened too — so the pair reads as "this
    many of this kind exist, this many of them are settled" rather than as two disjoint
    populations that have to be added up correctly by every caller.
    """
    out: dict[str | None, tuple[int, int]] = {}
    for promise in promises:
        opened, paid = out.get(promise.kind, (0, 0))
        out[promise.kind] = (opened + 1, paid + (1 if promise.status == PROMISE_PAID else 0))
    return out


def acts_for(keys: Sequence[str]) -> tuple[tuple[str, ...], ...]:
    """The book's scene keys split into three contiguous acts by ordinal.

    **Thirds of the beat sheet, not a new act model**, and the distinction matters: this
    project has one structure vocabulary (`domain/beats.py`) and a second one invented here
    would be a second thing to keep in agreement with the first. Three because that is the
    granularity the "everything resolves at the end" refusal needs and no finer claim is being
    made — nothing here asserts that act two is where anything in particular belongs.

    A sheet with fewer than three keys yields fewer than three acts rather than padding with
    empties, and the caller's rule abstains there. A rule that fires on a book too short to
    have the structure it describes is the failure mode I7 catalogues.
    """
    total = len(keys)
    if total < 3:
        return (tuple(keys),) if keys else ()
    first = total // 3
    second = 2 * total // 3
    return (tuple(keys[:first]), tuple(keys[first:second]), tuple(keys[second:]))


def window_fault(
    promise: Promise, start_key: str, end_key: str, *, keys: Sequence[str]
) -> str | None:
    """Why this payoff window is not a schedule, or None when it is one.

    Four checks, each of which is a distinct way a window can be worthless, and each phrased
    so the refusal names the offending value the way `_milestones`' refusals do:

    1. **Both keys name scenes the book has.** A window on `s99` of a ten-scene book is
       unsatisfiable, which is milestones' own rule.
    2. **The range runs forwards.** An inverted window contains no scene, so it is a declared
       bar that cannot be met — I7's check applied to a model's answer rather than to ours.
    3. **Payment is not scheduled before the debt exists.** A window opening before the scene
       that opened the promise is bookkeeping about the past.
    4. **Payment is not scheduled after it is already overdue.** A window ending after
       `due_key` plans the exact finding `promise.overdue.v0` exists to raise, which is a
       schedule agreeing in advance to fail.

    String comparison throughout, which is correct only because every key here is
    `beats_for`'s zero-padded minting — the same precondition `overdue_promises` runs on, and
    the reason no key is ever formatted in this module.
    """
    known = set(keys)
    if start_key not in known or end_key not in known:
        missing = sorted({start_key, end_key} - known)
        return f"window names {missing}, which the beat sheet does not have"
    if start_key > end_key:
        return f"window {start_key}-{end_key} runs backwards and contains no scene"
    if start_key < promise.opened_at_key:
        return (
            f"window opens at {start_key}, before {promise.subject!r} was opened at "
            f"{promise.opened_at_key}; payment cannot be scheduled before the debt"
        )
    if promise.due_key is not None and end_key > promise.due_key:
        return (
            f"window ends at {end_key}, after {promise.subject!r} is due at "
            f"{promise.due_key}; a schedule may not plan its own overdue finding"
        )
    return None


def schedule_fault(
    windows: Sequence[tuple[str, str]], *, keys: Sequence[str]
) -> str | None:
    """Why a whole payoff schedule is not one, or None when it is.

    **The check that is about the reader rather than about coherence**, and the sibling of
    `_milestones`' anti-stasis rule: a schedule in which every promise is paid in the final act
    is "everything resolves at the end", which is the shape PLAN.md §1a.3 item 3 names as the
    defect — promises paid *on a cadence a reader can feel*, not in one terminal dump.

    **Both rules abstain below two windows, and the abstention is I7 rather than leniency.**
    With one window there is no distinction to draw between "everything resolves at the end"
    and "the one thing resolves at the end", so a rule firing there would be refusing a
    schedule for a property it cannot observe — the same defect as a bar whose quantity cannot
    reach it. A book too short for three acts abstains for the same reason.
    """
    if len(windows) < 2:
        return None
    acts = acts_for(keys)
    if len(acts) < 3:
        return None
    final_act = set(acts[-1])
    if all(end in final_act for _, end in windows):
        return (
            f"all {len(windows)} payoff windows close inside the final act; a schedule that "
            "resolves everything at the end is the cadence defect it was asked to plan around"
        )
    if len(set(windows)) == 1:
        start, end = windows[0]
        return (
            f"all {len(windows)} payoff windows are the same range {start}-{end}; one window "
            "wearing a schedule pays every debt in one place"
        )
    return None


def overdue_promises(
    open_promises: Sequence[Promise], current_key: str | None
) -> tuple[Promise, ...]:
    """Open promises whose due position is strictly before the position being drafted.

    Pure arithmetic, in the order the ledger supplied. String comparison is correct only
    because both keys come from `beats_for`'s zero-padded minting — see the module
    docstring — and the comparison is strict (`<`): a scene *at* the due position is the
    scene still entitled to pay.

    Abstains, returning nothing, when `current_key` is None — a template that is not
    chronological minted no position for this beat, and comparing against a guessed one
    would be this module inventing the exact thing `beats_for` refused to. A promise whose
    own `due_key` is None is skipped for the same reason.
    """
    if current_key is None:
        return ()
    return tuple(
        promise
        for promise in open_promises
        if promise.status == PROMISE_OPEN
        and promise.due_key is not None
        and promise.due_key < current_key
    )


def describe_owed(promise: Promise) -> str:
    """The packed-item line for one open promise: what is owed, by when, and where to pay it.

    Deliberately prefixed "owes:" and phrased as a debt rather than as a fact — this line
    rides in the packet's THREADS section beside canon-backed open threads, and a rendering
    that read as an established event would launder a model's proposal into canon by
    register alone.

    **The scheduled window rides the same line and inherits the same register** (W2). "pay
    within s07-s09" is an instruction about a debt, which is what the whole line already is;
    splitting the schedule into its own packet section would have given a PROPOSED-grade
    model answer a heading of its own beside canon. A promise nobody has scheduled renders
    exactly as it did before this existed, which is what keeps the packet stable for every
    book that is never replanned.
    """
    owed = f"owes: {promise.description}"
    if promise.due_key is not None:
        owed += f" (due by {promise.due_key})"
    if promise.scheduled:
        owed += f"; pay within {promise.window_start_key}-{promise.window_end_key}"
    return owed


__all__ = [
    "PROMISE_KINDS",
    "PROMISE_OPEN",
    "PROMISE_PAID",
    "UNTYPED",
    "Promise",
    "acts_for",
    "describe_owed",
    "kind_counts",
    "normalise_kind",
    "overdue_promises",
    "parse_due_hint",
    "promise_id_for",
    "schedule_fault",
    "window_fault",
]
